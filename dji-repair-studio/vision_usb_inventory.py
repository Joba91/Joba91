"""Read present Windows PnP metadata for DJI devices. No drone service requests."""
import json
import re
import sys
import tempfile
import uuid
import time
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from vision_targets import target_info
from studio_version import VERSION

MAX_BYTES = 1024 * 1024
def launch_inventory_worker(job):
    from windows_job import start_hidden_process
    command = [sys.executable]
    if not getattr(sys, 'frozen', False):
        command.append(str(Path(__file__).with_name('launch.py')))
    command.extend(['--usb-inventory-worker', str(job)])
    return start_hidden_process(command, job.parent)


def query_windows_pnp(cancelled=lambda: False, launcher=None, max_seconds=25):
    if sys.platform != 'win32' and launcher is None:
        raise RuntimeError('La recopilación PnP requiere Windows 10/11.')
    launch = launcher or launch_inventory_worker
    raw = {'schema': 1, 'source': 'windows_pnp_present', 'collector_backend': 'cfgmgr32',
           'collection_complete': False, 'stage': 'arranque_del_worker', 'devices': [], 'property_errors': []}
    with tempfile.TemporaryDirectory(prefix='dji-pnp-') as folder:
        root = Path(folder); sid = uuid.uuid4().hex
        job = root/'job.json'; job.write_text(json.dumps({'session_id': sid}), encoding='utf-8')
        child = launch(job)
        reason = None
        try:
            deadline = time.monotonic() + max_seconds
            while child.poll() is None:
                if cancelled():
                    reason = 'cancelled'; break
                if time.monotonic() >= deadline:
                    reason = 'timeout'; break
                time.sleep(.05)
            if reason:
                child.terminate()
            code = child.wait(timeout=3)
            candidate = root/('snapshot.json' if reason else 'result.json')
            final_missing = not reason and not candidate.is_file()
            if not candidate.is_file() and not reason:
                candidate = root/'snapshot.json'
            if candidate.is_file():
                if candidate.is_symlink() or candidate.stat().st_size > MAX_BYTES:
                    raise ValueError('Instantánea PnP fuera del límite.')
                envelope = json.loads(candidate.read_text(encoding='utf-8'))
                if not isinstance(envelope, dict) or envelope.get('session_id') != sid:
                    raise ValueError('La instantánea PnP no pertenece a esta consulta.')
                value = envelope.get('inventory')
                validate_inventory(value)
                if value.get('collector_backend') != 'cfgmgr32' or type(value.get('collection_complete')) is not bool:
                    raise ValueError('Resultado del lector nativo no reconocido.')
                raw = value
            else:
                raw['error'] = 'El proceso lector no devolvió una instantánea.'
            raw['worker_exit_code'] = code
            if reason:
                raw['collection_complete'] = False
                raw[reason] = True
                raw['error'] = (('Recopilación detenida' if reason == 'cancelled' else
                                 f'El lector nativo agotó {max_seconds:g} segundos') +
                                '. Última etapa: ' + str(raw.get('stage', 'desconocida')) + '.')
            elif final_missing:
                raw['collection_complete'] = False
                raw['error'] = 'El lector no guardó el resultado final; se conservan datos parciales.'
            elif code != 0:
                raw['collection_complete'] = False
                raw.setdefault('error', f'El lector nativo terminó con código {code}.')
        finally:
            # Closing the job kills the bootloader and every child, even after a wait failure.
            child.close()
    return raw


def product_family(value):
    if not isinstance(value, str): return None
    for family, pattern in (
            ('Mini 4 Pro', r'(?:DJI\s+)?Mini\s*4\s*Pro(?:-|$)'),
            ('Air 3', r'(?:DJI\s+)?Air\s*3(?:-|$)')):
        if re.match(pattern, value.strip(), re.I): return family
    return None


def validate_firmware(firmware):
    if not isinstance(firmware, str) or not re.fullmatch(r'\d{2}\.\d{2}\.\d{4}', firmware):
        raise ValueError('Escribe el firmware de aeronave que muestra DJI Fly, con formato 01.00.0000.')
    return firmware


def validate_inventory(raw):
    if not isinstance(raw, dict) or raw.get('schema') != 1 or raw.get('source') != 'windows_pnp_present':
        raise ValueError('Formato de inventario PnP no reconocido.')
    rows = raw.get('devices')
    if not isinstance(rows, list) or len(rows) > 64:
        raise ValueError('Cantidad de nodos PnP fuera del límite.')
    seen = set()
    fields = {'instance_id', 'friendly_name', 'status', 'bus_product', 'parent', 'service', 'hardware_ids', 'problem_code'}
    for row in rows:
        if not isinstance(row, dict) or set(row) != fields:
            raise ValueError('Registro PnP incompleto o no reconocido.')
        instance = row['instance_id']
        if not isinstance(instance, str) or not re.fullmatch(r'USB\\VID_2CA3&PID_[0-9A-F]{4}(?:&[A-Z0-9_]+)*\\[^\x00-\x1f\\]{1,300}', instance, re.I):
            raise ValueError('El inventario contiene un nodo ajeno al proveedor DJI o una ruta inválida.')
        key = instance.casefold()
        if key in seen: raise ValueError('El inventario repite un nodo PnP.')
        seen.add(key)
        for field in fields - {'hardware_ids', 'problem_code'}:
            value = row[field]
            if value is not None and (not isinstance(value, str) or len(value) > 2048 or '\0' in value):
                raise ValueError('Propiedad PnP inválida o demasiado larga.')
        ids = row['hardware_ids']
        if ids is not None and (not isinstance(ids, list) or len(ids) > 32 or
                               any(not isinstance(s, str) or len(s) > 1024 for s in ids)):
            raise ValueError('Lista HardwareID inválida.')
        if row['problem_code'] is not None and (type(row['problem_code']) is not int or not 0 <= row['problem_code'] <= 0xffffffff):
            raise ValueError('Código de estado PnP inválido.')
    return rows


def collect_usb_profile(output_zip, model, firmware, cancelled=lambda: False, progress=lambda e: None,
                        collector=query_windows_pnp):
    target_info(model)
    validate_firmware(firmware)
    path = Path(output_zip).absolute()
    if path.suffix.lower() != '.zip' or path.exists() or not path.parent.is_dir():
        raise ValueError('Elige un ZIP nuevo; no se sobrescriben archivos.')
    result = {'state': 'desconocido', 'model_declared': model, 'firmware_declared': firmware,
              'source': 'Metadatos PnP presentes de Windows', 'devices': [], 'model_descriptor_matches': False,
              'usb_endpoints_verified': False, 'calibration_available': False, 'calibration_performed': False,
              'native_sdk_loaded': False, 'usb_operations_requested': 0, 'service_commands_sent': 0,
              'driver_changes': 0, 'support_bundle': str(path)}
    try:
        if cancelled(): raise InterruptedError('Recopilación detenida antes de consultar Windows.')
        progress({'mode': 'indeterminate', 'label': 'Leyendo dispositivos y controladores registrados en Windows'})
        raw = collector(cancelled=cancelled)
        rows = validate_inventory(raw)
        result['devices'] = rows
        result.update(collector_backend=raw.get('collector_backend', 'injected_test_fixture'),
                      collection_complete=raw.get('collection_complete', True),
                      collection_stage=raw.get('stage', 'completado'),
                      property_errors=raw.get('property_errors', []))
        if 'descriptor_inventory' in raw:
            result['descriptor_inventory']=raw['descriptor_inventory']
            requested=raw['descriptor_inventory'].get('standard_descriptor_reads_requested',False)
            result['standard_descriptor_reads_requested']=requested
            result['usb_operations_requested']=None if requested else 0
            result['usb_operation_count_known']=not requested
        if 'worker_exit_code' in raw: result['worker_exit_code'] = raw['worker_exit_code']
        if not result['collection_complete'] or cancelled():
            result['inventory_state'] = 'incompleto'
            detail = (str(raw.get('error', 'La consulta no terminó.')) +
                      f' Se conservaron {len(rows)} nodos parciales; no confirman identidad ni calibración.')
            if raw.get('cancelled') or cancelled(): raise InterruptedError(detail)
            raise RuntimeError(detail)
        roots = [r for r in rows if '&MI_' not in r['instance_id'].split('\\')[1].upper()]
        result['physical_root_count'] = len(roots)
        matching = [r for r in roots if product_family(r['bus_product']) == model]
        result['model_descriptor_matches'] = len(roots) == len(matching) == 1
        result['inventory_state'] = 'confirmado'
        result['detail'] = (f'Windows informa {len(rows)} nodos DJI. ' +
                            ('El nombre del único padre USB coincide con ' + model + '. ' if result['model_descriptor_matches'] else
                             'Modelo del padre USB sin coincidencia única. ') +
                            'Los endpoints y la compatibilidad de calibración siguen pendientes de validar.' +
                            (' Descriptores estándar: '+raw['descriptor_inventory']['state']+'.' if 'descriptor_inventory' in raw else ''))
    except Exception as exc:
        result.update(state='desconocido' if isinstance(exc, InterruptedError) else 'error', detail=str(exc), error=str(exc))
    data = json.dumps({'herramienta': 'DJI REPAIR Studio', 'version': VERSION, 'fecha_unix': time.time(), 'modelo_declarado': model,
                       'firmware_declarado': firmware, 'vision': {'usb_profile': result}}, ensure_ascii=False, indent=2).encode('utf-8')
    if len(data) > MAX_BYTES: raise ValueError('El informe excede el límite de archivo.')
    with ZipFile(path, 'x', ZIP_DEFLATED) as archive:
        archive.writestr('DJI-REPAIR-informe.json', data)
    if result.get('inventory_state') == 'confirmado':
        progress({'mode': 'determinate', 'percent': 100, 'label': 'Inventario Windows guardado · no es calibración'})
    result['detail'] += ' Archivo para compartir: ' + str(path)
    return result
