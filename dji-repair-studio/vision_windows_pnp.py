"""Read only CfgMgr32 device metadata. No USB endpoint, driver or factory APIs."""
import ctypes
import json
import re
import sys
from pathlib import Path
from vision_usb_parent import GUID, DEVPROPKEY, BUS_PRODUCT_KEY, windows_cfgmgr32

PRESENT_USB = 0x101  # CM_GETIDLIST_FILTER_ENUMERATOR | CM_GETIDLIST_FILTER_PRESENT
MAX_LIST_CHARS = 262144
MAX_PROPERTY_BYTES = 8192
MAX_DEVICES = 64
MAX_JSON_BYTES = 1024 * 1024
CR_BUFFER_SMALL = 0x1a


def device_key(pid):
    return DEVPROPKEY(GUID(0xa45c254e, 0xdf1c, 0x4efd,
                          (ctypes.c_ubyte * 8)(0x80, 0x20, 0x67, 0xd1, 0x46, 0xa8, 0x50, 0xe0)), pid)


PROPERTIES = {'bus_product': (BUS_PRODUCT_KEY, 0x12), 'friendly_name': (device_key(14), 0x12),
              'service': (device_key(6), 0x12), 'hardware_ids': (device_key(3), 0x2012)}


def windows_inventory_api():
    cm = windows_cfgmgr32()
    u32 = ctypes.c_uint32
    cm.CM_Get_Device_ID_List_SizeW.argtypes = [ctypes.POINTER(u32), ctypes.c_wchar_p, u32]
    cm.CM_Get_Device_ID_List_SizeW.restype = u32
    cm.CM_Get_Device_ID_ListW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_wchar), u32, u32]
    cm.CM_Get_Device_ID_ListW.restype = u32
    cm.CM_Get_DevNode_Status.argtypes = [ctypes.POINTER(u32), ctypes.POINTER(u32), u32, u32]
    cm.CM_Get_DevNode_Status.restype = u32
    return cm


def listed_dji_ids(cm):
    for attempt in range(2):
        size = ctypes.c_uint32()
        code = cm.CM_Get_Device_ID_List_SizeW(ctypes.byref(size), 'USB', PRESENT_USB)
        if code: raise RuntimeError(f'CM_Get_Device_ID_List_SizeW: CONFIGRET 0x{code:08x}.')
        if not 1 <= size.value <= MAX_LIST_CHARS:
            raise ValueError(f'CM_Get_Device_ID_List_SizeW devolvió {size.value} caracteres; límite 1..{MAX_LIST_CHARS}.')
        buffer = ctypes.create_unicode_buffer(size.value)
        code = cm.CM_Get_Device_ID_ListW('USB', buffer, size.value, PRESENT_USB)
        if code == CR_BUFFER_SMALL and attempt == 0: continue
        if code: raise RuntimeError(f'CM_Get_Device_ID_ListW: CONFIGRET 0x{code:08x}.')
        text = buffer[:]
        if text in ('\0', '\0\0'): return []
        if not text.endswith('\0\0'): raise ValueError('Lista PnP sin terminación MULTI_SZ.')
        all_ids = text.rstrip('\0').split('\0')
        if len(all_ids) > 4096 or any(not v or len(v) > 512 for v in all_ids):
            raise ValueError('Identificadores PnP vacíos o fuera del límite.')
        ids = [v for v in all_ids if re.match(r'^USB\\VID_2CA3&', v, re.I)]
        if len(ids) > MAX_DEVICES or len({v.casefold() for v in ids}) != len(ids):
            raise ValueError('Demasiados nodos DJI o identificadores repetidos.')
        if any(not re.fullmatch(r'USB\\VID_2CA3&PID_[0-9A-F]{4}(?:&[A-Z0-9_]+)*\\[^\x00-\x1f\\]{1,300}', v, re.I) for v in ids):
            raise ValueError('Identificador USB DJI no reconocido.')
        return ids
    raise RuntimeError('La lista USB cambió durante los dos intentos de lectura.')


def read_property(cm, node, key, expected_type):
    data = ctypes.create_string_buffer(MAX_PROPERTY_BYTES)
    size = ctypes.c_uint32(len(data)); kind = ctypes.c_uint32()
    code = cm.CM_Get_DevNode_PropertyW(node, ctypes.byref(key), ctypes.byref(kind),
                                     data, ctypes.byref(size), 0)
    if code: raise RuntimeError(f'CONFIGRET 0x{code:08x}')
    if kind.value != expected_type or not 2 <= size.value <= len(data) or size.value % 2:
        raise ValueError('Tipo o longitud de propiedad PnP no reconocidos.')
    text = data.raw[:size.value].decode('utf-16-le', errors='strict')
    if expected_type == 0x2012:
        if not text.endswith('\0\0'): raise ValueError('HardwareID sin MULTI_SZ completo.')
        values = text[:-2].split('\0') if text[:-2] else []
        if len(values) > 32 or any(not v or len(v) > 1024 for v in values):
            raise ValueError('Lista HardwareID fuera del límite.')
        return values
    if not text.endswith('\0') or '\0' in text[:-1] or len(text) > 2049:
        raise ValueError('Cadena PnP incompleta o demasiado larga.')
    return text[:-1]


def native_inventory(api_factory=windows_inventory_api, snapshot=lambda raw: None, cancelled=lambda: False):
    raw = {'schema': 1, 'source': 'windows_pnp_present', 'collector_backend': 'cfgmgr32',
           'collection_complete': False, 'stage': 'cargar_cfgmgr32', 'devices': [], 'property_errors': []}
    def stage(value):
        raw['stage'] = value
        snapshot(raw)
        if cancelled(): raise InterruptedError('Consulta nativa detenida.')
    try:
        stage('cargar_cfgmgr32')
        cm = api_factory()
        stage('enumerar_usb_presente')
        ids = listed_dji_ids(cm)
        raw['matching_ids_enumerated'] = len(ids)
        for index, instance in enumerate(ids):
            row = {'instance_id': instance, 'friendly_name': None, 'status': None, 'bus_product': None,
                   'parent': None, 'service': None, 'hardware_ids': None, 'problem_code': None}
            raw['devices'].append(row)
            stage(f'nodo_{index}_localizar')
            node = ctypes.c_uint32()
            code = cm.CM_Locate_DevNodeW(ctypes.byref(node), instance, 0)
            if code:
                row['status'] = f'CONFIGRET 0x{code:08x}'
                raw['property_errors'].append({'node_index': index, 'property': 'locate', 'error': row['status']})
                continue
            for name, (key, kind) in PROPERTIES.items():
                stage(f'nodo_{index}_{name}')
                try: row[name] = read_property(cm, node.value, key, kind)
                except Exception as exc:
                    raw['property_errors'].append({'node_index': index, 'property': name, 'error': str(exc)[:512]})
            if row['friendly_name'] is None:
                stage(f'nodo_{index}_device_description')
                try: row['friendly_name'] = read_property(cm, node.value, device_key(2), 0x12)
                except Exception as exc:
                    raw['property_errors'].append({'node_index': index, 'property': 'device_description', 'error': str(exc)[:512]})
            stage(f'nodo_{index}_parent')
            try:
                parent = ctypes.c_uint32(); identifier = ctypes.create_unicode_buffer(512)
                code = cm.CM_Get_Parent(ctypes.byref(parent), node.value, 0)
                if not code: code = cm.CM_Get_Device_IDW(parent.value, identifier, len(identifier), 0)
                if code: raise RuntimeError(f'CONFIGRET 0x{code:08x}')
                row['parent'] = identifier.value
            except Exception as exc:
                raw['property_errors'].append({'node_index': index, 'property': 'parent', 'error': str(exc)[:512]})
            stage(f'nodo_{index}_status')
            status = ctypes.c_uint32(); problem = ctypes.c_uint32()
            code = cm.CM_Get_DevNode_Status(ctypes.byref(status), ctypes.byref(problem), node.value, 0)
            if code:
                row['status'] = f'CONFIGRET 0x{code:08x}'
                raw['property_errors'].append({'node_index': index, 'property': 'status', 'error': row['status']})
            else:
                row.update(status=f'DN 0x{status.value:08x}', problem_code=problem.value)
            stage(f'nodo_{index}_completado')
        raw.update(collection_complete=True, stage='completado')
    except Exception as exc:
        raw['error'] = str(exc)
        if isinstance(exc, InterruptedError): raw['cancelled'] = True
    snapshot(raw)
    return raw


def atomic_json(path, raw):
    data = json.dumps(raw, ensure_ascii=False).encode('utf-8')
    if len(data) > MAX_JSON_BYTES: raise ValueError('La instantánea PnP supera el límite.')
    temp = path.with_suffix('.tmp')
    temp.write_bytes(data); temp.replace(path)


def inventory_worker(job_path):
    job_path = Path(job_path).absolute()
    if job_path.is_symlink() or job_path.stat().st_size > 4096:
        raise ValueError('Trabajo de inventario no válido.')
    job = json.loads(job_path.read_text(encoding='utf-8'))
    if set(job) != {'session_id'} or not isinstance(job['session_id'], str) or not re.fullmatch('[0-9a-f]{32}', job['session_id']):
        raise ValueError('Sesión de inventario no reconocida.')
    sid = job['session_id']; root = job_path.parent
    def snapshot(raw): atomic_json(root/'snapshot.json', {'session_id': sid, 'inventory': raw})
    raw = native_inventory(snapshot=snapshot)
    if raw['collection_complete']:
        from vision_usb_descriptors import collect_descriptors
        raw['collection_complete']=False
        def descriptor_stage(name, result):
            raw['stage']=name; raw['descriptor_inventory']=result; snapshot(raw)
        raw['descriptor_inventory']=collect_descriptors(raw['devices'],stage=descriptor_stage)
        raw.update(collection_complete=True,stage='completado')
        snapshot(raw)
    atomic_json(root/'result.json', {'session_id': sid, 'inventory': raw})
    return 0 if raw['collection_complete'] else 1
