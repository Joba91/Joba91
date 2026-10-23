"""Decode the observed 24/26 perception record, offline only.

Layout established by static analysis of the supplied x86 user library
(SHA256 03a04ab846defd1be8fe5a36dd5c03b8c5389bf264f3ac3bb9782a5a033b0c83,
TSGetPerceptionSensorSN RVA 119c80, conversion helper RVA 10f2f0).
This is an independent data parser: it never loads that library or sends USB.
The four selector labels come from historical logs, not model identification.
"""
import re

ROLES={4:'frontleft',8:'frontright',64:'backleft',128:'backright'}
VENDORS={0x10:'S',1:'C',0x20:'F',0x30:'Q',0x4e:'N'}
YEARS='ABCDEFGHJKLMNPQRSTUVWXYZ'
MONTHS='0123456789ABC'
DAYS='0123456789ABCDEFGHJKLMNPQRSTUVWXYZ'
ALNUM=re.compile(r'^[A-Z0-9]+$')

def decode_perception_record(payload):
    """Return a serial only for the bounded, verified record layout.

    Unknown and malformed layouts remain unknown. In particular the DLL's
    lossy '?' substitutions and embedded NULs are not presented as valid IDs.
    This verifies local data interpretation, never device health or success.
    """
    unknown={'state':'desconocido','detail':'Registro de percepción no reconocido.',
             'current_device_confirmed':False,'device_health':'desconocido'}
    if len(payload)!=20 or payload[:3]!=b'\x00\xa0\x00' or payload[3] not in ROLES:
        return unknown
    d=payload[4:]
    unknown.update(selector=payload[3],role_historical=ROLES[payload[3]])
    vendor=VENDORS.get(d[0],chr(d[0]))
    if (not ALNUM.fullmatch(vendor) or not 13<=d[8]<13+len(YEARS)
            or not 1<=d[9]<=12 or not 1<=d[10]<=31 or d[11]&15>9):
        return unknown
    # The native helper reverses these three prefix bytes, maps the vendor
    # and date codes, substitutes ASCII zero for the two absent characters,
    # appends the low-nibble decimal digit, then the four trailing characters.
    if any(c and not (48<=c<=57 or 65<=c<=90) for c in (d[1],d[2])):
        return unknown
    try:
        serial=(d[5:8][::-1].decode('ascii')+vendor+YEARS[d[8]-13]
                +MONTHS[d[9]]+DAYS[d[10]]+chr(d[2] or 48)+chr(d[1] or 48)
                +str(d[11]&15)+d[12:16].decode('ascii'))
    except UnicodeDecodeError:
        return unknown
    if len(serial)!=14 or not ALNUM.fullmatch(serial):return unknown
    return {'state':'confirmado','serial_from_payload':serial,'selector':payload[3],
            'role_historical':ROLES[payload[3]],'layout':'perception_24_26_record_v1',
            'detail':'Conversión del registro binario; identidad histórica, sin consulta USB.',
            'current_device_confirmed':False,'device_health':'desconocido'}

def request_selector(frame):
    """Recognize only the exact observed query shape; not a send API."""
    p=frame[11:-2]
    if (len(frame)==28 and frame[4:6]==b'\x2a\x12' and frame[8:11]==b'\x40\x24\x26'
            and p[:13]==b'\x0f'+bytes(11)+b'\xa0' and p[13]==0 and p[14] in ROLES):
        return p[14]
    return None

def is_perception_record(frame):
    return (len(frame)==33 and frame[4:6]==b'\x12\x2a'
            and frame[8:11]==b'\x00\x24\x26')
