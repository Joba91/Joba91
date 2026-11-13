import copy
import json
import tempfile
import unittest
import warnings
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from studio_service import packet
from flip_calibration_analysis import analyze_flip_trial

def synthetic_trial():
    request=packet(10,4,42,4,8,b'\1')
    report={'version':'SYNTHETIC','modelo_declarado':'DJI Flip','firmware_declarado':'01.00.1500',
        'gimbal':{'calibration_probe':{'routine':'JointCoarse','state':'error',
            'packet_audit':[{'direccion':'TX','hex':request.hex()}],
            'usb_evidence':{'read_error':{'type':'USBError','errno':None,'backend_error_code':-5,'winerror':None}}}}}
    raw=packet(4,10,42,4,8,b'\0',flags=128)
    raw+=b''.join(packet(4,10,i,4,0x30,b'\x52\1',flags=0) for i in range(599))
    raw+=b''.join(packet(4,10,i,4,0x30,b'\x64\4',flags=0) for i in range(10))
    return report,raw

class OfflineTrialTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def save(self,report=None,raw=None):
        r,b=synthetic_trial();p=self.root/'trial.zip'
        with ZipFile(p,'w',ZIP_DEFLATED) as z:
            z.writestr('DJI-REPAIR-informe.json',json.dumps(r if report is None else report))
            z.writestr('trial.bin',b if raw is None else raw)
        return p
    def test_repeated_status_and_later_usb_error_remain_visible_without_device_access(self):
        r=analyze_flip_trial(self.save())
        self.assertEqual(r['state'],'timeout_segun_referencia')
        self.assertEqual(r['status_counts'],{'5201':599,'6404':10})
        self.assertEqual(r['last_status_payload'],'6404')
        self.assertEqual(r['source_usb_read_error']['backend_error_code'],-5)
        self.assertTrue(r['historical_only']);self.assertFalse(r['current_device_confirmed'])
        self.assertEqual(r['usb_operations'],0);self.assertEqual(r['device_writes'],0)
        self.assertFalse(r['physical_calibration_validated']);self.assertFalse(r['flip_status_mapping_validated'])
        self.assertFalse(r['finish_6400_observed']);self.assertEqual(r['crc_issues'],0)
    def test_wrong_ack_sequence_sender_and_encryption_do_not_associate_reports(self):
        report,raw=synthetic_trial()
        for ack in (packet(4,10,43,4,8,b'\0',flags=128),packet(3,10,42,4,8,b'\0',flags=128),packet(4,10,42,4,8,b'\0',flags=129)):
            with self.subTest(ack=ack.hex()):
                r=analyze_flip_trial(self.save(report,ack+raw[14:]))
                self.assertEqual(r['correlated_ack_count'],0);self.assertEqual(r['status_counts'],{})
                self.assertIsNone(r['timeout_reference'])
    def test_reports_before_ack_and_ack_shaped_status_frames_are_not_attributed(self):
        report,_=synthetic_trial()
        raw=packet(4,10,1,4,0x30,b'\x64\4',flags=0)+packet(4,10,42,4,8,b'\0',flags=128)
        raw+=packet(4,10,2,4,0x30,b'\x64\4',flags=128)
        r=analyze_flip_trial(self.save(report,raw))
        self.assertEqual(r['status_counts'],{});self.assertIsNone(r['timeout_reference'])
    def test_crc_failure_partial_frame_and_unframed_bytes_are_reported(self):
        report,raw=synthetic_trial()
        for damaged in (raw[:-1],raw+b'noise',raw[:14]+raw[14:-1]+bytes([raw[-1]^1])):
            with self.subTest(size=len(damaged)):
                r=analyze_flip_trial(self.save(report,damaged))
                self.assertEqual(r['state'],'sin_fin_verificado')
                self.assertGreater(r['unframed_bytes'],0)
                self.assertFalse(r['physical_calibration_validated'])
    def test_module_zip_wrong_model_and_malformed_audit_are_refused(self):
        for bad in ({'gimbal':{}},[],{'modelo_declarado':'Mavic 3'},
                    {'modelo_declarado':'DJI Flip','gimbal':{'module_query':{}}},
                    {'modelo_declarado':'DJI Flip','gimbal':{'calibration_probe':{'routine':'JointCoarse','packet_audit':['bad']}}}):
            with self.assertRaises(ValueError):analyze_flip_trial(self.save(bad))
    def test_duplicate_report_and_oversized_bin_are_refused(self):
        p=self.save()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            with ZipFile(p,'a') as z:z.writestr('DJI-REPAIR-informe.json','{}')
        with self.assertRaises(ValueError):analyze_flip_trial(p)
        with self.assertRaises(ValueError):analyze_flip_trial(self.save(raw=bytes(1024**2+1)))
    def test_changed_routine_payload_and_multiple_requests_are_ambiguous(self):
        for change in ('routine','payload','multiple'):
            report,raw=synthetic_trial();q=report['gimbal']['calibration_probe']
            if change=='routine':q['routine']='LinearHall'
            if change=='payload':q['packet_audit'][0]['hex']=packet(10,4,42,4,8,b'\x71').hex()
            if change=='multiple':q['packet_audit'].append(copy.deepcopy(q['packet_audit'][0]))
            with self.assertRaises(ValueError):analyze_flip_trial(self.save(report,raw))
    def test_historical_6400_does_not_validate_physical_calibration(self):
        report,_=synthetic_trial()
        raw=packet(4,10,42,4,8,b'\0',flags=128)+packet(4,10,1,4,0x30,b'\x64\0',flags=0)
        r=analyze_flip_trial(self.save(report,raw))
        self.assertTrue(r['finish_6400_observed']);self.assertFalse(r['physical_calibration_validated'])
        self.assertFalse(r['current_device_confirmed']);self.assertEqual(r['usb_operations'],0)
        conflicting=raw+packet(4,10,2,4,0x30,b'\x64\4',flags=0)
        r=analyze_flip_trial(self.save(report,conflicting))
        self.assertEqual(r['state'],'informes_finales_incompatibles')
        self.assertFalse(r['physical_calibration_validated'])
