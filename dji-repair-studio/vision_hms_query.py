"""Experimental HMS subscription to the native tool's endpoint, no reset-all.

Exactly one 0a->1d, 21/05, payload 01 request. No retries, unsubscribe/global
reset (payload 00), factory, calibration or arbitrary writes. Data are observed
for eight seconds; future publication after closing the connection is unverified.
"""
import time
from pathlib import Path
from studio_protocol import checksum,Decoder
from vision_usb_passive import PassiveVisionUsbTransport,DECLARED_FIRMWARE,MAX_BYTES
from vision_hms import HmsTracker

LISTEN_SECONDS=8.0
MAX_READS=10000

def hms_subscription_request(sequence):
    if type(sequence) is not int or not 0<=sequence<=65535:raise ValueError('Secuencia fuera de rango.')
    prefix=b'\x55\x0e\x04'
    body=prefix+bytes([checksum(prefix,0x77,0x8c)])+b'\x0a\x1d'+sequence.to_bytes(2,'little')+b'\x40\x21\x05\x01'
    return body+checksum(body,0x3692,0x8408).to_bytes(2,'little')

class HmsTransport(PassiveVisionUsbTransport):
    def __init__(self):
        super().__init__();self.tx_audit=[];self._attempted=False
        self._hms_out=next(e for e in self.profile_interface if e.bEndpointAddress==4)
    def subscribe_hms(self,sequence):
        request=hms_subscription_request(sequence)
        if self._attempted:raise ValueError('La petición HMS no se repite en esta sesión.')
        if self.device is None or not self.claimed:raise RuntimeError('MI04 no está abierta.')
        self._attempted=True
        row={'hex':request.hex(' '),'sequence':sequence,'requested_bytes':14,
            'transferred_bytes':None,'status':'delivery_unknown'}
        self.tx_audit.append(row)
        count=self._hms_out.write(request,timeout=500);row['transferred_bytes']=count
        if count!=14:
            row['status']='short_write_delivery_unknown';raise IOError('Envío HMS incompleto; sin reintento.')
        row['status']='transferred';return request

def probe_hms(destination,firmware_declared,cancelled=lambda:False,progress=lambda event:None,
              transport_factory=None,clock=time.monotonic,sequence_seed=None):
    if firmware_declared!=DECLARED_FIRMWARE:raise ValueError('Declara el firmware 01.00.1100 de DJI Fly para esta prueba HMS.')
    path=Path(destination).absolute()
    if path.suffix.lower()!='.bin':raise ValueError('Se necesita un archivo NUEVO .bin para la recepción HMS.')
    if cancelled():raise InterruptedError('HMS detenido antes de abrir USB.')
    sequence=(time.time_ns()&65535) if sequence_seed is None else sequence_seed
    hms_subscription_request(sequence)  # Validate before file creation or USB.
    tracker=HmsTracker();decoder=Decoder();transport=None;evidence={};diagnostics=[];tx=[];acks=[]
    size=0;reads=0;start=None;elapsed=0;error=None;reason=None;completed=False;foreign=0;valid_frames=0
    def advance(value,label):progress({'mode':'determinate','percent':value,'basis':'tiempo_de_escucha_hms','label':label})
    advance(0,'Abriendo MI04 para prueba HMS; publicación de estados, sin fábrica ni calibración')
    with path.open('xb') as stream:
        try:
            transport=(transport_factory or HmsTransport)();evidence=dict(transport.evidence)
            if cancelled():reason='detenida_por_usuario'
            else:
                transport.subscribe_hms(sequence);start=clock();last=-1
                while True:
                    elapsed=max(0,clock()-start)
                    if cancelled():reason='detenida_por_usuario';break
                    if elapsed>=LISTEN_SECONDS:completed=True;reason='tiempo_cumplido';break
                    if size>=MAX_BYTES:reason='limite_de_bytes';break
                    if reads>=MAX_READS:reason='limite_de_lecturas';break
                    chunk=transport.read();reads+=1
                    if len(chunk)>512:raise RuntimeError('La lectura supera el tamaño de paquete USB previsto.')
                    if len(chunk)>MAX_BYTES-size:reason='limite_de_bytes';break
                    if chunk:stream.write(chunk);size+=len(chunk)
                    rejected=False
                    for frame in decoder.feed(chunk):
                        valid_frames+=1
                        if frame[9:11]==b'\x21\x06':
                            if frame[5]==0x0a:tracker.observe(frame)
                            else:foreign+=1
                        if (frame[4:6]==b'\x1d\x0a' and frame[9:11]==b'\x21\x05'
                                and frame[8]&0x80 and frame[8]&7==0):
                            payload=frame[11:-2];same=int.from_bytes(frame[6:8],'little')==sequence
                            ack={'frame_hex':frame.hex(' '),'sequence_matches':same,
                                'return_code_raw':payload[0] if len(payload)==1 else None,
                                'received_seconds':round(clock()-start,4)}
                            if len(acks)<20:acks.append(ack)
                            if same and len(payload)==1 and payload[0]!=0:rejected=True
                    if rejected:reason='suscripcion_rechazada';error='El servicio HMS rechazó la petición; se conserva su código.';break
                    value=min(99,int(max(0,clock()-start)/LISTEN_SECONDS*100))
                    if value!=last:
                        advance(value,f'Escucha HMS: {size} bytes; porcentaje de tiempo, salud desconocida');last=value
                stream.flush()
        except Exception as exc:
            error=str(exc);completed=False;reason='error_de_apertura_envio_o_lectura';diagnostics=getattr(exc,'diagnostics',[])
        finally:
            if transport:
                tx=list(transport.tx_audit)
                if start is not None:elapsed=max(0,clock()-start)
                try:transport.close()
                except Exception as exc:
                    error=(error+'; ' if error else '')+'Error al liberar USB: '+str(exc);completed=False;reason='error_al_cerrar'
    if completed and not error:advance(100,'Tiempo de escucha HMS completado; salud y calibración sin determinar')
    hms=tracker.result();detail=hms['detail']+(' Error: '+error if error else '')
    return {'state':'error' if error else 'desconocido','detail':detail,'origin':'live_hms_probe',
        'source':'Solicitud de publicación HMS experimental en modo normal','hms':hms,
        'capture_path':str(path),'firmware_declared':firmware_declared,'firmware_read_from_device':False,
        'usb':evidence,'opening_diagnostics':diagnostics,'tx_audit':tx,'subscription_ack_observations':acks,
        'subscription_accepted_by_matching_ack':any(a['sequence_matches'] and a['return_code_raw']==0 for a in acks),
        'protocol_commands_attempted':len(tx),'protocol_commands_sent':sum(t['status']=='transferred' for t in tx),
        'bulk_out_bytes_confirmed':sum(t['transferred_bytes'] or 0 for t in tx),
        'bulk_out_delivery_unknown':any(t['status']!='transferred' for t in tx),
        'received_bytes':size,'valid_frames_received':valid_frames,'bulk_in_attempts':reads,
        'bulk_in_timeouts':getattr(transport,'timeouts',0),'foreign_recipient_hms_packets':foreign,
        'listen_seconds':LISTEN_SECONDS,'elapsed_seconds':round(elapsed,3),'probe_completed':completed,
        'stop_reason':reason,'error':error,'device_health':'desconocido','calibration_status':'desconocido',
        'hms_support_validated_on_mini4':False,'subscription_status_after_close':'desconocido',
        'global_unsubscribe_commands_sent':0,'device_configuration_writes':0,'factory_commands_sent':0,
        'calibration_commands_sent':0,'driver_changes':0,'max_bytes':MAX_BYTES}
