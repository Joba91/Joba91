"""Single-shot experimental common DUML gimbal calibration for declared Flip.

The 04/08 command and 04/30 reports are known on other DJI gimbals. Flip
compatibility is unverified. No factory scripts, coefficient tables or retries.
A saved two-module query and a fresh matching preflight are required.
"""
import hashlib
import json
import re
import time
from pathlib import Path
from zipfile import ZipFile
from gimbal_profiles import FLIP
from flip_gimbal_query import FlipVersionTransport
from studio_protocol import Client,Decoder,version_request,is_version_reply
from studio_service import packet
from studio_version import VERSION
from vision_support_bundle import write_support_bundle

ROUTINES={'JointCoarse':1,'LinearHall':2}
STAGES={'JointCoarse':{'5101','5201','5301','5401','5501'},'LinearHall':{'0101','1101','1201','1401','1601','1701'}}
MAX_RX=1024*1024


def load_calibration_reference(path,firmware):
    if firmware!='01.00.1500':raise ValueError('La prueba Flip está preparada solo para el firmware declarado 01.00.1500.')
    path=Path(path)
    if not path.is_file() or path.stat().st_size>4*1024**2:raise ValueError('Elige el ZIP DJIFlip-Modulos de una consulta completada.')
    with ZipFile(path) as z:
        if len(z.infolist())>8 or z.namelist().count('DJI-REPAIR-informe.json')!=1:raise ValueError('Informe de módulos ambiguo.')
        info=z.getinfo('DJI-REPAIR-informe.json')
        bins=[i for i in z.infolist() if i.filename.lower().endswith('.bin')]
        if info.file_size>1024**2 or len(bins)!=1 or bins[0].file_size>65536:raise ValueError('Informe/captura de módulos fuera del límite.')
        report=json.loads(z.read(info));raw=z.read(bins[0])
    if not isinstance(report,dict) or report.get('modelo_declarado')!=FLIP or report.get('firmware_declarado')!=firmware:
        raise ValueError('Se requiere una consulta del DJI Flip con firmware declarado 01.00.1500.')
    q=report.get('gimbal',{}).get('module_query',{})
    if q.get('state')!='confirmado' or q.get('calibration_performed') is not False or q.get('factory_commands_sent')!=0 or q.get('gimbal_calibration_commands_sent')!=0:
        raise ValueError('La referencia debe ser una consulta de versiones sin calibración/fábrica.')
    evidence=q.get('usb_evidence',{});parent=evidence.get('parent_metadata',{})
    if (evidence.get('interface'),evidence.get('bulk_out'),evidence.get('bulk_in'),evidence.get('packet_size'))!=(4,'04','85',512) or evidence.get('reference_metadata_matches') is not True:
        raise ValueError('La referencia no acredita la apertura de MI04 esperada.')
    if not isinstance(parent.get('product'),str) or not 1<=len(parent['product'])<=512:raise ValueError('Producto USB de referencia inválido.')
    for key in ('child_instance_sha256','parent_instance_sha256'):
        if not isinstance(parent.get(key),str) or not re.fullmatch('[0-9a-f]{64}',parent[key]):raise ValueError('Faltan hashes de asociación al dispositivo.')
    audit=q.get('packet_audit',[])
    if not isinstance(audit,list) or len(audit)!=4:raise ValueError('Se requieren dos consultas y sus respuestas correlacionadas.')
    frames=Decoder().feed(raw);payloads={}
    for index,receiver in ((0,3),(2,4)):
        tx,rx=audit[index:index+2]
        if tx.get('direccion')!='TX' or rx.get('direccion')!='RX':raise ValueError('Orden de auditoría no admitido.')
        req=bytes.fromhex(tx['hex']);reply=bytes.fromhex(rx['hex'])
        if len(req)!=13:raise ValueError('Petición de versión inválida.')
        seq=int.from_bytes(req[6:8],'little')
        if req!=version_request(receiver,seq) or reply not in frames or not is_version_reply(reply,receiver,seq) or len(reply[11:-2])<26:
            raise ValueError('CRC, destino, secuencia o captura de referencia no coinciden.')
        payloads[receiver]=reply[11:-2][:26]
    return {**{k:parent[k] for k in ('product','child_instance_sha256','parent_instance_sha256')},
            'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'version_payloads':payloads}


class FlipCalibrationTransport(FlipVersionTransport):
    def __init__(self,reference,routine,**kwargs):
        if routine not in ROUTINES:raise ValueError('Rutina de prueba no admitida.')
        self.routine=routine;self.armed=False;self.cal_attempts=[];self.cal_confirmed=[];self.cal_uncertain=False
        super().__init__(reference,**kwargs);self.rx_limit=MAX_RX
        self.evidence['calibration_commands_enabled']='single experimental request after preflight'

    def arm(self):
        if len(self.tx_confirmed)!=2 or {r[5] for r in self.tx_confirmed}!={3,4}:
            raise ValueError('Faltan las dos consultas de versión previas.')
        self.armed=True

    def write(self,data):
        data=bytes(data)
        if len(data)==13:return super().write(data)
        if len(data)!=14 or data!=packet(10,4,int.from_bytes(data[6:8],'little'),4,8,bytes([ROUTINES[self.routine]])):
            raise ValueError('Solo se admite una petición de la rutina elegida; fábrica y otros paquetes no están habilitados.')
        if not self.armed or self.cal_attempts:raise ValueError('Prueba no preparada o ya enviada; no se reenvía.')
        self.cal_attempts.append(data)
        try:
            count=self.ep_out.write(data,timeout=500)
            if count!=len(data):raise OSError('Entrega incompleta/incierta de la petición de calibración; no se reenvía.')
        except Exception:self.cal_uncertain=True;raise
        self.cal_confirmed.append(data);return count


def is_report(frame):
    return frame[4:6]==b'\x04\x0a' and frame[9:11]==b'\x04\x30' and not frame[8]&7


def run_flip_calibration(destination,module_zip,firmware,routine,cancelled=lambda:False,progress=lambda e:None,
                         transport_factory=FlipCalibrationTransport,clock=time.monotonic,max_seconds=180):
    if routine not in ROUTINES:raise ValueError('Elige JointCoarse o LinearHall.')
    if not 1<=max_seconds<=180:raise ValueError('Límite de monitorización no admitido.')
    reference=load_calibration_reference(module_zip,firmware)
    path=Path(destination).absolute();capture=path.with_suffix('.bin')
    if path.suffix.lower()!='.zip' or path.exists() or capture.exists() or not path.parent.is_dir():
        raise ValueError('Elige un ZIP nuevo y un BIN asociado que no exista.')
    result={'state':'desconocido','routine':routine,'experimental':True,'flip_compatibility_validated':False,
            'model_declared':FLIP,'firmware_declared':firmware,'model_identity_confirmed':False,
            'reference_module_zip_sha256':reference['source_sha256'],'factory_commands_sent':0,
            'fixed_imu_coefficients_written':False,'firmware_parameter_persistence_known':False,
            'calibration_performed':False,'calibration_requests_attempted':0,'calibration_requests_bulk_complete':0,
            'calibration_delivery_uncertain':False,'device_reported_completion':False,'device_reported_failure':False,
            'ack_received':False,'ack_allowed_by_probe_policy':False,'progress_reports':[],'unknown_reports':[],
            'packet_audit':[],'report_count':0,'report_preview_limit':300,'audit_preview_limit':1024,'monitor_limit_seconds':max_seconds,'support_bundle':str(path),'capture_path':str(capture),'stop_command_sent':False}
    t=None;client=None;received=b'';sequence=None
    def audit(record):
        if len(result['packet_audit'])<1024:result['packet_audit'].append(record)
        else:result['audit_preview_truncated']=True
    def check():
        if cancelled():raise InterruptedError('Lectura detenida; no se envía una orden de parada al gimbal.')
    def event(percent,label):progress({'mode':'determinate','percent':percent,'basis':'hitos_de_comunicacion','label':label})
    with capture.open('xb') as stream:
        try:
            check();progress({'mode':'indeterminate','label':'Comprobando equipo y versiones antes de la prueba'})
            t=transport_factory(reference,routine);client=Client(t,timeout=3,retries=1,clock=clock,cancelled=cancelled)
            for name,receiver in (('Controlador',3),('Gimbal',4)):
                row=client.query(name)
                if row['estado']!='version_recibida':raise RuntimeError('Falta una versión reconocida antes de la prueba: '+name)
                replies=[bytes.fromhex(x['hex']) for x in client.packets if x['direccion']=='RX' and x['modulo']==name]
                if len(replies)!=1 or replies[0][11:-2][:26]!=reference['version_payloads'][receiver]:
                    raise RuntimeError('La versión/hardware actual no coincide con la consulta de referencia. No se envió calibración.')
            result['fresh_versions_match']=True;event(25,'Versiones actuales coincidentes · 1/4 hitos de comunicación')
            # Include traffic already read by Client; never attribute an earlier calibration to this request.
            d=Decoder();prior=d.feed(bytes(t.rx));deadline=clock()+.4
            while clock()<deadline:
                check();prior.extend(d.feed(t.read()))
            if any(is_report(f) and len(f[11:-2])==2 and f[12]==1 for f in prior):
                raise RuntimeError('Ya hay informes de actividad de calibración antes de la solicitud. No se inicia otra prueba.')
            check();t.arm();sequence=(time.time_ns()&65535)
            request=packet(10,4,sequence,4,8,bytes([ROUTINES[routine]]))
            result['packet_audit']=list(client.packets)+[{'direccion':'TX','modulo':'Gimbal','hex':request.hex(' ')}]
            result['calibration_performed']=None
            t.write(request);result['calibration_request_sequence']=sequence
            event(50,'Petición única entregada por USB · 2/4 hitos; inicio aún sin confirmar')
            decoder=Decoder();deadline=clock()+max_seconds;recognized=set();finish=False
            while clock()<deadline:
                check()
                for frame in decoder.feed(t.read()):
                    if frame[4:6]!=b'\x04\x0a' or frame[8]&7:continue
                    data=frame[11:-2]
                    if frame[9:11]==b'\x04\x08' and frame[8]&128 and int.from_bytes(frame[6:8],'little')==sequence:
                        result['ack_received']=True;result['ack_payload']=data.hex(' ')
                        result['ack_allowed_by_probe_policy']=data in ((b'\0',b'\1') if routine=='JointCoarse' else (b'\0',b'\1',b'\2'))
                        audit({'direccion':'RX','type':'initial_ack','hex':frame.hex(' ')})
                        if data==b'\xfb':
                            result.update(state='inicio_no_confirmado',detail='Respuesta inicial FB: esta prueba no confirma inicio. No se reenvía ni se cambia el modo de fábrica.');finish=True;break
                    elif is_report(frame):
                        result['report_count']+=1
                        audit({'direccion':'RX','type':'asynchronous_report','hex':frame.hex(' ')})
                        if data.hex() in STAGES[routine]:
                            first_progress=not recognized;recognized.add(data.hex())
                            if len(result['progress_reports'])<300:result['progress_reports'].append(data.hex())
                            if first_progress:event(75,'Progreso posterior a la petición observado · 3/4 hitos de comunicación')
                        elif data==b'\x64\x03':
                            result.update(state='fallo_informado_por_equipo',device_reported_failure=True,
                                detail='El equipo emitió 64 03 después de la petición. No se asigna una causa física.');finish=True;break
                        elif data==b'\x64\0':
                            result['device_reported_completion']=True
                            if recognized and result['ack_allowed_by_probe_policy']:
                                result.update(state='equipo_informa_fin',detail='ACK correlacionado, progreso posterior y fin 64 00 observados. No valida exactitud mecánica ni metrológica.');finish=True;break
                            result.update(state='fin_no_confirmado',detail='Se observó 64 00 sin inicio/progreso suficiente para esta prueba. No se declara éxito.');finish=True;break
                        else:
                            if len(result['unknown_reports'])<300:result['unknown_reports'].append(data.hex())
                if finish:break
            if not finish:result.update(state='tiempo_agotado',detail='Monitorización agotada sin fin verificable. No se reenvía, cambia de modo o declara calibración completada.')
        except Exception as exc:
            result.update(state='lectura_detenida' if isinstance(exc,InterruptedError) else 'error',detail=str(exc),error=str(exc))
            if hasattr(exc,'flip_evidence'):result['usb_evidence']=exc.flip_evidence
        finally:
            if client and not result['packet_audit']:result['packet_audit']=client.packets
            if t:
                received=bytes(t.rx)
                result.update(usb_evidence=t.evidence,version_requests_attempted=len(t.tx_attempts),
                    calibration_requests_attempted=len(t.cal_attempts),calibration_requests_bulk_complete=len(t.cal_confirmed),
                    calibration_delivery_uncertain=t.cal_uncertain,bulk_out_bytes_complete=sum(map(len,t.tx_confirmed+t.cal_confirmed)))
                result['calibration_performed']=None if t.cal_attempts else False
                try:t.close()
                except Exception as exc:result.update(state='error',cleanup_error=str(exc));result['detail']+=' Error al cerrar: '+str(exc)
            stream.write(received)
    result['rx_bytes']=len(received)
    write_support_bundle(capture,{'herramienta':'DJI REPAIR Studio','version':VERSION,'fecha_unix':time.time(),
        'modelo_declarado':FLIP,'firmware_declarado':firmware,'gimbal':{'calibration_probe':result}})
    if result['state']=='equipo_informa_fin':event(100,'Fin informado por el equipo y ZIP guardado · 4/4 hitos; prueba experimental')
    result['detail']+=' Archivo para compartir: '+str(path)
    return result
