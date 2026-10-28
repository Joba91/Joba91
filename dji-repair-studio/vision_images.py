"""Capture native image topics in an isolated x86 child; never calibrate."""
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from vision_image_receiver import validate_runtime, TOPICS, FIRMWARE, PGM_HEADER, WIDTH, HEIGHT, digest


def default_engine_directory():
    candidates = [Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')) /
                  'DJI Product' / 'DJI Assistant 2 (Consumer Drones Series)' / 'DJIEngine']
    return str(next((p for p in candidates if p.is_dir()), candidates[0]))


def identity_preflight():
    from vision_usb_passive import PassiveVisionUsbTransport
    transport = PassiveVisionUsbTransport(backend_name='libusb0')
    try:
        return dict(transport.evidence)
    finally:
        transport.close()


def receiver_path():
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
    path = root / 'vision_receiver32.exe'
    if not path.is_file():
        raise RuntimeError('Falta el receptor de 32 bits de esta distribución de DJI REPAIR.')
    with path.open('rb') as stream:
        head = stream.read(64)
        if len(head) != 64 or head[:2] != b'MZ':
            raise ValueError('Receptor de imágenes inválido.')
        offset = struct.unpack_from('<I', head, 60)[0]
        if offset > 1024 * 1024:
            raise ValueError('Cabecera del receptor fuera de límites.')
        stream.seek(offset)
        if stream.read(6) != b'PE\0\0\x4c\x01':
            raise ValueError('El receptor debe ser un ejecutable x86.')
    return path


def launch_receiver(job):
    if sys.platform != 'win32':
        raise RuntimeError('La recepción nativa de imágenes requiere Windows.')
    from windows_job import start_hidden_process
    return start_hidden_process([str(receiver_path()), str(job)], job.parent)


def validate_frames(root, native):
    rows = native.get('frames')
    if not isinstance(rows, list) or len(rows) > len(TOPICS):
        raise ValueError('Lista de imágenes inválida del receptor.')
    seen = set()
    result = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Registro de imagen inválido.')
        topic = row.get('topic')
        if topic not in TOPICS or topic in seen or row.get('file') != TOPICS[topic]:
            raise ValueError('Canal o ruta de imagen no permitidos.')
        path = root / row['file']
        if path.is_symlink() or not path.is_file() or path.stat().st_size != len(PGM_HEADER) + WIDTH * HEIGHT:
            raise ValueError('Archivo de imagen incompleto.')
        with path.open('rb') as stream:
            if stream.read(len(PGM_HEADER)) != PGM_HEADER:
                raise ValueError('Cabecera de imagen no reconocida.')
        if digest(path) != row.get('sha256'):
            raise ValueError('La imagen no coincide con su SHA-256.')
        seen.add(topic)
        result.append(dict(row))
    return result


def capture_images(output_zip, engine, firmware, cancelled=lambda: False, progress=lambda e: None,
                   preflight=identity_preflight, launcher=launch_receiver, max_seconds=30):
    if firmware != FIRMWARE:
        raise ValueError('Esta prueba se limita al firmware declarado 01.00.1100.')
    target = Path(output_zip).absolute()
    if target.suffix.lower() != '.zip' or target.exists() or not target.parent.is_dir():
        raise ValueError('Selecciona un ZIP nuevo; no se sobrescriben archivos.')
    images_dir = target.with_suffix('')
    if images_dir.exists():
        raise ValueError('Ya existe la carpeta de imágenes de ese nombre.')
    images_dir.mkdir()
    sid = uuid.uuid4().hex
    report = {'session_id': sid, 'state': 'desconocido', 'detail': '', 'frames': [],
              'firmware_declared': firmware, 'source': 'Receptor nativo x86 de DJI REPAIR',
              'interfaces_configured': {'v1': 5, 'dbus': 3}, 'profile_reference': 'wa140 / dual_chip_a7',
              'calibration_performed': False, 'calibration_commands_requested': 0,
              'parameter_writes_requested': 0, 'health': 'desconocido',
              'device_identity_from_images_confirmed': False, 'native_usb_traffic_bytes': None,
              'support_bundle': str(target), 'images_directory': str(images_dir)}
    process = None
    try:
        if cancelled():
            raise InterruptedError('Prueba detenida antes de abrir el equipo.')
        source_files = validate_runtime(engine)
        progress({'mode': 'indeterminate', 'label': 'Comprobando identidad USB antes de recibir imágenes'})
        report['usb_identity_preflight'] = preflight()
        if cancelled():
            raise InterruptedError('Prueba detenida antes de iniciar el receptor.')
        with tempfile.TemporaryDirectory(prefix='.receptor-', dir=images_dir) as temporary:
            work = Path(temporary)
            runtime = work / 'runtime'
            runtime.mkdir()
            for name, path in source_files.items():
                copied = runtime / name
                shutil.copyfile(path, copied)
            validate_runtime(runtime)
            job = work / 'job.json'
            job.write_text(json.dumps({'session_id': sid, 'runtime': str(runtime), 'seconds': 10,
                                       'firmware': firmware}), encoding='utf-8')
            progress({'mode': 'indeterminate', 'label': 'Iniciando receptor x86 · no se ejecuta calibración'})
            process = launcher(job)
            deadline = time.monotonic() + max_seconds
            consumed = 0
            partial = b''
            event_count = 0
            timed_out = False
            while process.poll() is None:
                if cancelled() or time.monotonic() >= deadline:
                    (work / 'stop.flag').write_bytes(b'')
                    timed_out = not cancelled()
                    try:
                        process.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        process.terminate()
                        try:
                            process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=3)
                    break
                events = work / 'events.jsonl'
                if events.is_file():
                    if events.stat().st_size > 32768:
                        raise ValueError('El canal de eventos del receptor excedió su límite.')
                    with events.open('rb') as stream:
                        stream.seek(consumed)
                        block = stream.read(32769)
                        consumed += len(block)
                    partial += block
                    while b'\n' in partial:
                        line, partial = partial.split(b'\n', 1)
                        event_count += 1
                        if event_count > 32:
                            raise ValueError('Demasiados eventos del receptor.')
                        event = json.loads(line)
                        if event.get('session_id') != sid or type(event.get('frames')) is not int or not 0 <= event['frames'] <= 2:
                            raise ValueError('Evento de otra sesión o contador inválido.')
                        if event.get('stage') == 'inicializacion_nativa':
                            progress({'mode': 'indeterminate', 'label': 'Inicializando transporte nativo MI03 / MI05'})
                        else:
                            progress({'mode': 'determinate', 'percent': min(90, event['frames'] * 50),
                                      'label': f"Imágenes recibidas: {event['frames']}/2 · verificando archivos"})
                time.sleep(0.05)
            exit_code = process.wait(timeout=3)
            report['receiver_exit_code'] = exit_code
            result = work / 'result.json'
            if not result.is_file():
                if cancelled():
                    raise InterruptedError('Recepción detenida; no se obtuvo un resultado completo.')
                fatal = work / 'fatal.json'
                if fatal.is_file() and fatal.stat().st_size <= 16384:
                    error = json.loads(fatal.read_text(encoding='utf-8')).get('error')
                    if isinstance(error, str) and error:
                        raise RuntimeError('El receptor no pudo iniciarse: ' + error[:4096])
                raise RuntimeError('El receptor no terminó dentro del límite.' if timed_out else
                                   f'El receptor terminó sin informe (código {exit_code}).')
            if result.stat().st_size > 512 * 1024:
                raise ValueError('Informe del receptor fuera de límites.')
            native = json.loads(result.read_text(encoding='utf-8'))
            if native.get('session_id') != sid:
                raise ValueError('El resultado pertenece a otra sesión.')
            rows = validate_frames(work, native)
            for row in rows:
                destination = images_dir / row['file']
                with destination.open('xb') as out, (work / row['file']).open('rb') as src:
                    shutil.copyfileobj(src, out)
                row['image_path'] = str(destination)
            report.update(frames=rows, native_result=native)
            complete = exit_code == 0 and native.get('completed') is True and len(rows) == 2 and not timed_out and not cancelled()
            report['state'] = 'confirmado' if complete else 'error' if native.get('state') == 'error' or exit_code else 'desconocido'
            report['detail'] = f'Recepción: {len(rows)}/2 imágenes verificadas. No se realizó calibración.'
            if native.get('error'):
                report['detail'] += ' ' + native['error']
            if native.get('cleanup_error'):
                report['detail'] += ' ' + native['cleanup_error']
            report['completed'] = complete
    except Exception as exc:
        report.update(state='desconocido' if isinstance(exc, InterruptedError) else 'error',
                      detail=str(exc), error=str(exc), completed=False)
    finally:
        if process is not None:
            try:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=3)
            except Exception as exc:
                report.update(state='error', completed=False, cleanup_error=str(exc))
                report['detail'] += ' Error al cerrar el receptor: ' + str(exc)
            finally:
                close = getattr(process, 'close', None)
                if close is not None: close()
    encoded = json.dumps({'vision': {'images': report}}, ensure_ascii=False, indent=2).encode('utf-8')
    if len(encoded) > 1024 * 1024:
        raise ValueError('Informe de imágenes demasiado grande.')
    with ZipFile(target, 'x', ZIP_DEFLATED) as archive:
        for row in report['frames']:
            archive.write(images_dir / row['file'], row['file'])
        archive.writestr('DJI-REPAIR-informe.json', encoded)
    if report.get('completed'):
        progress({'mode': 'determinate', 'percent': 100, 'label': 'Imágenes verificadas: 2/2 · no es calibración'})
    report['detail'] += ' Archivo para compartir: ' + str(target)
    return report
