"""On-demand reachability probe, bounded including DNS by a disposable child.

No authentication, HTTP requests, redirects, credentials, or calibration downloads.
"""
import json
import os
import socket
import ssl
import subprocess
import sys
import time
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from vision_interfaces import Evidence, LocalCalibrationProvider

def service_target(url):
    parsed=urlsplit(url.strip())
    if parsed.scheme!='https' or not parsed.hostname or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment:
        raise ValueError('Usa https://servidor:puerto sin usuario, contraseña, tokens ni fragmentos')
    host=parsed.hostname
    if len(host)>253 or any(c.isspace() for c in host) or any(c in host for c in ('\\','%','\x00')):
        raise ValueError('Nombre de servidor no válido')
    port=443 if parsed.port is None else parsed.port
    if not 1<=port<=65535:raise ValueError('Puerto no válido')
    return host,port

def _connect_tls(host,port,timeout):
    start=time.monotonic()
    try:
        context=ssl.create_default_context()
        with socket.create_connection((host,port),timeout=timeout) as sock:
            with context.wrap_socket(sock,server_hostname=host):pass
        return {'state':'confirmado','detail':'TCP y TLS verificables accesibles. No demuestra autenticación ni servicio de calibración disponible.',
                'source':'Sondeo solicitado por el usuario','host':host,'port':port,'elapsed_seconds':round(time.monotonic()-start,3),
                'authentication':'desconocido','calibration_service':'desconocido','download_enabled':False}
    except ssl.SSLCertVerificationError:
        return {'state':'error','detail':'Certificado TLS no verificable; no se desactiva la validación.', 'source':'Sondeo solicitado por el usuario'}
    except (OSError,ssl.SSLError):
        return {'state':'error','detail':'No se pudo verificar la conexión TCP/TLS en el plazo solicitado; no prueba que el servidor esté apagado.',
                'source':'Sondeo solicitado por el usuario'}

def probe_server(url, timeout=5):
    host,port=service_target(url)
    timeout=float(timeout)
    if not 0.5<=timeout<=10:raise ValueError('Tiempo de espera permitido: 0,5 a 10 segundos')
    options={'creationflags':subprocess.CREATE_NO_WINDOW} if sys.platform=='win32' else {}
    # Files work with a --windowed executable, where sys.stdin/stdout may be None.
    # Reuse the existing PyInstaller runtime: this is a worker, not a new onefile
    # application parent. It can be killed directly without a second bootloader.
    env=dict(os.environ);env['PYINSTALLER_RESET_ENVIRONMENT']='0'
    with tempfile.TemporaryDirectory(prefix='dji-vision-probe-') as temp:
        request=Path(temp)/'request.json';output=Path(temp)/'result.json'
        request.write_text(json.dumps({'host':host,'port':port,'timeout':timeout}),encoding='utf-8')
        if getattr(sys,'frozen',False):command=[sys.executable,'--vision-probe-worker',str(request),str(output)]
        else:command=[sys.executable,'-c','import sys; from vision_services import probe_worker; probe_worker(sys.argv[1],sys.argv[2])',str(request),str(output)]
        try:
            child=subprocess.run(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                timeout=timeout,check=False,env=env,**options)
            if child.returncode:raise ValueError('El proceso de diagnóstico no pudo completar el sondeo')
            report=json.loads(output.read_text(encoding='utf-8'))
            if report.get('state') not in ('confirmado','desconocido','error'):raise ValueError('Resultado de sondeo inválido')
            return report
        except subprocess.TimeoutExpired:
            return {'state':'error','detail':'Tiempo máximo agotado (incluye DNS, inicio del proceso, TCP y TLS).',
                    'source':'Sondeo solicitado por el usuario','timeout_seconds':timeout,'download_enabled':False}

def probe_worker(request_path,output_path):
    data=json.loads(Path(request_path).read_text(encoding='utf-8'))
    report=_connect_tls(data['host'],int(data['port']),float(data['timeout']))
    Path(output_path).write_text(json.dumps(report,ensure_ascii=True),encoding='utf-8')

class AuthorizedServiceProvider:
    def __init__(self,url):
        service_target(url);self.url=url
    def probe(self,timeout=5):return probe_server(self.url,timeout)
    def candidates(self,inventory):return []
    def compatibility(self,inventory,identity):
        return Evidence('desconocido','Faltan API autorizada, autenticación configurada e identificadores contrastados.', 'Proveedor de servicio configurable')
    def download(self,*args,**kwargs):
        raise NotImplementedError('Descarga no disponible: falta contrato de API y autenticación autorizada. No se reutilizan credenciales del paquete.')
