"""Build an x86 Python receiver without executing Windows or DJI binaries."""
import hashlib
import importlib.util
import io
import json
import marshal
import struct
import sys
import zlib
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from pe_packaging import PE, embed_manifest, set_checksum

ROOT = Path(__file__).parent
TOOLS = ROOT / 'build-tools/receiver32'
RUNTIME = TOOLS / 'python/tools'
LOADER = TOOLS / 'pyinstaller/PyInstaller/loader'
sys.path.insert(0, str(ROOT / 'build-tools'))
import pefile

def compiled(path, name):
    return marshal.dumps(compile(path.read_text(encoding='utf-8-sig'), name, 'exec', dont_inherit=True))

assert sys.version_info[:2] == (3, 13)
assert pefile.PE(str(RUNTIME / 'python313.dll')).FILE_HEADER.Machine == 0x14c
base = io.BytesIO()
with ZipFile(base, 'w', ZIP_DEFLATED) as z:
    for p in (RUNTIME / 'Lib').rglob('*.py'):
        rel = p.relative_to(RUNTIME / 'Lib')
        if any(x in ('site-packages', '__pycache__', 'test', 'tests', 'idlelib', 'turtledemo', 'venv', 'ensurepip') for x in rel.parts):
            continue
        z.writestr(rel.with_suffix('.pyc').as_posix(), importlib.util.MAGIC_NUMBER + bytes(12) + compiled(p, rel.as_posix()))
module = ROOT / 'src/vision_image_receiver.py'
pyz = bytearray(b'PYZ\0' + importlib.util.MAGIC_NUMBER + bytes(4))
compressed = zlib.compress(compiled(module, module.name), 9)
toc = [('vision_image_receiver', (0, len(pyz), len(compressed)))]
pyz.extend(compressed)
pyz[8:12] = struct.pack('!i', len(pyz))
pyz.extend(marshal.dumps(toc))
entries = []
def add(name, data, kind):
    entries.append((name.replace('/', '\\') if kind in (b'b', b'x') else name, data, kind))
add('struct', compiled(RUNTIME / 'Lib/struct.py', 'struct.py'), b'm')
for name in ('pyimod01_archive', 'pyimod02_importers', 'pyimod03_ctypes', 'pyimod04_pywin32'):
    add(name, compiled(LOADER / (name + '.py'), name + '.py'), b'm')
add('pyiboot01_bootstrap', compiled(LOADER / 'pyiboot01_bootstrap.py', 'pyiboot01_bootstrap.py'), b's')
add('receiver_main', compiled(ROOT / 'receiver32/entry.py', 'receiver_main.py'), b's')
add('PYZ.pyz', bytes(pyz), b'z')
add('base_library.zip', base.getvalue(), b'x')
for folder in (RUNTIME, RUNTIME / 'DLLs'):
    for p in folder.iterdir():
        if p.suffix.lower() not in ('.dll', '.pyd') or p.stem.startswith(('_test', 'xx')):
            continue
        assert pefile.PE(str(p), fast_load=True).FILE_HEADER.Machine == 0x14c
        add(p.name, p.read_bytes(), b'b')
add('licenses/Python-LICENSE.txt', (RUNTIME / 'LICENSE.txt').read_bytes(), b'x')
copying = next((TOOLS / 'pyinstaller').glob('*.dist-info/licenses/COPYING.txt'))
add('licenses/PyInstaller-COPYING.txt', copying.read_bytes(), b'x')
boot = (TOOLS / 'pyinstaller/PyInstaller/bootloader/Windows-32bit-intel/run.exe').read_bytes()
boot = embed_manifest(boot, (ROOT / 'windows.manifest').read_bytes())
body = bytearray()
table = bytearray()
manifest = []
for name, data, kind in entries:
    encoded = data if kind == b'z' else zlib.compress(data, 9)
    offset = len(body)
    body.extend(encoded)
    n = name.encode() + b'\0'
    size = (18 + len(n) + 15) // 16 * 16
    table.extend(struct.pack('!iIIIBc', size, offset, len(encoded), len(data), int(kind != b'z'), kind) + n + bytes(size - 18 - len(n)))
    manifest.append({'name': name, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)})
offset = len(body)
body.extend(table)
body.extend(struct.pack('!8sIIII64s', b'MEI\014\013\012\013\016', len(body) + 88, offset, len(table), 313,
                        b'python313.dll'.ljust(64, b'\0')))
out = ROOT / 'src/vision_receiver32.exe'
out.write_bytes(set_checksum(boot + body))
assert pefile.PE(str(out), fast_load=True).FILE_HEADER.Machine == 0x14c
assert PE(out.read_bytes()).manifest() == (ROOT / 'windows.manifest').read_bytes()
validation = {'machine': 'x86', 'bytes': out.stat().st_size, 'sha256': hashlib.sha256(out.read_bytes()).hexdigest(),
              'source_sha256': hashlib.sha256(module.read_bytes()).hexdigest(),
              'entry_sha256': hashlib.sha256((ROOT / 'receiver32/entry.py').read_bytes()).hexdigest(),
              'assets': json.loads((TOOLS / 'assets.json').read_text()), 'members': manifest,
              'dji_binaries_included': False, 'dji_binaries_executed': False}
(ROOT / 'receiver32-build.json').write_text(json.dumps(validation, indent=2))
print(out.name, out.stat().st_size, validation['sha256'])
