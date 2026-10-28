"""Minimal, bounded PE helpers for adding the executable's Windows manifest.
Only unsigned x86/x64 bootloaders with unused header space and no existing resources
are accepted. Application code and existing section bytes are left intact.
"""
import struct
import xml.etree.ElementTree as ET

class PE:
    def __init__(self, data):
        self.data = data
        if data[:2] != b'MZ': raise ValueError('Missing MZ header')
        self.pe = struct.unpack_from('<I', data, 60)[0]
        if data[self.pe:self.pe+4] != b'PE\0\0': raise ValueError('Missing PE signature')
        self.opt = self.pe + 24
        magic = struct.unpack_from('<H', data, self.opt)[0]
        if magic not in (0x10b, 0x20b):
            raise ValueError('Only PE32 and PE32+ are supported')
        self.thunk_size = 4 if magic == 0x10b else 8
        self.directories = self.opt + (96 if magic == 0x10b else 112)
        self.nsections = struct.unpack_from('<H', data, self.pe+6)[0]
        self.section_table = self.opt + struct.unpack_from('<H', data, self.pe+20)[0]
        self.sections = []
        for i in range(self.nsections):
            offset = self.section_table + i*40
            name = data[offset:offset+8].rstrip(b'\0')
            virtual_size, va, rawsize, raw = struct.unpack_from('<IIII', data, offset+8)
            self.sections.append((name, virtual_size, va, rawsize, raw))

    def offset(self, rva):
        for _, vsize, va, rsize, raw in self.sections:
            if va <= rva < va + max(vsize, rsize): return raw+rva-va
        if rva < struct.unpack_from('<I', self.data, self.opt+60)[0]: return rva
        raise ValueError(f'RVA outside sections: {rva:x}')

    def directory(self, index):
        return struct.unpack_from('<II', self.data, self.directories+index*8)

    def manifest(self):
        rva, size = self.directory(2)
        if not rva or not size: return None
        base = self.offset(rva)
        def child(relative, identity):
            if not 0 <= relative <= size-16: raise ValueError('Invalid resource directory')
            pos = base+relative
            named, ids = struct.unpack_from('<HH', self.data, pos+12)
            for index in range(named+ids):
                if relative+16+(index+1)*8 > size: raise ValueError('Invalid resource entry')
                key, target = struct.unpack_from('<II', self.data, pos+16+index*8)
                if key == identity: return target
            return None
        resource = child(0, 24)
        if resource is None: return None
        if not resource & 0x80000000: raise ValueError('Invalid manifest resource type')
        resource = child(resource & 0x7fffffff, 1)
        if resource is None: return None
        if not resource & 0x80000000: raise ValueError('Invalid manifest resource ID')
        target = child(resource & 0x7fffffff, 0)
        if target is None or target & 0x80000000: raise ValueError('Missing neutral manifest language')
        if target+16 > size: raise ValueError('Invalid resource data')
        data_rva, length, _, _ = struct.unpack_from('<IIII', self.data, base+target)
        start = self.offset(data_rva)
        return self.data[start:start+length]

    def imports(self):
        rva, size = self.directory(1)
        if not rva: return {}
        result = {}; pos = self.offset(rva)
        while self.data[pos:pos+20] != bytes(20):
            original, _, _, name_rva, thunk = struct.unpack_from('<IIIII', self.data, pos)
            start = self.offset(name_rva)
            dll = self.data[start:self.data.index(0, start)].decode().lower()
            at = self.offset(original or thunk); names=[]
            while True:
                value = struct.unpack_from('<I' if self.thunk_size == 4 else '<Q', self.data, at)[0]
                if not value: break
                if value & (1 << (self.thunk_size*8-1)): names.append(value & 65535)
                else:
                    name_start=self.offset(value)+2
                    names.append(self.data[name_start:self.data.index(0,name_start)].decode())
                at += self.thunk_size
            result[dll] = names; pos += 20
        return result


def validate_manifest(xml):
    root = ET.fromstring(xml)
    identities = root.findall('.//{urn:schemas-microsoft-com:asm.v1}assemblyIdentity')
    if not any(e.get('name') == 'Microsoft.Windows.Common-Controls' and
               e.get('version') == '6.0.0.0' and
               e.get('publicKeyToken') == '6595b64144ccf1df'
               for e in identities):
        raise ValueError('Manifest must select Common Controls v6')
    execution = root.find('.//{urn:schemas-microsoft-com:asm.v3}requestedExecutionLevel')
    if execution is None or execution.get('level') != 'asInvoker':
        raise ValueError('Unexpected elevation requirement')


def embed_manifest(bootloader, xml):
    validate_manifest(xml)
    pe = PE(bootloader)
    if any(pe.directory(2)): raise ValueError('Resources already exist')
    if any(pe.directory(4)): raise ValueError('Signed binary: refusing to invalidate certificate')
    section_align, file_align = struct.unpack_from('<II', bootloader, pe.opt+32)
    align = lambda n,a: (n+a-1)//a*a
    header = pe.section_table+40*pe.nsections
    first_raw = min(s[4] for s in pe.sections if s[3])
    if header+40 > first_raw or header+40 > struct.unpack_from('<I', bootloader, pe.opt+60)[0]:
        raise ValueError('Not enough unused section header space')
    if any(bootloader[header:header+40]): raise ValueError('Section header space is not empty')
    va = align(max(s[2]+max(s[1],s[3]) for s in pe.sections),section_align)
    raw = align(len(bootloader),file_align)
    # RT_MANIFEST(24) -> CREATEPROCESS_MANIFEST_RESOURCE_ID(1) -> LANG_NEUTRAL(0).
    resource=bytearray()
    for key,target in ((24,0x80000018),(1,0x80000030),(0,72)):
        resource.extend(struct.pack('<IIHHHH',0,0,0,0,0,1))
        resource.extend(struct.pack('<II',key,target))
    resource.extend(struct.pack('<IIII',va+88,len(xml),0,0))
    resource.extend(xml)
    output=bytearray(bootloader)
    struct.pack_into('<H',output,pe.pe+6,pe.nsections+1)
    struct.pack_into('<I',output,pe.opt+56,align(va+len(resource),section_align))
    initialized=struct.unpack_from('<I',output,pe.opt+8)[0]
    struct.pack_into('<I',output,pe.opt+8,initialized+align(len(resource),file_align))
    struct.pack_into('<II',output,pe.directories+16,va,len(resource))
    struct.pack_into('<I',output,pe.opt+64,0)  # Checksum is recomputed for the finished file.
    output[header:header+40]=struct.pack('<8sIIIIIIHHI',b'.rsrc\0\0\0',len(resource),va,align(len(resource),file_align),raw,0,0,0,0,0x40000040)
    output.extend(bytes(raw-len(output)))
    output.extend(resource)
    output.extend(bytes(align(len(resource),file_align)-len(resource)))
    result=bytes(output)
    assert PE(result).manifest()==xml
    assert PE(result).imports()==pe.imports()
    for _,_,_,size,offset in pe.sections:
        assert result[offset:offset+size]==bootloader[offset:offset+size]
    return result


def set_checksum(data):
    """Compute the standard PE checksum, excluding its own field."""
    result=bytearray(data);at=PE(data).opt+64
    struct.pack_into('<I',result,at,0)
    if len(result)%2:words=result+b'\0'
    else:words=result
    value=sum(x[0] for x in struct.iter_unpack('<H',words))
    while value>>16:value=(value&65535)+(value>>16)
    struct.pack_into('<I',result,at,value+len(result))
    return bytes(result)
