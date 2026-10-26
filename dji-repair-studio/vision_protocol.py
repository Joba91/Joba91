"""Bounded offline framing diagnostics. Unknown payloads remain opaque."""
import re
from pathlib import Path
from studio_protocol import checksum
from vision_history import analyze_dji_log, is_dji_log
from vision_sensor_records import decode_perception_record, is_perception_record
from collections import Counter
from vision_hms import HmsTracker

MAX_CAPTURE = 32 * 1024**2
MAX_FRAMES = 100000
PREVIEW = 200

class CaptureDecoder:
    def __init__(self):
        self.buffer=bytearray();self.offset=0;self.frames=[];self.total_frames=0
        self.issues=[];self.issue_count=0;self.discarded=0;self.sequence_frames=set()
        self.perception=[];self.perception_counts=Counter()
        self.hms=HmsTracker()

    def issue(self,kind,detail):
        self.issue_count+=1
        if self.issue_count>200000:raise ValueError('Demasiados errores de trama; analiza un fragmento menor')
        if len(self.issues)<PREVIEW:self.issues.append({'offset':self.offset,'kind':kind,'detail':detail})

    def drop(self,n):
        del self.buffer[:n];self.offset+=n;self.discarded+=n

    def feed(self,data,final=False,cancelled=lambda:False):
        self.buffer.extend(data)
        while self.buffer:
            if cancelled():raise InterruptedError('Análisis local detenido')
            start=self.buffer.find(0x55)
            if start<0:
                self.issue('ruido','Bytes sin inicio 55');self.drop(len(self.buffer));break
            if start:
                self.issue('ruido','Bytes anteriores al inicio 55');self.drop(start)
            if len(self.buffer)<4:
                if final:self.issue('truncada','Cabecera incompleta');self.drop(len(self.buffer))
                break
            size=int.from_bytes(self.buffer[1:3],'little') & 0x03ff
            if size<13:
                self.issue('longitud_invalida',f'Longitud declarada {size}, mínimo 13');self.drop(1);continue
            if checksum(self.buffer[:3],0x77,0x8c)!=self.buffer[3]:
                self.issue('crc_cabecera','CRC8 no coincide');self.drop(1);continue
            if len(self.buffer)<size:
                if not final:break
                self.issue('truncada',f'Se declaran {size} bytes; quedan {len(self.buffer)}')
                # At EOF allow a later independently valid frame to be recovered.
                self.drop(1);continue
            frame=bytes(self.buffer[:size])
            if checksum(frame[:-2],0x3692,0x8408)!=int.from_bytes(frame[-2:],'little'):
                self.issue('crc_trama','CRC16 no coincide o longitud declarada incorrecta');self.drop(1);continue
            self.total_frames+=1
            if self.total_frames>MAX_FRAMES:raise ValueError('Captura supera 100000 tramas; analiza un fragmento menor')
            self.sequence_frames.add(frame)
            self.hms.observe(frame)
            if is_perception_record(frame):
                record=decode_perception_record(frame[11:-2])
                self.perception_counts['records']+=1
                self.perception_counts['decoded' if record['state']=='confirmado' else 'unknown_layout_or_invalid_serial']+=1
                record.update(line=f'offset {self.offset}',offset=self.offset,
                    label_comparison='sin_etiqueta_contrastable',header_correlation_confirmed=False,success_inferred=False)
                if len(self.perception)<PREVIEW:self.perception.append(record)
            if len(self.frames)<PREVIEW:
                self.frames.append({'offset':self.offset,'length':size,'header_version_bits':frame[2]>>2,
                    'sender_raw':f'{frame[4]:02x}','receiver_raw':f'{frame[5]:02x}',
                    'sequence_raw':int.from_bytes(frame[6:8],'little'),'flags_raw':f'{frame[8]:02x}',
                    'command_set_raw':f'{frame[9]:02x}','command_id_raw':f'{frame[10]:02x}',
                    'payload_raw':frame[11:-2].hex(' '),'hex':frame.hex(' '),
                    'command_meaning':'desconocido','crc8_valid':True,'crc16_valid':True})
            del self.buffer[:size];self.offset+=size

    def result(self):
        return {'state':'error' if self.issue_count else ('confirmado' if self.total_frames else 'desconocido'),
                'valid_frames':self.total_frames,'distinct_frames':len(self.sequence_frames),
                'issue_count':self.issue_count,'discarded_bytes':self.discarded,'pending_bytes':len(self.buffer),
                'frames_preview':self.frames,'issues_preview':self.issues,'preview_limit':PREVIEW,
                'hms':self.hms.result(),
                'perception_records':{'counts':dict(self.perception_counts),'observations_preview':self.perception,
                    'preview_limit':PREVIEW,'current_device_confirmed':False,
                    'detail':'Conversión del formato binario observado; no valida consulta, salud o compatibilidad.'},
                'identity':{'state':'desconocido','detail':'Las tramas no identifican por sí solas el dron o los sensores.'},
                'detail':'Solo estructura y CRC; no se infieren comandos, salud ni compatibilidad óptica.'}

def decode_bytes(data, cancelled=lambda:False):
    if len(data)>MAX_CAPTURE:raise ValueError('Captura supera 32 MiB')
    decoder=CaptureDecoder();decoder.feed(data,final=True,cancelled=cancelled);return decoder.result()

def _hex_runs(line):
    # Remove the ASCII column of common hex dumps; ignore timestamps before 55.
    line=line.split('|',1)[0]
    # A continuation can contain 55 in its payload: preserve the whole dump row.
    plain=re.sub(r'^\s*[0-9a-fA-F]{4,16}:\s*','',line)
    if re.fullmatch(r'\s*(?:[0-9a-fA-F]{2}[ \t]*)+\s*',plain):return bytes.fromhex(plain)
    pattern=re.compile(r'(?:[0-9a-fA-F]{2}(?:[ \t]+|(?=[0-9a-fA-F]{2})|$))+')
    short=b''
    for marker in re.finditer(r'(?<![0-9a-fA-F])55(?=\s|[0-9a-fA-F]{2}|$)',line):
        match=pattern.match(line,marker.start())
        if not match:continue
        data=bytes.fromhex(match.group())
        # A timestamp ending in :55 is not the packet when RX/TX follows it.
        if len(data)>=4:return data
        short=data
    return short

def analyze_capture(path, format='auto', cancelled=lambda:False):
    source=Path(path).expanduser().absolute()
    with source.open('rb') as stream:data=stream.read(MAX_CAPTURE+1)
    if len(data)>MAX_CAPTURE:raise ValueError('Captura supera 32 MiB')
    if format not in ('auto','binary','hexlog','djilog'):raise ValueError('Formato de captura no admitido')
    if format=='auto':
        # Raw captures can be printable; .bin/.raw forces binary rather than guessing.
        format='binary' if source.suffix.lower() in ('.bin','.raw','.dump') else 'hexlog' if data.startswith((b'\xff\xfe',b'\xfe\xff')) else 'binary' if b'\0' in data else 'hexlog'
    ignored=0;extracted=bytearray();lines=0
    encoding=None
    if format in ('hexlog','djilog'):
        if data.startswith((b'\xff\xfe',b'\xfe\xff')):text=data.decode('utf-16');encoding='utf-16'
        else:
            try:text=data.decode('utf-8-sig');encoding='utf-8-sig'
            except UnicodeDecodeError:
                try:text=data.decode('gb18030');encoding='gb18030'
                except UnicodeDecodeError:text=data.decode('utf-8-sig',errors='replace');encoding='utf-8-replaced'
        if format=='djilog' or is_dji_log(text):
            result=analyze_dji_log(text,cancelled)
            result.update(source=str(source),format='djilog',encoding=encoding,source_bytes=len(data),lines=len(text.splitlines()),
                initial_150_ack_claim='El contador usa ACK etiquetados de este archivo; no implica respuestas exitosas ni validación del equipo actual.')
            return result
        for line in text.splitlines():
            if cancelled():raise InterruptedError('Análisis de registro detenido')
            lines+=1;chunk=_hex_runs(line)
            if chunk:extracted.extend(chunk)
            elif line.strip():ignored+=1
        raw=bytes(extracted)
    else:raw=data
    result=decode_bytes(raw,cancelled)
    result.update(source=str(source),format=format,encoding=encoding,source_bytes=len(data),analyzed_bytes=len(raw),
                  lines=lines,ignored_text_lines=ignored,
                  declared_historical_usb={'state':'desconocido',
                    'detail':'Una captura de bytes no acredita por sí sola VID/PID, interfaz o endpoints del equipo actual.'},
                  initial_150_ack_claim='Sin verificar en esta captura: el recuento histórico de ACK no se atribuye a bytes sin etiquetas.')
    if not raw:result['detail']='No se encontraron bytes HEX reconocibles. Prueba otro formato; no se interpreta como captura sana.'
    return result
