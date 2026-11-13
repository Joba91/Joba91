import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from zipfile import ZipFile
from studio_protocol import version_request
from studio_service import packet
from flip_gimbal_query import load_reference,FlipVersionTransport,query_flip_modules,MAX_RX
from test_vision_usb_inventory import node
from test_passive_usb import Device

ROOT='USB\\VID_2CA3&PID_0020\\SYNTHETIC'
CHILD='USB\\VID_2CA3&PID_0020&MI_04\\SYNTHETIC_CHILD'

def reference_report():
    return {'modelo_declarado':'DJI Flip','firmware_declarado':'01.00.1500','gimbal':{'usb_profile':{
        'collection_complete':True,'devices':[node(ROOT,'DJI-SYNTHETIC'),{**node(CHILD,'BULK Interface'),'parent':ROOT}],
        'descriptor_inventory':{'state':'confirmado','errors':[],'aliases':[{'pnp_interface_number':4,
            'complete':True,'pnp_instance_matches':True,'configurations':[{'bConfigurationValue':1,'interfaces':[{
                'bInterfaceNumber':4,'bAlternateSetting':0,'bInterfaceClass':255,'bInterfaceSubClass':0x43,
                'bInterfaceProtocol':1,'bNumEndpoints':2,'endpoints':[
                    {'bEndpointAddress':4,'bmAttributes':2,'wMaxPacketSize':512},
                    {'bEndpointAddress':0x85,'bmAttributes':2,'wMaxPacketSize':512}]}]}]}]}}}}

def save_reference(path,report=None):
    with ZipFile(path,'w') as z:z.writestr('DJI-REPAIR-informe.json',json.dumps(reference_report() if report is None else report))
    return path

class Clock:
    value=0
    def __call__(self):return self.value

class Exchange:
    """Only synthetic endpoint data, exercising the production transport guard."""
    def __init__(self,ref,respond=True,wrong_seq=False):
        self.clock=Clock();self.device=Device();self.util=Mock();self.pending=b'';self.respond=respond
        self.out=self.device.cfg[0][0];self.inside=self.device.cfg[0][1]
        def write(req,timeout):
            assert timeout==500
            payload=b'\0\0'+(b'SYNTHETIC-FC' if req[5]==3 else b'SYNTHETIC-GIMBAL').ljust(16,b'\0')+bytes(4)+(0x04000007).to_bytes(4,'little')
            seq=int.from_bytes(req[6:8],'little')
            if self.respond:self.pending=packet(req[5],10,(seq+1)&65535 if wrong_seq else seq,0,1,payload,flags=128)
            return len(req)
        def read(size,timeout):
            assert size==512 and timeout==200
            self.clock.value+=.25
            data=self.pending;self.pending=b'';return data
        self.out.write.side_effect=write;self.inside.read.side_effect=read
        self.transport=FlipVersionTransport(ref,enumerator=lambda:[self.device],
            selector=lambda devices:(devices[0],{'selected_mi':4}),
            parent_reader=lambda dev:{k:ref[k] for k in ('product','child_instance_sha256','parent_instance_sha256')},util=self.util)

class ReferenceTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def test_complete_reference_is_loaded_without_a_marketing_alias(self):
        ref=load_reference(save_reference(self.root/'p.zip'),'01.00.1500')
        self.assertEqual(ref['product'],'DJI-SYNTHETIC');self.assertEqual(len(ref['child_instance_sha256']),64)
    def test_wrong_model_firmware_partial_and_ambiguous_profile_refused(self):
        for key in ('model','firmware','partial','roots','alias','endpoint','mi','parent'):
            with self.subTest(key=key):
                r=reference_report();raw=r['gimbal']['usb_profile'];a=raw['descriptor_inventory']['aliases'][0]
                if key=='model':r['modelo_declarado']='Mini 4 Pro'
                if key=='firmware':r['firmware_declarado']='01.00.1600'
                if key=='partial':raw['collection_complete']=False
                if key=='roots':raw['devices'].append(node('USB\\VID_2CA3&PID_0020\\OTHER'))
                if key=='alias':raw['descriptor_inventory']['aliases'].append(copy.deepcopy(a))
                if key=='endpoint':a['configurations'][0]['interfaces'][0]['endpoints'][1]['bEndpointAddress']=0x86
                if key=='mi':a['pnp_interface_number']=5
                if key=='parent':raw['devices'][1]['parent']='OTHER'
                with self.assertRaises(ValueError):load_reference(save_reference(self.root/'p.zip',r),'01.00.1500')
    def test_malformed_and_duplicate_json_members_are_refused(self):
        for r in ([],{}, {'gimbal':[]}, {'gimbal':{},'modelo_declarado':'DJI Flip','firmware_declarado':'01.00.1500'}):
            with self.assertRaises(ValueError):load_reference(save_reference(self.root/'p.zip',r),'01.00.1500')
        p=self.root/'duplicate.zip'
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            with ZipFile(p,'w') as z:
                z.writestr('DJI-REPAIR-informe.json','{}');z.writestr('DJI-REPAIR-informe.json','{}')
        with self.assertRaises(ValueError):load_reference(p,'01.00.1500')

class TransportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.ref=load_reference(save_reference(Path(self.temp.name)/'p.zip'),'01.00.1500')
        self.exchange=Exchange(self.ref);self.t=self.exchange.transport;self.addCleanup(self.t.close)
    def test_only_two_version_requests_can_reach_out(self):
        self.assertEqual(self.t.write(version_request(3,1)),13)
        self.assertEqual(self.t.write(version_request(4,2)),13)
        with self.assertRaises(ValueError):self.t.write(version_request(3,3))
        self.assertEqual(self.exchange.out.write.call_count,2)
    def test_factory_calibration_and_other_receivers_cannot_reach_usb(self):
        for req in (packet(10,4,1,4,8,b'\1'),packet(42,0x8f,1,0,0x44,b'\x80\x0astart_factory\0'),
                    version_request(1,2),version_request(11,2),b''):
            with self.assertRaises(ValueError):self.t.write(req)
        self.exchange.out.write.assert_not_called()
    def test_duplicate_receiver_is_not_retried(self):
        self.t.write(version_request(3,1))
        with self.assertRaises(ValueError):self.t.write(version_request(3,2))
        self.assertEqual(self.exchange.out.write.call_count,1)
    def test_short_write_is_uncertain_and_not_repeated(self):
        self.exchange.out.write.side_effect=lambda *args,**kw:3
        with self.assertRaises(OSError):self.t.write(version_request(3,1))
        self.assertTrue(self.t.uncertain_tx);self.assertEqual(self.t.tx_confirmed,[])
        with self.assertRaises(ValueError):self.t.write(version_request(3,2))
    def test_changed_parent_is_refused_before_open_configuration_or_claim(self):
        d=Device();util=Mock()
        with self.assertRaisesRegex(ValueError,'no coincide'):
            FlipVersionTransport(self.ref,enumerator=lambda:[d],selector=lambda ds:(ds[0],{}),parent_reader=lambda d:{},util=util)
        d.get_active_configuration.assert_not_called();util.claim_interface.assert_not_called();util.dispose_resources.assert_called_once_with(d)
    def test_changed_endpoints_are_refused_without_configuration_changes(self):
        d=Device();d.cfg[0][1].bEndpointAddress=0x86;util=Mock()
        with self.assertRaisesRegex(ValueError,'Endpoints'):
            FlipVersionTransport(self.ref,enumerator=lambda:[d],selector=lambda ds:(ds[0],{}),parent_reader=lambda d:self.ref,util=util)
        util.claim_interface.assert_not_called()
        for method in ('set_configuration','reset','detach_kernel_driver','set_interface_altsetting','clear_halt'):
            getattr(d,method).assert_not_called()
    def test_close_releases_once_and_never_changes_configuration(self):
        self.t.close();self.t.close()
        self.exchange.util.release_interface.assert_called_once_with(self.exchange.device,4)
        self.exchange.util.dispose_resources.assert_called_once_with(self.exchange.device)
        for method in ('set_configuration','reset','detach_kernel_driver','ctrl_transfer','clear_halt'):
            getattr(self.exchange.device,method).assert_not_called()
    def test_rx_limit_is_bounded_and_disconnect_propagates(self):
        self.t.rx.extend(b'x'*(MAX_RX-1));self.exchange.inside.read.side_effect=lambda *a,**k:b'12'
        with self.assertRaises(RuntimeError):self.t.read()
        self.assertEqual(len(self.t.rx),MAX_RX)

    def test_pinned_libusb0_timeout_and_typed_timeout_are_idle_reads(self):
        from usb.core import USBError,USBTimeoutError
        for error in (USBError('SYNTHETIC timeout',-116),USBTimeoutError('SYNTHETIC timeout',-110,110)):
            with self.subTest(error=type(error).__name__):
                self.exchange.inside.read.side_effect=error
                self.assertEqual(self.t.read(),b'')
                self.assertEqual(self.t.evidence['last_read_timeout']['backend_error_code'],error.backend_error_code)
        self.assertEqual(self.t.evidence['read_timeouts'],2)
        self.assertEqual(self.t.rx,b'');self.exchange.out.write.assert_not_called()

    def test_other_usb_errors_are_not_hidden_even_when_text_says_timeout(self):
        from usb.core import USBError
        for code in (None,-5,-19,-4,-110):
            with self.subTest(code=code):
                error=USBError('timeout error',code)
                self.exchange.inside.read.side_effect=error
                with self.assertRaises(USBError) as caught:self.t.read()
                self.assertIs(caught.exception,error)
                self.assertEqual(self.t.evidence['read_error']['backend_error_code'],code)
        self.assertNotIn('read_timeouts',self.t.evidence)

    def test_pyusb_windows_errno_mismatch_reproduces_generic_timeout(self):
        from unittest.mock import patch
        from usb.backend import libusb0
        from usb.core import USBError,USBTimeoutError
        with patch.object(libusb0,'_lib',Mock(usb_strerror=lambda:b'SYNTHETIC libusb0 timeout')),patch.object(libusb0.errno,'ETIMEDOUT',138):
            with self.assertRaises(USBError) as caught:libusb0._check(-116)
        self.assertNotIsInstance(caught.exception,USBTimeoutError)
        self.assertEqual(caught.exception.backend_error_code,-116)
        self.assertIsNone(caught.exception.errno)
        self.exchange.inside.read.side_effect=caught.exception
        self.assertEqual(self.t.read(),b'')

class QueryTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.profile=save_reference(self.root/'profile.zip')
    def tearDown(self):self.temp.cleanup()
    def run_query(self,respond=True,wrong_seq=False,**kw):
        ref=load_reference(self.profile,'01.00.1500');self.ex=Exchange(ref,respond=respond,wrong_seq=wrong_seq)
        return query_flip_modules(self.root/'modules.zip',self.profile,'01.00.1500',transport_factory=lambda ref:self.ex.transport,clock=self.ex.clock,**kw)
    def test_correlated_versions_raw_rx_and_query_audit_are_bundled(self):
        events=[];r=self.run_query(progress=events.append)
        self.assertEqual(r['state'],'confirmado');self.assertEqual(len(r['modules']),2)
        self.assertEqual(r['bulk_out_bytes_confirmed'],26);self.assertEqual(r['version_requests_attempted'],2)
        self.assertFalse(r['model_identity_confirmed']);self.assertFalse(r['calibration_available'])
        self.assertEqual(r['gimbal_calibration_commands_sent'],0);self.assertEqual(r['factory_commands_sent'],0)
        self.assertEqual(events[-1]['percent'],100);self.assertIn('no es calibración',events[-1]['label'])
        self.ex.util.release_interface.assert_called_once()
        with ZipFile(self.root/'modules.zip') as z:
            self.assertEqual(len(z.read('modules.bin')),78)
            report=json.loads(z.read('DJI-REPAIR-informe.json'));self.assertIn('module_query',report['gimbal'])
            self.assertEqual([x['direccion'] for x in r['packet_audit']],['TX','RX','TX','RX'])
    def test_no_response_and_wrong_sequence_do_not_confirm_versions_or_reach_100(self):
        for respond,wrong in ((False,False),(True,True)):
            with self.subTest(respond=respond,wrong=wrong):
                for p in (self.root/'modules.zip',self.root/'modules.bin'):p.unlink(missing_ok=True)
                events=[];r=self.run_query(respond,wrong,progress=events.append)
                self.assertEqual(r['state'],'desconocido');self.assertTrue(all(x['estado']=='sin_respuesta' for x in r['modules']))
                self.assertFalse(any(e.get('percent')==100 for e in events));self.assertEqual(self.ex.out.write.call_count,2)
    def test_open_failure_is_saved_with_last_stage_and_empty_capture(self):
        def fail(ref):
            e=OSError('synthetic open failure');e.flip_evidence={'stage':'reclamar_mi04'};raise e
        r=query_flip_modules(self.root/'modules.zip',self.profile,'01.00.1500',transport_factory=fail)
        self.assertEqual(r['state'],'error');self.assertEqual(r['usb_evidence']['stage'],'reclamar_mi04')
        self.assertEqual(r['rx_bytes'],0);self.assertTrue((self.root/'modules.zip').is_file())
    def test_cancel_before_open_and_existing_files_send_nothing(self):
        factory=Mock();r=query_flip_modules(self.root/'modules.zip',self.profile,'01.00.1500',transport_factory=factory,cancelled=lambda:True)
        factory.assert_not_called();self.assertEqual(r['state'],'desconocido')
        with self.assertRaises(ValueError):query_flip_modules(self.root/'modules.zip',self.profile,'01.00.1500',transport_factory=factory)
        factory.assert_not_called()
