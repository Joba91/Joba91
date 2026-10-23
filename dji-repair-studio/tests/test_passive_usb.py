"""USB dependency fakes: no real drone or official DLL required."""
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch,Mock
import usb.core
from vision_usb_passive import PassiveVisionUsbTransport,capture_passive
from vision_protocol import decode_bytes
from studio_service import packet
from test_sensor_records import sample

class Endpoint:
    def __init__(self,address):
        self.bEndpointAddress=address;self.bmAttributes=2;self.wMaxPacketSize=512
        self.read=Mock(return_value=b'abc')
        self.write=Mock(side_effect=AssertionError('OUT forbidden'))

class Interface(list):
    bInterfaceNumber=4;bAlternateSetting=0;bInterfaceClass=255;bInterfaceSubClass=0x43;bInterfaceProtocol=1;bNumEndpoints=2
    def __init__(self):super().__init__([Endpoint(4),Endpoint(0x85)])

class Configuration(list):
    bConfigurationValue=1
    def __init__(self):super().__init__([Interface()])

class Device:
    iProduct=2;speed=3
    def __init__(self):
        self.cfg=Configuration();self.get_active_configuration=Mock(return_value=self.cfg)
        for name in ('set_configuration','set_interface_altsetting','reset','detach_kernel_driver','ctrl_transfer','clear_halt','write'):
            setattr(self,name,Mock(side_effect=AssertionError('Forbidden: '+name)))

class PassiveTransportTests(unittest.TestCase):
    def setUp(self):
        self.device=Device();self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.backend=self.stack.enter_context(patch('usb.backend.libusb1.get_backend',return_value=object()))
        self.find=self.stack.enter_context(patch('usb.core.find',return_value=[self.device]))
        self.product=self.stack.enter_context(patch('usb.util.get_string',return_value='Mini 4 Pro-SYNTHETIC'))
        self.claim=self.stack.enter_context(patch('usb.util.claim_interface'))
        self.release=self.stack.enter_context(patch('usb.util.release_interface'))
        self.dispose=self.stack.enter_context(patch('usb.util.dispose_resources'))
    def assert_no_device_changes(self):
        for name in ('set_configuration','set_interface_altsetting','reset','detach_kernel_driver','ctrl_transfer','clear_halt','write'):
            getattr(self.device,name).assert_not_called()
        self.device.cfg[0][0].write.assert_not_called()
        self.device.cfg[0][1].write.assert_not_called()
    def test_only_matching_interface_read_and_release(self):
        t=PassiveVisionUsbTransport();self.assertFalse(hasattr(t,'write'))
        self.assertEqual(t.read(),b'abc')
        self.device.cfg[0][1].read.assert_called_once_with(512,timeout=200)
        self.claim.assert_called_once_with(self.device,4)
        t.close();t.close();self.release.assert_called_once_with(self.device,4)
        self.dispose.assert_called_once_with(self.device)
        self.assert_no_device_changes()
    def test_timeout_is_no_data_and_never_clears_halt(self):
        self.device.cfg[0][1].read.side_effect=usb.core.USBTimeoutError('timeout')
        t=PassiveVisionUsbTransport();self.assertEqual(t.read(),b'')
        self.assertEqual((t.attempts,t.timeouts),(1,1));t.close();self.assert_no_device_changes()
    def test_disconnect_is_not_swallowed_as_timeout(self):
        self.device.cfg[0][1].read.side_effect=usb.core.USBError('disconnected')
        t=PassiveVisionUsbTransport()
        with self.assertRaises(usb.core.USBError):t.read()
        t.close();self.assert_no_device_changes()
    def test_other_models_and_speeds_are_rejected(self):
        for product,speed in [('Mavic 4 Pro',3),('Mini 4 Pro-SYNTHETIC',2)]:
            self.product.return_value=product;self.device.speed=speed
            with self.assertRaises(RuntimeError):PassiveVisionUsbTransport()
        self.claim.assert_not_called();self.assert_no_device_changes()
    def test_wrong_endpoint_or_class_is_not_replaced_by_another_interface(self):
        self.device.cfg[0][1].bEndpointAddress=0x86
        with self.assertRaises(RuntimeError):PassiveVisionUsbTransport()
        self.device.cfg[0][1].bEndpointAddress=0x85;self.device.cfg[0].bInterfaceClass=8
        with self.assertRaises(RuntimeError):PassiveVisionUsbTransport()
        self.claim.assert_not_called();self.assert_no_device_changes()
    def test_missing_backend_and_ambiguous_devices_do_not_open(self):
        self.backend.return_value=None
        with self.assertRaises(RuntimeError):PassiveVisionUsbTransport()
        self.find.assert_not_called();self.backend.return_value=object()
        for devices in ([],[self.device,self.device]):
            self.find.return_value=devices
            with self.assertRaises(RuntimeError):PassiveVisionUsbTransport()
        self.device.get_active_configuration.assert_not_called()
    def test_driver_access_failure_disposes_without_install_or_detach(self):
        self.claim.side_effect=usb.core.USBError('access denied')
        with self.assertRaises(usb.core.USBError):PassiveVisionUsbTransport()
        self.release.assert_not_called();self.dispose.assert_called_once_with(self.device)
        self.assert_no_device_changes()

class Clock:
    def __init__(self):self.now=0
    def __call__(self):return self.now

class Receiver:
    def __init__(self,clock,chunks):
        self.clock=clock;self.chunks=iter(chunks);self.attempts=0;self.timeouts=0;self.closed=False
        self.evidence={'interface':4,'bulk_in':'85'}
    def read(self):
        self.clock.now+=1;self.attempts+=1
        item=next(self.chunks,b'')
        if isinstance(item,Exception):raise item
        if not item:self.timeouts+=1
        return item
    def close(self):self.closed=True

class PassiveCaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'capture.bin';self.clock=Clock();self.progress=[]
    def run_capture(self,chunks,**kwargs):
        self.receiver=Receiver(self.clock,chunks)
        return capture_passive(self.path,'01.00.1100',transport_factory=lambda:self.receiver,
            clock=self.clock,progress=self.progress.append,**kwargs)
    def test_receives_raw_bytes_and_percentage_measures_time_only(self):
        r=self.run_capture([b'ab',b'cd'])
        self.assertEqual(self.path.read_bytes(),b'abcd');self.assertEqual(r['received_bytes'],4)
        self.assertEqual(r['state'],'confirmado');self.assertTrue(self.receiver.closed)
        self.assertEqual(self.progress[-1]['percent'],100)
        self.assertTrue(all(e['basis']=='tiempo_de_recepcion' for e in self.progress))
        self.assertEqual(r['device_health'],'desconocido');self.assertFalse(r['firmware_read_from_device'])
        self.assertEqual((r['bulk_out_bytes'],r['protocol_commands_sent'],r['device_writes']),(0,0,0))
    def test_empty_capture_is_not_sensor_failure_or_health(self):
        r=self.run_capture([])
        self.assertEqual(r['state'],'desconocido');self.assertEqual(r['received_bytes'],0)
        self.assertTrue(r['reception_completed']);self.assertFalse(r['live_sensor_query_validated'])
    def test_interruption_keeps_partial_file_and_never_100(self):
        r=self.run_capture([b'partial'],cancelled=lambda:self.clock.now>=1)
        self.assertEqual(self.path.read_bytes(),b'partial');self.assertEqual(r['stop_reason'],'detenida_por_usuario')
        self.assertFalse(r['reception_completed']);self.assertLess(self.progress[-1]['percent'],100)
        self.assertTrue(self.receiver.closed)
    def test_read_error_retains_bytes_and_error(self):
        r=self.run_capture([b'partial',OSError('USB unplugged')])
        self.assertEqual(r['state'],'error');self.assertIn('USB unplugged',r['error'])
        self.assertEqual(self.path.read_bytes(),b'partial');self.assertTrue(self.receiver.closed)
        self.assertLess(self.progress[-1]['percent'],100)
    def test_byte_limit_is_not_full_duration(self):
        with patch('vision_usb_passive.MAX_BYTES',3):r=self.run_capture([b'abcd'])
        self.assertEqual(self.path.read_bytes(),b'abc');self.assertEqual(r['stop_reason'],'limite_de_bytes')
        self.assertFalse(r['reception_completed']);self.assertLess(self.progress[-1]['percent'],100)
    def test_no_overwrite_and_validation_before_usb(self):
        self.path.write_bytes(b'original');factory=Mock()
        with self.assertRaises(FileExistsError):capture_passive(self.path,'01.00.1100',transport_factory=factory)
        with self.assertRaises(ValueError):capture_passive(self.path,'01.00.0200',transport_factory=factory)
        factory.assert_not_called();self.assertEqual(self.path.read_bytes(),b'original')
    def test_cancel_before_open_creates_no_file_or_device(self):
        factory=Mock()
        with self.assertRaises(InterruptedError):capture_passive(self.path,'01.00.1100',cancelled=lambda:True,transport_factory=factory)
        factory.assert_not_called();self.assertFalse(self.path.exists())
    def test_open_failure_is_recorded_without_guessing_identity(self):
        factory=Mock(side_effect=OSError('Driver access unavailable'))
        r=capture_passive(self.path,'01.00.1100',transport_factory=factory)
        self.assertEqual(r['state'],'error');self.assertEqual(r['usb'],{})
        self.assertEqual(r['bulk_in_attempts'],0);self.assertFalse(r['reception_completed'])
    def test_reception_close_failure_cannot_be_success(self):
        self.receiver=Receiver(self.clock,[]);self.receiver.close=Mock(side_effect=OSError('release failed'))
        r=capture_passive(self.path,'01.00.1100',transport_factory=lambda:self.receiver,clock=self.clock,progress=self.progress.append)
        self.assertEqual(r['state'],'error');self.assertFalse(r['reception_completed'])
        self.assertLess(self.progress[-1]['percent'],100)
    def test_disk_failure_cannot_finish_at_100_and_releases_usb(self):
        self.receiver=Receiver(self.clock,[b'bytes'])
        with patch('pathlib.Path.open') as output:
            output.return_value.__enter__.return_value.write.side_effect=OSError('disk full')
            r=capture_passive(self.path,'01.00.1100',transport_factory=lambda:self.receiver,clock=self.clock,progress=self.progress.append)
        self.assertEqual(r['state'],'error');self.assertFalse(r['reception_completed'])
        self.assertIn('disk full',r['error']);self.assertTrue(self.receiver.closed)
        self.assertLess(self.progress[-1]['percent'],100)
    def test_binary_sensor_conversion_requires_valid_crc_and_keeps_unknown_identity(self):
        frame=packet(0x12,0x2a,900,0x24,0x26,sample(),flags=0)
        result=decode_bytes(frame[:8]+frame[8:])
        self.assertEqual(result['perception_records']['counts'],{'records':1,'decoded':1})
        self.assertEqual(result['perception_records']['observations_preview'][0]['serial_from_payload'],'ABCTAC10071234')
        self.assertEqual(result['identity']['state'],'desconocido')
        damaged=bytearray(frame);damaged[-1]^=1
        self.assertEqual(decode_bytes(damaged)['perception_records']['counts'],{})

if __name__=='__main__':unittest.main()
