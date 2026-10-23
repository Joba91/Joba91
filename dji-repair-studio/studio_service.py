"""Protocol operations reconstructed from the user's YanDron archive.
No original executable/DLL is run. No fixed IMU coefficients are written.
"""
import re
import struct
import time
from studio_protocol import Decoder, checksum

MODELS = ('Mavic 3', 'Mavic 3 Pro', 'Mavic 3E', 'Mavic 3T', 'Mini 3 Pro')
ACTIONS = ('Escuchar progreso (20 s)', 'Entrar modo fabrica',
           'JointCoarse', 'LinearHall', 'Salir modo fabrica')
STATUS = {
    '0101': 'Auto: preparar', '0201': 'Auto: esperar', '0301': 'Auto: etapa 3',
    '0401': 'Auto: etapa 4', '0501': 'Auto: etapa 5', '0601': 'Auto: finalizar',
    '1101': 'LinearHall: preparar', '1201': 'LinearHall: esperar',
    '1401': 'LinearHall: listo', '1601': 'LinearHall: barrido', '1701': 'LinearHall: finalizar',
    '5201': 'JointCoarse: YAW', '5301': 'JointCoarse: ROLL',
    '5401': 'JointCoarse: PITCH', '5501': 'JointCoarse: finalizar',
    '6400': 'El equipo informa calibracion completada',
    '6403': 'El equipo informa calibracion fallida',
}

class Cancelled(Exception): pass


def packet(sender, receiver, seq, command_set, command_id, payload=b'', flags=0x40):
    size = 13 + len(payload)
    if size > 1023: raise ValueError('Paquete demasiado largo')
    prefix = b'\x55' + struct.pack('<H', size | 1024)
    data = prefix + bytes([checksum(prefix, 0x77, 0x8c), sender, receiver])
    data += struct.pack('<H', seq) + bytes([flags, command_set, command_id]) + payload
    return data + struct.pack('<H', checksum(data, 0x3692, 0x8408))


def unpack_hex(text):
    cleaned = re.sub(r'0[xX]', '', text.strip())
    cleaned = re.sub(r'[\s,_-]', '', cleaned)
    if not cleaned or len(cleaned) % 2 or re.search('[^0-9a-fA-F]', cleaned):
        raise ValueError('Introduce bytes HEX completos, por ejemplo: 55 0E 04 66 ...')
    return bytes.fromhex(cleaned)


def analyze(text):
    data = unpack_hex(text)
    if len(data) < 13: raise ValueError('El paquete debe contener al menos 13 bytes')
    size_version = int.from_bytes(data[1:3], 'little')
    size, version = size_version & 1023, size_version >> 10
    valid = (data[0] == 0x55 and size == len(data) and version == 1
             and checksum(data[:3], 0x77, 0x8c) == data[3]
             and checksum(data[:-2], 0x3692, 0x8408) == int.from_bytes(data[-2:], 'little'))
    result = {'valido': valid, 'longitud_declarada': size, 'longitud_real': len(data),
              'version_protocolo': version, 'emisor': f'{data[4]:02x}', 'receptor': f'{data[5]:02x}',
              'secuencia': int.from_bytes(data[6:8], 'little'),
              'respuesta': bool(data[8] & 128), 'ack': (data[8] >> 5) & 3,
              'cmd_set': f'{data[9]:02x}', 'cmd_id': f'{data[10]:02x}',
              'payload': data[11:-2].hex(' '),
              'crc8_correcto': checksum(data[:3], 0x77, 0x8c) == data[3],
              'crc16_correcto': checksum(data[:-2], 0x3692, 0x8408) == int.from_bytes(data[-2:], 'little')}
    if valid and data[4:6] == b'\x04\x0a' and data[9:11] == b'\x04\x30':
        result['estado_calibracion'] = STATUS.get(data[11:-2].hex(), 'Estado desconocido')
    return result


def validate(model, firmware, action, prepared=False):
    if model not in MODELS:
        raise ValueError('Modelo sin calibracion validada en esta herramienta. Mavic 4 Pro y Classic no estan habilitados en esta seccion.')
    if action not in ACTIONS: raise ValueError('Accion no admitida')
    if action in ('Escuchar progreso (20 s)', 'Salir modo fabrica'): return
    if not re.fullmatch(r'\d{2}\.\d{2}\.\d{4}', firmware):
        raise ValueError('Escribe el firmware que muestra DJI Fly: NN.NN.NNNN')
    if model == 'Mavic 3' and tuple(map(int, firmware.split('.'))) < (1, 0, 500):
        raise ValueError('Se requiere firmware minimo 01.00.0500 para Mavic 3.')
    if action in ('JointCoarse', 'LinearHall') and not prepared:
        raise ValueError('Primero entra en modo fabrica y reinicia el equipo. Marca la casilla solo despues de hacerlo.')

class Session:
    def __init__(self, transport, emit=lambda text: None, cancelled=lambda: False,
                 clock=time.monotonic, timeout=20, progress=lambda value: None):
        self.transport, self.emit, self.cancelled = transport, emit, cancelled
        self.clock, self.timeout = clock, timeout
        self.progress = progress
        self.decoder = Decoder()
        self.sequence = time.time_ns() & 65535
        self.events = []
        self.pending = []

    def log(self, direction, data):
        self.events.append({'direccion': direction, 'hex': data.hex(' ')})
        self.emit(direction + ' ' + data.hex(' '))

    def check(self):
        if self.cancelled():
            raise Cancelled('Lectura detenida; esto NO envia una orden de parada al gimbal.')

    def read_frames(self):
        self.check()
        try:
            chunk = self.transport.read(4096)
        except Exception as exc:
            # Preserve actual I/O and disconnect failures; only USB timeouts are idle reads.
            if exc.__class__.__name__ == 'USBTimeoutError' or getattr(exc, 'backend_error_code', None) == -7:
                return []
            raise
        frames = self.decoder.feed(bytes(chunk))
        for frame in frames: self.log('RX', frame)
        return frames

    def drain(self, duration=0.25):
        deadline = self.clock() + duration
        while self.clock() < deadline:
            self.read_frames()
        self.pending.clear()
        self.decoder = Decoder()

    def request(self, sender, receiver, command_set, command_id, payload, expected=None):
        self.check()
        self.sequence = (self.sequence + 1) & 65535
        seq = self.sequence
        frame = packet(sender, receiver, seq, command_set, command_id, payload)
        self.log('TX', frame)
        count = self.transport.write(frame)
        if count is not None and count != len(frame): raise OSError('Escritura incompleta')
        deadline = self.clock() + self.timeout
        while self.clock() < deadline:
            frames = self.read_frames()
            for index, reply in enumerate(frames):
                if (reply[4] != receiver or reply[5] != sender or not reply[8] & 128
                    or reply[8] & 7 or reply[9:11] != bytes([command_set, command_id])
                    or int.from_bytes(reply[6:8], 'little') != seq):
                    self.pending.append(reply)
                    continue
                data = reply[11:-2]
                self.pending.extend(frames[index+1:])
                if expected is not None and data != expected:
                    raise RuntimeError(f'Respuesta no aceptada: {data.hex(" ") or "vacia"}; no se asume exito.')
                return data
        raise TimeoutError('Sin confirmacion del comando. No se reenvia automaticamente.')

    def factory(self, enter):
        self.drain()
        payload = b'\x80\x0a' + (b'start_factory\0' if enter else b'stop_factory\0')
        failures = []
        confirmations = 0
        for receiver in (0x8f, 0x68):
            try:
                self.request(0x2a, receiver, 0, 0x44, payload, expected=b'\0')
                confirmations += 1
                self.progress({'percent': confirmations * 50, 'mode': 'determinate', 'basis': 'confirmaciones', 'label': f'Confirmaciones de modo: {confirmations}/2'})
            except Exception as exc:
                failures.append(f'{receiver:02x}: {exc}')
                if enter: break
        if failures:
            raise RuntimeError('Confirmacion incompleta de modo fabrica: ' + '; '.join(failures)
                               + '. Revisa el log; puede haber un cambio parcial. Usa Salir modo fabrica si es necesario.')
        return {'estado': 'orden_confirmada_reinicio_pendiente',
                'detalle': 'Reinicia manualmente el dron para ' + ('activar' if enter else 'salir del') + ' modo fabrica.'}

    def monitor(self, seconds, require_progress=False, expected_stages=None):
        deadline = self.clock() + seconds
        saw_progress = False
        seen = []
        confirmed = set()
        while self.clock() < deadline:
            self.check()
            frames, self.pending = self.pending, []
            frames += self.read_frames()
            for frame in frames:
                if frame[4:6] != b'\x04\x0a' or frame[9:11] != b'\x04\x30' or frame[8] & 7:
                    continue
                data = frame[11:-2]
                state = STATUS.get(data.hex(), 'Estado desconocido: ' + data.hex(' '))
                seen.append(data.hex()); self.emit(state)
                if (len(data) == 2 and data[1] == 1 and data.hex() in STATUS
                    and (expected_stages is None or data.hex() in expected_stages)):
                    saw_progress = True
                    if require_progress and expected_stages:
                        confirmed.add(data.hex())
                        percent = int(len(confirmed) / (len(expected_stages) + 1) * 100)
                        self.progress({'percent': percent, 'mode': 'determinate', 'basis': 'hitos',
                                       'label': f'Hitos observados: {len(confirmed)}/{len(expected_stages)+1}; {state}'})
                if data == b'\x64\x03': raise RuntimeError('El equipo informa calibracion FALLIDA (64 03).')
                if data == b'\x64\x00':
                    if require_progress and not saw_progress:
                        raise RuntimeError('Recibido 64 00 sin etapas de esta sesion; resultado no confirmado.')
                    if require_progress:
                        self.progress({'percent': 100, 'mode': 'determinate', 'basis': 'hitos', 'label': 'Fin informado por el equipo'})
                    return {'estado': 'equipo_informa_fin', 'etapas': seen,
                            'detalle': 'Fin informado por el equipo; no valida mecanica, horizonte ni datos IMU.'}
        if require_progress:
            raise TimeoutError('No se recibio fin de calibracion verificable en 90 s. No se declara exito; salir de modo fabrica al terminar.')
        return {'estado': 'escucha_completada', 'etapas': seen,
                'detalle': 'Escucha pasiva. Sin mensajes no implica averia.'}

    def calibrate(self, action):
        if action not in ('JointCoarse', 'LinearHall'): raise ValueError('Calibracion desconocida')
        self.drain()
        data = self.request(0x0a, 0x04, 4, 8, bytes([1 if action == 'JointCoarse' else 2]))
        self.emit('Respuesta inicial: ' + data.hex(' ') + '. Aun no confirma calibracion.')
        # The original expects 2 payload bytes for JointCoarse, 1 for LinearHall.
        # The user's one-byte echo 01 is not a terminal result. Permit it only
        # as an unconfirmed start and require subsequent matching progress + end.
        if data == b'\xfb' or (action == 'JointCoarse' and len(data) != 2 and data != b'\x01') or (action == 'LinearHall' and data not in (b'\0', b'\x02')):
            raise RuntimeError('Respuesta de inicio no reconocida/aceptada; no se declara calibracion iniciada.')
        stages = {'5201', '5301', '5401', '5501'} if action == 'JointCoarse' else {'1101', '1201', '1401', '1601', '1701'}
        result = self.monitor(90, require_progress=True, expected_stages=stages)
        result['imu_escrita'] = False
        result['salida_fabrica_pendiente'] = True
        result['detalle'] += ' No se escriben coeficientes IMU fijos. Salir de modo fabrica y reiniciar.'
        return result
