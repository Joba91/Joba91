import copy
import ctypes as C
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from vision_windows_pnp import (DEVPROPKEY, PROPERTIES, listed_dji_ids, read_property,
                                native_inventory, inventory_worker, atomic_json, PRESENT_USB)
from vision_usb_inventory import query_windows_pnp, collect_usb_profile, launch_inventory_worker
from test_vision_usb_inventory import inventory, node


def u32(pointer, value):
    C.cast(pointer, C.POINTER(C.c_uint32))[0] = value


class FakeCM:
    """Synthetic ABI fixture; no Windows or drone operations."""
    def __init__(self, ids=None):
        self.ids = ids if ids is not None else [node()['instance_id']]
        self.calls = []; self.fail_property = None; self.wrong_type = False; self.race = 0
    def CM_Get_Device_ID_List_SizeW(self, output, enumerator, flags):
        self.calls.append(('size', enumerator, flags))
        u32(output, len('\0'.join(self.ids)+'\0\0') if self.ids else 1); return 0
    def CM_Get_Device_ID_ListW(self, enumerator, output, size, flags):
        self.calls.append(('list', enumerator, flags))
        if self.race:
            self.race -= 1; return 0x1a
        text = '\0'.join(self.ids)+'\0\0' if self.ids else '\0'
        for i, char in enumerate(text): output[i] = char
        return 0
    def CM_Locate_DevNodeW(self, output, instance, flags):
        self.calls.append(('locate', instance, flags)); u32(output, 7); return 0
    def CM_Get_DevNode_PropertyW(self, dev, key, kind, data, size, flags):
        key = C.cast(key, C.POINTER(DEVPROPKEY)).contents
        name = ('bus_product' if key.fmtid.data1 == 0x540b947e else
                {14:'friendly_name', 6:'service', 3:'hardware_ids', 2:'description'}[key.pid])
        self.calls.append(('property', name))
        if self.fail_property == name: return 0x25
        value = {'bus_product':'DJI Air 3-SYNTHETIC', 'friendly_name':'Synthetic device',
                 'service':'usbccgp', 'hardware_ids':'USB\\VID_2CA3&PID_0020\0',
                 'description':'Synthetic fallback'}[name] + '\0'
        payload = value.encode('utf-16-le'); C.memmove(data, payload, len(payload))
        u32(size, len(payload)); u32(kind, 7 if self.wrong_type else (0x2012 if name=='hardware_ids' else 0x12))
        return 0
    def CM_Get_Parent(self, out, dev, flags): u32(out, 8); return 0
    def CM_Get_Device_IDW(self, dev, out, size, flags): out.value = 'SYNTHETIC_PARENT'; return 0
    def CM_Get_DevNode_Status(self, status, problem, dev, flags):
        u32(status, 0x2000); u32(problem, 0); return 0


class NativeTests(unittest.TestCase):
    def test_filters_present_usb_before_properties_and_reads_utf16_multisz(self):
        cm = FakeCM(['USB\\VID_1234&PID_0001\\OTHER', node()['instance_id']])
        raw = native_inventory(api_factory=lambda: cm)
        self.assertTrue(raw['collection_complete']); self.assertEqual(len(raw['devices']), 1)
        row = raw['devices'][0]
        self.assertEqual(row['bus_product'], 'DJI Air 3-SYNTHETIC')
        self.assertEqual(row['hardware_ids'], ['USB\\VID_2CA3&PID_0020'])
        self.assertEqual(row['status'], 'DN 0x00002000'); self.assertEqual(row['problem_code'], 0)
        self.assertEqual(raw['property_errors'], [])
        self.assertEqual(cm.calls[:2], [('size','USB',PRESENT_USB), ('list','USB',PRESENT_USB)])
        self.assertEqual([c[1] for c in cm.calls if c[0]=='locate'], [node()['instance_id']])
    def test_empty_list_and_single_race_retry(self):
        self.assertEqual(listed_dji_ids(FakeCM([])), [])
        cm = FakeCM(); cm.race = 1
        self.assertEqual(listed_dji_ids(cm), cm.ids)
        self.assertEqual(len(cm.calls), 4)
        cm.race = 2
        with self.assertRaisesRegex(RuntimeError, 'CONFIGRET'): listed_dji_ids(cm)
    def test_bad_duplicate_and_too_many_ids_stop_before_properties(self):
        for ids in ([node()['instance_id']]*2, ['USB\\VID_2CA3&PID_0020\\BAD\\PATH'],
                    [f'USB\\VID_2CA3&PID_0020\\SYNTHETIC{i}' for i in range(65)]):
            cm = FakeCM(ids)
            raw = native_inventory(api_factory=lambda: cm)
            self.assertFalse(raw['collection_complete']); self.assertEqual(raw['devices'], [])
            self.assertFalse(any(c[0]=='property' for c in cm.calls))
    def test_wrong_type_is_not_decoded_as_success(self):
        cm = FakeCM(); cm.wrong_type = True
        with self.assertRaises(ValueError): read_property(cm, 7, *PROPERTIES['bus_product'])
        raw = native_inventory(api_factory=lambda: cm)
        self.assertTrue(raw['collection_complete']); self.assertIsNone(raw['devices'][0]['bus_product'])
        self.assertEqual(len(raw['property_errors']), 5)
    def test_missing_property_retains_other_values_and_records_stage_error(self):
        cm = FakeCM(); cm.fail_property = 'bus_product'
        raw = native_inventory(api_factory=lambda: cm)
        self.assertIsNone(raw['devices'][0]['bus_product'])
        self.assertEqual(raw['devices'][0]['service'], 'usbccgp')
        self.assertEqual(raw['property_errors'][0]['property'], 'bus_product')
    def test_friendly_name_falls_back_to_description(self):
        cm=FakeCM(); cm.fail_property='friendly_name'
        raw=native_inventory(api_factory=lambda: cm)
        self.assertEqual(raw['devices'][0]['friendly_name'],'Synthetic fallback')
    def test_cancel_snapshot_keeps_already_read_fields(self):
        snapshots=[]
        def save(raw): snapshots.append(copy.deepcopy(raw))
        raw=native_inventory(api_factory=FakeCM, snapshot=save,
                             cancelled=lambda: bool(snapshots and snapshots[-1]['stage']=='nodo_0_service'))
        self.assertFalse(raw['collection_complete']); self.assertTrue(raw['cancelled'])
        self.assertEqual(raw['stage'],'nodo_0_service')
        self.assertEqual(raw['devices'][0]['bus_product'],'DJI Air 3-SYNTHETIC')
        self.assertIsNone(raw['devices'][0]['service'])
    def test_unplugged_node_is_recorded_without_inventing_properties(self):
        cm=FakeCM(); cm.CM_Locate_DevNodeW=lambda *args: 0xd
        raw=native_inventory(api_factory=lambda: cm)
        self.assertEqual(raw['property_errors'][0]['property'],'locate')
        self.assertIsNone(raw['devices'][0]['bus_product'])
    def test_native_load_failure_retains_last_stage(self):
        def unavailable(): raise OSError('SYNTHETIC missing API')
        raw=native_inventory(api_factory=unavailable)
        self.assertEqual(raw['stage'],'cargar_cfgmgr32'); self.assertIn('missing API',raw['error'])
    def test_worker_writes_bound_session_result_and_rejects_untrusted_job(self):
        with tempfile.TemporaryDirectory() as folder:
            job=Path(folder)/'job.json'; job.write_text(json.dumps({'session_id':'a'*32}))
            raw=native_inventory(api_factory=FakeCM)
            with patch('vision_windows_pnp.native_inventory',return_value=raw):
                self.assertEqual(inventory_worker(job),0)
            result=json.loads((job.parent/'result.json').read_text())
            self.assertEqual(result,{'session_id':'a'*32,'inventory':raw})
            job.write_text(json.dumps({'session_id':'../invalid','destination':'elsewhere'}))
            with self.assertRaises(ValueError): inventory_worker(job)


class Process:
    def __init__(self, code=0): self.code=code; self.closed=False; self.terminated=False
    def poll(self): return self.code
    def wait(self, timeout): return 1 if self.terminated else self.code
    def terminate(self): self.terminated=True
    def close(self): self.closed=True


class WorkerTests(unittest.TestCase):
    def launcher(self, raw, *, stuck=False, bad_session=False, result=True):
        self.process=Process(None if stuck else 0)
        def launch(job):
            sid=json.loads(job.read_text())['session_id']
            atomic_json(job.parent/('result.json' if result else 'snapshot.json'),
                        {'session_id':'b'*32 if bad_session else sid,'inventory':raw})
            return self.process
        return launch
    def raw(self, complete=True):
        return {**inventory(node()),'collector_backend':'cfgmgr32','collection_complete':complete,
                'stage':'completado' if complete else 'nodo_0_status','property_errors':[]}
    def test_hidden_launcher_uses_same_executable_without_powershell(self):
        with patch('windows_job.start_hidden_process') as start:
            launch_inventory_worker(Path('/tmp/synthetic/job.json'))
        args,cwd=start.call_args.args
        self.assertIn('--usb-inventory-worker',args)
        self.assertEqual(args[-1],'/tmp/synthetic/job.json')
        self.assertFalse(any('powershell' in arg.lower() for arg in args))
    def test_completed_worker_result_is_returned_and_job_closed(self):
        result=query_windows_pnp(launcher=self.launcher(self.raw()))
        self.assertTrue(result['collection_complete']); self.assertTrue(self.process.closed)
    def test_timeout_preserves_snapshot_rows_stage_and_kills_job(self):
        result=query_windows_pnp(launcher=self.launcher(self.raw(False),stuck=True,result=False),max_seconds=0)
        self.assertFalse(result['collection_complete']); self.assertTrue(result['timeout'])
        self.assertEqual(result['devices'],[node()]); self.assertEqual(result['stage'],'nodo_0_status')
        self.assertTrue(self.process.terminated); self.assertTrue(self.process.closed)
        with tempfile.TemporaryDirectory() as folder:
            events=[]
            report=collect_usb_profile(Path(folder)/'partial.zip','Air 3','01.00.1600',
                                       collector=lambda **kw:result,progress=events.append)
            self.assertEqual(report['devices'],[node()]); self.assertEqual(report['inventory_state'],'incompleto')
            self.assertFalse(report['model_descriptor_matches']); self.assertFalse(report['calibration_available'])
            self.assertFalse(any(e.get('percent')==100 for e in events))
    def test_cancel_preserves_snapshot(self):
        result=query_windows_pnp(launcher=self.launcher(self.raw(False),stuck=True,result=False),cancelled=lambda:True)
        self.assertTrue(result['cancelled']); self.assertEqual(len(result['devices']),1)
        self.assertTrue(self.process.terminated); self.assertTrue(self.process.closed)
    def test_another_session_cannot_supply_inventory(self):
        with self.assertRaisesRegex(ValueError,'esta consulta'):
            query_windows_pnp(launcher=self.launcher(self.raw(),bad_session=True))
        self.assertTrue(self.process.closed)
    def test_wait_failure_still_closes_entire_job(self):
        launch=self.launcher(self.raw())
        self.process.wait=lambda **kw: (_ for _ in ()).throw(TimeoutError('synthetic stuck wait'))
        with self.assertRaises(TimeoutError): query_windows_pnp(launcher=launch)
        self.assertTrue(self.process.closed)
    def test_missing_final_file_cannot_promote_snapshot_to_complete(self):
        result=query_windows_pnp(launcher=self.launcher(self.raw(),result=False))
        self.assertFalse(result['collection_complete'])

if __name__=='__main__':unittest.main()
