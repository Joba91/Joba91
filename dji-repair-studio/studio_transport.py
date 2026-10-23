"""USB transport with bundled libusb. Does not install/change device drivers."""
import sys
from pathlib import Path

class UsbTransport:
    def __init__(self, timeout=500):
        import usb.core
        import usb.util
        import usb.backend.libusb1
        self.core, self.util = usb.core, usb.util
        root = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
        native = root / 'libusb-1.0.dll'
        backend = usb.backend.libusb1.get_backend(find_library=lambda name: str(native)) if native.is_file() else usb.backend.libusb1.get_backend()
        if backend is None: raise RuntimeError('No se pudo cargar el backend libusb incluido.')
        devices = list(usb.core.find(find_all=True, idVendor=0x2ca3, backend=backend) or [])
        if len(devices) != 1:
            raise RuntimeError(f'Se encontraron {len(devices)} dispositivos USB DJI. Conecta un solo dron o utiliza puerto serie.')
        self.device = devices[0]; self.claimed = False; self.timeout = max(100, timeout)
        self.name = self.port = "BULK"
        try:
            cfg = self.device.get_active_configuration()
            interfaces = [i for i in cfg if i.bInterfaceNumber == 4 and i.bAlternateSetting == 0]
            if len(interfaces) != 1: raise RuntimeError('No se encontro la interfaz USB bulk 4.')
            interface = interfaces[0]
            endpoints = [e for e in interface if usb.util.endpoint_type(e.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK]
            self.ep_in = next((e for e in endpoints if usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN), None)
            self.ep_out = next((e for e in endpoints if usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT), None)
            if self.ep_in is None or self.ep_out is None: raise RuntimeError('Faltan endpoints bulk de entrada/salida.')
            usb.util.claim_interface(self.device, 4); self.claimed = True
        except Exception:
            self.close(); raise
    @property
    def in_waiting(self): return 1
    def read(self, size=4096):
        try:
            return self.ep_in.read(self.ep_in.wMaxPacketSize, timeout=self.timeout)
        except self.core.USBTimeoutError:
            return b""
    def write(self, data): return self.ep_out.write(data, timeout=max(2000, self.timeout))
    def reset_input_buffer(self): pass
    def close(self):
        try:
            if self.claimed: self.util.release_interface(self.device, 4); self.claimed = False
        finally: self.util.dispose_resources(self.device)
