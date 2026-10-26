"""Receive from the observed Mini 4 Pro bulk IN endpoint, without DJI commands.

Only standard descriptor reads, an interface claim, bulk IN and release are used.
No bulk OUT, vendor control requests, reset, set_configuration, alternate-setting
changes, kernel-driver detachment, clear_halt or driver installation are exposed.
"""
import sys
import time
from pathlib import Path
from vision_usb_legacy import select_mi04

MAX_BYTES=1024**2
DECLARED_FIRMWARE='01.00.1100'

class UsbOpeningError(RuntimeError):
    def __init__(self,diagnostics):
        self.diagnostics=diagnostics
        super().__init__('No se pudo preparar USB. '+'; '.join(
            f"{d['backend']} / {d['stage']}: {d['message']}" for d in diagnostics))

class PassiveVisionUsbTransport:
    def __init__(self,backend_name='auto'):
        import usb.core
        import usb.util
        import usb.backend.libusb1
        import usb.backend.libusb0
        self.core,self.util=usb.core,usb.util
        self.device=None;self.claimed=False;self.attempts=0;self.timeouts=0
        if backend_name not in ('auto','libusb0','libusb1'):raise ValueError('API USB desconocida.')
        order=(['libusb0','libusb1'] if sys.platform=='win32' else ['libusb1']) if backend_name=='auto' else [backend_name]
        diagnostics=[]
        for api in order:
            self._stage='load_backend';self._candidate_count=None
            try:
                if api=='libusb0':
                    native=Path(sys._MEIPASS)/'libusb0.dll' if hasattr(sys,'_MEIPASS') else Path(__file__).parent/'native/libusb0.dll'
                    backend=usb.backend.libusb0.get_backend(find_library=lambda name:str(native)) if native.is_file() else None
                else:
                    native=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))/'libusb-1.0.dll'
                    backend=(usb.backend.libusb1.get_backend(find_library=lambda name:str(native))
                        if native.is_file() else usb.backend.libusb1.get_backend())
                if backend is None:raise RuntimeError('No se pudo cargar la biblioteca de usuario incluida; ningún controlador fue modificado.')
                self._stage='enumerate_devices'
                devices=list(usb.core.find(find_all=True,idVendor=0x2ca3,idProduct=0x0020,backend=backend) or [])
                self._candidate_count=len(devices)
                selection=None
                if api=='libusb0' and devices:
                    self._stage='identify_libusb0_interfaces'
                    selected,selection=select_mi04(devices)
                    devices=[selected]
                if len(devices)!=1:raise RuntimeError(f'Se encontraron {len(devices)} dispositivos 2CA3:0020 con esta API. Conecta un solo Mini 4 Pro.')
                self.device=devices[0]
                self._open_profile(api)
                self.evidence.update(backend=api,backend_attempts=diagnostics)
                if selection is not None:self.evidence['legacy_interface_selection']=selection
                return
            except Exception as exc:
                diagnostic={'backend':api,'stage':self._stage,'candidate_devices':self._candidate_count,
                    'exception_type':type(exc).__name__,'message':str(exc),
                    'errno':getattr(exc,'errno',None),'backend_error_code':getattr(exc,'backend_error_code',None)}
                if hasattr(exc,'observations'):diagnostic['interface_observations']=exc.observations
                try:self.close()
                except Exception as cleanup:diagnostic['cleanup_error']=str(cleanup)
                diagnostics.append(diagnostic)
                # Never bypass a profile mismatch, ambiguous devices, access denial,
                # busy device or failed claim by trying a different device/API.
                may_fallback=(self._stage=='load_backend' or
                    (self._stage=='enumerate_devices' and self._candidate_count==0) or isinstance(exc,NotImplementedError))
                if not may_fallback:break
        raise UsbOpeningError(diagnostics)

    def _open_profile(self,api):
        try:
            self._stage='get_active_configuration'
            cfg=self.device.get_active_configuration()
            self._stage='check_configuration_and_speed'
            speed=self.device.speed
            if cfg.bConfigurationValue!=1 or (speed!=3 and not (api=='libusb0' and speed is None)):
                raise RuntimeError('La configuración/velocidad USB no coincide con el perfil recibido.')
            self._stage='read_product_descriptor'
            product=self.util.get_string(self.device,self.device.iProduct)
            self._stage='check_product'
            if not product or not (product=='Mini 4 Pro' or product.startswith('Mini 4 Pro-')):
                raise RuntimeError('El descriptor de producto USB no identifica Mini 4 Pro. No se abrirá otra interfaz.')
            self._stage='check_interface_and_endpoints'
            interfaces=[i for i in cfg if i.bInterfaceNumber==4 and i.bAlternateSetting==0]
            if len(interfaces)!=1:raise RuntimeError('No hay una única interfaz 4, alternativa 0.')
            interface=interfaces[0]
            if (interface.bInterfaceClass,interface.bInterfaceSubClass,interface.bInterfaceProtocol)!=(255,0x43,1):
                raise RuntimeError('La clase de la interfaz 4 no coincide con el reporte recibido.')
            endpoints=list(interface)
            signature=sorted((e.bEndpointAddress,e.bmAttributes,e.wMaxPacketSize) for e in endpoints)
            if interface.bNumEndpoints!=2 or signature!=[(4,2,512),(0x85,2,512)]:
                raise RuntimeError('Los endpoints de la interfaz 4 no coinciden con OUT 04 / IN 85, bulk de 512 bytes.')
            self.ep_in=next(e for e in endpoints if e.bEndpointAddress==0x85)
            self._stage='claim_interface_4'
            self.util.claim_interface(self.device,4);self.claimed=True
            self.evidence={'usb_product_family_reported':'Mini 4 Pro','vid':'2ca3','pid':'0020',
                'configuration':1,'interface':4,'alternate_setting':0,'bulk_in':'85','bulk_out_present':'04',
                'max_packet_size':512,'speed':'High-Speed' if speed==3 else 'no_informada_por_libusb0',
                'speed_verified':speed==3,'usb_descriptors_matched':True,
                'product_descriptor_is_not_authenticated_identity':True}
            self._stage='ready_to_receive'
        except Exception:raise

    def read(self):
        self.attempts+=1
        try:return bytes(self.ep_in.read(512,timeout=200))
        except self.core.USBTimeoutError:
            self.timeouts+=1;return b''

    def close(self):
        if self.device is None:return
        try:
            if self.claimed:self.util.release_interface(self.device,4)
        finally:
            self.claimed=False
            device=self.device;self.device=None
            self.util.dispose_resources(device)

def capture_passive(destination,firmware_declared,seconds=5,cancelled=lambda:False,
                    progress=lambda event:None,transport_factory=None,clock=time.monotonic):
    """Save a bounded new .bin; timeout/no traffic is not sensor failure.

    The duration measures bulk reception after opening; standard descriptor
    access and analysis have their own duration. The caller must close other USB
    applications to avoid competing reads. Interrupted/error captures are retained.
    """
    if firmware_declared!=DECLARED_FIRMWARE:
        raise ValueError('Para esta prueba declara el firmware 01.00.1100 que muestra DJI Fly; no se cambia el firmware.')
    if not 1<=seconds<=10:raise ValueError('Tiempo de recepción fuera de rango (1–10 segundos).')
    path=Path(destination).absolute()
    if path.suffix.lower()!='.bin':raise ValueError('La captura debe guardarse en un archivo nuevo .bin.')
    if cancelled():raise InterruptedError('Captura detenida antes de abrir USB.')
    transport=None;size=0;attempts=0;timeouts=0;started=None;elapsed=0;reason=None;error=None;completed=False;evidence={};opening_diagnostics=[]
    progress({'mode':'determinate','percent':0,'basis':'tiempo_de_recepcion',
              'label':'Abriendo USB para recepción pasiva; sin peticiones de servicio'})
    # Exclusive creation preserves existing files even if the user reuses a name.
    with path.open('xb') as stream:
        try:
            factory=transport_factory or PassiveVisionUsbTransport
            transport=factory();evidence=dict(transport.evidence);started=clock();last_percent=-1
            while True:
                elapsed=max(0,clock()-started)
                if cancelled():reason='detenida_por_usuario';break
                if elapsed>=seconds:reason='tiempo_cumplido';completed=True;break
                if size>=MAX_BYTES:reason='limite_de_bytes';break
                chunk=transport.read()
                if len(chunk)>512:raise RuntimeError('La lectura excede el tamaño de paquete previsto.')
                remaining=MAX_BYTES-size
                if chunk:
                    stream.write(chunk[:remaining]);size+=min(len(chunk),remaining)
                percent=min(99,int(max(0,clock()-started)/seconds*100))
                if percent!=last_percent:
                    progress({'mode':'determinate','percent':percent,'basis':'tiempo_de_recepcion',
                              'label':f'Recepción USB pasiva: {size} bytes; porcentaje del tiempo de captura'})
                    last_percent=percent
            stream.flush()
        except Exception as exc:
            reason='error_de_lectura_o_apertura';error=str(exc);completed=False
            opening_diagnostics=getattr(exc,'diagnostics',[])
        finally:
            if transport:
                attempts=transport.attempts;timeouts=transport.timeouts
                if started is not None:elapsed=max(0,clock()-started)
                try:transport.close()
                except Exception as exc:
                    error=(error+'; ' if error else '')+'Error al liberar USB: '+str(exc)
                    completed=False;reason='error_al_cerrar'
    if completed:
        progress({'mode':'determinate','percent':100,'basis':'tiempo_de_recepcion',
                  'label':'100 % del tiempo de recepción cumplido; diagnóstico de sensores desconocido'})
    return {'state':'error' if error else 'confirmado' if completed and size else 'desconocido',
        'detail':(f'Recepción pasiva: {size} bytes. '+('Error: '+error if error else
                  'No confirma salud ni identificación de sensores. No se enviaron peticiones de servicio.')),
        'source':'Recepción USB local solicitada; no es una captura de otra aplicación',
        'firmware_declared':firmware_declared,'firmware_read_from_device':False,
        'usb':evidence,'capture_path':str(path),'received_bytes':size,'requested_seconds':seconds,
        'opening_diagnostics':opening_diagnostics,
        'reception_elapsed_seconds':round(elapsed,3),'reception_completed':completed,'stop_reason':reason,
        'bulk_in_attempts':attempts,'bulk_in_timeouts':timeouts,'bulk_out_bytes':0,
        'protocol_commands_sent':0,'device_writes':0,'driver_changes':0,'factory_commands_sent':0,
        'device_health':'desconocido','live_sensor_query_validated':False,
        'error':error,'max_bytes':MAX_BYTES}
