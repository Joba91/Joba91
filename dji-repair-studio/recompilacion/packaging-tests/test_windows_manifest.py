import hashlib
import json
import struct
import unittest
import zlib
import xml.etree.ElementTree as ET
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'build-tools')]
import pefile
from pe_packaging import embed_manifest,validate_manifest

ORIGINAL=ROOT/'DJI REPAIR Studio.exe'
FIXED=ROOT/'DJI REPAIR Studio 1.0.1.exe'

def payload(blob):
    marker=b'MEI\014\013\012\013\016'
    index=blob.rfind(marker)
    length=struct.unpack_from('!I',blob,index+8)[0]
    return blob[index+88-length:]

class ManifestRegressionTests(unittest.TestCase):
    def test_legacy_usb_library_is_verified_x64_user_library(self):
        path=ROOT/'src/native/libusb0.dll'
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),'0cd18719d5701e9cc642fc93a83f13830931d6f29f664fedbdf212bcb7c349bd')
        pe=pefile.PE(str(path));self.assertEqual(pe.FILE_HEADER.Machine,0x8664)
        exports={e.name for e in pe.DIRECTORY_ENTRY_EXPORT.symbols}
        self.assertTrue({b'usb_init',b'usb_open',b'usb_claim_interface',b'usb_bulk_read',b'usb_close'}<=exports)
    def test_new_single_window_build_retains_startup_fix(self):
        pe=pefile.PE(str(ROOT/'DJI REPAIR Studio 1.6.0.exe'))
        resource=next(e for e in pe.DIRECTORY_ENTRY_RESOURCE.entries if e.id==24)
        data=resource.directory.entries[0].directory.entries[0].data.struct
        validate_manifest(pe.get_data(data.OffsetToData,data.Size))
        self.assertEqual(pe.OPTIONAL_HEADER.CheckSum,pe.generate_checksum())
    def test_original_requires_ordinal_380_but_has_no_manifest(self):
        pe=pefile.PE(str(ORIGINAL))
        imported=next(x for x in pe.DIRECTORY_ENTRY_IMPORT if x.dll.lower()==b'comctl32.dll')
        self.assertIn(380,[x.ordinal for x in imported.imports])
        self.assertEqual(pe.OPTIONAL_HEADER.DATA_DIRECTORY[2].VirtualAddress,0)
    def test_embedded_resource_24_1_0_selects_v6_without_elevation(self):
        pe=pefile.PE(str(FIXED))
        resource=next(e for e in pe.DIRECTORY_ENTRY_RESOURCE.entries if e.id==24)
        name=next(e for e in resource.directory.entries if e.id==1)
        language=next(e for e in name.directory.entries if e.id==0)
        data=language.data.struct
        xml=pe.get_data(data.OffsetToData,data.Size)
        doc=ET.fromstring(xml)
        identity=doc.find('.//{urn:schemas-microsoft-com:asm.v1}assemblyIdentity')
        self.assertEqual(identity.get('name'),'Microsoft.Windows.Common-Controls')
        self.assertEqual(identity.get('version'),'6.0.0.0')
        level=doc.find('.//{urn:schemas-microsoft-com:asm.v3}requestedExecutionLevel')
        self.assertEqual(level.get('level'),'asInvoker')
        validate_manifest(xml)
    def test_packaged_application_is_byte_for_byte_unchanged(self):
        self.assertEqual(hashlib.sha256(payload(ORIGINAL.read_bytes())).digest(),hashlib.sha256(payload(FIXED.read_bytes())).digest())
    def test_native_imports_unchanged(self):
        def imports(path):
            pe=pefile.PE(str(path))
            return [(entry.dll,[(i.name,i.ordinal) for i in entry.imports]) for entry in pe.DIRECTORY_ENTRY_IMPORT]
        self.assertEqual(imports(ORIGINAL),imports(FIXED))
    def test_finished_checksum_matches_independent_pe_parser(self):
        pe=pefile.PE(str(FIXED))
        self.assertEqual(pe.OPTIONAL_HEADER.CheckSum,pe.generate_checksum())
    def test_v5_manifest_refused(self):
        xml=(ROOT/'windows.manifest').read_bytes().replace(b'version="6.0.0.0"',b'version="5.0.0.0"')
        with self.assertRaises(ValueError):validate_manifest(xml)
    def test_existing_resources_cannot_be_overwritten(self):
        with self.assertRaisesRegex(ValueError,'Resources already exist'):
            embed_manifest(FIXED.read_bytes(),(ROOT/'windows.manifest').read_bytes())

    def test_x86_receiver_preserves_imports_and_embeds_v6_manifest(self):
        source=ROOT/'build-tools/receiver32/pyinstaller/PyInstaller/bootloader/Windows-32bit-intel/run.exe'
        pe=pefile.PE(str(ROOT/'src/vision_receiver32.exe'))
        original=pefile.PE(str(source))
        self.assertEqual(pe.FILE_HEADER.Machine,0x14c)
        self.assertEqual(pe.OPTIONAL_HEADER.Magic,0x10b)
        self.assertEqual(pe.OPTIONAL_HEADER.CheckSum,pe.generate_checksum())
        def imports(image):
            return [(entry.dll,[(i.name,i.ordinal) for i in entry.imports]) for entry in image.DIRECTORY_ENTRY_IMPORT]
        self.assertEqual(imports(original),imports(pe))
        resource=next(e for e in pe.DIRECTORY_ENTRY_RESOURCE.entries if e.id==24)
        data=resource.directory.entries[0].directory.entries[0].data.struct
        validate_manifest(pe.get_data(data.OffsetToData,data.Size))

    def test_x86_receiver_archive_members_match_build_record(self):
        blob=(ROOT/'src/vision_receiver32.exe').read_bytes()
        at=blob.rfind(b'MEI\014\013\012\013\016')
        _,length,offset,size,abi,library=struct.unpack('!8sIIII64s',blob[at:])
        self.assertEqual(abi,313)
        self.assertEqual(library.rstrip(b'\0'),b'python313.dll')
        start=at+88-length;pos=start+offset;seen={}
        while pos<start+offset+size:
            entry_length,location,packed,unpacked,flag,kind=struct.unpack_from('!iIIIBc',blob,pos)
            self.assertGreaterEqual(entry_length,18)
            name=blob[pos+18:pos+entry_length].split(b'\0',1)[0].decode()
            data=blob[start+location:start+location+packed]
            if flag:data=zlib.decompress(data)
            self.assertEqual(len(data),unpacked)
            self.assertNotIn(name,seen)
            seen[name]={'name':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
            pos+=entry_length
        expected=json.loads((ROOT/'receiver32-build.json').read_text())['members']
        self.assertEqual(seen,{row['name']:row for row in expected})
        self.assertIn('receiver_main',seen)
        self.assertIn('_ctypes.pyd',seen)

if __name__=='__main__':unittest.main()
