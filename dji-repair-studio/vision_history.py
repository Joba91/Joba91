"""Offline DJI Test records. Log association is not protocol success or live ID.

Only explicit CMD/ACK/Send markers are parsed. Authentication text is ignored.
No USB, network, DLL loading, calibration writes or command transmission.
"""
import hashlib
import re
from collections import Counter
from studio_protocol import checksum
from vision_sensor_records import decode_perception_record, is_perception_record, request_selector

LIMIT=100000
PREVIEW=200
RECORD=re.compile(r'^\s*(CMD|ACK):\s*(.*)$',re.I)
SEND=re.compile(r'msg:\s*Log:\s*cmd Send:\s*(.*)$',re.I)
HEX=re.compile(r'^\s*((?:[0-9a-fA-F]{2}[ \t]*)+)(?:#+)?\s*$')

def is_dji_log(text):
    return bool(re.search(r'func:tpf::|Log:\s*CmdAndAck:',text))

def frame_issue(data):
    if len(data)<13:return 'trama_truncada'
    if data[0]!=0x55:return 'inicio_invalido'
    if (int.from_bytes(data[1:3],'little') & 0x3ff)!=len(data):return 'longitud_incorrecta'
    if checksum(data[:3],0x77,0x8c)!=data[3]:return 'crc_cabecera'
    if checksum(data[:-2],0x3692,0x8408)!=int.from_bytes(data[-2:],'little'):return 'crc_trama'
    return None

def frame_summary(data,number,direction):
    return {'line':number,'record_label':direction,'length':len(data),
            'frame_sha256':hashlib.sha256(data).hexdigest(),
            'sender_raw':f'{data[4]:02x}','receiver_raw':f'{data[5]:02x}',
            'sequence_raw':int.from_bytes(data[6:8],'little'),'flags_raw':f'{data[8]:02x}',
            'command_set_raw':f'{data[9]:02x}','command_id_raw':f'{data[10]:02x}',
            'payload_length':len(data)-13,'payload_sha256':hashlib.sha256(data[11:-2]).hexdigest(),
            'command_meaning':'desconocido','crc8_valid':True,'crc16_valid':True}

def analyze_dji_log(text,cancelled=lambda:False):
    lines=text.splitlines();records=[];sends=[];sensors=[];invalid_sensors=0;usb=Counter();projects=set();flows=Counter()
    for number,line in enumerate(lines,1):
        if cancelled():raise InterruptedError('Análisis histórico detenido')
        match=RECORD.match(line)
        if match:records.append((number,match[1].upper(),match[2]))
        else:
            match=SEND.search(line)
            if match:sends.append((number,'SEND',match[1]))
        if len(records)+len(sends)>LIMIT:raise ValueError('Demasiados registros de tráfico; analiza un fragmento menor')
        match=re.search(r'\b(frontleft|frontright|backleft|backright)\s*=\s*(\S+)',line,re.I)
        if match:
            serial=match[2]
            if re.fullmatch(r'[A-Za-z0-9]{14}',serial):
                if len(sensors)<PREVIEW:sensors.append({'line':number,'role_reported':match[1].lower(),'serial_reported':serial,
                    'source':'Etiqueta histórica; sin decodificación del payload ni lectura del equipo actual'})
            else:invalid_sensors+=1
        if 'Device seen.' in line or 'Device to be found.' in line:
            match=re.search(r'vid:([0-9a-f]+), pid:([0-9a-f]+), mi:([0-9a-f]+)',line,re.I)
            if match:usb[(int(match[1],16),int(match[2],16),int(match[3],16))]+=1
        match=re.search(r'"project"\s*:\s*"([A-Za-z0-9_-]{1,40})"',line)
        if match:projects.add(match[1])
        match=re.search(r'item name: main:([A-Za-z0-9_]{1,80}):',line)
        if match:flows[match[1]]+=1
    # CmdAndAck repeats the Send-layer command. Prefer the explicit pair records
    # per file; keep Send only as a fallback and disclose the choice.
    selected=records if records else sends
    counts=Counter();distinct={'CMD':set(),'ACK':set(),'SEND':set()};frames=[];issues=[];pairs=[];pair_counts=Counter()
    pending=None;valid_bytes=0;perception=[];perception_counts=Counter()
    for record_index,(number,direction,raw) in enumerate(selected):
        if cancelled():raise InterruptedError('Análisis histórico detenido')
        counts[direction]+=1;match=HEX.fullmatch(raw)
        data=bytes.fromhex(match[1]) if match else b''
        error=frame_issue(data) if match else 'registro_hex_no_reconocido'
        if error:
            counts['invalid']+=1
            if len(issues)<PREVIEW:issues.append({'line':number,'kind':error,'record_label':direction})
            pending=None
            continue
        counts['valid']+=1;valid_bytes+=len(data);distinct[direction].add(data)
        if len(frames)<PREVIEW:frames.append(frame_summary(data,number,direction))
        if direction=='CMD':
            if pending:pair_counts['requests_without_adjacent_ack']+=1
            pending=(data,number)
        elif direction=='ACK':
            if is_perception_record(data):
                decoded=decode_perception_record(data[11:-2])
                perception_counts['records']+=1
                perception_counts['decoded' if decoded['state']=='confirmado' else 'unknown_layout_or_invalid_serial']+=1
                decoded.update(line=number,label_comparison='sin_etiqueta_contrastable',
                    header_correlation_confirmed=False,success_inferred=False)
                # Association is still historical, even when selectors agree.
                selector=request_selector(pending[0]) if pending else None
                decoded['selector_agrees_with_adjacent_query']=(selector==decoded.get('selector')) if selector is not None else None
                if selector is not None:
                    perception_counts['selector_agreements' if decoded['selector_agrees_with_adjacent_query'] else 'selector_mismatches']+=1
                boundary=selected[record_index+1][0] if record_index+1<len(selected) else len(lines)+1
                labels=[s for s in sensors if number<s['line']<boundary
                        and s['role_reported']==decoded.get('role_historical')]
                if decoded['state']=='confirmado' and len(labels)==1:
                    decoded['label_line']=labels[0]['line']
                    decoded['label_comparison']='coincide' if labels[0]['serial_reported']==decoded['serial_from_payload'] else 'difiere'
                    perception_counts['label_matches' if decoded['label_comparison']=='coincide' else 'label_mismatches']+=1
                if len(perception)<PREVIEW:perception.append(decoded)
            if pending:
                request,request_line=pending
                if request==data:status='echo_no_confirma_respuesta'
                elif (data[4]==request[5] and data[5]==request[4] and data[6:8]==request[6:8]
                      and data[9:11]==request[9:11] and data[8]&0x80):status='cabeceras_correlacionadas_resultado_desconocido'
                else:status='asociacion_del_registro_sin_correlacion_de_cabeceras'
                pair_counts[status]+=1
                if len(pairs)<PREVIEW:pairs.append({'command_line':request_line,'ack_line':number,'correlation':status})
            else:pair_counts['acks_without_adjacent_request']+=1
            pending=None
    if pending:pair_counts['requests_without_adjacent_ack']+=1
    all_distinct=distinct['CMD']|distinct['ACK']|distinct['SEND']
    result={'state':'error' if counts['invalid'] else 'confirmado' if counts['valid'] else 'desconocido',
        'valid_frames':counts['valid'],'distinct_frames':len(all_distinct),'issue_count':counts['invalid'],
        'discarded_bytes':0,'pending_bytes':0,'frames_preview':frames,'issues_preview':issues,'preview_limit':PREVIEW,
        'analyzed_bytes':valid_bytes,'identity':{'state':'desconocido','detail':'Datos históricos; el dron conectado no se ha consultado.'},
        'detail':'Tramas de registros históricos; CRC y correlación no prueban éxito, compatibilidad ni identidad actual.',
        'historical_traffic':{'record_counts':dict(counts),'distinct_labeled_cmd':len(distinct['CMD']),
            'distinct_labeled_ack':len(distinct['ACK']),'association_counts':dict(pair_counts),'pairs_preview':pairs,
            'ignored_send_layer_records':len(sends) if records else 0,'record_layer':'CMD/ACK' if records else 'SEND'},
        'historical_sensors':{'state':'desconocido','observations_preview':sensors,'preview_limit':PREVIEW,
            'invalid_or_empty_labels':invalid_sensors,'detail':'Son etiquetas del archivo, no números de serie leídos actualmente.'},
        'perception_records':{'counts':dict(perception_counts),'observations_preview':perception,'preview_limit':PREVIEW,
            'detail':'SN convertidos desde payloads históricos y comparados con etiquetas cuando están disponibles. '
                     'La secuencia y el bit de respuesta siguen sin correlación confirmada; no prueba salud ni identidad actual.',
            'current_device_confirmed':False,'usb_operations':0},
        'historical_usb':{'state':'confirmado' if usb else 'desconocido','observations':[
            {'vid':f'{k[0]:04x}','pid':f'{k[1]:04x}','interface':k[2],'occurrences':v} for k,v in usb.items()],
            'endpoints_confirmed':False,'current_device_confirmed':False,
            'detail':'VID/PID/interfaz declarados en el registro; faltan descriptores y validación con el equipo actual.'},
        'historical_context':{'project_names':sorted(projects),'flow_labels':dict(flows),'marketing_model_confirmed':False},
        'usb_operations':0,'device_writes':0,'success_inferred':False}
    return result
