import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile
from vision_support_bundle import write_support_bundle

class SupportBundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'capture.bin'
    def test_empty_capture_still_carries_error_report(self):
        self.path.write_bytes(b'');report={'version':'1.2.5','error':'MI04 could not be selected'}
        target=write_support_bundle(self.path,report)
        with ZipFile(target) as z:
            self.assertEqual(z.testzip(),None);self.assertEqual(z.read('capture.bin'),b'')
            self.assertEqual(json.loads(z.read('DJI-REPAIR-informe.json')),report)
            self.assertEqual(len(z.namelist()),2)
    def test_received_bytes_preserved(self):
        self.path.write_bytes(b'\x55\0\x99')
        with ZipFile(write_support_bundle(self.path,{'detail':'recepción'})) as z:
            self.assertEqual(z.read('capture.bin'),self.path.read_bytes())
            self.assertEqual(json.loads(z.read('DJI-REPAIR-informe.json'))['detail'],'recepción')
    def test_existing_archive_never_overwritten(self):
        self.path.write_bytes(b'');target=self.path.with_suffix('.zip');target.write_bytes(b'original')
        with self.assertRaises(FileExistsError):write_support_bundle(self.path,{})
        self.assertEqual(target.read_bytes(),b'original')
    def test_partial_new_archive_removed_after_write_error(self):
        self.path.write_bytes(b'')
        with patch('vision_support_bundle.ZipFile.writestr',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):write_support_bundle(self.path,{})
        self.assertFalse(self.path.with_suffix('.zip').exists());self.assertTrue(self.path.exists())
    def test_input_and_report_bounds(self):
        with self.assertRaises(ValueError):write_support_bundle(self.path,{})
        self.path.write_bytes(b'a'*(1024**2+1))
        with self.assertRaises(ValueError):write_support_bundle(self.path,{})
        self.path.write_bytes(b'')
        with self.assertRaises(ValueError):write_support_bundle(self.path,{'detail':'a'*(8*1024**2)})

if __name__=='__main__':unittest.main()
