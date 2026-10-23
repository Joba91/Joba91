"""Read-only DUML v1 version requests. No motor or calibration commands."""
import struct
import time

MODULES = {'Controlador': 3, 'Gimbal': 4, 'Camara': 1, 'Bateria': 11}

def checksum(data, seed, polynomial):
    for value in data:
        seed ^= value
        for _ in range(8):
            seed = (seed >> 1) ^ polynomial if seed & 1 else seed >> 1
    return seed

def version_request(receiver, sequence):
    if receiver not in MODULES.values():
        raise ValueError('Destino no admitido')
    prefix = b'\x55\x0d\x04'
    header = prefix + bytes([checksum(prefix, 0x77, 0x8c)])
    packet = header + bytes([10, receiver]) + struct.pack('<H', sequence) + b'\x40\x00\x01'
    return packet + struct.pack('<H', checksum(packet, 0x3692, 0x8408))

class Decoder:
    def __init__(self):
        self.buffer = bytearray()
        self.invalid = 0

    def feed(self, data):
        self.buffer.extend(data)
        frames = []
        while self.buffer:
            start = self.buffer.find(0x55)
            if start < 0:
                self.buffer.clear()
                break
            del self.buffer[:start]
            if len(self.buffer) < 4:
                break
            size_version = int.from_bytes(self.buffer[1:3], 'little')
            size = size_version & 1023
            if size_version >> 10 != 1 or size < 13 or checksum(self.buffer[:3], 0x77, 0x8c) != self.buffer[3]:
                self.invalid += 1
                del self.buffer[0]
                continue
            if len(self.buffer) < size:
                break
            frame = bytes(self.buffer[:size])
            if checksum(frame[:-2], 0x3692, 0x8408) != int.from_bytes(frame[-2:], 'little'):
                self.invalid += 1
                del self.buffer[0]
                continue
            del self.buffer[:size]
            frames.append(frame)
        return frames

def is_version_reply(frame, receiver, sequence):
    return (len(frame) >= 13 and frame[4] == receiver and frame[5] == 10
            and int.from_bytes(frame[6:8], 'little') == sequence
            and frame[8] & 0x80 and frame[8] & 7 == 0 and frame[9:11] == b'\x00\x01')

def format_version(value):
    return f'{value >> 24:02d}.{(value >> 16) & 255:02d}.{value & 65535:04d}'

def parse_version(frame):
    data = frame[11:-2]
    if len(data) < 26:
        raise ValueError('Respuesta de version demasiado corta; se conserva el paquete en el informe')
    # Layout observed in the supplied project's version decoder. These are module
    # versions, not a confirmed marketing model or the DJI Fly firmware bundle.
    return {'hardware': data[2:18].split(b'\0', 1)[0].decode('ascii', errors='replace') or '-',
            'loader': format_version(int.from_bytes(data[18:22], 'little')),
            'firmware_modulo': format_version(int.from_bytes(data[22:26], 'little')),
            'prefijo_sin_interpretar': data[:2].hex()}

class Client:
    def __init__(self, transport, timeout=2, retries=3, clock=time.monotonic, cancelled=lambda: False, emit=lambda value: None):
        self.transport = transport
        self.cancelled = cancelled
        self.emit = emit
        self.timeout = timeout
        self.retries = retries
        self.clock = clock
        self.sequence = time.time_ns() & 65535
        self.decoder = Decoder()
        self.packets = []

    def query(self, name):
        receiver = MODULES[name]
        for attempt in range(self.retries):
            if self.cancelled(): raise InterruptedError("Consulta detenida")
            self.sequence = (self.sequence + 1) & 65535
            request = version_request(receiver, self.sequence)
            self.packets.append({'direccion': 'TX', 'modulo': name, 'hex': request.hex(' ')})
            self.emit('TX '+request.hex(' '))
            self.transport.write(request)
            deadline = self.clock() + self.timeout
            while self.clock() < deadline:
                if self.cancelled(): raise InterruptedError("Consulta detenida")
                for frame in self.decoder.feed(self.transport.read()):
                    # Unrelated USB traffic is not retained as module information.
                    if not is_version_reply(frame, receiver, self.sequence):
                        continue
                    self.packets.append({'direccion': 'RX', 'modulo': name, 'hex': frame.hex(' ')})
                    self.emit('RX '+frame.hex(' '))
                    try:
                        result = parse_version(frame)
                    except ValueError as exc:
                        return {'modulo': name, 'estado': 'formato_no_reconocido', 'detalle': str(exc)}
                    return {'modulo': name, 'estado': 'version_recibida', **result}
        return {'modulo': name, 'estado': 'sin_respuesta', 'intentos': self.retries}
