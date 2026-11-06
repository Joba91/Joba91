"""Inventory libusb0 descriptor caches. Never claim/read bulk or configure USB.

The pinned libusb-win32 enumeration reads standard device/config descriptors.
PyUSB descriptor getters then access its parsed cache. No service command or
arbitrary control-transfer API is exposed here. Descriptor presence is not a
validated vision transport or an authenticated aircraft identity.
"""
import hashlib
import re
import sys
from pathlib import Path
from vision_usb_legacy import device_alias, read_alias_hardware_ids
from vision_usb_parent import read_alias_instance_id

LIBUSB0_SHA256 = '0cd18719d5701e9cc642fc93a83f13830931d6f29f664fedbdf212bcb7c349bd'
MI_ID = re.compile(r'USB\\VID_2CA3&PID_0020(?:&REV_[0-9A-F]{4})?&MI_([0-9A-F]{2})', re.I)


def enumerate_legacy_descriptors():
    import usb.core
    import usb.backend.libusb0
    path = Path(sys._MEIPASS)/'libusb0.dll' if hasattr(sys, '_MEIPASS') else Path(__file__).parent/'native/libusb0.dll'
    if hashlib.sha256(path.read_bytes()).hexdigest() != LIBUSB0_SHA256:
        raise ValueError('La biblioteca de descriptores no coincide con el binario verificado.')
    backend = usb.backend.libusb0.get_backend(find_library=lambda name: str(path))
    if backend is None: raise RuntimeError('No se pudo cargar la biblioteca de descriptores libusb0.')
    return usb.core.find(find_all=True, idVendor=0x2ca3, idProduct=0x0020, backend=backend)


def bounded(value, name, maximum=255, minimum=0):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError('Descriptor fuera del límite: ' + name)
    return value


def read_cached_configuration(device, index, budget):
    cfg = device[index]  # libusb0: parsed descriptor cache, not get_active_configuration()
    result = {name: bounded(getattr(cfg, name), name, 65535 if name=='wTotalLength' else 255)
              for name in ('bConfigurationValue', 'wTotalLength', 'bNumInterfaces', 'bmAttributes', 'bMaxPower')}
    bounded(cfg.bNumInterfaces, 'bNumInterfaces', 32)
    result['interfaces'] = []; seen=set()
    for interface in cfg:
        budget['interfaces'] += 1
        if budget['interfaces'] > 128: raise ValueError('Demasiados descriptores de interfaz.')
        item = {name: bounded(getattr(interface,name),name) for name in (
            'bInterfaceNumber','bAlternateSetting','bInterfaceClass','bInterfaceSubClass','bInterfaceProtocol','bNumEndpoints')}
        bounded(item['bNumEndpoints'], 'bNumEndpoints', 16)
        key=(item['bInterfaceNumber'],item['bAlternateSetting'])
        if key in seen: raise ValueError('Descriptor de interfaz/alternativa repetido.')
        seen.add(key); item['endpoints']=[]; addresses=set()
        for ep in interface:
            budget['endpoints'] += 1
            if budget['endpoints'] > 256: raise ValueError('Demasiados descriptores de endpoint.')
            endpoint={name:bounded(getattr(ep,name),name,65535 if name=='wMaxPacketSize' else 255)
                      for name in ('bEndpointAddress','bmAttributes','wMaxPacketSize','bInterval')}
            address=endpoint['bEndpointAddress']
            if address & 0x70 or not address & 0xf or address in addresses:
                raise ValueError('Dirección de endpoint inválida o repetida.')
            addresses.add(address)
            endpoint.update(direction='IN' if address & 0x80 else 'OUT',
                            transfer_type=('control','isochronous','bulk','interrupt')[endpoint['bmAttributes'] & 3])
            item['endpoints'].append(endpoint)
        if len(item['endpoints']) != item['bNumEndpoints']:
            raise ValueError('Cantidad de endpoints distinta del descriptor.')
        result['interfaces'].append(item)
    if len({i['bInterfaceNumber'] for i in result['interfaces']}) != result['bNumInterfaces']:
        raise ValueError('Cantidad de interfaces distinta del descriptor.')
    return result


def collect_descriptors(pnp_rows, enumerate_devices=enumerate_legacy_descriptors,
                        probe=read_alias_hardware_ids, probe_instance=read_alias_instance_id, stage=lambda name, result: None):
    result={'state':'desconocido','source':'libusb0 parsed standard descriptor cache',
            'aliases':[],'errors':[], 'standard_descriptor_reads_requested':False,
            'active_configuration_queried':False,'interfaces_claimed':0,'bulk_reads':0,'bulk_writes':0,
            'service_commands_sent':0,'configuration_writes':0,'calibration_performed':False,
            'transport_validated':False,'authenticated_identity':False}
    try:
        roots=[r for r in pnp_rows if '&MI_' not in r['instance_id'].split('\\')[1].upper()]
        if len(roots)!=1 or not re.fullmatch(r'USB\\VID_2CA3&PID_0020\\[^\\]+',roots[0]['instance_id'],re.I):
            raise ValueError('Se requiere un único padre DJI 2CA3:0020; no se seleccionan dispositivos por orden.')
        root_id=roots[0]['instance_id'].casefold(); interfaces={}
        for row in pnp_rows:
            match=re.fullmatch(r'USB\\VID_2CA3&PID_0020&MI_([0-9A-F]{2})\\[^\\]+',row['instance_id'],re.I)
            if match:
                mi=int(match[1],16)
                if (row.get('parent') or '').casefold()!=root_id or mi in interfaces:
                    raise ValueError('Relación PnP de interfaces ambigua o contradictoria.')
                interfaces[mi]=row
        if not interfaces: raise ValueError('No hay interfaces PnP asociadas al padre único.')
        stage('descriptores_enumerar_libusb0', result)
        result['standard_descriptor_reads_requested']=True
        devices=[]
        for device in enumerate_devices() or []:
            devices.append(device)
            if len(devices)>32: raise ValueError('Demasiados alias libusb0.')
        if not devices: raise RuntimeError('libusb0 no enumeró alias accesibles para 2CA3:0020.')
        seen=set(); budget={'interfaces':0,'endpoints':0}
        for device in devices:
            row={'configurations':[]}; result['aliases'].append(row)
            try:
                alias=device_alias(device)
                row['alias_index']=int(alias[-4:])
                if alias in seen: raise ValueError('Alias libusb0 repetido.')
                seen.add(alias); stage('descriptores_alias_'+alias[-4:]+'_hardware_ids',result)
                ids=probe(alias)
                if not isinstance(ids,list) or not 1<=len(ids)<=32 or any(not isinstance(v,str) or len(v)>1024 for v in ids):
                    raise ValueError('HardwareID del alias inválido.')
                matches=[MI_ID.fullmatch(v) for v in ids]
                if not all(matches) or len({int(m[1],16) for m in matches})!=1:
                    raise ValueError('El alias no acredita una única interfaz DJI 2CA3:0020.')
                mi=int(matches[0][1],16); row['pnp_interface_number']=mi
                if mi not in interfaces: raise ValueError('Interfaz del alias no presente en el inventario PnP.')
                instance=probe_instance(alias)
                if not isinstance(instance,str) or instance.casefold()!=interfaces[mi]['instance_id'].casefold():
                    raise ValueError('El nodo actual del alias no coincide con el inventario PnP de esta sesión.')
                row['pnp_instance_matches']=True
                if (device.idVendor,device.idProduct)!=(0x2ca3,0x0020):
                    raise ValueError('VID/PID del descriptor contradictorio.')
                row['device_descriptor']={name:bounded(getattr(device,name),name,65535 if name in ('bcdUSB','bcdDevice') else 255)
                    for name in ('bcdUSB','bcdDevice','bDeviceClass','bDeviceSubClass','bDeviceProtocol','bMaxPacketSize0','bNumConfigurations')}
                count=bounded(device.bNumConfigurations,'bNumConfigurations',4,1)
                for index in range(count):
                    stage(f'descriptores_alias_{alias[-4:]}_config_{index}',result)
                    row['configurations'].append(read_cached_configuration(device,index,budget))
                row['alias_mi_present_in_cache']=any(i['bInterfaceNumber']==mi for c in row['configurations'] for i in c['interfaces'])
                row['complete']=True
            except Exception as exc:
                row.update(complete=False,error=str(exc)[:1000]);result['errors'].append(str(exc)[:1000])
            stage('descriptores_alias_guardado',result)
        result['state']='confirmado' if not result['errors'] else 'incompleto'
        result['detail']='Descriptores estándar inventariados; configuración activa, transporte y calibración sin validar.'
    except Exception as exc:
        result.update(state='error',detail=str(exc)[:1000]);result['errors'].append(str(exc)[:1000])
    stage('descriptores_finalizados',result)
    return result
