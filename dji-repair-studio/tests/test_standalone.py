import io
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import Mock, patch
from studio_transport import UsbTransport
from comm_og_service_tool import do_module_info_request, PRODUCT_CODE
from studio_service import packet

class StandaloneTests(unittest.TestCase):
    def test_usb_reads_packet_size_even_when_serial_api_requests_one_byte(self):
        transport=object.__new__(UsbTransport)
        transport.ep_in=Mock(wMaxPacketSize=512)
        transport.timeout=200
        transport.core=SimpleNamespace(USBTimeoutError=TimeoutError)
        transport.ep_in.read.return_value=b'data'
        self.assertEqual(transport.read(1),b'data')
        transport.ep_in.read.assert_called_once_with(512,timeout=200)
    def test_usb_timeout_is_idle_but_other_errors_propagate(self):
        transport=object.__new__(UsbTransport)
        transport.ep_in=Mock(wMaxPacketSize=64);transport.timeout=100
        transport.core=SimpleNamespace(USBTimeoutError=TimeoutError)
        transport.ep_in.read.side_effect=TimeoutError
        self.assertEqual(transport.read(),b'')
        transport.ep_in.read.side_effect=OSError('disconnect')
        with self.assertRaises(OSError):transport.read()
    def test_legacy_module_query_with_new_serial_compatible_transport(self):
        class Transport:
            name=port='BULK'
            pending=b''
            closed=False
            @property
            def in_waiting(self):return len(self.pending)
            def write(self,req):
                payload=b'\0\0'+b'TEST-HW'.ljust(16,b'\0')+bytes(4)+(0x04000007).to_bytes(4,'little')+bytes(5)
                self.pending=packet(req[5],req[4],int.from_bytes(req[6:8],'little'),0,1,payload,flags=128)
            def read(self,size):data=self.pending;self.pending=b'';return data
            def reset_input_buffer(self):pass
            def close(self):self.closed=True
        transport=Transport()
        po=SimpleNamespace(module='all',bulk=True,port='',baudrate=9600,timeout=200,dry_test=False,verbose=0,retry=1,product=PRODUCT_CODE.WM260)
        with patch('comm_og_service_tool.open_serial_port',return_value=transport),redirect_stdout(io.StringIO()):
            result=do_module_info_request(po)
        self.assertEqual(len(result),4);self.assertTrue(transport.closed)

if __name__=='__main__':unittest.main()
