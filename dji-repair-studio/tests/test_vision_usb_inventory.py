import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from zipfile import ZipFile
from vision_targets import require_active_profile
from vision_usb_inventory import collect_usb_profile, product_family, validate_inventory


def node(instance='USB\\VID_2CA3&PID_0020\\SYNTHETIC', product='DJI Air 3-SYNTHETIC'):
    return {'instance_id': instance, 'friendly_name': 'Synthetic device', 'status': 'OK',
            'bus_product': product, 'parent': 'SYNTHETIC_PARENT', 'service': 'usbccgp',
            'hardware_ids': ['USB\\VID_2CA3&PID_0020'], 'problem_code': 0}


def inventory(*rows):
    return {'schema': 1, 'source': 'windows_pnp_present', 'devices': list(rows)}


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
    def tearDown(self):
        self.temp.cleanup()
    def capture(self, raw, **kwargs):
        return collect_usb_profile(self.root/'profile.zip', 'Air 3', '01.00.1600',
                                   collector=lambda **unused: raw, **kwargs)
    def test_air3_does_not_authorize_mini4_requests(self):
        with self.assertRaisesRegex(ValueError, 'Air 3'):
            require_active_profile('Air 3')
    def test_product_matching_keeps_air3s_and_other_models_separate(self):
        for text in ('Air 3', 'DJI Air3-SYNTHETIC', 'air 3-SYNTHETIC'):
            self.assertEqual(product_family(text), 'Air 3')
        for text in ('Air 3S', 'DJI Air 3S-SYNTHETIC', 'Air 3 S', 'Mavic 3', 'Mini 4 Pro'):
            self.assertNotEqual(product_family(text), 'Air 3')
    def test_matching_inventory_is_saved_without_claiming_endpoints_or_calibration(self):
        events=[]; result=self.capture(inventory(node()), progress=events.append)
        self.assertEqual(result['state'], 'desconocido')
        self.assertTrue(result['model_descriptor_matches'])
        self.assertFalse(result['usb_endpoints_verified'])
        self.assertFalse(result['calibration_available'])
        self.assertEqual(result['service_commands_sent'], 0)
        self.assertFalse(result['native_sdk_loaded'])
        self.assertEqual(events[-1]['percent'], 100)
        self.assertIn('no es calibración', events[-1]['label'])
        with ZipFile(self.root/'profile.zip') as z:
            self.assertEqual(z.namelist(), ['DJI-REPAIR-informe.json'])
            data=json.loads(z.read('DJI-REPAIR-informe.json'))
            self.assertEqual(data['firmware_declarado'], '01.00.1600')
            self.assertEqual(data['modelo_declarado'], 'Air 3')
    def test_interface_name_does_not_replace_missing_physical_parent(self):
        child=node('USB\\VID_2CA3&PID_0020&MI_04\\SYNTHETIC')
        result=self.capture(inventory(child))
        self.assertFalse(result['model_descriptor_matches'])
    def test_ambiguous_parents_are_not_selected_by_list_order(self):
        result=self.capture(inventory(node(),node('USB\\VID_2CA3&PID_0020\\SYNTHETIC2')))
        self.assertFalse(result['model_descriptor_matches'])
    def test_another_drone_is_not_marked_as_air3(self):
        result=self.capture(inventory(node(product='Mini 4 Pro-SYNTHETIC')))
        self.assertFalse(result['model_descriptor_matches'])
    def test_malformed_or_oversized_inventory_is_refused(self):
        cases=[inventory(*[node()]*65), inventory(node('USB\\VID_1234&PID_0020\\SYNTHETIC')),
               inventory(node(),node()), inventory({**node(),'problem_code':True}),
               inventory({**node(),'hardware_ids':['x'*1025]})]
        for raw in cases:
            with self.subTest(raw_count=len(raw['devices'])), self.assertRaises(ValueError):
                validate_inventory(raw)
    def test_failure_and_cancellation_keep_zip_without_fake_success(self):
        result=self.capture(inventory(node()), cancelled=lambda: True)
        self.assertEqual(result['state'], 'desconocido')
        self.assertNotIn('inventory_state', result)
        self.assertTrue((self.root/'profile.zip').is_file())
    def test_windows_query_errors_are_saved_for_review(self):
        def fail(**unused):raise OSError('synthetic PnP failure')
        result=collect_usb_profile(self.root/'error.zip','Air 3','01.00.1600',collector=fail)
        self.assertEqual(result['state'],'error')
        self.assertIn('synthetic PnP failure',result['detail'])
    def test_existing_files_and_bad_firmware_are_refused_before_query(self):
        p=self.root/'existing.zip';p.write_bytes(b'keep');call=Mock()
        with self.assertRaises(ValueError):
            collect_usb_profile(p,'Air 3','01.00.1600',collector=call)
        with self.assertRaises(ValueError):
            collect_usb_profile(self.root/'bad.zip','Air 3','unknown',collector=call)
        call.assert_not_called();self.assertEqual(p.read_bytes(),b'keep')


if __name__=='__main__':unittest.main()
