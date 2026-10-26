import ctypes
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from vision_usb_legacy import (ALIAS_PREFIX,GET_DEVICE_PROPERTY,HARDWARE_ID_REQUEST,
    device_alias,read_alias_hardware_ids,select_mi04,LegacyInterfaceError)

def device(index):
    name=(ALIAS_PREFIX+f'{index:04d}--0x2ca3-0x0020').encode()+b'\0'
    return SimpleNamespace(_ctx=SimpleNamespace(dev=SimpleNamespace(filename=name)))

class Kernel:
    def __init__(self,raw):
        self.raw=raw;self.CreateFileW=Mock(return_value=123)
        self.DeviceIoControl=Mock(side_effect=self.query);self.CloseHandle=Mock(return_value=1)
    def query(self,handle,code,request,request_size,output,output_size,actual,overlapped):
        if self.raw is False:return 0
        ctypes.memmove(output,self.raw,min(len(self.raw),output_size))
        ctypes.cast(actual,ctypes.POINTER(ctypes.c_uint32))[0]=len(self.raw)
        return 1

class NativeMetadataTests(unittest.TestCase):
    def test_exact_read_only_ioctl_abi_and_handle_close(self):
        hardware=['USB\\VID_2CA3&PID_0020&REV_0504&MI_04','USB\\VID_2CA3&PID_0020&MI_04']
        raw=('\0'.join(hardware)+'\0\0').encode('utf-16-le');kernel=Kernel(raw)
        alias=ALIAS_PREFIX+'0006'
        self.assertEqual(read_alias_hardware_ids(alias,kernel),hardware)
        kernel.CreateFileW.assert_called_once_with(alias,0,0,None,3,0,None)
        call=kernel.DeviceIoControl.call_args.args
        self.assertEqual(call[1],0x222400);self.assertEqual(call[3],24)
        self.assertEqual(ctypes.string_at(call[2],24),struct.pack('<II16x',1000,1))
        self.assertEqual(call[5],8192);self.assertIsNone(call[-1])
        kernel.CloseHandle.assert_called_once_with(123)
    def test_invalid_path_never_opens_a_handle(self):
        kernel=Kernel(b'')
        for path in ('C:\\file',ALIAS_PREFIX+'0000',ALIAS_PREFIX+'0256',ALIAS_PREFIX+'0006/other',ALIAS_PREFIX+'６０００'):
            with self.assertRaises(ValueError):read_alias_hardware_ids(path,kernel)
        kernel.CreateFileW.assert_not_called()
    def test_open_failure_does_not_issue_ioctl_or_close_invalid_handle(self):
        kernel=Kernel(b'');kernel.CreateFileW.return_value=ctypes.c_void_p(-1).value
        with self.assertRaises(OSError):read_alias_hardware_ids(ALIAS_PREFIX+'0001',kernel)
        kernel.DeviceIoControl.assert_not_called();kernel.CloseHandle.assert_not_called()
    def test_ioctl_failure_closes_handle(self):
        kernel=Kernel(False)
        with self.assertRaises(OSError):read_alias_hardware_ids(ALIAS_PREFIX+'0001',kernel)
        kernel.CloseHandle.assert_called_once_with(123)
    def test_truncated_unterminated_and_oversized_metadata_rejected(self):
        for raw in (b'\0',b'\0\0',b'A\0B\0',b'\0'*8194,b'\x00\xd8\x00\x00\x00\x00'):
            kernel=Kernel(raw)
            with self.assertRaises((ValueError,UnicodeError)):
                read_alias_hardware_ids(ALIAS_PREFIX+'0001',kernel)
            kernel.CloseHandle.assert_called_once_with(123)
    def test_close_failure_is_not_success(self):
        kernel=Kernel('USB\\VID_2CA3&PID_0020&MI_04\0\0'.encode('utf-16-le'))
        kernel.CloseHandle.return_value=0
        with self.assertRaises(OSError):read_alias_hardware_ids(ALIAS_PREFIX+'0001',kernel)
    def test_pinned_pyusb_signed_filename_array_is_supported(self):
        source=(ALIAS_PREFIX+'0012--0x2ca3-0x0020').encode()+b'\0'
        field=(ctypes.c_int8*len(source)).from_buffer_copy(source)
        dev=SimpleNamespace(_ctx=SimpleNamespace(dev=SimpleNamespace(filename=field)))
        self.assertEqual(device_alias(dev),ALIAS_PREFIX+'0012')
    def test_raw_alias_must_belong_to_expected_vid_pid(self):
        for raw in ((ALIAS_PREFIX+'0001--0x0000-0x0020').encode(),b'other',None):
            dev=SimpleNamespace(_ctx=SimpleNamespace(dev=SimpleNamespace(filename=raw)))
            with self.assertRaises((ValueError,TypeError)):device_alias(dev)

class AliasSelectionTests(unittest.TestCase):
    def test_six_interfaces_are_not_six_drones_and_mi04_need_not_be_first(self):
        devices=[device(i) for i in range(1,7)]
        mapping={1:2,2:3,3:5,4:6,5:7,6:4}
        probe=Mock(side_effect=lambda path:[f'USB\\VID_2CA3&PID_0020&MI_{mapping[int(path[-4:])]:02X}'])
        selected,evidence=select_mi04(devices,probe)
        self.assertIs(selected,devices[-1]);self.assertEqual(evidence['selected_alias_index'],6)
        self.assertEqual(evidence['enumerated_aliases'],6);self.assertEqual(probe.call_count,6)
    def test_two_mi04_matches_are_ambiguous(self):
        with self.assertRaises(LegacyInterfaceError) as error:
            select_mi04([device(1),device(2)],lambda path:['USB\\VID_2CA3&PID_0020&MI_04'])
        self.assertEqual(len(error.exception.observations),2)
    def test_single_entry_also_requires_proven_mi04(self):
        for hardware in ('USB\\VID_2CA3&PID_0020&MI_03','USB\\VID_2CA3&PID_0020'):
            with self.assertRaises(LegacyInterfaceError):select_mi04([device(1)],lambda path:[hardware])
    def test_missing_property_on_another_alias_prevents_guessing(self):
        def probe(path):
            if path.endswith('0002'):raise OSError('metadata denied')
            return ['USB\\VID_2CA3&PID_0020&MI_04']
        with self.assertRaises(LegacyInterfaceError) as error:select_mi04([device(1),device(2)],probe)
        self.assertIn('error',error.exception.observations[1])
    def test_revision_and_case_variants_select_correctly(self):
        dev=device(1)
        selected,evidence=select_mi04([dev],lambda path:['usb\\vid_2ca3&pid_0020&rev_0504&mi_04','USB\\VID_2CA3&PID_0020&MI_04'])
        self.assertIs(selected,dev);self.assertEqual(evidence['selected_mi'],4)
    def test_conflicting_or_wrong_ids_do_not_prove_mi04(self):
        for ids in (['USB\\VID_2CA3&PID_0000&MI_04'],['USB\\VID_2CA3&PID_0020&MI_04','USB\\VID_0000&PID_0020&MI_04'],['USB\\VID_2CA3&PID_0020&MI_03','USB\\VID_2CA3&PID_0020&MI_04'],[]):
            with self.assertRaises(LegacyInterfaceError):select_mi04([device(1)],lambda path:ids)
    def test_duplicate_aliases_not_counted_as_distinct_devices(self):
        with self.assertRaises(LegacyInterfaceError):
            select_mi04([device(1),device(1)],lambda path:['USB\\VID_2CA3&PID_0020&MI_04'])
    def test_bound_limits_queries(self):
        probe=Mock()
        for devices in ([],[device(i) for i in range(1,34)]):
            with self.assertRaises(LegacyInterfaceError):select_mi04(devices,probe)
        probe.assert_not_called()

if __name__=='__main__':unittest.main()
