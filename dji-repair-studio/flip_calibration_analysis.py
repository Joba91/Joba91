"""Bounded offline review of Flip trial ZIPs; never opens a device.

The common reference enum names 04 TIMEOUT. This is a reference-based
interpretation, not a verified Flip-specific fault or axis diagnosis.
"""
import hashlib
import json
from collections import Counter
from pathlib import Path
from zipfile import ZipFile
from studio_protocol import Decoder
from studio_service import packet
from gimbal_profiles import FLIP

STATUS_REFERENCE='https://github.com/EmoLa63/DJI_Fly_1.21.4_Decompiled/blob/0eecc6cd8d9905acccb7965c2361dd05fa3c2908/smali_classes8/uav/sdk/keyvalue/value/gimbal/GimbalCommonCalibrationStatus.smali'

def status_reference(payload):
    if payload!=b'\x64\x04':return None
    return {'raw_payload':'6404','common_status':4,'common_name':'TIMEOUT',
            'source':STATUS_REFERENCE,'flip_mapping_validated':False,
            'physical_cause_confirmed':False}

def analyze_flip_trial(path):
    path=Path(path)
    if not path.is_file() or path.stat().st_size>4*1024**2:
        raise ValueError('Elige un ZIP de prueba Flip de hasta 4 MiB.')
    with ZipFile(path) as z:
        infos=z.infolist();names=z.namelist()
        if len(infos)>8 or names.count('DJI-REPAIR-informe.json')!=1:
            raise ValueError('Se requiere un informe único de una prueba Flip.')
        info=z.getinfo('DJI-REPAIR-informe.json');bins=[i for i in infos if i.filename.lower().endswith('.bin')]
        if info.file_size>1024**2 or len(bins)!=1 or bins[0].file_size>1024**2:
            raise ValueError('El informe o el BIN supera el límite de análisis.')
        report=json.loads(z.read(info));raw=z.read(bins[0])
    if not isinstance(report,dict) or report.get('modelo_declarado')!=FLIP:
        raise ValueError('El archivo no es una prueba declarada del DJI Flip.')
    gimbal=report.get('gimbal');q=gimbal.get('calibration_probe') if isinstance(gimbal,dict) else None
    if not isinstance(q,dict) or q.get('routine') not in ('JointCoarse','LinearHall'):
        raise ValueError('Selecciona el ZIP de JointCoarse o LinearHall; no el de módulos o perfil USB.')
    audit=q.get('packet_audit')
    if not isinstance(audit,list) or len(audit)>1024 or any(not isinstance(a,dict) for a in audit):
        raise ValueError('Auditoría de la prueba no válida.')
    requests=[];routine=q['routine'];value=1 if routine=='JointCoarse' else 2
    for a in audit:
        if a.get('direccion')!='TX':continue
        h=a.get('hex')
        if not isinstance(h,str) or len(h)>4096:raise ValueError('Petición de auditoría inválida.')
        req=bytes.fromhex(h)
        if len(req)>=11 and req[9:11]==b'\x04\x08':
            if len(req)!=14 or req!=packet(10,4,int.from_bytes(req[6:8],'little'),4,8,bytes([value])):
                raise ValueError('La petición de calibración no coincide con la rutina declarada.')
            requests.append(req)
    if len(requests)>1:raise ValueError('La auditoría registra varias peticiones; asociación ambigua.')
    decoder=Decoder();frames=decoder.feed(raw)
    ack_indices=[]
    if requests:
        req=requests[0]
        ack_indices=[i for i,f in enumerate(frames) if f[4:6]==b'\x04\x0a' and f[8]==128
                     and f[6:8]==req[6:8] and f[9:11]==b'\x04\x08']
    # Reports before the correlated ACK are not attributed to this trial.
    after=frames[ack_indices[0]+1:] if ack_indices else []
    reports=[f[11:-2] for f in after if f[4:6]==b'\x04\x0a' and f[8]==0 and f[9:11]==b'\x04\x30']
    counts=Counter(p.hex() for p in reports);last=reports[-1] if reports else b''
    refs=[status_reference(p) for p in reports if status_reference(p)]
    unframed=len(raw)-sum(map(len,frames))
    intact=decoder.invalid==0 and not decoder.buffer and unframed==0
    meaning=refs[-1] if refs else None
    state='timeout_segun_referencia' if meaning and intact else 'sin_fin_verificado'
    detail=('La captura contiene 64 04: TIMEOUT según la referencia común. La causa física y su validación específica en Flip siguen pendientes.'
            if state=='timeout_segun_referencia' else 'La captura no permite confirmar un resultado de calibración con esta interpretación.')
    if meaning and intact and counts.get('6400',0):
        state='informes_finales_incompatibles'
        detail='La captura contiene 64 04 y 64 00. Se conserva la ambigüedad; no se declara éxito.'
    if not intact:detail+=' Hay fragmentos o errores de integridad; revisa los contadores.'
    evidence=q.get('usb_evidence');err=evidence.get('read_error') if isinstance(evidence,dict) else None
    err={k:err[k] for k in ('type','errno','backend_error_code','winerror') if k in err} if isinstance(err,dict) else None
    return {'state':state,'routine':routine,'model_declared':FLIP,
        'firmware_declared':report.get('firmware_declarado'),'historical_only':True,
        'current_device_confirmed':False,'usb_operations':0,'device_writes':0,
        'physical_calibration_validated':False,'flip_status_mapping_validated':False,
        'source':str(path),'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'source_app_version':report.get('version'),'source_capture_sha256':hashlib.sha256(raw).hexdigest(),
        'raw_bytes':len(raw),'crc_valid_frames':len(frames),'crc_issues':decoder.invalid,
        'pending_bytes':len(decoder.buffer),'unframed_bytes':unframed,
        'calibration_requests_in_audit':len(requests),'correlated_ack_count':len(ack_indices),
        'ack_payloads':[frames[i][11:-2].hex() for i in ack_indices[:20]],
        'post_ack_status_count':len(reports),'status_counts':dict(counts),
        'last_status_payload':last.hex(),'timeout_reference':meaning,
        'finish_6400_observed':counts.get('6400',0)>0,
        'source_report_state':q.get('state'),'source_usb_read_error':err,
        'detail':'Análisis de archivo histórico; no calibra ni consulta el dron. '+detail}
