# DJI REPAIR Studio 1.9.0

Windows 10/11 x64, una interfaz. Se incorporan **pruebas experimentales de
JointCoarse y LinearHall para DJI Flip**, firmware **01.00.1500 declarado**.
**Compatibilidad Flip sin validación física:** se prueba la petición común DJI;
no se presenta como un procedimiento de taller ya comprobado para este modelo.

[Descarga](../downloads/LEEME.md) · [Detalle Flip](DJI-FLIP.md) ·
[Mini 4 Pro](VISION-MINI4PRO.md) · [Air 3](VISION-AIR3.md)

## Cambio de esta versión

La captura 1.8.1 aportada por el usuario contiene dos respuestas 00/01 válidas y
correlacionadas por MI04: controlador 01.00.0057 y gimbal 00.00.2052, versiones de
módulo observadas, no la versión de aeronave DJI Fly. Hay comunicación de
información; eso no prueba compatibilidad de las calibraciones.

Cada prueba exige ese ZIP de módulos, comprueba de nuevo nodo/producto/endpoints
y dos versiones actuales coincidentes, y aborta si detecta progreso previo.
Solo se permite una petición 04/08: 01 JointCoarse o 02 LinearHall. No se cambian
modos de fábrica, se reenvía, fuerza otra interfaz o escriben tablas IMU fijas.
El firmware puede persistir ajustes propios de su rutina; el efecto está sin validar.

ACK correlacionado admitido + progreso posterior conocido + fin 64 00 permiten
informar `equipo_informa_fin`. El 100 % exige también guardar el ZIP. No afirma
exactitud física/metrológica ni identidad autenticada. Se conservan RX/BIN,
auditoría y errores; cancelar detiene lectura, no motores. [Uso y límites](DJI-FLIP.md).

## Validación

373 pruebas de aplicación/interfaz y 11 de empaquetado. EXE x64 bajo Wine con
trazas sintéticas, incluidos límites de una petición y rechazo de fábrica.
No hay Flip físico en cloud. El receptor propio x86 y las funciones previas
mantienen sus límites; calibración óptica Mini 4 Pro/Air 3 todavía pendiente.
Fuentes y licencias incluidas. Desarrollo Python 3.13/Tk; `python launch.py`,
`python -m unittest discover -s tests -v`, compilación Windows `build_windows.ps1`.
