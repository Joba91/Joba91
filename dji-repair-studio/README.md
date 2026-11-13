# DJI REPAIR Studio 1.8.1

Windows 10/11 x64, una interfaz. DJI Flip, firmware 01.00.1500 declarado:
se añade una **consulta experimental de versión al controlador y al gimbal**.
**JointCoarse y LinearHall del Flip siguen pendientes de implementación.**

[Descarga](../downloads/LEEME.md) · [DJI Flip](DJI-FLIP.md) ·
[Mini 4 Pro](VISION-MINI4PRO.md) · [Air 3](VISION-AIR3.md)

## Resultado y siguiente prueba

El perfil Flip 1.8.0 recibido contiene ocho nodos PnP y seis alias con descriptores
completos. MI04 ofrece OUT04/IN85 bulk512, configuración 1/alternativa 0. Nombre
USB genérico DJI-…; no se asume una identidad comercial por esa cadena.

En 1.8.1 selecciona DJI Flip y pulsa **Consultar FC y gimbal (Flip)**. Elige tu
ZIP previo DJIFlip-PerfilUSB-….zip y guarda DJIFlip-Modulos-….zip. El mismo ZIP
previo se usa como referencia; no hace falta repetir el inventario ya recibido.
Se compara producto y nodo actual con ese perfil y se revisan los endpoints antes
de reclamar MI04. Solo se permiten dos solicitudes 00/01, sin reenvíos. Se guardan
RX crudo, auditoría y campos observados en `gimbal.module_query`, en la misma vista.

No se aceptan órdenes de fábrica/calibración, configuración o paquetes arbitrarios.
Los campos de versión usan el formato común del proyecto y conservan el original;
no son identidad autenticada o diagnóstico de salud. Falta probar la consulta en
el Flip real y resolver el contrato de las rutinas de taller pedidas.

## Validación

362 pruebas de aplicación/interfaz y 11 de empaquetado. EXE x64 bajo Wine con
fixtures sintéticos y corpus históricos; no hay Flip conectado en cloud. Prueba
sintética: dos respuestas, 78 bytes RX, 26 bytes OUT, cero órdenes de fábrica o
calibración, MI04 liberada y ZIP guardado. No se ejecutan programas DJI en cloud.

Se mantienen las funciones previas y sus límites. La calibración óptica de
Mini 4 Pro/Air 3 sigue pendiente. Fuentes y licencias incluidas. Desarrollo:
Python 3.13/Tk, `python launch.py`, pruebas `python -m unittest discover -s tests -v`,
compilación Windows `build_windows.ps1`. El receptor propio x86 no se modifica.
