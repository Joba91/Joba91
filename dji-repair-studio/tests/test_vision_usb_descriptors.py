import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as N
from unittest.mock import Mock, patch
from zipfile import ZipFile
import json
from vision_usb_descriptors import collect_descriptors
from vision_usb_inventory import collect_usb_profile, product_family
from test_vision_usb_inventory import node,inventory
from vision_usb_legacy import ALIAS_PREFIX

ROOT='USB\\VID_2CA3&PID_0020\\SYNTHETIC'
CHILD='USB\\VID_2CA3&PID_0020&MI_03\\SYNTHETIC_CHILD'
ROWS=[node(ROOT,product='e3t-SYNTHETIC'),{**node(CHILD,product='BULK Interface'),'parent':ROOT}]

class Interface:
    bInterfaceNumber=3;bAlternateSetting=0;bInterfaceClass=255;bInterfaceSubClass=0x43;bInterfaceProtocol=1;bNumEndpoints=2
    def __init__(self):
        self.endpoints=[N(bEndpointAddress=4,bmAttributes=2,wMaxPacketSize=512,bInterval=0),
                        N(bEndpointAddress=0x85,bmAttributes=2,wMaxPacketSize=512,bInterval=0)]
    def __iter__(self):return iter(self.endpoints)
class Config:
    bConfigurationValue=1;wTotalLength=32;bNumInterfaces=1;bmAttributes=0x80;bMaxPower=250
    def __init__(self):self.interfaces=[Interface()]
    def __iter__(self):return iter(self.interfaces)
class Device:
    idVendor=0x2ca3;idProduct=0x0020;bcdUSB=0x200;bcdDevice=0x504;bDeviceClass=0;bDeviceSubClass=0;bDeviceProtocol=0;bMaxPacketSize0=64;bNumConfigurations=1
    def __init__(self):
        self._ctx=N(dev=N(filename=(ALIAS_PREFIX+'0003--0x2ca3-0x0020').encode()))
        self.cfg=Config();self.cache_reads=0
    def __getitem__(self,index):self.cache_reads+=1;return self.cfg
    # Any attempt to operate the device must fail these tests immediately.
    def __getattr__(self,name):
        if name in ('get_active_configuration','ctrl_transfer','read','write','set_configuration','reset','set_interface_altsetting'):
            raise AssertionError('Forbidden device operation: '+name)
        raise AttributeError(name)

class DescriptorTests(unittest.TestCase):
    def setUp(self):self.device=Device()
    def capture(self,rows=None,**kw):
        args={'enumerate_devices':lambda:[self.device], 'probe':lambda alias:['USB\\VID_2CA3&PID_0020&REV_0504&MI_03','USB\\VID_2CA3&PID_0020&MI_03'],
              'probe_instance':lambda alias:CHILD}
        args.update(kw);return collect_descriptors(ROWS if rows is None else rows,**args)
    def test_cache_reports_observed_addresses_without_any_device_command(self):
        result=self.capture();self.assertEqual(result['state'],'confirmado')
        row=result['aliases'][0];self.assertTrue(row['pnp_instance_matches']);self.assertTrue(row['alias_mi_present_in_cache'])
        eps=row['configurations'][0]['interfaces'][0]['endpoints']
        self.assertEqual([(e['bEndpointAddress'],e['direction'],e['transfer_type']) for e in eps],[(4,'OUT','bulk'),(0x85,'IN','bulk')])
        self.assertFalse(result['transport_validated']);self.assertFalse(result['active_configuration_queried'])
        for key in ('interfaces_claimed','bulk_reads','bulk_writes','service_commands_sent','configuration_writes'):
            self.assertEqual(result[key],0)
    def test_e3t_is_preserved_without_assuming_a_marketing_model(self):
        self.assertIsNone(product_family('e3t-SYNTHETIC'))
        self.assertEqual(self.capture()['state'],'confirmado')
    def test_multiple_physical_parents_stop_before_usb_enumeration(self):
        enum=Mock();raw=self.capture(ROWS+[node('USB\\VID_2CA3&PID_0020\\OTHER')],enumerate_devices=enum)
        enum.assert_not_called();self.assertFalse(raw['standard_descriptor_reads_requested'])
        self.assertEqual(raw['state'],'error')
    def test_cross_parent_interfaces_are_refused_before_enumeration(self):
        rows=copy.deepcopy(ROWS);rows[1]['parent']='USB\\VID_2CA3&PID_0020\\OTHER'
        enum=Mock();self.capture(rows,enumerate_devices=enum);enum.assert_not_called()
    def test_current_alias_node_must_match_the_pnp_session(self):
        result=self.capture(probe_instance=lambda alias:CHILD+'DIFFERENT')
        self.assertEqual(result['state'],'incompleto');self.assertEqual(self.device.cache_reads,0)
    def test_alias_hardware_ids_must_agree(self):
        result=self.capture(probe=lambda alias:['USB\\VID_2CA3&PID_0020&MI_03','USB\\VID_2CA3&PID_0020&MI_04'])
        self.assertEqual(result['state'],'incompleto');self.assertEqual(self.device.cache_reads,0)
    def test_other_vendor_or_missing_mi_cannot_supply_descriptors(self):
        for ids in (['USB\\VID_1234&PID_0020&MI_03'],['USB\\VID_2CA3&PID_0020']):
            result=self.capture(probe=lambda alias:ids)
            self.assertEqual(result['state'],'incompleto')
        self.assertEqual(self.device.cache_reads,0)
    def test_excess_aliases_refused(self):
        result=self.capture(enumerate_devices=lambda:[Device() for _ in range(33)])
        self.assertEqual(result['state'],'error');self.assertEqual(result['aliases'],[])
    def test_duplicate_alias_is_not_silently_counted_twice(self):
        result=self.capture(enumerate_devices=lambda:[self.device,self.device])
        self.assertEqual(result['state'],'incompleto');self.assertFalse(result['aliases'][1]['complete'])
    def test_no_accessible_alias_does_not_mean_sensor_failure(self):
        result=self.capture(enumerate_devices=lambda:[])
        self.assertEqual(result['state'],'error');self.assertFalse(result['calibration_performed'])
    def test_endpoint_count_and_duplicate_address_are_checked(self):
        for change in ('count','duplicate','zero','reserved'):
            with self.subTest(change=change):
                self.device=Device();i=self.device.cfg.interfaces[0]
                if change=='count':i.bNumEndpoints=3
                if change=='duplicate':i.endpoints[1].bEndpointAddress=4
                if change=='zero':i.endpoints[0].bEndpointAddress=0
                if change=='reserved':i.endpoints[0].bEndpointAddress=0x74
                result=self.capture();self.assertEqual(result['state'],'incompleto')
    def test_configuration_and_interface_limits_are_checked(self):
        self.device.bNumConfigurations=5;self.assertEqual(self.capture()['state'],'incompleto')
        self.device=Device();self.device.cfg.bNumInterfaces=33
        self.assertEqual(self.capture()['state'],'incompleto')
    def test_missing_alias_mi_in_cache_is_explicit(self):
        self.device.cfg.interfaces[0].bInterfaceNumber=4
        result=self.capture();self.assertFalse(result['aliases'][0]['alias_mi_present_in_cache'])
        self.assertFalse(result['transport_validated'])
    def test_library_failure_retains_error_and_stage(self):
        stages=[]
        def fail():raise OSError('synthetic descriptor library error')
        result=self.capture(enumerate_devices=fail,stage=lambda name,result:stages.append(name))
        self.assertEqual(result['state'],'error');self.assertIn('synthetic',result['detail'])
        self.assertEqual(stages[-1],'descriptores_finalizados')
    def test_profile_zip_contains_descriptor_observations_with_unknown_usb_operation_count(self):
        descriptor=self.capture()
        raw={**inventory(*ROWS),'descriptor_inventory':descriptor}
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'profile.zip'
            result=collect_usb_profile(path,'Air 3','01.00.1600',collector=lambda **kw:raw)
            self.assertIsNone(result['usb_operations_requested']);self.assertFalse(result['usb_operation_count_known'])
            self.assertEqual(result['service_commands_sent'],0);self.assertFalse(result['calibration_available'])
            self.assertFalse(result['usb_endpoints_verified']);self.assertFalse(result['model_descriptor_matches'])
            with ZipFile(path) as z:
                report=json.loads(z.read('DJI-REPAIR-informe.json'))
                self.assertEqual(report['vision']['usb_profile']['descriptor_inventory'],descriptor)
    def test_pinned_library_is_checked_before_loading(self):
        from vision_usb_descriptors import enumerate_legacy_descriptors
        with patch('vision_usb_descriptors.Path.read_bytes',return_value=b'wrong library'),patch('usb.backend.libusb0.get_backend') as load:
            with self.assertRaisesRegex(ValueError,'verificado'): enumerate_legacy_descriptors()
            load.assert_not_called()

if __name__=='__main__':unittest.main()
