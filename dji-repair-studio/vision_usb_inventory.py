"""Read present Windows PnP metadata for DJI devices. No drone service requests."""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from vision_targets import target_info
from studio_version import VERSION

MAX_BYTES = 1024 * 1024
# A fixed command, with no user text, paths, model or firmware interpolated.
PNP_SCRIPT = r'''
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$devices = @(Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match '^USB\\VID_2CA3&' } | Select-Object -First 65)
if ($devices.Count -gt 64) { throw 'Too many DJI PnP entries' }
$rows = @(foreach ($d in $devices) {
    $values = @{}
    foreach ($key in @('DEVPKEY_Device_BusReportedDeviceDesc','DEVPKEY_Device_Parent','DEVPKEY_Device_Service','DEVPKEY_Device_HardwareIds','DEVPKEY_Device_ProblemCode')) {
        try { $values[$key] = (Get-PnpDeviceProperty -InstanceId $d.InstanceId -KeyName $key -ErrorAction Stop).Data }
        catch { $values[$key] = $null }
    }
    $hardware = $null
    if ($null -ne $values['DEVPKEY_Device_HardwareIds']) { $hardware = @($values['DEVPKEY_Device_HardwareIds']) }
    [PSCustomObject]@{ instance_id=$d.InstanceId; friendly_name=$d.FriendlyName; status=$d.Status;
        bus_product=$values['DEVPKEY_Device_BusReportedDeviceDesc']; parent=$values['DEVPKEY_Device_Parent'];
        service=$values['DEVPKEY_Device_Service']; hardware_ids=$hardware;
        problem_code=$values['DEVPKEY_Device_ProblemCode'] }
})
[PSCustomObject]@{ schema=1; source='windows_pnp_present'; devices=$rows } | ConvertTo-Json -Depth 6 -Compress
'''


def query_windows_pnp(cancelled=lambda: False):
    if sys.platform != 'win32':
        raise RuntimeError('La recopilación PnP requiere Windows 10/11.')
    executable = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    if not executable.is_file():
        raise RuntimeError('Windows PowerShell no está disponible en su ubicación del sistema.')
    command = [str(executable), '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', PNP_SCRIPT]
    child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
    deadline = time.monotonic() + 25
    try:
        while True:
            if cancelled():
                raise InterruptedError('Recopilación de metadatos detenida.')
            if time.monotonic() >= deadline:
                raise TimeoutError('Windows no terminó la consulta PnP dentro de 25 segundos.')
            try:
                out, error = child.communicate(timeout=.1)
                break
            except subprocess.TimeoutExpired:
                pass
        if child.returncode:
            detail = error.decode('utf-8-sig', errors='replace').strip()[:2000]
            raise RuntimeError('Consulta PnP de Windows fallida: ' + detail)
        if len(out) > MAX_BYTES:
            raise ValueError('El inventario de Windows supera el límite.')
        return json.loads(out.decode('utf-8-sig'))
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate(timeout=3)


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
        rows = validate_inventory(collector(cancelled=cancelled))
        if cancelled(): raise InterruptedError('Recopilación detenida.')
        result['devices'] = rows
        roots = [r for r in rows if '&MI_' not in r['instance_id'].split('\\')[1].upper()]
        result['physical_root_count'] = len(roots)
        matching = [r for r in roots if product_family(r['bus_product']) == model]
        result['model_descriptor_matches'] = len(roots) == len(matching) == 1
        result['inventory_state'] = 'confirmado'
        result['detail'] = (f'Windows informa {len(rows)} nodos DJI. ' +
                            ('El nombre del único padre USB coincide con ' + model + '. ' if result['model_descriptor_matches'] else
                             'Modelo del padre USB sin coincidencia única. ') +
                            'Los endpoints y la compatibilidad de calibración siguen pendientes de validar.')
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
