# DJI REPAIR Studio 1.2.6

Resuelve la comprobación de producto en interfaces libusb0 que no exponen el
nombre completo de la aeronave: obtiene el nodo PnP del alias MI04 elegido y su
padre físico directo, exige VID/PID 2CA3:0020 y producto Mini 4 Pro informado por
el bus. No busca otro equipo por nombre ni sustituye un descriptor que identifica
otro modelo. Consulta los metadatos antes de la apertura exclusiva de PyUSB.

El informe conserva el producto leído en la interfaz y en el padre, incluso al
fallar. Las rutas PnP se guardan como huellas; el producto local puede incluir
identificadores de unidad. No se sube ningún informe automáticamente.
Mantiene selección única MI04, comprobación de endpoints y ZIP automático.

170 pruebas de aplicación y 9 de empaquetado aprobadas. El EXE arranca bajo Wine
y comprueba exportaciones Windows y buffers nativos con datos sintéticos.
El informe real de 1.2.5 confirma selección MI04/configuración, pero no lectura.
La consulta del padre y recepción físicas siguen pendientes. Sin consulta activa,
calibración, modo fábrica, cambios de controlador o escrituras al dron.
