# DJI REPAIR Studio 1.9.2

[Descargar ZIP con EXE · Windows 10/11 x64](https://raw.githubusercontent.com/Joba91/Joba91/main/downloads/DJI_Repair_Studio_1.9.2.zip)

Extrae en una carpeta nueva y abre **DJI REPAIR Studio 1.9.2.exe**.
Esta entrega mejora el diagnóstico; **todavía no resuelve la falta de movimiento
de yaw y roll ni valida una calibración completa del Flip**.

## Revisar la captura existente sin conectar el dron

1. Selecciona **DJI Flip**.
2. Pulsa **Analizar prueba Flip (ZIP)** en el lateral.
3. Elige **DJIFlip-JointCoarse-20261113-155452.zip**.

El lector debe mostrar 5201 ×599, 6404 ×10 y el error USB registrado -5. No hace
falta repetir JointCoarse ni ejecutar LinearHall para revisar ese archivo.
El 100 % de esta acción significa análisis del ZIP finalizado; no es calibración.

La definición común de calibración identifica el estado 04 como TIMEOUT.
Se revisaron los enums y el decodificador nativo estáticamente en una referencia
pública de DJI Fly. La autenticidad del APK y la semántica exacta del firmware
Flip no están verificadas. No se asigna una causa mecánica a partir de ese código.

El informe de las pruebas conserva el estado y el error de lectura posterior.
Los informes contradictorios 64 04 y 64 00 no se convierten en éxito.
Las peticiones y restricciones experimentales JointCoarse/LinearHall se conservan.
No se añaden órdenes de fábrica, reintentos ni parámetros IMU fijos.

392 pruebas de aplicación/interfaz y 11 de empaquetado aprobadas. EXE x64 bajo
Wine con capturas sintéticas; sin hardware Flip en cloud. Se incluyen fuentes,
licencias, informe de investigación y validación. No se redistribuyen capturas
originales ni bibliotecas DJI.

[Investigación 64 04](../dji-repair-studio/INFORME-FLIP-6404.md) ·
[DJI Flip](../dji-repair-studio/DJI-FLIP.md) ·
[Mini 4 Pro](../dji-repair-studio/VISION-MINI4PRO.md) ·
[Air 3](../dji-repair-studio/VISION-AIR3.md)
