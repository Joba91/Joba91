"""Read-only directory/ZIP inventory. Manifests are data, never instructions."""
import hashlib
import os
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath

MAX_FILES = 5000
MAX_TOTAL = 2 * 1024**3
MAX_FILE = 256 * 1024**2
MAX_MANIFEST = 4 * 1024**2

def safe_name(name):
    name = name.replace('\\', '/')
    p = PurePosixPath(name)
    if not name or name.startswith('/') or any(x in ('..', '') for x in name.split('/')) or ':' in name or '\x00' in name:
        raise ValueError('Ruta no admitida en el paquete')
    value = p.as_posix()
    if value == '.': raise ValueError('Ruta vacía')
    return value

def manifest_name(name):
    return Path(name).name.lower() in ('md5sum', 'md5sums', 'md5.txt', 'md5sum.txt', 'md5sums.txt') or name.lower().endswith(('.md5', '.md5sum'))

def parse_manifest(text, name):
    """GNU md5sum and BSD MD5 only. Reject ambiguous/unknown lines explicitly."""
    entries=[];errors=[]
    base=PurePosixPath(name).parent
    for number, line in enumerate(text.lstrip('\ufeff').splitlines(),1):
        line=line.strip()
        if not line or line.startswith(('#',';')): continue
        gnu=re.fullmatch(r'([0-9a-fA-F]{32})[ \t]+\*?(.+)', line)
        bsd=re.fullmatch(r'MD5 \((.+)\) = ([0-9a-fA-F]{32})', line, re.I)
        if gnu: digest, path=gnu.groups()
        elif bsd: path,digest=bsd.groups()
        else:
            errors.append({'line':number,'error':'Formato MD5 no reconocido'});continue
        try: path=safe_name((base / safe_name(path)).as_posix())
        except ValueError:
            errors.append({'line':number,'error':'Ruta MD5 no admitida'});continue
        entries.append({'path':path,'expected':digest.lower(),'line':number})
    return entries,errors

def inspect_package(path, progress=lambda event:None, cancelled=lambda:False):
    source=Path(path).expanduser().absolute()
    errors=[];items=[];archive=None
    def check():
        if cancelled(): raise InterruptedError('Importación local detenida')
    def add(name,size,opener):
        if len(items)>=MAX_FILES:raise ValueError('Paquete supera 5000 archivos')
        if size>MAX_FILE:raise ValueError('Archivo supera 256 MiB')
        if sum(x[1] for x in items)+size>MAX_TOTAL:raise ValueError('Paquete supera 2 GiB')
        items.append((safe_name(name),size,opener))
    try:
        if source.is_dir():
            root=source.resolve()
            def walk_error(exc):errors.append({'error':'No se pudo enumerar una carpeta: '+str(exc)})
            for current,dirs,files in os.walk(root,followlinks=False,onerror=walk_error):
                check()
                for name in list(dirs):
                    p=Path(current)/name
                    if p.is_symlink() or p.is_junction():
                        errors.append({'path':p.relative_to(root).as_posix(),'error':'Enlace de carpeta omitido'});dirs.remove(name)
                for name in sorted(files):
                    p=Path(current)/name;rel=p.relative_to(root).as_posix()
                    if p.is_symlink() or not p.resolve().is_relative_to(root):
                        errors.append({'path':rel,'error':'Enlace de archivo omitido'});continue
                    if not p.is_file():
                        errors.append({'path':rel,'error':'Entrada no regular omitida'});continue
                    try:add(rel,p.stat().st_size,lambda p=p:p.open('rb'))
                    except OSError as exc:errors.append({'path':rel,'error':str(exc)})
            kind='carpeta'
        elif source.is_file() and zipfile.is_zipfile(source):
            archive=zipfile.ZipFile(source);kind='ZIP'
            for info in archive.infolist():
                check()
                if info.is_dir():continue
                if stat.S_ISLNK(info.external_attr>>16):raise ValueError('ZIP contiene enlaces simbólicos')
                if info.flag_bits & 1:raise ValueError('ZIP cifrado no admitido; no se solicitan contraseñas')
                if info.file_size>1024**2 and info.file_size/max(1,info.compress_size)>300:
                    raise ValueError('Relación de compresión excesiva')
                add(info.filename,info.file_size,lambda info=info:archive.open(info,'r'))
        else:raise ValueError('Selecciona una carpeta o un ZIP local legible')
        folded=[n.casefold() for n,_,_ in items]
        if len(set(folded))!=len(folded):raise ValueError('Nombres duplicados o ambiguos para Windows')
        files=[];manifests=[]
        for index,(name,size,opener) in enumerate(items):
            check();entry={'path':name,'size':size}
            try:
                md5=hashlib.md5(usedforsecurity=False);sha=hashlib.sha256();read=0;content=bytearray()
                is_manifest=manifest_name(name)
                with opener() as stream:
                    before=os.fstat(stream.fileno()) if kind=='carpeta' else None
                    while chunk:=stream.read(1024*1024):
                        check();read+=len(chunk)
                        if read>MAX_FILE:raise ValueError('Archivo cambió o supera el límite')
                        md5.update(chunk);sha.update(chunk)
                        if is_manifest and len(content)<=MAX_MANIFEST:content.extend(chunk)
                    after=os.fstat(stream.fileno()) if before else None
                if read!=size or (before and (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns)):
                    raise ValueError('Archivo cambió durante la lectura; repite la importación')
                entry.update(md5=md5.hexdigest(),sha256=sha.hexdigest())
                if is_manifest:
                    if len(content)>MAX_MANIFEST:raise ValueError('Manifiesto supera 4 MiB')
                    manifests.append((name,bytes(content).decode('utf-8-sig')))
            except InterruptedError:
                raise
            except (OSError,ValueError,UnicodeError,zipfile.BadZipFile,RuntimeError) as exc:
                entry['error']=str(exc);errors.append({'path':name,'error':str(exc)})
            files.append(entry)
            progress({'mode':'determinate','percent':int((index+1)/max(1,len(items))*100),
                      'basis':'archivos','label':f'Archivos leídos: {index+1}/{len(items)} (no acredita compatibilidad)'})
        by_name={f['path'].casefold():f for f in files};checks=[];manifest_errors=[]
        for name,content in manifests:
            entries,problems=parse_manifest(content,name)
            manifest_errors.extend({'manifest':name,**e} for e in problems)
            if not entries:manifest_errors.append({'manifest':name,'error':'Sin entradas MD5 verificables'})
            seen=set()
            for item in entries:
                key=item['path'].casefold();file=by_name.get(key)
                state='coincide' if file and file.get('md5')==item['expected'] else ('falta' if not file else 'no_coincide_o_ilegible')
                if key in seen:
                    manifest_errors.append({'manifest':name,'error':'Entrada MD5 duplicada','path':item['path']})
                seen.add(key);checks.append({'manifest':name,**item,'state':state})
        covered={c['path'].casefold() for c in checks if c['state']=='coincide'}
        unchecked=[f['path'] for f in files if not manifest_name(f['path']) and f['path'].casefold() not in covered]
        bad=bool(errors or manifest_errors or any(c['state']!='coincide' for c in checks))
        state='error' if bad else ('confirmado' if checks and not unchecked else 'desconocido')
        detail=('Errores de lectura/manifiesto o coincidencia MD5.' if bad else
                'MD5 coincide para todos los archivos de datos inventariados.' if state=='confirmado' else
                'No hay manifiesto MD5 reconocido o su cobertura es incompleta.')
        return {'source':str(source),'kind':kind,'file_count':len(files),'files':files,
                'integrity':{'state':state,'detail':detail,'source':'Lectura local actual',
                    'md5_authenticates':False,'checks':checks,'uncovered':unchecked,'errors':errors+manifest_errors},
                'authenticity':{'state':'desconocido','detail':'MD5 no demuestra autenticidad ni compatibilidad.'},
                'package_identity':{'state':'desconocido','detail':'No se han interpretado metadatos propietarios; nombres no identifican sensores.'},
                'executed_files':0,'extracted_files':0,'device_writes':0}
    finally:
        if archive:archive.close()
