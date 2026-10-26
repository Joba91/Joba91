"""Read the product of the physical USB parent associated with a libusb0 MI04.

Fixed, read-only operations: libusb-win32 GET_OBJECT_NAME (registry key of the
already selected PDO), then Configuration Manager parent/BusReportedDeviceDesc.
No USB service command, PnP reconfiguration or driver/registry write is exposed.
Windows API declarations/property key were checked against Microsoft win32metadata
WinSDK cfgmgr32.h and devpkey.h. No Microsoft header is redistributed.
"""
import ctypes
import hashlib
import re
import struct
import sys
from vision_usb_legacy import windows_kernel32,_alias_path,_windows_error,device_alias

GET_OBJECT_NAME=0x2223fc
OBJECT_NAME_REQUEST=struct.pack('<II16x',1000,0)
MAX_BYTES=8192
CHILD_RE=re.compile(r'USB\\VID_2CA3&PID_0020(?:&REV_[0-9A-F]{4})?&MI_04\\[A-Z0-9&._+{}#-]{1,200}',re.I)
PARENT_RE=re.compile(r'USB\\VID_2CA3&PID_0020\\[A-Z0-9&._+{}#-]{1,200}',re.I)

class GUID(ctypes.Structure):
    _fields_=[('data1',ctypes.c_uint32),('data2',ctypes.c_uint16),('data3',ctypes.c_uint16),('data4',ctypes.c_ubyte*8)]

class DEVPROPKEY(ctypes.Structure):
    _fields_=[('fmtid',GUID),('pid',ctypes.c_uint32)]

BUS_PRODUCT_KEY=DEVPROPKEY(GUID(0x540b947e,0x8b40,0x45bc,(ctypes.c_ubyte*8)(0xa8,0xa2,0x6a,0x0b,0x89,0x4c,0xbd,0xa2)),4)

def read_alias_instance(alias,kernel=None):
    alias=_alias_path(alias);kernel=kernel if kernel is not None else windows_kernel32()
    handle=kernel.CreateFileW(alias,0,0,None,3,0,None)
    if handle in (None,ctypes.c_void_p(-1).value):raise _windows_error('No se pudo consultar el nodo PnP del alias MI04.')
    try:
        request=ctypes.create_string_buffer(OBJECT_NAME_REQUEST,len(OBJECT_NAME_REQUEST))
        output=ctypes.create_string_buffer(MAX_BYTES);actual=ctypes.c_uint32()
        if not kernel.DeviceIoControl(handle,GET_OBJECT_NAME,request,len(OBJECT_NAME_REQUEST),output,
                len(output),ctypes.byref(actual),None):
            raise _windows_error('El controlador no devolvió el nodo PnP asociado al alias MI04.')
        if not 2<=actual.value<=MAX_BYTES:raise ValueError('Longitud inválida del nombre PnP.')
        raw=output.raw[:actual.value]
        if not raw.endswith(b'\0') or b'\0' in raw[:-1]:raise ValueError('Nombre PnP incompleto o inválido.')
        name=raw[:-1].decode('ascii',errors='strict')
        match=re.fullmatch(r'\\REGISTRY\\MACHINE\\SYSTEM\\(?:CurrentControlSet|ControlSet[0-9]{3})\\Enum\\(USB\\[^\\]+\\[^\\]+)(?:\\Device Parameters)?',name,re.I)
        if not match or not CHILD_RE.fullmatch(match[1]):
            raise ValueError('El nodo devuelto no acredita la interfaz MI04 del VID/PID esperado.')
        return match[1]
    finally:
        if not kernel.CloseHandle(handle):raise _windows_error('No se pudo cerrar la consulta del nodo PnP.')

def windows_cfgmgr32():
    if sys.platform!='win32':raise RuntimeError('La consulta del dispositivo padre requiere Windows.')
    cm=ctypes.WinDLL('cfgmgr32',use_last_error=True);dword=ctypes.c_uint32
    cm.CM_Locate_DevNodeW.argtypes=[ctypes.POINTER(dword),ctypes.c_wchar_p,dword]
    cm.CM_Locate_DevNodeW.restype=dword
    cm.CM_Get_Parent.argtypes=[ctypes.POINTER(dword),dword,dword];cm.CM_Get_Parent.restype=dword
    cm.CM_Get_Device_IDW.argtypes=[dword,ctypes.POINTER(ctypes.c_wchar),dword,dword]
    cm.CM_Get_Device_IDW.restype=dword
    cm.CM_Get_DevNode_PropertyW.argtypes=[dword,ctypes.POINTER(DEVPROPKEY),ctypes.POINTER(dword),
        ctypes.c_void_p,ctypes.POINTER(dword),dword]
    cm.CM_Get_DevNode_PropertyW.restype=dword
    return cm

def _checked(status,operation):
    if status!=0:raise RuntimeError(f'Windows no pudo completar {operation} (CONFIGRET 0x{int(status):08x}).')

def read_parent_product(instance,cm=None):
    if not CHILD_RE.fullmatch(instance):raise ValueError('Se requiere el nodo MI04 validado, no una selección por nombre.')
    cm=cm if cm is not None else windows_cfgmgr32()
    child=ctypes.c_uint32();parent=ctypes.c_uint32()
    _checked(cm.CM_Locate_DevNodeW(ctypes.byref(child),instance,0),'localizar MI04 presente')
    _checked(cm.CM_Get_Parent(ctypes.byref(parent),child.value,0),'obtener el padre de MI04')
    identifier=ctypes.create_unicode_buffer(512)
    _checked(cm.CM_Get_Device_IDW(parent.value,identifier,len(identifier),0),'leer la identidad del padre')
    parent_id=identifier.value
    if not PARENT_RE.fullmatch(parent_id):raise ValueError('El padre de MI04 no corresponde al dispositivo USB físico esperado.')
    data=ctypes.create_string_buffer(MAX_BYTES);size=ctypes.c_uint32(MAX_BYTES);kind=ctypes.c_uint32()
    _checked(cm.CM_Get_DevNode_PropertyW(parent.value,ctypes.byref(BUS_PRODUCT_KEY),ctypes.byref(kind),data,ctypes.byref(size),0),
        'leer BusReportedDeviceDesc del padre')
    if kind.value!=0x12 or not 2<=size.value<=MAX_BYTES or size.value%2:
        raise ValueError('Formato inválido del producto del dispositivo padre.')
    value=data.raw[:size.value].decode('utf-16-le',errors='strict')
    if not value.endswith('\0') or '\0' in value[:-1]:raise ValueError('Nombre de producto del padre incompleto o inválido.')
    product=value[:-1]
    if not product or len(product)>512:raise ValueError('Nombre de producto del padre vacío o excesivo.')
    return {'product':product,'source':'Windows physical USB parent / BusReportedDeviceDesc',
        'child_mi':4,'parent_vid':'2ca3','parent_pid':'0020','metadata_only':True,
        'child_instance_sha256':hashlib.sha256(instance.upper().encode()).hexdigest(),
        'parent_instance_sha256':hashlib.sha256(parent_id.upper().encode()).hexdigest()}

def parent_product_for_device(device):
    instance=read_alias_instance(device_alias(device))
    return read_parent_product(instance)
