"""Extension contracts. No device writes, DLL loading or calibration installer."""
from dataclasses import dataclass, field, asdict
from typing import Protocol

@dataclass(frozen=True)
class Evidence:
    state: str  # confirmado, desconocido, error
    detail: str
    source: str
    data: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)

class CaptureTransport(Protocol):
    """Receive only; no write method or service-command API."""
    def read(self) -> bytes: ...
    def close(self) -> None: ...

class IdentificationProvider(Protocol):
    def identify(self) -> Evidence: ...

class CalibrationProvider(Protocol):
    def candidates(self, inventory: dict) -> list[dict]: ...
    def compatibility(self, inventory: dict, identity: Evidence) -> Evidence: ...

class UnavailableIdentification:
    def identify(self):
        return Evidence('desconocido',
            'SN de registros históricos: conversión disponible en Analizar captura. '
            'Capturar USB pasivo recibe tráfico sin peticiones de servicio. '
            'La consulta activa de sensores sigue pendiente de validar en modo normal para este firmware.',
            'Estado de implementación; no se contactó un dron',
            {'usb_enabled': False, 'passive_capture_available':True, 'active_sensor_query_enabled':False, 'write_enabled': False})

class LocalCalibrationProvider:
    def candidates(self, inventory):
        # Files are candidates by container type only, never by proven compatibility.
        return [{'path': f['path'], 'sha256': f.get('sha256'), 'compatibility': 'desconocido'}
                for f in inventory.get('files', [])
                if f['path'].lower().endswith(('.bin', '.dat', '.cal', '.cali')) and not f.get('error')]

    def compatibility(self, inventory, identity):
        if inventory.get('integrity', {}).get('state') == 'error':
            return Evidence('error', 'Integridad fallida; no seleccionar datos para un equipo.', 'Verificación local')
        return Evidence('desconocido',
            'MD5, nombre del modelo y nombres de archivos no demuestran compatibilidad. '
            'Faltan identificadores confirmados de módulos/sensores y correspondencia validada con el paquete.',
            'Proveedor local; sin protocolo de selección validado',
            {'selection_enabled': False, 'download_enabled': False, 'write_enabled': False})
