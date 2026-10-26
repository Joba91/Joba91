"""Observed 21/08 envelopes: four-byte header followed by counted TLV records.

All 121 messages in three supplied captures obey this structure. Only tag 0,
length 20 exposes a code candidate (first LE uint32). Other bytes stay opaque:
presence of a code is not evidence of an active/current alarm. No data source,
sensor position, timestamp, severity or active/cleared bit is guessed.
"""
from studio_protocol import checksum

REFERENCE_COMMIT='118e2825a347499efb8ed253146552c5b9b10779'
REFERENCE_URL=f'https://github.com/dji-sdk/Onboard-SDK/blob/{REFERENCE_COMMIT}/osdk-core/api/src/dji_hms_internal.cpp'
REFERENCES={
    '0x1A510380':'Referencia SDK: error de calibración de visión inferior.',
    '0x1A510382':'Referencia SDK: error de calibración de visión posterior.',
    '0x1A510384':'Referencia SDK: error de calibración de visión izquierda.',
    '0x1A510385':'Referencia SDK: error de calibración de visión derecha.',
    '0x1C000404':'Referencia SDK: sin tarjeta SD.',
    '0x1C000408':'Referencia SDK: sistema de archivos de SD no compatible.',
}

def code_reference(code):
    description=REFERENCES.get(code,'Sin descripción validada para Mini 4 Pro.')
    return {'description':description,'reference_description_available':code in REFERENCES,
        'reference_source':REFERENCE_URL if code in REFERENCES else None,
        'reference_applies_to_current_model_confirmed':False,'alarm_activity':'desconocido',
        'reference_does_not_prove_active_fault':True}

def parse_hms_extended_frame(frame):
    if (len(frame)<13 or frame[0]!=0x55 or int.from_bytes(frame[1:3],'little')>>10!=1
            or int.from_bytes(frame[1:3],'little')&1023!=len(frame)
            or checksum(frame[:3],0x77,0x8c)!=frame[3]
            or checksum(frame[:-2],0x3692,0x8408)!=int.from_bytes(frame[-2:],'little')):
        raise ValueError('Trama HMS extendida con longitud, versión DUML o CRC inválidos.')
    if frame[9:11]!=b'\x21\x08' or frame[8]!=0:raise ValueError('Familia o flags HMS extendidos no reconocidos.')
    payload=frame[11:-2]
    if len(payload)<4 or payload[0]!=0:raise ValueError('Cabecera o versión 21/08 no reconocida.')
    offset=4;records=[];opaque=[]
    for _ in range(payload[3]):
        if offset+2>len(payload):raise ValueError('Falta cabecera TLV declarada en 21/08.')
        tag,size=payload[offset:offset+2];offset+=2
        if offset+size>len(payload):raise ValueError('Longitud TLV excede los bytes disponibles.')
        body=payload[offset:offset+size];offset+=size
        if tag!=0 or size!=20:
            opaque.append({'tag_raw':tag,'length':size,'body_hex':body.hex(' '),'interpretation':'desconocido'})
            continue
        code=f'0x{int.from_bytes(body[:4],"little"):08X}'
        records.append({'alarm_code_raw':code,'sensor_index_raw':None,'report_level_raw':None,
            'tag_raw':tag,'body_length':size,'record_variant_raw':body.hex(' '),
            'body_bytes_4_to_19_raw':body[4:].hex(' '),
            'vision_association_confirmed':False,'device_health':'desconocido',
            **code_reference(code)})
    if offset!=len(payload):raise ValueError('Bytes sobrantes o contador TLV incorrecto en 21/08.')
    return {'sender_raw':f'{frame[4]:02x}','receiver_raw':f'{frame[5]:02x}',
        'command_id_raw':'08','sequence_raw':int.from_bytes(frame[6:8],'little'),
        'message_version':payload[0],'cycle_index':payload[1],
        'packet_index':payload[2]&127,'end_flag':bool(payload[2]&128),
        'declared_record_count':payload[3],'records':records,'opaque_records':opaque,
        'payload_hex':payload.hex(' '),'layout':'observed_21_08_v0_counted_tlv',
        'mini4_layout_validated':False,'alarm_activity_semantics_validated':False}
