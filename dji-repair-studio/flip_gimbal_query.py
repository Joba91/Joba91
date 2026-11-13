"""Experimental Flip module-version query, bound to a saved USB inventory.

Only two standard DUML 00/01 requests (FC and gimbal) are permitted on OUT 04.
Factory/calibration requests, arbitrary packets, retries, device configuration,
reset, alternate-setting changes and driver detachment are not exposed.
"""
import hashlib
import json
import time
from pathlib import Path
from zipfile import ZipFile
from gimbal_profiles import FLIP
from studio_protocol import Client,version_request
from studio_version import VERSION
from vision_usb_inventory import validate_inventory,validate_firmware
from vision_usb_descriptors import enumerate_legacy_descriptors
from vision_usb_legacy import select_mi04
from vision_usb_parent import parent_product_for_device
from vision_support_bundle import write_support_bundle

MAX_RX=65536

def load_reference(path,firmware):
    validate_firmware(firmware)
    path=Path(path)
    if not path.is_file() or path.stat().st_size>4*1024**2:raise ValueError('Elige el ZIP de perfil USB del Flip (máximo 4 MiB).')
    with ZipFile(path) as z:
        if len(z.infolist())>8 or z.namelist().count('DJI-REPAIR-informe.json')!=1:
            raise ValueError('El ZIP no contiene un informe USB único.')
        info=z.getinfo('DJI-REPAIR-informe.json')
        if info.file_size>1024**2:raise ValueError('Informe USB demasiado grande.')
        report=json.loads(z.read(info))
    if not isinstance(report,dict) or not isinstance(report.get('gimbal'),dict):raise ValueError('Informe de gimbal no reconocido.')
    if report.get('modelo_declarado')!=FLIP or report.get('firmware_declarado')!=firmware:
        raise ValueError('El modelo/firmware declarado del perfil no coincide con el Flip seleccionado.')
    raw=report.get('gimbal',{}).get('usb_profile',{})
    if not isinstance(raw,dict):raise ValueError('Perfil USB no reconocido.')
    rows=validate_inventory({'schema':1,'source':'windows_pnp_present','devices':raw.get('devices')})
    if raw.get('collection_complete') is not True:raise ValueError('El perfil USB no terminó de recopilarse.')
    roots=[r for r in rows if '&MI_' not in r['instance_id'].split('\\')[1].upper()]
    if len(roots)!=1 or roots[0]['instance_id'].split('\\')[1].upper()!='VID_2CA3&PID_0020':
        raise ValueError('Se requiere un único padre 2CA3:0020 en el perfil.')
    children=[r for r in rows if r['instance_id'].split('\\')[1].upper()=='VID_2CA3&PID_0020&MI_04']
    if len(children)!=1 or (children[0].get('parent') or '').casefold()!=roots[0]['instance_id'].casefold():
        raise ValueError('El perfil no relaciona una única MI04 con su padre.')
    desc=raw.get('descriptor_inventory',{})
    if not isinstance(desc,dict):raise ValueError('Descriptores no reconocidos.')
    if desc.get('state')!='confirmado' or desc.get('errors'):
        raise ValueError('Se necesitan los descriptores completos del perfil USB.')
    aliases=desc.get('aliases',[])
    if not isinstance(aliases,list) or len(aliases)>32 or any(not isinstance(a,dict) for a in aliases):raise ValueError('Lista de alias del perfil inválida.')
    matches=[a for a in aliases if a.get('pnp_interface_number')==4]
    if len(matches)!=1 or matches[0].get('complete') is not True or matches[0].get('pnp_instance_matches') is not True:
        raise ValueError('El perfil no acredita un único alias MI04 completo.')
    cfgs=matches[0].get('configurations',[])
    if not isinstance(cfgs,list) or len(cfgs)!=1 or not isinstance(cfgs[0],dict) or cfgs[0].get('bConfigurationValue')!=1:
        raise ValueError('Configuración de referencia no admitida.')
    interfaces=cfgs[0].get('interfaces',[])
    if not isinstance(interfaces,list) or len(interfaces)!=1 or not isinstance(interfaces[0],dict):raise ValueError('MI04 de referencia ambigua.')
    i=interfaces[0]
    if tuple(i.get(k) for k in ('bInterfaceNumber','bAlternateSetting','bInterfaceClass','bInterfaceSubClass','bInterfaceProtocol','bNumEndpoints'))!=(4,0,255,0x43,1,2):
        raise ValueError('La clase de MI04 no coincide con la referencia observada.')
    eps=i.get('endpoints',[])
    if not isinstance(eps,list) or len(eps)!=2 or any(not isinstance(e,dict) for e in eps) or sorted((e.get('bEndpointAddress'),e.get('bmAttributes'),e.get('wMaxPacketSize')) for e in eps)!=[(4,2,512),(0x85,2,512)]:
        raise ValueError('Se requiere OUT 04 / IN 85 bulk de 512 bytes.')
    product=roots[0].get('bus_product')
    if not product:raise ValueError('Falta el nombre de producto del padre USB.')
    return {'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(), 'product':product,
            'child_instance_sha256':hashlib.sha256(children[0]['instance_id'].upper().encode()).hexdigest(),
            'parent_instance_sha256':hashlib.sha256(roots[0]['instance_id'].upper().encode()).hexdigest()}

class FlipVersionTransport:
    def __init__(self,reference,enumerator=enumerate_legacy_descriptors,selector=select_mi04,parent_reader=parent_product_for_device,util=None):
        import usb.util
        import usb.core
        self.util=util or usb.util;self.core=usb.core;self.device=None;self.claimed=False
        self.rx=bytearray();self.rx_limit=MAX_RX;self.tx_attempts=[];self.tx_confirmed=[];self.uncertain_tx=False
        self.evidence={'stage':'enumerar_alias_libusb0','identity_authenticated':False,'marketing_model_confirmed':False}
        try:
            devices=[]
            for device in enumerator() or []:
                devices.append(device)
                if len(devices)>32:raise ValueError('Demasiados alias libusb0.')
            self.evidence['stage']='identificar_mi04'
            self.device,selection=selector(devices)
            self.evidence['selection']=selection;self.evidence['stage']='comparar_padre_con_perfil'
            parent=parent_reader(self.device)
            for key in ('product','child_instance_sha256','parent_instance_sha256'):
                if parent.get(key)!=reference[key]:raise ValueError('El dispositivo actual no coincide con el perfil USB. Recopila uno nuevo en este puerto.')
            self.evidence['parent_metadata']=parent
            self.evidence['stage']='validar_descriptores_actuales'
            cfg=self.device.get_active_configuration()
            if cfg.bConfigurationValue!=1:raise ValueError('Configuración activa distinta de 1; no se cambia automáticamente.')
            interfaces=[i for i in cfg if i.bInterfaceNumber==4 and i.bAlternateSetting==0]
            if len(interfaces)!=1:raise ValueError('No hay una única MI04 alternativa 0.')
            i=interfaces[0]
            if (i.bInterfaceClass,i.bInterfaceSubClass,i.bInterfaceProtocol,i.bNumEndpoints)!=(255,0x43,1,2):
                raise ValueError('Clase de MI04 actual distinta del perfil.')
            eps=list(i)
            if len(eps)!=2 or sorted((e.bEndpointAddress,e.bmAttributes,e.wMaxPacketSize) for e in eps)!=[(4,2,512),(0x85,2,512)]:
                raise ValueError('Endpoints actuales distintos de OUT 04 / IN 85 bulk 512.')
            self.ep_out=next(e for e in eps if e.bEndpointAddress==4);self.ep_in=next(e for e in eps if e.bEndpointAddress==0x85)
            self.evidence['stage']='reclamar_mi04';self.util.claim_interface(self.device,4);self.claimed=True
            self.evidence.update(stage='consulta_preparada',interface=4,bulk_out='04',bulk_in='85',packet_size=512,
                                 reference_metadata_matches=True,calibration_commands_enabled=False)
        except Exception as exc:
            try:self.close()
            except Exception as cleanup:self.evidence['cleanup_error']=str(cleanup)
            exc.flip_evidence=dict(self.evidence)
            raise

    def write(self,data):
        data=bytes(data)
        if len(data)!=13 or data[5] not in (3,4) or data!=version_request(data[5],int.from_bytes(data[6:8],'little')):
            raise ValueError('Solo se admiten consultas de versión 00/01 al controlador y al gimbal.')
        if len(self.tx_attempts)>=2 or any(frame[5]==data[5] for frame in self.tx_attempts):
            raise ValueError('Solo una consulta por módulo; no se reenvía.')
        self.tx_attempts.append(data)
        try:
            count=self.ep_out.write(data,timeout=500)
            if count!=len(data):raise OSError('Escritura incompleta de la consulta de versión.')
        except Exception:
            self.uncertain_tx=True;raise
        self.tx_confirmed.append(data);return count

    def read(self):
        if len(self.rx)>=self.rx_limit:raise RuntimeError('Límite de recepción alcanzado.')
        try:chunk=bytes(self.ep_in.read(512,timeout=200))
        except self.core.USBTimeoutError:return b''
        if len(chunk)>512:raise ValueError('Lectura superior al tamaño permitido.')
        remaining=self.rx_limit-len(self.rx)
        self.rx.extend(chunk[:remaining])
        if len(chunk)>remaining:raise RuntimeError('Límite de recepción alcanzado.')
        return chunk

    def close(self):
        if self.device is None:return
        device=self.device;self.device=None
        try:
            if self.claimed:self.util.release_interface(device,4)
        finally:
            self.claimed=False;self.util.dispose_resources(device)


def query_flip_modules(destination,profile_path,firmware,cancelled=lambda:False,progress=lambda e:None,
                       transport_factory=FlipVersionTransport,clock=time.monotonic):
    reference=load_reference(profile_path,firmware)
    path=Path(destination).absolute();capture=path.with_suffix('.bin')
    if path.suffix.lower()!='.zip' or path.exists() or capture.exists() or not path.parent.is_dir():
        raise ValueError('Elige un ZIP nuevo; tampoco se sobrescribe su BIN asociado.')
    result={'state':'desconocido','model_declared':FLIP,'firmware_declared':firmware,'model_identity_confirmed':False,
        'reference_profile_sha256':reference['source_sha256'],'modules':[],'calibration_available':False,'calibration_performed':False,
        'factory_commands_sent':0,'gimbal_calibration_commands_sent':0,'configuration_writes':0,'native_sdk_loaded':False,
        'support_bundle':str(path),'capture_path':str(capture),'packet_audit':[],
        'version_requests_attempted':0,'bulk_out_requests_complete':0,'bulk_out_bytes_confirmed':0,
        'bulk_out_delivery_uncertain':False,'version_requests_limit':2,'usb_operation_count_known':False}
    transport=None;client=None;received=b''
    with capture.open('xb') as stream:
        try:
            if cancelled():raise InterruptedError('Consulta detenida antes de abrir USB.')
            progress({'mode':'indeterminate','label':'Preparando MI04 del equipo asociado al perfil Flip'})
            transport=transport_factory(reference)
            client=Client(transport,timeout=3,retries=1,clock=clock,cancelled=cancelled)
            for name in ('Controlador','Gimbal'):
                row=client.query(name);result['modules'].append(row)
                count=sum(r['estado']=='version_recibida' for r in result['modules'])
                progress({'mode':'determinate','percent':count*33,'label':f'Versiones reconocidas: {count}/2; no es calibración'})
            count=sum(r['estado']=='version_recibida' for r in result['modules'])
            result['state']='confirmado' if count==2 else 'desconocido'
            result['detail']=f'{count}/2 módulos con formato de versión reconocido. Son versiones de módulos; identidad, salud y calibración siguen sin confirmar.'
        except Exception as exc:
            result.update(state='desconocido' if isinstance(exc,InterruptedError) else 'error',detail=str(exc),error=str(exc))
            if hasattr(exc,'flip_evidence'):result['usb_evidence']=exc.flip_evidence
        finally:
            if client:result['packet_audit']=client.packets
            if transport:
                received=bytes(transport.rx)
                result.update(usb_evidence=transport.evidence,version_requests_attempted=len(transport.tx_attempts),
                    bulk_out_requests_complete=len(transport.tx_confirmed),bulk_out_bytes_confirmed=sum(map(len,transport.tx_confirmed)),
                    bulk_out_delivery_uncertain=transport.uncertain_tx)
                try:transport.close()
                except Exception as exc:result.update(state='error',cleanup_error=str(exc));result['detail']+=' Error al cerrar USB: '+str(exc)
            stream.write(received)
    result['rx_bytes']=len(received)
    write_support_bundle(capture,{'herramienta':'DJI REPAIR Studio','version':VERSION,'fecha_unix':time.time(),
        'modelo_declarado':FLIP,'firmware_declarado':firmware,'gimbal':{'module_query':result}})
    if result['state']=='confirmado':progress({'mode':'determinate','percent':100,'label':'Dos versiones y ZIP guardados · no es calibración'})
    result['detail']+=' Archivo para compartir: '+str(path)
    return result
