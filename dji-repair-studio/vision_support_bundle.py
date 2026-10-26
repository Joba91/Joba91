"""Save a local shareable capture + JSON; no upload and no overwriting."""
import json
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED

def write_support_bundle(capture_path,report):
    capture=Path(capture_path)
    if capture.suffix.lower()!='.bin' or not capture.is_file():
        raise ValueError('Se necesita el archivo .bin creado por la captura.')
    if capture.stat().st_size>1024**2:raise ValueError('La captura supera el límite de recepción de 1 MiB.')
    encoded=json.dumps(report,ensure_ascii=False,indent=2).encode('utf-8')
    if len(encoded)>8*1024**2:raise ValueError('El informe supera el límite de 8 MiB.')
    target=capture.with_suffix('.zip');created=False
    try:
        with target.open('xb') as stream:
            created=True
            with ZipFile(stream,'w',ZIP_DEFLATED) as z:
                z.write(capture,capture.name)
                z.writestr('DJI-REPAIR-informe.json',encoded)
    except Exception:
        if created:target.unlink(missing_ok=True)
        raise
    return str(target.absolute())
