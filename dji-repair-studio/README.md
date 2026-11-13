# DJI REPAIR Studio 1.8.0

Windows 10/11 x64, una ventana con botones laterales. Se añade el **proyecto de
gimbal DJI Flip**, firmware **01.00.1500 declarado** por el usuario.
**JointCoarse y LinearHall del Flip todavía no están implementadas.**

[Descarga](../downloads/LEEME.md) · [DJI Flip](DJI-FLIP.md) ·
[Mini 4 Pro](VISION-MINI4PRO.md) · [Air 3](VISION-AIR3.md)

## Cambio de esta versión

Flip tiene una vista propia en Calibración y lectura de conexión USB. El botón
Recopilar perfil USB genera un ZIP con `gimbal.usb_profile`. El firmware se
conserva por modelo; la preparación de fábrica y resultados previos se limpian
al cambiar de equipo. Los eventos de la vista de visión no cambian Flip a Mini 4.
Las operaciones heredadas quedan bloqueadas para Flip antes de abrir transporte.
No se asigna un código interno ni se copian comandos de otro modelo.

Para continuar: selecciona DJI Flip, revisa 01.00.1500 y pulsa Recopilar perfil USB.
Comparte DJIFlip-PerfilUSB-….zip. Esa lectura no mueve ni calibra el gimbal. Hace
falta además contrastar el modo de taller, peticiones y respuestas de ambas
rutinas para este modelo. Los descriptores por sí solos no resuelven eso.

Se mantienen las funciones anteriores de otros modelos con sus límites. La
calibración óptica Mini 4 Pro/Air 3 sigue pendiente; sus rutas de sensores se
mantienen separadas de Flip. [Estado de visión](ESTADO-VISION-2026-11-06.md).

## Desarrollo y validación

Python 3.13/Tk. `python launch.py` y `python -m unittest discover -s tests -v`.
Compilación en Windows: build_windows.ps1. Fuentes y licencias incluidas.
344 pruebas de aplicación/interfaz y 11 de empaquetado. Arranque x64 bajo Wine,
fixtures sintéticos y corpus históricos; sin hardware Flip en cloud. El receptor
x86 propio se conserva; no se reconstruye ni se prueba su arranque en este kernel.
El inventario puede leer descriptores estándar; no consulta sensores o cambia
configuración. CfgMgr32 de Wine devuelve longitud USB cero y se guarda como error.
No se ejecutan programas DJI en cloud ni se redistribuyen sus DLL o registros.
