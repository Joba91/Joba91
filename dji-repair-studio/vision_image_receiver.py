"""Bounded x86 receiver for two native vision topics. No calibration API binding.

The SDK remains in the user's installation. The helper runs in its own process;
this module never loads it when imported by the x64 graphical application.
"""
import ctypes
import hashlib
import json
import os
import struct
import sys
import time
from pathlib import Path

SDK_PINS = {'fs_dbus_lib.dll': 'f530863e700e37d18b35e7dbc23df1d007f76dff61be5e39afe0311115db43e8', 'fs_usb.dll': 'b936ffdcb62ec85765964144bacfd82be484f8c63a4c2fc1750f5df08a34db2c', 'libusb0.dll': 'c24b231889c6c4856eafb9c90b99ae01cbbbe897498be161624d3bd36266a921', 'libusb0_dji.dll': '23e6ca9418a102976485110cfb11c20aa3c69d0701cd993b782ca97012b01831', 'msvcp140.dll': '44029e501ea748eeb030312d461de074c05c83fc01dbdd80c633ec755a7695a5', 'msvcr100.dll': '8793353461826fbd48f25ea8b835be204b758ce7510db2af631b28850355bd18', 'pthreadvc2.dll': 'c669b51345871b2f7ce8ccb98acc36fba0b1f0a136977b244789c687c7851a0e'}
CONFIG_SHA256 = '5b0106d86e669c1ff9073ea0e5634244d4b6c99e6e4fa6516e122c38e3a8fc9b'
TOPICS = {'raw/down/left': 'down-left.pgm', 'raw/down/right': 'down-right.pgm'}
MODEL = 'wa140'
FIRMWARE = '01.00.1100'
WIDTH, HEIGHT = 640, 480
EXTRA_SIZE = 196
PGM_HEADER = b'P5\n640 480\n255\n'
MAX_JOB_BYTES = 16384


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def validate_runtime(directory):
    directory = Path(directory).absolute()
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError('Selecciona la carpeta DJIEngine de Consumer Drones Series.')
    files = {}
    for path in directory.iterdir():
        key = path.name.casefold()
        if key in files:
            raise ValueError('Nombres de archivo ambiguos en el motor local.')
        files[key] = path
    result = {}
    for name, expected in {**SDK_PINS, 'dbus_pc.json': CONFIG_SHA256}.items():
        path = files.get(name)
        if path is None or not path.is_file() or path.is_symlink():
            raise ValueError(f'Falta el componente local requerido: {name}')
        if not 0 < path.stat().st_size <= 32 * 1024 * 1024 or digest(path) != expected:
            raise ValueError(f'La versión de {name} no coincide con el motor analizado.')
        result[name] = str(path)
    config = json.loads(Path(result['dbus_pc.json']).read_text(encoding='utf-8-sig'))
    matches = [key for key, value in config.items()
               if any(row.get('mode_name') == MODEL for row in value.get('mode', []))]
    if matches != ['dual_chip_a7']:
        raise ValueError('El archivo no acredita el perfil wa140 analizado.')
    usb = config['dual_chip_a7']['interface']['usb']
    if {(int(x['vendor_id'], 16), int(x['product_id'], 16), x['interface'], x['desc']) for x in usb} != {
            (0x2ca3, 0x20, 5, 'v1'), (0x2ca3, 0x20, 3, 'dbus')}:
        raise ValueError('La configuración de interfaces difiere de la referencia.')
    return result


def parse_image_metadata(raw):
    """Offsets corroborated in the Consumer worker; accept its 640x480 8-bit case."""
    if not 28 <= len(raw) <= EXTRA_SIZE:
        raise ValueError('Longitud de metadatos de imagen no reconocida.')
    width, height = struct.unpack_from('<HH', raw, 6)
    bits = raw[14]
    size = struct.unpack_from('<I', raw, 24)[0]
    if (width, height, bits, size) != (WIDTH, HEIGHT, 8, WIDTH * HEIGHT):
        raise ValueError(f'Formato no validado: {width}x{height}, {bits} bits, {size} bytes.')
    return {'width': width, 'height': height, 'bits_per_pixel': bits, 'payload_bytes': size,
            'metadata_hex': raw.hex(), 'format_source': 'Referencia estática del motor Consumer; recepción experimental'}


class NativeReceiver:
    """Only initialization, topic subscription and reception are exposed."""
    def __init__(self, runtime):
        if sys.platform != 'win32' or struct.calcsize('P') != 4:
            raise RuntimeError('El receptor nativo requiere Windows y un proceso de 32 bits.')
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.SetErrorMode.argtypes = [ctypes.c_uint32]
        self.kernel.SetErrorMode.restype = ctypes.c_uint32
        self.kernel.SetErrorMode(0x8003)
        self.kernel.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
        self.kernel.SetDllDirectoryW.restype = ctypes.c_int
        if not self.kernel.SetDllDirectoryW(str(runtime)):
            raise OSError('No se pudo preparar la búsqueda de dependencias del receptor.')
        self.lib = ctypes.CDLL(str(Path(runtime) / 'fs_dbus_lib.dll'), winmode=0x900)
        self.lib.ss_dbus_pc_init.argtypes = [ctypes.c_char_p]
        self.lib.ss_dbus_pc_init.restype = ctypes.c_uint32
        self.lib.ss_dbus_all_peer_node_is_online.argtypes = []
        self.lib.ss_dbus_all_peer_node_is_online.restype = ctypes.c_bool
        class Attr(ctypes.Structure):
            _fields_ = [('module_name', ctypes.c_char_p), ('data_name', ctypes.c_char_p)]
        self.Attr = Attr
        self.lib.ss_dbus_shm_subscriber_new.argtypes = [ctypes.POINTER(Attr), ctypes.POINTER(ctypes.c_void_p)]
        self.lib.ss_dbus_shm_subscriber_new.restype = ctypes.c_uint32
        self.lib.ss_dbus_shm_subscriber_wait_data.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                                          ctypes.POINTER(ctypes.c_uint32), ctypes.c_uint32]
        self.lib.ss_dbus_shm_subscriber_wait_data.restype = ctypes.c_uint32
        self.lib.ss_dbus_shm_subscriber_destroy.argtypes = [ctypes.c_void_p]
        self.lib.ss_dbus_shm_subscriber_destroy.restype = ctypes.c_uint32
        self.kernel.GetCurrentProcess.restype = ctypes.c_void_p
        self.kernel.GetCurrentProcess.argtypes = []
        self.kernel.ReadProcessMemory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
        self.kernel.ReadProcessMemory.restype = ctypes.c_int
        self.handles = []
        self.attributes = []

    def initialize(self):
        code = self.lib.ss_dbus_pc_init(MODEL.encode('ascii'))
        if code:
            raise RuntimeError(f'Inicialización DBus rechazada: 0x{code:08x}')

    def subscribe(self, topic):
        if topic not in TOPICS:
            raise ValueError('Canal no permitido.')
        attr = self.Attr(b'dji_repair_receiver', topic.encode('ascii'))
        handle = ctypes.c_void_p()
        code = self.lib.ss_dbus_shm_subscriber_new(ctypes.byref(attr), ctypes.byref(handle))
        if code or not handle.value:
            raise RuntimeError(f'Suscripción rechazada para {topic}: 0x{code:08x}')
        self.handles.append(handle)
        self.attributes.append(attr)
        return handle

    def receive(self, handle, timestamp):
        # Match the native worker's descriptor and separate 196-byte metadata.
        descriptor = ctypes.create_string_buffer(96)
        extra = ctypes.create_string_buffer(EXTRA_SIZE)
        struct.pack_into('<II', descriptor, 0x14, ctypes.addressof(extra), EXTRA_SIZE)
        code = self.lib.ss_dbus_shm_subscriber_wait_data(handle, descriptor, ctypes.byref(timestamp), 200)
        if code:
            return None, code
        metadata_size = struct.unpack_from('<I', descriptor, 0x18)[0]
        if not 28 <= metadata_size <= EXTRA_SIZE:
            raise ValueError('Metadatos nativos fuera del límite de recepción.')
        metadata = parse_image_metadata(extra.raw[:metadata_size])
        address = struct.unpack_from('<I', descriptor, 0)[0]
        if not address:
            raise ValueError('La biblioteca devolvió una dirección de imagen vacía.')
        pixels = ctypes.create_string_buffer(metadata['payload_bytes'])
        actual = ctypes.c_size_t()
        if not self.kernel.ReadProcessMemory(self.kernel.GetCurrentProcess(), address, pixels,
                                            len(pixels), ctypes.byref(actual)) or actual.value != len(pixels):
            raise OSError('La imagen no se pudo copiar íntegramente desde la memoria del receptor.')
        return (metadata, pixels.raw), 0

    def close(self):
        codes = []
        for handle in reversed(self.handles):
            codes.append(int(self.lib.ss_dbus_shm_subscriber_destroy(handle)))
        self.handles.clear()
        self.attributes.clear()
        # No DLL unload: the SDK's background threads end with this process.
        return codes


def run_job(job_file, api_factory=NativeReceiver):
    job_file = Path(job_file).absolute()
    if job_file.stat().st_size > MAX_JOB_BYTES:
        raise ValueError('Trabajo de recepción demasiado grande.')
    job = json.loads(job_file.read_text(encoding='utf-8'))
    if set(job) != {'session_id', 'runtime', 'seconds', 'firmware'}:
        raise ValueError('Trabajo de recepción no reconocido.')
    sid = job['session_id']
    if not isinstance(sid, str) or len(sid) != 32 or any(x not in '0123456789abcdef' for x in sid):
        raise ValueError('Identificador de sesión inválido.')
    if job['firmware'] != FIRMWARE or type(job['seconds']) is not int or not 1 <= job['seconds'] <= 10:
        raise ValueError('Firmware o límite de tiempo no admitido.')
    root = job_file.parent
    runtime = Path(job['runtime']).absolute()
    if runtime.parent != root or runtime.name != 'runtime':
        raise ValueError('El runtime debe pertenecer a esta sesión.')
    validate_runtime(runtime)
    result = {'session_id': sid, 'state': 'desconocido', 'frames': [], 'error': None,
              'topics': list(TOPICS), 'native_initialization_started': False,
              'calibration_commands_requested': 0, 'parameter_writes_requested': 0,
              'native_usb_traffic_bytes': None, 'native_initialization_effects_validated_on_hardware': False,
              'device_identity_from_image_confirmed': False, 'health': 'desconocido',
              'calibration_performed': False, 'native_status_counts': {}, 'cleanup_codes': []}
    api = None
    started = time.monotonic()
    events = (root / 'events.jsonl').open('x', encoding='utf-8')
    def emit(stage):
        events.write(json.dumps({'session_id': sid, 'stage': stage, 'frames': len(result['frames'])}) + '\n')
        events.flush()
    try:
        os.chdir(root)
        if (root / 'stop.flag').exists():
            raise InterruptedError('Recepción cancelada antes de inicializar el transporte.')
        (root / 'dbus_pc.json').write_bytes((runtime / 'dbus_pc.json').read_bytes())
        emit('inicializacion_nativa')
        api = api_factory(runtime)
        result['native_initialization_started'] = True
        api.initialize()
        if (root / 'stop.flag').exists():
            raise InterruptedError('Recepción cancelada antes de suscribirse a las imágenes.')
        result['all_native_peers_online'] = bool(api.lib.ss_dbus_all_peer_node_is_online()) if hasattr(api, 'lib') else None
        handles = {topic: api.subscribe(topic) for topic in TOPICS}
        stamps = {topic: ctypes.c_uint32(0xffffffff) for topic in TOPICS}
        deadline = time.monotonic() + job['seconds']
        emit('recepcion_de_imagenes')
        completed = set()
        while time.monotonic() < deadline and len(completed) < len(TOPICS):
            if (root / 'stop.flag').exists():
                result['cancelled'] = True
                break
            for topic, handle in handles.items():
                if topic in completed or (root / 'stop.flag').exists():
                    continue
                received, code = api.receive(handle, stamps[topic])
                key = f'0x{code:08x}'
                result['native_status_counts'][key] = result['native_status_counts'].get(key, 0) + 1
                if received is None:
                    continue
                metadata, pixels = received
                # Validate again at the file boundary, independent of the FFI adapter.
                checked = parse_image_metadata(bytes.fromhex(metadata['metadata_hex']))
                if len(pixels) != checked['payload_bytes']:
                    raise ValueError('Carga de imagen truncada.')
                data = PGM_HEADER + pixels
                name = TOPICS[topic]
                with (root / name).open('xb') as out:
                    out.write(data)
                result['frames'].append({'topic': topic, 'file': name, 'sha256': hashlib.sha256(data).hexdigest(),
                                         'timestamp_raw': stamps[topic].value, **checked})
                completed.add(topic)
                emit('imagen_guardada')
        result['completed'] = len(completed) == len(TOPICS)
        result['state'] = 'confirmado' if result['completed'] else 'desconocido'
    except InterruptedError as exc:
        result.update(state='desconocido', error=str(exc), cancelled=True, completed=False)
    except Exception as exc:
        result.update(state='error', error=str(exc), completed=False)
    finally:
        if api is not None:
            try:
                result['cleanup_codes'] = api.close()
                if any(result['cleanup_codes']):
                    result.update(state='error', completed=False,
                                  cleanup_error='La biblioteca notificó errores al cerrar las suscripciones.')
            except Exception as exc:
                result.update(state='error', cleanup_error=str(exc), completed=False)
        result['elapsed_seconds'] = round(time.monotonic() - started, 3)
        events.close()
        text = json.dumps(result, ensure_ascii=False, indent=2)
        temporary = root / 'result.tmp'
        temporary.write_text(text, encoding='utf-8')
        temporary.replace(root / 'result.json')
    return result
