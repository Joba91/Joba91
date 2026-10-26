"""Independent, bounded decoder for the HMS reference layout, not a health verdict.

Native HMSCheck: 3-byte header, byte 2 low 7 bits packet index/high bit end;
records of 6 bytes. OSDK documents uint32 code + uint8 index + uint8 level.
Its C++ bitfield declaration differs: we use the explicit shifts in the supplied
native reader, and keep compatibility with Mini 4 Pro unvalidated. No M300 code
descriptions are assigned to Mini 4 Pro. No USB, imports of official DLLs or TX.
"""
from studio_protocol import checksum
from vision_hms_extended import parse_hms_extended_frame,code_reference

PREVIEW=100
MAX_PACKETS=1024
MAX_SOURCES=16
MAX_CYCLE_RECORDS=256

def parse_hms_frame(frame):
    if (len(frame)<13 or frame[0]!=0x55 or int.from_bytes(frame[1:3],'little')>>10!=1
            or int.from_bytes(frame[1:3],'little')&1023!=len(frame)
            or checksum(frame[:3],0x77,0x8c)!=frame[3]
            or checksum(frame[:-2],0x3692,0x8408)!=int.from_bytes(frame[-2:],'little')):
        raise ValueError('Trama HMS con longitud, versión DUML o CRC inválidos.')
    if frame[9:11]!=b'\x21\x06':raise ValueError('No es un mensaje de datos HMS 21/06.')
    if frame[8]!=0:raise ValueError('Flags HMS sin formato de publicación contrastado; se conserva sin interpretar.')
    payload=frame[11:-2]
    if len(payload)<3 or (len(payload)-3)%6:raise ValueError('Longitud HMS distinta de 3 + 6*N.')
    if payload[0]!=0:raise ValueError('Versión de mensaje HMS no reconocida; no se aplica el formato v0.')
    records=[]
    for at in range(3,len(payload),6):
        records.append({'alarm_code_raw':f'0x{int.from_bytes(payload[at:at+4],"little"):08X}',
            'sensor_index_raw':payload[at+4],'report_level_raw':payload[at+5],
            'level_in_reference_range':payload[at+5]<=4,
            'description':'Sin descripción validada para Mini 4 Pro.',
            'vision_association_confirmed':False,'device_health':'desconocido'})
        records[-1].update(code_reference(records[-1]['alarm_code_raw']))
    return {'sender_raw':f'{frame[4]:02x}','receiver_raw':f'{frame[5]:02x}',
        'command_id_raw':'06','sequence_raw':int.from_bytes(frame[6:8],'little'),'message_version':payload[0],
        'cycle_index':payload[1],'packet_index':payload[2]&127,'end_flag':bool(payload[2]&128),
        'records':records,'payload_hex':payload.hex(' '),
        'layout':'reference_hms_v0_native_end_bit7','mini4_layout_validated':False}

class HmsTracker:
    def __init__(self):
        self.packets=0;self.decoded=0;self.unknown=0;self.record_count=0
        self.completed=0;self.abandoned=0;self.duplicates=0;self.limited=False
        self.issues=[];self.packet_preview=[];self.records={};self.sources={};self.cycle_preview=[]
        self.family_counts={'21/06':0,'21/08':0};self.opaque_count=0;self.opaque_preview=[]
    def issue(self,detail):
        if len(self.issues)<20:self.issues.append(detail)
    def invalidate(self,state,detail):
        if state['completed']:
            self.completed-=1;state['completed']=False
            if 'preview' in state:state['preview']['valid_reference_cycle']=False
            for key in state.get('confirmed_keys',()):
                record=self.records[key];record['complete_cycle_observations']-=1
                record['seen_in_complete_cycle']=record['complete_cycle_observations']>0
        state['invalid']=True;self.issue(detail)
    def observe(self,frame):
        if len(frame)<11 or frame[9]!=0x21 or frame[10] not in (6,8):return
        self.packets+=1
        family=f'21/{frame[10]:02x}';self.family_counts[family]+=1
        if self.packets>MAX_PACKETS:self.limited=True;return
        try:p=parse_hms_frame(frame) if frame[10]==6 else parse_hms_extended_frame(frame)
        except ValueError as exc:
            self.unknown+=1;self.issue(str(exc));return
        self.decoded+=1
        if len(self.packet_preview)<20:self.packet_preview.append(p)
        source=(p['sender_raw'],p['receiver_raw'],p['command_id_raw']);state=self.sources.get(source)
        if state is None and len(self.sources)>=MAX_SOURCES:
            self.limited=True;self.issue('Demasiados emisores HMS.');return
        if state is None or state['cycle']!=p['cycle_index']:
            if state and not state['completed']:self.abandoned+=1
            state={'cycle':p['cycle_index'],'parts':{},'end':None,'invalid':False,'completed':False,'record_count':0}
            self.sources[source]=state
        index=p['packet_index']
        if index in state['parts']:
            if state['parts'][index]['payload_hex']==p['payload_hex']:self.duplicates+=1;return
            self.invalidate(state,'Paquete contradictorio para el mismo emisor/ciclo/índice.');return
        if state['completed']:
            self.invalidate(state,'Paquete extra después del cierre del mismo ciclo.');return
        record_count=p.get('declared_record_count',len(p['records']))
        if state['record_count']+record_count>MAX_CYCLE_RECORDS:
            state['invalid']=True;self.limited=True;self.issue('Ciclo HMS supera el límite de registros.');return
        state['parts'][index]=p;state['record_count']+=record_count
        for opaque in p.get('opaque_records',[]):
            self.opaque_count+=1
            if len(self.opaque_preview)<20:self.opaque_preview.append({'sender_raw':source[0],**opaque})
        for record in p['records']:
            self.record_count+=1
            key=source+(record['alarm_code_raw'],record['sensor_index_raw'],record['report_level_raw'],record.get('record_variant_raw'))
            if key not in self.records and len(self.records)>=PREVIEW:self.limited=True;continue
            aggregate=self.records.setdefault(key,{**record,'sender_raw':source[0],'receiver_raw':source[1],'command_id_raw':source[2],
                'observations':0,'seen_in_complete_cycle':False,'complete_cycle_observations':0})
            aggregate['observations']+=1
        if p['end_flag']:
            if state['end'] is not None and state['end']!=index:
                state['invalid']=True;self.issue('Dos cierres distintos para el mismo ciclo HMS.')
            state['end']=index
        end=state['end']
        if end is not None and any(i>end for i in state['parts']):
            state['invalid']=True;self.issue('Hay paquetes después del índice final del ciclo HMS.')
        if (not state['invalid'] and end is not None and set(state['parts'])==set(range(end+1))):
            state['completed']=True;self.completed+=1
            keys=set()
            for part in state['parts'].values():
                for record in part['records']:
                    key=source+(record['alarm_code_raw'],record['sensor_index_raw'],record['report_level_raw'],record.get('record_variant_raw'))
                    if key in self.records:keys.add(key)
            state['confirmed_keys']=keys
            for key in keys:
                self.records[key]['seen_in_complete_cycle']=True
                self.records[key]['complete_cycle_observations']+=1
            if len(self.cycle_preview)<32:
                state['preview']={'sender_raw':source[0],'receiver_raw':source[1],
                    'command_id_raw':source[2],
                    'cycle_index':state['cycle'],'packets':end+1,'record_count':state['record_count'],'valid_reference_cycle':True}
                self.cycle_preview.append(state['preview'])
    def result(self):
        records=list(self.records.values())
        return {'state':'desconocido','detail':f'HMS: {self.completed} ciclos completos del formato de referencia; '
            f'{len(records)} registros distintos observados. Salud y calibración sin determinar.',
            'packets_seen':self.packets,'decoded_packets':self.decoded,'unknown_packets':self.unknown,
            'family_counts':dict(self.family_counts),'opaque_record_observations':self.opaque_count,
            'opaque_records_preview':list(self.opaque_preview),
            'complete_cycles':self.completed,'incomplete_cycles':self.abandoned+sum(not s['completed'] for s in self.sources.values()),
            'duplicate_packets':self.duplicates,'record_observations':self.record_count,'distinct_records_shown':len(records),
            'records_preview':records,'cycles_preview':list(self.cycle_preview),'packets_preview':list(self.packet_preview),
            'issues_preview':list(self.issues),'preview_limit':PREVIEW,'limits_reached':self.limited,
            'device_health':'desconocido','calibration_status':'desconocido','mini4_layout_validated':False,
            'alarm_code_mapping_validated':False,'empty_cycle_does_not_prove_health':True,
            'alarm_activity':'desconocido','code_presence_does_not_prove_active_fault':True,
            'source':'Formato HMS de referencia; compatibilidad específica pendiente de validar'}
