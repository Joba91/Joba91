"""Identify a libusb0 driver alias by local Windows hardware IDs, not list order.

The public libusb-win32 ABI uses GET_DEVICE_PROPERTY 0x222400 and a packed
24-byte request (timeout DWORD, property DWORD, 16 unused bytes). Property 1 is
DevicePropertyHardwareID. Its handler calls IoGetDeviceProperty on the PDO;
it does not send a USB request or change a driver/device setting.
Source: libusb-win32 commit 0987f983a89e5e60d3c2db2af46564239c1b0d37,
driver_api.h, ioctl.c and driver_registry.c; complete source is distributed.
"""
import ctypes
import re
import struct
import sys

GET_DEVICE_PROPERTY=0x222400
HARDWARE_ID_REQUEST=struct.pack('<II16x',1000,1)
MAX_ALIASES=32
MAX_PROPERTY_BYTES=8192
ALIAS_PREFIX='\\\\.\\libusb0-'

class LegacyInterfaceError(RuntimeError):
    def __init__(self,message,observations):
        self.observations=observations
        super().__init__(message)

def _alias_path(path):
    if not isinstance(path,str) or not path.lower().startswith(ALIAS_PREFIX):
        raise ValueError('Ruta de alias libusb0 no reconocida.')
    number=path[len(ALIAS_PREFIX):]
    if len(number)!=4 or not number.isascii() or not number.isdigit() or not 1<=int(number)<=255:
        raise ValueError('Índice de alias libusb0 fuera del intervalo previsto.')
    return ALIAS_PREFIX+number

def device_alias(device):
    """Use the pinned PyUSB 1.3.1 raw libusb0 filename, not USB address guesses."""
    try:field=device._ctx.dev.filename
    except AttributeError:raise ValueError('La API no expuso el nombre del alias libusb0.')
    raw=bytes(field) if isinstance(field,(bytes,bytearray)) else bytes(int(x)&255 for x in field)
    name=raw.split(b'\0',1)[0].decode('ascii')
    alias,separator,identity=name.partition('--')
    if separator!='--' or identity.lower()!='0x2ca3-0x0020':
        raise ValueError('El alias no corresponde al VID/PID DJI esperado.')
    return _alias_path(alias)

def windows_kernel32():
    if sys.platform!='win32':raise RuntimeError('La identificación de alias libusb0 requiere Windows.')
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    dword=ctypes.c_uint32;handle=ctypes.c_void_p;ptr=ctypes.c_void_p
    kernel.CreateFileW.argtypes=[ctypes.c_wchar_p,dword,dword,ptr,dword,dword,handle]
    kernel.CreateFileW.restype=handle
    kernel.DeviceIoControl.argtypes=[handle,dword,ptr,dword,ptr,dword,ctypes.POINTER(dword),ptr]
    kernel.DeviceIoControl.restype=ctypes.c_int
    kernel.CloseHandle.argtypes=[handle];kernel.CloseHandle.restype=ctypes.c_int
    return kernel

def _windows_error(message):
    code=getattr(ctypes,'get_last_error',lambda:0)()
    if hasattr(ctypes,'WinError'):return ctypes.WinError(code,message)
    return OSError(code,message)

def read_alias_hardware_ids(alias,kernel=None):
    """Read exactly one local metadata property; no generic IOCTL/write API."""
    alias=_alias_path(alias)
    kernel=kernel if kernel is not None else windows_kernel32()
    # FILE_ANY_ACCESS metadata IOCTL: no read/write access, synchronous handle,
    # no configuration, endpoint, factory, reset or vendor-control operation.
    handle=kernel.CreateFileW(alias,0,0,None,3,0,None)
    if handle in (None,ctypes.c_void_p(-1).value):
        raise _windows_error('No se pudo abrir el alias para consultar sus metadatos locales.')
    try:
        request=ctypes.create_string_buffer(HARDWARE_ID_REQUEST,len(HARDWARE_ID_REQUEST))
        output=ctypes.create_string_buffer(MAX_PROPERTY_BYTES);actual=ctypes.c_uint32()
        if not kernel.DeviceIoControl(handle,GET_DEVICE_PROPERTY,request,len(HARDWARE_ID_REQUEST),
                output,len(output),ctypes.byref(actual),None):
            raise _windows_error('El controlador no devolvió los identificadores HardwareID del alias.')
        size=actual.value
        if not 4<=size<=MAX_PROPERTY_BYTES or size%2:
            raise ValueError('Longitud inválida de la propiedad HardwareID.')
        text=output.raw[:size].decode('utf-16-le',errors='strict')
        if not text.endswith('\0\0'):
            raise ValueError('HardwareID no contiene un MULTI_SZ completo.')
        ids=text[:-2].split('\0')
        if not ids or any(not value or len(value)>1024 for value in ids):
            raise ValueError('Propiedad HardwareID vacía o inválida.')
        return ids
    finally:
        if not kernel.CloseHandle(handle):raise _windows_error('No se pudo cerrar la consulta de metadatos del alias.')

def select_mi04(devices,probe=None):
    """Require one proven MI04 across all aliases; never choose the first one."""
    if not 1<=len(devices)<=MAX_ALIASES:
        raise LegacyInterfaceError('Cantidad de alias libusb0 fuera del límite de identificación.',[])
    probe=probe or read_alias_hardware_ids
    observations=[];matches=[];failed=False;seen=set()
    for device in devices:
        row={}
        try:
            alias=device_alias(device)
            index=int(alias[len(ALIAS_PREFIX):]);row['alias_index']=index
            if index in seen:raise ValueError('La enumeración repite un mismo alias.')
            seen.add(index)
            ids=probe(alias)
            if not isinstance(ids,list) or not ids or not all(isinstance(v,str) for v in ids):
                raise ValueError('La consulta no devolvió una lista de HardwareID.')
            interfaces=set();identified=False
            for value in ids:
                match=re.fullmatch(r'USB\\VID_2CA3&PID_0020(?:&REV_[0-9A-F]{4})?(?:&MI_([0-9A-F]{2}))?',value,re.I)
                if not match:
                    if value.upper().startswith('USB\\VID_'):
                        raise ValueError('HardwareID USB contradictorio o no admitido en el mismo alias.')
                    continue
                identified=True
                if match[1] is not None:interfaces.add(int(match[1],16))
            if not identified:raise ValueError('HardwareID no acredita el VID/PID esperado para ese alias.')
            if len(interfaces)>1:raise ValueError('El mismo alias declara números MI contradictorios.')
            mi=next(iter(interfaces)) if interfaces else None
            row.update(mi=mi,hardware_ids_identified=True,matches_mi04=mi==4)
            if mi==4:matches.append((device,index))
        except Exception as exc:
            failed=True;row.update(error=str(exc),exception_type=type(exc).__name__,
                errno=getattr(exc,'errno',None),winerror=getattr(exc,'winerror',None))
        observations.append(row)
    if failed:
        raise LegacyInterfaceError('No se identificaron todos los alias libusb0; no se seleccionará una interfaz por su posición.',observations)
    if len(matches)!=1:
        raise LegacyInterfaceError(f'Se identificaron {len(matches)} entradas MI04 entre {len(devices)} alias; se necesita una coincidencia única.',observations)
    device,index=matches[0]
    return device,{'method':'local_driver_hardware_ids','enumerated_aliases':len(devices),
        'selected_alias_index':index,'selected_mi':4,'metadata_queries_only':True,
        'observations':observations}
