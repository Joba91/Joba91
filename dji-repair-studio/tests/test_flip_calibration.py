import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as N
from unittest.mock import Mock
from zipfile import ZipFile
from studio_service import packet
from studio_protocol import version_request
from flip_gimbal_query import load_reference,query_flip_modules
from flip_gimbal_calibration import load_calibration_reference,FlipCalibrationTransport,run_flip_calibration
from test_flip_query import save_reference,Exchange,Clock
from test_passive_usb import Device

class CalibrationFixture:
    def __init__(self,ref,routine,scenario='success'):
        self.clock=Clock();self.device=Device();self.util=Mock();self.pending=[];self.sent=[]
        self.out=self.device.cfg[0][0];self.inside=self.device.cfg[0][1]
        def report(data,sender=4,cmd=0x30):return packet(sender,10,600,4,cmd,data,flags=0)
        def write(req,timeout):
            self.sent.append(req)
            if req[9:11]==b'\0\1':
                payload=ref['version_payloads'][req[5]]
                if scenario=='changed_version' and req[5]==4:payload=payload[:-1]+bytes([payload[-1]^1])
                self.pending.append(packet(req[5],10,int.from_bytes(req[6:8],'little'),0,1,payload,flags=128))
                if scenario=='already_busy' and req[5]==4:self.pending.append(report(b'\x52\1'))
                return len(req)
            if scenario=='short_write':return 3
            if scenario=='libusb0_silent':return len(req)
            seq=int.from_bytes(req[6:8],'little')
            ack_payload=b'\xfb' if scenario=='fb' else (b'\x99' if scenario=='unknown_ack' else b'\1')
            ack=packet(4,10,seq+(1 if scenario=='wrong_ack_seq' and seq<65535 else 0),4,8,ack_payload,flags=128)
            if scenario=='wrong_ack_seq' and seq==65535:ack=packet(4,10,0,4,8,ack_payload,flags=128)
            self.pending.append(ack)
            stage=b'\x52\1' if routine=='JointCoarse' else b'\x12\1'
            if scenario not in ('ack_only','terminal_only','fb','timeout','disconnect','cancel'):
                self.pending.append(report(stage,sender=3 if scenario=='wrong_sender' else 4))
            if scenario not in ('ack_only','fb','timeout','disconnect','cancel'):
                terminal=b'\x64\x04' if scenario in ('firmware_timeout','timeout_then_disconnect','conflicting_terminal') else b'\x64\3' if scenario=='failure' else b'\x64\0'
                self.pending.append(report(terminal,sender=3 if scenario=='wrong_sender' else 4))
            if scenario=='conflicting_terminal':self.pending.append(report(b'\x64\0'))
            if scenario=='ack_shaped_status':
                self.pending[-2:]=[packet(4,10,600,4,0x30,stage,flags=128),packet(4,10,601,4,0x30,b'\x64\0',flags=128)]
            return len(req)
        def read(size,timeout):
            self.clock.value+=.2
            if scenario in ('disconnect','timeout_then_disconnect') and not self.pending and any(r[9:11]==b'\4\10' for r in self.sent):raise OSError('SYNTHETIC disconnected')
            if not self.pending and scenario in ('libusb0_idle','libusb0_silent','usb_error_before_cal'):
                from usb.core import USBError
                raise USBError('SYNTHETIC libusb0 read',-5 if scenario=='usb_error_before_cal' else -116)
            return self.pending.pop(0) if self.pending else b''
        self.out.write.side_effect=write;self.inside.read.side_effect=read
        self.transport=FlipCalibrationTransport(ref,routine,enumerator=lambda:[self.device],
            selector=lambda ds:(ds[0],{'selected_mi':4}),
            parent_reader=lambda d:{k:ref[k] for k in ('product','child_instance_sha256','parent_instance_sha256')},util=self.util)

class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        profile=save_reference(self.root/'profile.zip');ref=load_reference(profile,'01.00.1500');ex=Exchange(ref)
        self.modules=self.root/'modules.zip'
        query_flip_modules(self.modules,profile,'01.00.1500',transport_factory=lambda r:ex.transport,clock=ex.clock)
        self.ref=load_calibration_reference(self.modules,'01.00.1500')
    def tearDown(self):self.temp.cleanup()
    def run_probe(self,routine='JointCoarse',scenario='success',**kw):
        for p in (self.root/'cal.zip',self.root/'cal.bin'):p.unlink(missing_ok=True)
        self.fixture=CalibrationFixture(self.ref,routine,scenario)
        return run_flip_calibration(self.root/'cal.zip',self.modules,'01.00.1500',routine,
            transport_factory=lambda r,a:self.fixture.transport,clock=self.fixture.clock,max_seconds=2,**kw)
    def test_joint_and_linear_accept_only_fresh_ack_progress_and_terminal(self):
        for routine in ('JointCoarse','LinearHall'):
            with self.subTest(routine=routine):
                events=[];r=self.run_probe(routine,progress=events.append)
                self.assertEqual(r['state'],'equipo_informa_fin');self.assertTrue(r['device_reported_completion'])
                self.assertTrue(r['ack_received']);self.assertIsNone(r['calibration_performed'])
                self.assertEqual(r['calibration_requests_attempted'],1);self.assertEqual(r['calibration_requests_bulk_complete'],1)
                self.assertEqual(r['factory_commands_sent'],0);self.assertFalse(r['flip_compatibility_validated'])
                self.assertEqual(events[-1]['percent'],100);self.assertEqual(self.fixture.out.write.call_count,3)
                self.assertEqual(self.fixture.sent[-1][11:-2],b'\1' if routine=='JointCoarse' else b'\2')
                self.fixture.util.release_interface.assert_called_once_with(self.fixture.device,4)
                with ZipFile(self.root/'cal.zip') as z:
                    data=json.loads(z.read('DJI-REPAIR-informe.json'))['gimbal']['calibration_probe']
                    self.assertEqual(data['state'],'equipo_informa_fin');self.assertEqual(len(z.read('cal.bin')),r['rx_bytes'])
    def test_libusb0_idle_before_request_allows_one_probe_for_each_routine(self):
        for routine in ('JointCoarse','LinearHall'):
            with self.subTest(routine=routine):
                r=self.run_probe(routine,scenario='libusb0_idle')
                self.assertEqual(r['state'],'equipo_informa_fin')
                self.assertEqual(r['calibration_requests_attempted'],1)
                self.assertEqual(self.fixture.out.write.call_count,3)
                self.assertGreater(r['usb_evidence']['read_timeouts'],0)
                self.assertEqual(r['usb_evidence']['last_read_timeout']['backend_error_code'],-116)

    def test_repeated_libusb0_idle_after_probe_is_not_completion_or_retry(self):
        events=[];r=self.run_probe(scenario='libusb0_silent',progress=events.append)
        self.assertNotEqual(r['state'],'equipo_informa_fin')
        self.assertFalse(r['device_reported_completion'])
        self.assertFalse(any(e.get('percent')==100 for e in events))
        self.assertEqual(r['calibration_requests_attempted'],1)
        self.assertEqual(self.fixture.out.write.call_count,3)
        self.assertGreater(r['usb_evidence']['read_timeouts'],1)

    def test_real_usb_error_in_drain_stops_before_calibration_and_saves_code(self):
        r=self.run_probe(scenario='usb_error_before_cal')
        self.assertEqual(r['state'],'error')
        self.assertEqual(r['calibration_requests_attempted'],0)
        self.assertEqual(r['usb_evidence']['read_error']['backend_error_code'],-5)
        self.assertEqual(self.fixture.out.write.call_count,2)
    def test_ack_only_unknown_ack_terminal_only_and_wrong_sequence_are_not_success(self):
        for scenario in ('ack_only','unknown_ack','terminal_only','wrong_ack_seq','wrong_sender'):
            with self.subTest(scenario=scenario):
                events=[];r=self.run_probe(scenario=scenario,progress=events.append)
                self.assertNotEqual(r['state'],'equipo_informa_fin')
                self.assertFalse(any(e.get('percent')==100 for e in events))
                self.assertEqual(r['calibration_requests_attempted'],1)
    def test_preexisting_progress_and_changed_version_send_no_calibration(self):
        for scenario in ('already_busy','changed_version'):
            with self.subTest(scenario=scenario):
                r=self.run_probe(scenario=scenario)
                self.assertEqual(r['state'],'error');self.assertEqual(r['calibration_requests_attempted'],0)
                self.assertIs(r['calibration_performed'],False)
                self.assertTrue(all(req[9:11]==b'\0\1' for req in self.fixture.sent))
    def test_fb_is_retained_without_factory_fallback_or_retry(self):
        r=self.run_probe(scenario='fb')
        self.assertEqual(r['state'],'inicio_no_confirmado');self.assertEqual(r['ack_payload'],'fb')
        self.assertEqual(r['factory_commands_sent'],0);self.assertEqual(self.fixture.out.write.call_count,3)
        self.assertEqual(r['calibration_requests_attempted'],1)
    def test_device_failure_is_not_success_and_does_not_assign_physical_cause(self):
        events=[];r=self.run_probe(scenario='failure',progress=events.append)
        self.assertEqual(r['state'],'fallo_informado_por_equipo');self.assertTrue(r['device_reported_failure'])
        self.assertFalse(any(e.get('percent')==100 for e in events))
    def test_6404_is_common_reference_timeout_without_axis_diagnosis_or_retry(self):
        events=[];r=self.run_probe(scenario='firmware_timeout',progress=events.append)
        self.assertEqual(r['state'],'timeout_rutina_segun_referencia')
        self.assertTrue(r['routine_timeout_reported_by_common_reference'])
        self.assertEqual(r['last_status_payload'],'6404')
        self.assertEqual(r['status_counts'],{'5201':1,'6404':1})
        self.assertEqual(r['last_status_reference']['common_name'],'TIMEOUT')
        self.assertFalse(r['last_status_reference']['physical_cause_confirmed'])
        self.assertFalse(r['flip_status_mapping_validated'])
        self.assertFalse(r['device_reported_completion'])
        self.assertEqual(r['calibration_requests_attempted'],1)
        self.assertEqual(self.fixture.out.write.call_count,3)
        self.assertFalse(any(e.get('percent')==100 for e in events))
    def test_timeout_reference_is_preserved_when_a_later_usb_read_fails(self):
        r=self.run_probe(scenario='timeout_then_disconnect')
        self.assertEqual(r['state'],'timeout_rutina_segun_referencia')
        self.assertIn('SYNTHETIC disconnected',r['monitoring_error'])
        self.assertEqual(r['last_status_payload'],'6404')
        self.assertEqual(r['calibration_requests_attempted'],1)
        self.assertTrue((self.root/'cal.zip').is_file())
    def test_conflicting_terminal_and_ack_shaped_status_do_not_complete(self):
        for scenario in ('conflicting_terminal','ack_shaped_status'):
            with self.subTest(scenario=scenario):
                events=[];r=self.run_probe(scenario=scenario,progress=events.append)
                self.assertNotEqual(r['state'],'equipo_informa_fin')
                self.assertFalse(any(e.get('percent')==100 for e in events))
                if scenario=='conflicting_terminal':self.assertEqual(r['state'],'informes_finales_incompatibles')
                else:self.assertEqual(r['report_count'],0)
    def test_timeout_disconnect_and_uncertain_write_preserve_zip_and_never_resend(self):
        for scenario in ('timeout','disconnect','short_write'):
            with self.subTest(scenario=scenario):
                r=self.run_probe(scenario=scenario)
                self.assertNotEqual(r['state'],'equipo_informa_fin');self.assertTrue((self.root/'cal.zip').is_file())
                self.assertEqual(r['calibration_requests_attempted'],1);self.assertIsNone(r['calibration_performed'])
                self.fixture.util.release_interface.assert_called_once()
                self.assertEqual(r['calibration_delivery_uncertain'],scenario=='short_write')
    def test_cancel_after_request_is_read_stop_not_motor_stop(self):
        def cancelled():return hasattr(self,'fixture') and bool(self.fixture.transport.cal_attempts)
        r=self.run_probe(scenario='cancel',cancelled=cancelled)
        self.assertEqual(r['state'],'lectura_detenida');self.assertFalse(r['stop_command_sent'])
        self.assertEqual(r['calibration_requests_attempted'],1);self.assertIsNone(r['calibration_performed'])
    def test_transport_denies_factory_other_routine_and_repeat(self):
        f=CalibrationFixture(self.ref,'JointCoarse');t=f.transport
        self.addCleanup(t.close)
        with self.assertRaises(ValueError):t.write(packet(10,4,1,4,8,b'\1'))
        t.write(version_request(3,10));t.write(version_request(4,11));t.arm()
        for req in (packet(42,0x8f,1,0,0x44,b'\x80\x0astart_factory\0'),packet(10,4,1,4,8,b'\2'),packet(10,4,1,4,9,b'\1')):
            with self.assertRaises(ValueError):t.write(req)
        t.write(packet(10,4,12,4,8,b'\1'))
        with self.assertRaises(ValueError):t.write(packet(10,4,13,4,8,b'\1'))
        self.assertEqual(f.out.write.call_count,3)
    def test_corrupt_reference_wrong_firmware_and_non_module_zip_stop_before_usb(self):
        factory=Mock()
        for fw in ('01.00.1600',''):
            with self.assertRaises(ValueError):run_flip_calibration(self.root/'cal.zip',self.modules,fw,'JointCoarse',transport_factory=factory)
        with self.assertRaises(ValueError):load_calibration_reference(self.root/'profile.zip','01.00.1500')
        with ZipFile(self.modules) as z:
            r=json.loads(z.read('DJI-REPAIR-informe.json'));raw=z.read('modules.bin')
        r['gimbal']['module_query']['packet_audit'][1]['hex']='55 00'
        bad=self.root/'bad.zip'
        with ZipFile(bad,'w') as z:
            z.writestr('DJI-REPAIR-informe.json',json.dumps(r));z.writestr('raw.bin',raw)
        with self.assertRaises(ValueError):run_flip_calibration(self.root/'cal.zip',bad,'01.00.1500','JointCoarse',transport_factory=factory)
        factory.assert_not_called()
