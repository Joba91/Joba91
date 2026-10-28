"""Cross-package a self-contained Windows x64 executable from verified Windows assets.
Run with CPython 3.13. Does not execute Windows code during packaging.
"""
import hashlib,importlib.util,io,json,marshal,struct,zlib,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/"build-tools"))
import pefile
from pe_packaging import PE,embed_manifest,set_checksum,validate_manifest
from zipfile import ZipFile,ZIP_DEFLATED
ROOT=Path(__file__).parent
RUNTIME=ROOT/'runtime';VENDOR=ROOT/'vendor';SRC=ROOT/'src'
MAGIC=b'MEI\014\013\012\013\016'

def code(path,name):
    return marshal.dumps(compile(path.read_text(encoding='utf-8-sig'),name,'exec',dont_inherit=True))

# Bootstrap must be loadable before the PYZ importer. Include complete stdlib
# bytecode in the base zip (excluding test/dev tools and third-party packages).
stdlib_count=0
base=io.BytesIO()
with ZipFile(base,'w',ZIP_DEFLATED) as z:
    for path in sorted((RUNTIME/'Lib').rglob('*.py')):
        rel=path.relative_to(RUNTIME/'Lib')
        if any(part in ('test','tests','site-packages','__pycache__','idlelib','turtledemo','ensurepip','venv') for part in rel.parts):continue
        data=importlib.util.MAGIC_NUMBER+bytes(12)+code(path,rel.as_posix())
        z.writestr(rel.with_suffix('.pyc').as_posix(),data);stdlib_count+=1
modules={}
for path in sorted(SRC.glob('*.py')):
    if path.name=='launch.py':continue
    modules[path.stem]=(0,code(path,path.name))
for package in ('serial','usb'):
    for path in sorted((VENDOR/package).rglob('*.py')):
        rel=path.relative_to(VENDOR)
        name='.'.join(rel.with_suffix('').parts)
        if path.stem=='__init__':name=name.removesuffix('.__init__');kind=1
        else:kind=0
        modules[name]=(kind,code(path,rel.as_posix()))
pyz=bytearray(b'PYZ\0'+importlib.util.MAGIC_NUMBER+bytes(4));toc=[]
for name,(kind,data) in sorted(modules.items()):
    compressed=zlib.compress(data,9)
    toc.append((name,(kind,len(pyz),len(compressed))));pyz.extend(compressed)
pyz[8:12]=struct.pack('!i',len(pyz));pyz.extend(marshal.dumps(toc))
entries=[]
def add(name,data,typ):
    if typ in (b'b',b'x'):name=name.replace('/',chr(92))
    entries.append((name,data,typ))
add('struct',code(RUNTIME/'Lib/struct.py','struct.py'),b'm')
loader=VENDOR/'PyInstaller/loader'
for name in ('pyimod01_archive','pyimod02_importers','pyimod03_ctypes','pyimod04_pywin32'):
    add(name,code(loader/f'{name}.py',f'{name}.py'),b'm')
add('pyiboot01_bootstrap',code(loader/'pyiboot01_bootstrap.py','pyiboot01_bootstrap.py'),b's')
add('pyi_rth__tkinter',code(VENDOR/'PyInstaller/hooks/rthooks/pyi_rth__tkinter.py','pyi_rth__tkinter.py'),b's')
add('studio_main',code(SRC/'launch.py','launch.py'),b's')
add('PYZ.pyz',bytes(pyz),b'z')
add('base_library.zip',base.getvalue(),b'x')
receiver=SRC/'vision_receiver32.exe'
assert receiver.is_file() and pefile.PE(str(receiver),fast_load=True).FILE_HEADER.Machine==0x14c
add('vision_receiver32.exe',receiver.read_bytes(),b'x')
# Flat native extension/library layout expected by the frozen Python loader.
native={}
legacy=SRC/'native/libusb0.dll'
assert hashlib.sha256(legacy.read_bytes()).hexdigest()=='0cd18719d5701e9cc642fc93a83f13830931d6f29f664fedbdf212bcb7c349bd'
assert pefile.PE(str(legacy)).FILE_HEADER.Machine==0x8664
for folder in (RUNTIME,RUNTIME/'DLLs',RUNTIME/'Library/bin',VENDOR/'libusb_package',SRC/'native'):
    for path in sorted(folder.glob('*')):
        if path.suffix.lower() not in ('.dll','.pyd'):continue
        if path.stem.startswith(('_test','_ctypes_test','xxlimited','xxsubtype')):continue
        name=path.name
        if name.lower() in native:
            if native[name.lower()].read_bytes()!=path.read_bytes():
                a=pefile.PE(str(native[name.lower()]));b=pefile.PE(str(path))
                va=a.VS_FIXEDFILEINFO[0];vb=b.VS_FIXEDFILEINFO[0]
                assert (va.FileVersionMS,va.FileVersionLS)==(vb.FileVersionMS,vb.FileVersionLS),f'Native version collision: {name}'
                assert {e.name for e in a.DIRECTORY_ENTRY_EXPORT.symbols}=={e.name for e in b.DIRECTORY_ENTRY_EXPORT.symbols},f'Native export collision: {name}'
                print('Duplicado de misma version/API; se conserva la copia del runtime Python:',name)
        else:native[name.lower()]=path
for name,path in sorted(native.items()):add(path.name,path.read_bytes(),b'b')
for folder,target in [(RUNTIME/'Library/lib/tcl8.6','_tcl_data'),(RUNTIME/'Library/lib/tk8.6','_tk_data'),(RUNTIME/'Library/lib/tcl8','tcl8')]:
    for path in sorted(folder.rglob('*')):
        if path.is_file():add(target+'/'+path.relative_to(folder).as_posix(),path.read_bytes(),b'x')
for path in sorted((ROOT/'licenses').rglob('*')):
    if path.is_file():add('licenses/'+path.relative_to(ROOT/'licenses').as_posix(),path.read_bytes(),b'x')
for package in VENDOR.glob('*.dist-info'):
    for path in package.rglob('*'):
        if path.is_file() and any(x in path.name.lower() for x in ('license','copying','copyright')):
            add('licenses/'+package.name+'/'+path.relative_to(package).as_posix(),path.read_bytes(),b'x')
copying=VENDOR/'PyInstaller/COPYING.txt'
if copying.exists():add('licenses/PyInstaller/COPYING.txt',copying.read_bytes(),b'x')
# No original DJI executable or runtime is read by this builder.
boot=(VENDOR/'PyInstaller/bootloader/Windows-64bit-intel/runw.exe').read_bytes()
boot=embed_manifest(boot,(ROOT/'windows.manifest').read_bytes())
body=bytearray();table=bytearray();manifest=[]
for name,data,typ in entries:
    offset=len(body)
    compressed=data if typ==b'z' else zlib.compress(data,9)
    flag=0 if typ==b'z' else 1
    body.extend(compressed)
    n=name.encode()+b'\0';size=(18+len(n)+15)//16*16
    table.extend(struct.pack('!iIIIBc',size,offset,len(compressed),len(data),flag,typ)+n+bytes(size-18-len(n)))
    manifest.append({'name':name,'type':typ.decode(),'size':len(data),'sha256':hashlib.sha256(data).hexdigest()})
offset=len(body);body.extend(table)
body.extend(struct.pack('!8sIIII64s',MAGIC,len(body)+88,offset,len(table),313,b'python313.dll'.ljust(64,b'\0')))
out=ROOT/'DJI REPAIR Studio 1.6.0.exe';out.write_bytes(set_checksum(boot+body))
# Read the finished archive back and validate all members and code objects.
b=out.read_bytes();at=b.rfind(MAGIC);_,ln,to,tl,ver,lib=struct.unpack('!8sIIII64s',b[at:]);start=at+88-ln
prefix=bytearray(b[:start]);struct.pack_into("<I",prefix,PE(boot).opt+64,0)
assert bytes(prefix)==boot
validate_manifest(PE(b).manifest())
pos=start+to;seen=[]
while pos<start+to+tl:
    size,off,clen,ulen,flag,typ=struct.unpack_from('!iIIIBc',b,pos)
    name=b[pos+18:pos+size].rstrip(b'\0').decode();data=b[start+off:start+off+clen]
    if flag:data=zlib.decompress(data)
    assert len(data)==ulen
    record=manifest[len(seen)];assert name==record['name'] and hashlib.sha256(data).hexdigest()==record['sha256']
    if typ in (b's',b'm'):marshal.loads(data)
    seen.append(name);pos+=size
assert len(seen)==len(entries) and pos==start+to+tl
assert 'python313.dll' in seen and '_tkinter.pyd' in seen and 'libusb-1.0.dll' in seen and 'libusb0.dll' in seen
assert '_tcl_data'+chr(92)+'init.tcl' in seen and '_tk_data'+chr(92)+'tk.tcl' in seen
(ROOT/'bundle-manifest.json').write_text(json.dumps({'stdlib_modules':stdlib_count,'pyz_modules':len(modules),'entries':manifest,'exe_sha256':hashlib.sha256(b).hexdigest(),'common_controls_manifest':'6.0.0.0'},indent=2))
print('EXE independiente:',out.name, len(b),'bytes')
print('Contenido verificado:',len(seen),'archivos;',stdlib_count,'modulos stdlib;',len(modules),'modulos de aplicacion y dependencias.')
print('Ningun archivo depende de la instalacion DJI REPAIR anterior.')
