"""Entry point for the isolated x86 receiver. Self-test never loads DJI code."""
import json
import os
import struct
import sys
from pathlib import Path
from vision_image_receiver import parse_image_metadata, run_job

if len(sys.argv) == 3 and sys.argv[1] == '--self-test':
    raw = bytearray(196)
    struct.pack_into('<HH', raw, 6, 640, 480)
    raw[14] = 8
    struct.pack_into('<I', raw, 24, 307200)
    import ctypes
    result = {'pointer_bits': struct.calcsize('P') * 8, 'ctypes_available': True,
              'metadata_payload_bytes': parse_image_metadata(raw)['payload_bytes'],
              'dji_code_loaded': False, 'usb_operations': 0, 'calibration_performed': False}
    Path(sys.argv[2]).write_text(json.dumps(result, indent=2), encoding='utf-8')
    sys.exit(0)

if len(sys.argv) != 2:
    sys.exit(2)
try:
    result = run_job(sys.argv[1])
    code = 1 if result['state'] == 'error' else 0
except Exception as exc:
    try:
        job = Path(sys.argv[1]).absolute()
        if job.is_file():
            (job.parent / 'fatal.json').write_text(json.dumps({'error': str(exc)}), encoding='utf-8')
    except Exception:
        pass
    code = 1
# The native SDK has no documented global shutdown API. Do not unload it while
# its background threads are running; exit the isolated process instead.
os._exit(code)
