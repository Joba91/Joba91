import hashlib
import json
import os
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import vision_image_receiver as receiver
import vision_images as images


def metadata():
    data = bytearray(196)
    struct.pack_into('<HH', data, 6, 640, 480)
    data[14] = 8
    struct.pack_into('<I', data, 24, 307200)
    return bytes(data)


class RuntimeFixture:
    def __init__(self, root):
        self.root = root
        self.sdk = root / 'engine'
        self.sdk.mkdir()
        self.library = b'fixture, never executable'
        (self.sdk / 'fake.dll').write_bytes(self.library)
        config = {'dual_chip_a7': {'mode': [{'mode_name': 'wa140'}], 'interface': {'usb': [
            {'vendor_id': '0x2ca3', 'product_id': '0x0020', 'interface': 5, 'desc': 'v1'},
            {'vendor_id': '0x2ca3', 'product_id': '0x0020', 'interface': 3, 'desc': 'dbus'}]}}}
        data = json.dumps(config).encode()
        (self.sdk / 'dbus_pc.json').write_bytes(data)
        self.patches = [patch.object(receiver, 'SDK_PINS', {'fake.dll': hashlib.sha256(self.library).hexdigest()}),
                        patch.object(receiver, 'CONFIG_SHA256', hashlib.sha256(data).hexdigest())]
        for item in self.patches:
            item.start()

    def close(self):
        for item in reversed(self.patches):
            item.stop()


class FakeAPI:
    def __init__(self, runtime):
        self.topics = []
    def initialize(self):
        pass
    def subscribe(self, topic):
        self.topics.append(topic)
        return topic
    def receive(self, handle, timestamp):
        timestamp.value = 123
        return (receiver.parse_image_metadata(metadata()), bytes([17]) * 307200), 0
    def close(self):
        return [0, 0]


class FinishedProcess:
    def poll(self):
        return 0
    def wait(self, timeout=None):
        return 0


class ImageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.fixture = RuntimeFixture(self.root)
        self.cwd = Path.cwd()
    def tearDown(self):
        os.chdir(self.cwd)
        self.fixture.close()
        self.temp.cleanup()

    def job(self):
        work = self.root / 'work'
        work.mkdir()
        runtime = work / 'runtime'
        runtime.mkdir()
        for p in self.fixture.sdk.iterdir():
            (runtime / p.name).write_bytes(p.read_bytes())
        p = work / 'job.json'
        p.write_text(json.dumps({'session_id': 'a' * 32, 'runtime': str(runtime),
                                 'seconds': 1, 'firmware': '01.00.1100'}))
        return p

    def launcher(self, job):
        before = Path.cwd()
        receiver.run_job(job, api_factory=FakeAPI)
        os.chdir(before)
        return FinishedProcess()

    def test_reference_image_layout(self):
        parsed = receiver.parse_image_metadata(metadata())
        self.assertEqual((parsed['width'], parsed['height'], parsed['payload_bytes']), (640, 480, 307200))

    def test_nonreference_formats_are_rejected_before_reading_pixels(self):
        for offset, value in [(6, 0), (8, 0), (14, 16), (24, 1)]:
            b = bytearray(metadata())
            b[offset] = value
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                receiver.parse_image_metadata(b)
        for length in [0, 27, 197]:
            with self.subTest(length=length), self.assertRaises(ValueError):
                receiver.parse_image_metadata(bytes(length))

    def test_runtime_fingerprints_fail_closed(self):
        self.assertEqual(len(receiver.validate_runtime(self.fixture.sdk)), 2)
        (self.fixture.sdk / 'fake.dll').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'no coincide'):
            receiver.validate_runtime(self.fixture.sdk)

    def test_receiver_saves_real_payload_shape_and_does_not_claim_calibration(self):
        job = self.job()
        result = receiver.run_job(job, api_factory=FakeAPI)
        self.assertTrue(result['completed'])
        self.assertEqual(len(result['frames']), 2)
        self.assertFalse(result['calibration_performed'])
        self.assertFalse(result['device_identity_from_image_confirmed'])
        self.assertEqual(result['calibration_commands_requested'], 0)
        self.assertIsNone(result['native_usb_traffic_bytes'])
        self.assertEqual(len(images.validate_frames(job.parent, result)), 2)

    def test_cancel_before_frames_preserves_unknown_state(self):
        job = self.job()
        (job.parent / 'stop.flag').write_bytes(b'')
        result = receiver.run_job(job, api_factory=FakeAPI)
        self.assertEqual(result['frames'], [])
        self.assertFalse(result['completed'])
        self.assertEqual(result['state'], 'desconocido')

    def test_cancel_after_initialization_prevents_topic_subscriptions(self):
        job = self.job()
        instances = []
        class Cancel(FakeAPI):
            def initialize(self):
                instances.append(self)
                (job.parent / 'stop.flag').write_bytes(b'')
        result = receiver.run_job(job, api_factory=Cancel)
        self.assertEqual(instances[0].topics, [])
        self.assertTrue(result['cancelled'])
        self.assertFalse(result['completed'])

    def test_stuck_receiver_is_terminated_and_never_completes_progress(self):
        class Stuck:
            stopped = False
            def poll(self):
                return 1 if self.stopped else None
            def wait(self, timeout=None):
                if not self.stopped:
                    raise subprocess.TimeoutExpired('synthetic receiver', timeout)
                return 1
            def terminate(self):
                self.stopped = True
        child = Stuck()
        events = []
        result = images.capture_images(self.root / 'timeout.zip', self.fixture.sdk, '01.00.1100',
                                       preflight=lambda: {}, launcher=lambda job: child,
                                       max_seconds=0, progress=events.append)
        self.assertTrue(child.stopped)
        self.assertFalse(result['completed'])
        self.assertEqual(result['state'], 'error')
        self.assertFalse(any(e.get('percent') == 100 for e in events))
        self.assertTrue((self.root / 'timeout.zip').is_file())

    def test_helper_startup_failure_is_preserved_in_bundle(self):
        def fail(job):
            (job.parent / 'fatal.json').write_text(json.dumps({'error': 'synthetic missing runtime dependency'}))
            return FinishedProcess()
        result = images.capture_images(self.root / 'fatal.zip', self.fixture.sdk, '01.00.1100',
                                       preflight=lambda: {}, launcher=fail)
        self.assertFalse(result['completed'])
        self.assertIn('synthetic missing runtime dependency', result['detail'])

    def test_corrupt_payload_is_not_saved(self):
        class Truncated(FakeAPI):
            def receive(self, handle, timestamp):
                return (receiver.parse_image_metadata(metadata()), b'short'), 0
        job = self.job()
        result = receiver.run_job(job, api_factory=Truncated)
        self.assertEqual(result['state'], 'error')
        self.assertFalse(list(job.parent.glob('*.pgm')))

    def test_cleanup_failure_does_not_report_completed(self):
        class BadClose(FakeAPI):
            def close(self):
                return [0xD0010003]
        result = receiver.run_job(self.job(), api_factory=BadClose)
        self.assertFalse(result['completed'])
        self.assertEqual(result['state'], 'error')

    def test_capture_bundle_and_progress_are_bound_to_verified_files(self):
        events = []
        result = images.capture_images(self.root / 'capture.zip', self.fixture.sdk, '01.00.1100',
                                       preflight=lambda: {'simulated_for_unit_test': True},
                                       launcher=self.launcher, progress=events.append)
        self.assertTrue(result['completed'], result)
        self.assertEqual(events[-1]['percent'], 100)
        self.assertIn('no es calibración', events[-1]['label'])
        self.assertFalse(result['calibration_performed'])
        with ZipFile(self.root / 'capture.zip') as z:
            self.assertEqual(set(z.namelist()), {'DJI-REPAIR-informe.json', *receiver.TOPICS.values()})
            self.assertIsNone(z.testzip())
            self.assertNotIn(b'fake.dll', z.read('DJI-REPAIR-informe.json'))

    def test_cancellation_before_preflight_still_creates_honest_report(self):
        called = []
        result = images.capture_images(self.root / 'cancel.zip', self.fixture.sdk, '01.00.1100',
                                       preflight=lambda: called.append(True), cancelled=lambda: True)
        self.assertFalse(called)
        self.assertFalse(result['completed'])
        self.assertEqual(result['state'], 'desconocido')
        self.assertTrue((self.root / 'cancel.zip').is_file())

    def test_mismatched_sdk_does_not_touch_usb(self):
        (self.fixture.sdk / 'fake.dll').write_bytes(b'wrong')
        called = []
        result = images.capture_images(self.root / 'bad.zip', self.fixture.sdk, '01.00.1100',
                                       preflight=lambda: called.append(True))
        self.assertFalse(called)
        self.assertEqual(result['state'], 'error')

    def test_wrong_firmware_and_existing_destinations_are_refused(self):
        with self.assertRaises(ValueError):
            images.capture_images(self.root / 'wrong.zip', self.fixture.sdk, '01.00.0200')
        p = self.root / 'existing.zip'
        p.write_bytes(b'keep')
        with self.assertRaises(ValueError):
            images.capture_images(p, self.fixture.sdk, '01.00.1100')
        self.assertEqual(p.read_bytes(), b'keep')

    def test_untrusted_frame_paths_and_duplicates_are_refused(self):
        job = self.job()
        result = receiver.run_job(job, api_factory=FakeAPI)
        for replacement in ['../other.pgm', '/absolute.pgm']:
            altered = {**result, 'frames': [{**result['frames'][0], 'file': replacement}]}
            with self.assertRaises(ValueError):
                images.validate_frames(job.parent, altered)
        with self.assertRaises(ValueError):
            images.validate_frames(job.parent, {'frames': [result['frames'][0]] * 2})

    def test_foreign_session_cannot_mark_capture_complete(self):
        def launcher(job):
            (job.parent / 'result.json').write_text(json.dumps({'session_id': 'b' * 32, 'frames': [], 'completed': True}))
            return FinishedProcess()
        result = images.capture_images(self.root / 'foreign.zip', self.fixture.sdk, '01.00.1100',
                                       preflight=lambda: {}, launcher=launcher)
        self.assertEqual(result['state'], 'error')
        self.assertFalse(result['completed'])


if __name__ == '__main__':
    unittest.main()
