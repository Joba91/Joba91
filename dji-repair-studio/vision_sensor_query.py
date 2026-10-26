"""Bounded experimental SN queries, reconstructed independently from evidence.

Only the four observed 24/26 SN requests are exposed. No generic send API,
factory-mode dependency, firmware/configuration writer or retry sequence exists.
The original filter ignores sequence/ACK flags; candidates remain observations,
never authenticated identity, health or confirmed request/reply correlation.
"""
import time
from pathlib import Path
from studio_protocol import checksum,Decoder
from vision_sensor_records import ROLES,decode_perception_record,is_perception_record
from vision_usb_passive import PassiveVisionUsbTransport,DECLARED_FIRMWARE,MAX_BYTES

SELECTORS=(4,8,64,128)
BASELINE_SECONDS=0.6
WINDOW_SECONDS=3.0
MAX_SECONDS=15.0
MAX_READS=10000

def sn_request(selector,sequence):
    if type(selector) is not int or selector not in SELECTORS:
        raise ValueError('Solo se admiten los cuatro selectores SN contrastados.')
    if type(sequence) is not int or not 0<=sequence<=65535:raise ValueError('Secuencia fuera de rango.')
    prefix=b'\x55\x1c\x04'
    body=(prefix+bytes([checksum(prefix,0x77,0x8c)])+b'\x2a\x12'
          +sequence.to_bytes(2,'little')+b'\x40\x24\x26'
          +b'\x0f'+bytes(11)+b'\xa0\x00'+bytes([selector]))
    return body+checksum(body,0x3692,0x8408).to_bytes(2,'little')

class SensorSnTransport(PassiveVisionUsbTransport):
    """Same verified MI04 profile; OUT is limited to a single SN query per selector."""
    def __init__(self):
        super().__init__()
        self.tx_audit=[];self._sent_selectors=set()
        self._sn_out=next(e for e in self.profile_interface if e.bEndpointAddress==4)

    def send_sn_query(self,selector,sequence):
        request=sn_request(selector,sequence)
        if selector in self._sent_selectors:raise ValueError('No se repite una consulta SN en la misma sesión.')
        if self.device is None or not self.claimed:raise RuntimeError('La interfaz MI04 no está abierta.')
        self._sent_selectors.add(selector)
        row={'selector':selector,'sequence':sequence,'hex':request.hex(' '),
             'requested_bytes':len(request),'transferred_bytes':None,'status':'delivery_unknown'}
        self.tx_audit.append(row)
        # A timeout/short write can still have reached the device. Never retry.
        transferred=self._sn_out.write(request,timeout=500)
        row['transferred_bytes']=transferred
        if transferred!=len(request):
            row['status']='short_write_delivery_unknown'
            raise IOError('Envío SN incompleto; se detiene sin repetir la petición.')
        row['status']='transferred'
        return request

class ProbeStopped(Exception):pass

def query_sensor_serials(destination,firmware_declared,cancelled=lambda:False,
                         progress=lambda event:None,transport_factory=None,
                         clock=time.monotonic,sequence_seed=None):
    """Test the observed SN queries in normal mode, retaining RX and TX evidence.

    Normal-mode support on the user's firmware is unvalidated. Even four valid
    serials do not change current_device_confirmed or correlation to true.
    No response does not imply a fault or trigger a mode change.
    """
    if firmware_declared!=DECLARED_FIRMWARE:
        raise ValueError('Esta prueba requiere firmware declarado 01.00.1100 desde DJI Fly.')
    path=Path(destination).absolute()
    if path.suffix.lower()!='.bin':raise ValueError('Elige un archivo NUEVO .bin para conservar la recepción.')
    if cancelled():raise InterruptedError('Consulta detenida antes de abrir USB.')
    if sequence_seed is None:sequence_seed=time.time_ns()&65535
    if type(sequence_seed) is not int or not 0<=sequence_seed<=65535:raise ValueError('Secuencia inicial fuera de rango.')
    transport=None;started=None;size=0;reads=0;decoder=Decoder();frame_count=0
    evidence={};diagnostics=[];error=None;stop_reason=None;completed=False;elapsed=0
    queries=[];baseline=[];other_records=0;tx=[];baseline_pending=0
    def advance(percent,label):
        progress({'mode':'determinate','percent':percent,'basis':'ventanas_de_consulta', 'label':label})
    advance(0,'Abriendo MI04 para prueba SN; sin fábrica ni calibración')
    with path.open('xb') as stream:
        try:
            transport=(transport_factory or SensorSnTransport)();evidence=dict(transport.evidence);started=clock()
            def check():
                if cancelled():raise ProbeStopped('detenida_por_usuario')
                if clock()-started>=MAX_SECONDS:raise ProbeStopped('limite_de_tiempo')
                if size>=MAX_BYTES:raise ProbeStopped('limite_de_bytes')
                if reads>=MAX_READS:raise ProbeStopped('limite_de_lecturas')
            def receive_until(deadline,row=None):
                nonlocal size,reads,frame_count,other_records
                while clock()<deadline:
                    check();chunk=transport.read();reads+=1
                    if len(chunk)>512:raise RuntimeError('La lectura excede el paquete de 512 bytes del perfil.')
                    if len(chunk)>MAX_BYTES-size:raise ProbeStopped('limite_de_bytes')
                    if chunk:stream.write(chunk);size+=len(chunk)
                    for frame in decoder.feed(chunk):
                        frame_count+=1
                        if not is_perception_record(frame):continue
                        record=decode_perception_record(frame[11:-2])
                        observation={**record,'frame_hex':frame.hex(' '),'response_sequence':int.from_bytes(frame[6:8],'little'),
                            'received_seconds':round(clock()-started,4),'receive_batch_end_offset':size,
                            'query_reply_correlation_validated':False,'success_inferred':False,
                            'detail':'SN observado en tráfico actual; no prueba correlación ni salud.'}
                        if row is None:
                            if len(baseline)<20:baseline.append(observation)
                        elif record.get('selector')==row['selector']:
                            observation['seconds_after_query_transfer']=round(clock()-started-row['request_transfer_finished_seconds'],4)
                            observation['request_sequence_equal']=observation['response_sequence']==row['sequence']
                            observation['seen_before_queries']=any(b.get('serial_from_payload')==record.get('serial_from_payload')
                                and b.get('selector')==record.get('selector') for b in baseline)
                            if len(row['observations'])<20:row['observations'].append(observation)
                            row['matching_records']+=1
                            serial=record.get('serial_from_payload')
                            if serial and serial not in row['serials_observed']:
                                if len(row['serials_observed'])<20:row['serials_observed'].append(serial)
                                else:row['distinct_serials_truncated']=True
                        else:other_records+=1
            receive_until(clock()+BASELINE_SECONDS)
            # Never join a partial baseline frame to the first query window.
            baseline_pending=len(decoder.buffer);decoder=Decoder()
            for index,selector in enumerate(SELECTORS):
                check()
                row={'selector':selector,'role_historical':ROLES[selector],'sequence':(sequence_seed+index+1)&65535,
                     'state':'desconocido','query_status':'pending','matching_records':0,'observations':[],
                     'serials_observed':[],'distinct_serials_truncated':False,
                     'current_device_confirmed':False,'device_health':'desconocido'}
                queries.append(row)
                row['query_status']='sending'
                row['request_attempt_seconds']=round(clock()-started,4)
                transport.send_sn_query(selector,row['sequence'])
                row['request_transfer_finished_seconds']=round(clock()-started,4)
                row['query_status']='receiving'
                receive_until(clock()+WINDOW_SECONDS,row)
                row['query_status']='window_completed'
                row['window_finished_seconds']=round(clock()-started,4)
                # Do not carry a previous query's partial frame into the next.
                row['unassigned_pending_bytes']=len(decoder.buffer);decoder=Decoder()
                serials=row['serials_observed'];serials.sort()
                row['observation_status']='ambiguo' if row['distinct_serials_truncated'] or len(serials)>1 else 'sn_observado' if serials else 'sin_registro_identificable'
                advance(min(99,(index+1)*25),f'Ventanas completadas: {index+1}/4; identificación experimental, salud desconocida')
            completed=True;stop_reason='cuatro_ventanas_completadas';stream.flush()
        except ProbeStopped as exc:stop_reason=str(exc)
        except Exception as exc:
            error=str(exc);completed=False;stop_reason='error_de_apertura_envio_o_lectura';diagnostics=getattr(exc,'diagnostics',[])
        finally:
            if transport:
                tx=list(transport.tx_audit)
                if started is not None:elapsed=max(0,clock()-started)
                try:transport.close()
                except Exception as exc:
                    error=(error+'; ' if error else '')+'Error al liberar USB: '+str(exc)
                    completed=False;stop_reason='error_al_cerrar'
    # Partial sessions retain any candidates for inspection, never stale success.
    for row in queries:
        if 'observation_status' not in row:
            row['observation_status']='ventana_incompleta'
    if completed and not error:advance(100,'4/4 ventanas completadas; SN experimentales, salud desconocida')
    observed=sum(bool(q['serials_observed']) for q in queries)
    detail=(f'Prueba SN: {observed}/4 selectores con SN observado; correlación e identificación sin confirmar. '
            +'Salud desconocida. '+('Error: '+error if error else 'No se cambió a modo fábrica ni se inició calibración.'))
    return {'state':'error' if error else 'desconocido','detail':detail,'source':'Consulta SN experimental en modo normal',
        'origin':'live_sn_probe','firmware_declared':firmware_declared,'firmware_read_from_device':False,
        'usb':evidence,'opening_diagnostics':diagnostics,'capture_path':str(path),'received_bytes':size,
        'reception_elapsed_seconds':round(elapsed,3),'probe_completed':completed,'stop_reason':stop_reason,
        'queries':queries,'baseline_observations':baseline,'baseline_pending_bytes_unassigned':baseline_pending,'other_selector_records':other_records,
        'tx_audit':tx,'protocol_commands_attempted':len(tx),'protocol_commands_sent':sum(t['status']=='transferred' for t in tx),
        'bulk_out_bytes_confirmed':sum(t['transferred_bytes'] or 0 for t in tx),
        'bulk_out_delivery_unknown':any(t['status']!='transferred' for t in tx),
        'bulk_in_attempts':reads,'bulk_in_timeouts':getattr(transport,'timeouts',0),'valid_frames_received':frame_count,
        'device_configuration_writes':0,'factory_commands_sent':0,'calibration_commands_sent':0,'driver_changes':0,
        'query_reply_correlation_validated':False,'current_device_confirmed':False,
        'normal_mode_firmware_support_validated':False,'device_health':'desconocido',
        'error':error,'max_bytes':MAX_BYTES,'max_seconds_after_open':MAX_SECONDS}
