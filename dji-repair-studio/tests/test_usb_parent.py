"""Native metadata fixtures only: no USB requests or real identifiers."""
import ctypes
import struct
import unittest
from unittest.mock import Mock,patch
from vision_usb_legacy import ALIAS_PREFIX
from vision_usb_parent import (read_alias_instance,read_parent_product,
    parent_product_for_device,GUID,DEVPROPKEY,BUS_PRODUCT_KEY)
from test_legacy_interfaces import Kernel,device

CHILD=r'USB\VID_2CA3&PID_0020&MI_04\7&SYNTHETIC&0&0004'
PARENT=r'USB\VID_2CA3&PID_0020\SYNTHETIC'
PRODUCT='Mini 4 Pro-SYNTHETIC'

class ConfigManager:
    def __init__(self,parent=PARENT,product=PRODUCT):
        self.parent=parent;self.raw=(product+'\0').encode('utf-16-le');self.kind=0x12
        self.CM_Locate_DevNodeW=Mock(side_effect=self.locate)
        self.CM_Get_Parent=Mock(side_effect=self.get_parent)
        self.CM_Get_Device_IDW=Mock(side_effect=self.identifier)
        self.CM_Get_DevNode_PropertyW=Mock(side_effect=self.property)
    def locate(self,out,instance,flags):
        assert instance==CHILD and flags==0
        ctypes.cast(out,ctypes.POINTER(ctypes.c_uint32))[0]=42;return 0
    def get_parent(self,out,child,flags):
        assert child==42 and flags==0
        ctypes.cast(out,ctypes.POINTER(ctypes.c_uint32))[0]=43;return 0
    def identifier(self,node,out,capacity,flags):
        assert node==43 and capacity==512 and flags==0
        out.value=self.parent;return 0
    def property(self,node,key,kind,out,size,flags):
        assert node==43 and flags==0
        assert ctypes.string_at(key,20)==ctypes.string_at(ctypes.byref(BUS_PRODUCT_KEY),20)
        assert ctypes.cast(size,ctypes.POINTER(ctypes.c_uint32))[0]==8192
        ctypes.cast(kind,ctypes.POINTER(ctypes.c_uint32))[0]=self.kind
        ctypes.cast(size,ctypes.POINTER(ctypes.c_uint32))[0]=len(self.raw)
        ctypes.memmove(out,self.raw,min(8192,len(self.raw)));return 0

class ParentMetadataTests(unittest.TestCase):
    def test_native_property_key_layout_matches_windows_sdk(self):
        self.assertEqual(ctypes.sizeof(GUID),16);self.assertEqual(ctypes.sizeof(DEVPROPKEY),20)
        self.assertEqual(ctypes.string_at(ctypes.byref(BUS_PRODUCT_KEY),20),
            bytes.fromhex('7e940b54408bbc45a8a26a0b894cbda204000000'))
    def test_alias_ioctl_returns_the_exact_selected_child_and_closes(self):
        raw=('\\REGISTRY\\MACHINE\\SYSTEM\\ControlSet001\\Enum\\'+CHILD+'\0').encode('ascii')
        kernel=Kernel(raw)
        self.assertEqual(read_alias_instance(ALIAS_PREFIX+'0006',kernel),CHILD)
        kernel.CreateFileW.assert_called_once_with(ALIAS_PREFIX+'0006',0,0,None,3,0,None)
        args=kernel.DeviceIoControl.call_args.args
        self.assertEqual(args[1],0x2223fc);self.assertEqual(args[3],24)
        self.assertEqual(ctypes.string_at(args[2],24),struct.pack('<II16x',1000,0))
        self.assertEqual(args[5],8192);self.assertIsNone(args[-1])
        kernel.CloseHandle.assert_called_once_with(123)
    def test_current_control_set_device_parameters_suffix(self):
        raw=('\\REGISTRY\\MACHINE\\SYSTEM\\CurrentControlSet\\Enum\\'+CHILD+'\\Device Parameters\0').encode('ascii')
        self.assertEqual(read_alias_instance(ALIAS_PREFIX+'0006',Kernel(raw)),CHILD)
    def test_wrong_child_registry_path_or_incomplete_name_is_rejected(self):
        prefix='\\REGISTRY\\MACHINE\\SYSTEM\\ControlSet001\\Enum\\'
        for value in (prefix+CHILD.replace('MI_04','MI_03')+'\0',prefix+CHILD.replace('2CA3','0000')+'\0',
                prefix+CHILD, prefix+CHILD+'\0junk\0','C:\\file\0',prefix+CHILD+'\\extra\0'):
            with self.subTest(value=value):
                kernel=Kernel(value.encode('ascii'))
                with self.assertRaises(ValueError):read_alias_instance(ALIAS_PREFIX+'0006',kernel)
                kernel.CloseHandle.assert_called_once()
    def test_invalid_or_failed_ioctl_does_not_accept_metadata(self):
        for raw in (False,b'\0',b'x'*8193,b'\xff\0'):
            kernel=Kernel(raw)
            with self.assertRaises((OSError,ValueError,UnicodeError)):read_alias_instance(ALIAS_PREFIX+'0006',kernel)
            kernel.CloseHandle.assert_called_once()
    def test_invalid_alias_cannot_open_a_handle(self):
        kernel=Kernel(b'')
        with self.assertRaises(ValueError):read_alias_instance('C:\\file',kernel)
        kernel.CreateFileW.assert_not_called()
    def test_failed_open_and_close_are_reported(self):
        kernel=Kernel(b'');kernel.CreateFileW.return_value=ctypes.c_void_p(-1).value
        with self.assertRaises(OSError):read_alias_instance(ALIAS_PREFIX+'0006',kernel)
        kernel.DeviceIoControl.assert_not_called();kernel.CloseHandle.assert_not_called()
        kernel=Kernel(('\\REGISTRY\\MACHINE\\SYSTEM\\ControlSet001\\Enum\\'+CHILD+'\0').encode())
        kernel.CloseHandle.return_value=0
        with self.assertRaises(OSError):read_alias_instance(ALIAS_PREFIX+'0006',kernel)
    def test_parent_binding_and_property_only_with_hashed_instances(self):
        cm=ConfigManager();result=read_parent_product(CHILD,cm)
        self.assertEqual(result['product'],PRODUCT);self.assertTrue(result['metadata_only'])
        self.assertNotIn(CHILD,str(result));self.assertNotIn(PARENT,str(result))
        self.assertEqual(len(result['parent_instance_sha256']),64)
        for name in ('CM_Locate_DevNodeW','CM_Get_Parent','CM_Get_Device_IDW','CM_Get_DevNode_PropertyW'):
            getattr(cm,name).assert_called_once()
    def test_wrong_parent_or_an_interface_parent_is_blocked_before_property(self):
        for parent in (PARENT.replace('0020','0000'),CHILD,r'ROOT\USB\SYNTHETIC'):
            cm=ConfigManager(parent=parent)
            with self.assertRaises(ValueError):read_parent_product(CHILD,cm)
            cm.CM_Get_DevNode_PropertyW.assert_not_called()
    def test_wrong_child_never_locates_or_searches_by_product(self):
        cm=ConfigManager()
        with self.assertRaises(ValueError):read_parent_product(CHILD.replace('MI_04','MI_03'),cm)
        cm.CM_Locate_DevNodeW.assert_not_called()
    def test_each_config_manager_failure_stops_without_ancestor_search(self):
        for name in ('CM_Locate_DevNodeW','CM_Get_Parent','CM_Get_Device_IDW','CM_Get_DevNode_PropertyW'):
            cm=ConfigManager();method=getattr(cm,name);method.side_effect=None;method.return_value=13
            with self.assertRaisesRegex(RuntimeError,'CONFIGRET 0x0000000d'):read_parent_product(CHILD,cm)
    def test_invalid_property_type_length_encoding_or_terminator(self):
        for raw,kind in ((b'\0\0',0x13),(b'x',0x12),(b'\0'*8194,0x12),
                ('name'.encode('utf-16-le'),0x12),('a\0b\0'.encode('utf-16-le'),0x12),
                (b'\0\0',0x12),(b'\x00\xd8\0\0',0x12)):
            cm=ConfigManager();cm.raw=raw;cm.kind=kind
            with self.assertRaises((ValueError,UnicodeError)):read_parent_product(CHILD,cm)
    def test_device_lookup_binds_selected_alias_not_first_result(self):
        with patch('vision_usb_parent.read_alias_instance',return_value=CHILD) as instance,patch('vision_usb_parent.read_parent_product',return_value={'product':PRODUCT}) as parent:
            self.assertEqual(parent_product_for_device(device(6)),{'product':PRODUCT})
        instance.assert_called_once_with(ALIAS_PREFIX+'0006');parent.assert_called_once_with(CHILD)

if __name__=='__main__':unittest.main()
