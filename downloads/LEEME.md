# DJI REPAIR Studio 1.9.0

[Descargar ZIP con EXE · Windows 10/11 x64](https://raw.githubusercontent.com/Joba91/Joba91/main/downloads/DJI_Repair_Studio_1.9.0.zip)

Extrae en una carpeta nueva y abre **DJI REPAIR Studio 1.9.0.exe**.
**JointCoarse y LinearHall del Flip están disponibles como pruebas experimentales.
La compatibilidad con este modelo todavía no está validada físicamente.**

La captura 1.8.1 recibida confirma dos respuestas de versión correlacionadas en
MI04: controlador 01.00.0057 y gimbal 00.00.2052 (versiones internas de módulo).
Se pasa ahora a probar la petición común DJI de calibración, una sola vez.

## Primera prueba: JointCoarse

1. Selecciona **DJI Flip / USB bulk**, firmware declarado **01.00.1500**.
2. Pulsa **JointCoarse · prueba Flip**.
3. Selecciona tu **DJIFlip-Modulos-….zip** con las dos respuestas de versión.
4. Guarda un ZIP nuevo de prueba y lee la confirmación del programa.
5. Comparte **DJIFlip-JointCoarse-….zip**, incluso si hay error o no inicia.

El gimbal puede moverse por sus límites y el firmware puede guardar ajustes.
Retira el protector y las hélices y deja libre el recorrido. Detener lectura no
frena motores. Conviene revisar esa primera captura antes de probar LinearHall.

## Comportamiento y límites

Se comprueban de nuevo el producto/nodo/endpoints y ambas versiones actuales
contra el ZIP elegido. Progreso de calibración previo impide otra solicitud.
Solo una petición 04/08: 01 JointCoarse o 02 LinearHall. No se reenvía, activa
fábrica automáticamente, fuerza otra interfaz o escriben tablas IMU fijas.
El modo actual no está identificado; la rutina podría no iniciar si exige otro.

El 100 % exige ACK correlacionado admitido, progreso posterior conocido, fin
64 00 y ZIP guardado. Cuenta hitos de comunicación, no movimiento físico.
ACK solo, fin sin progreso, rechazo y tiempo agotado no se presentan como éxito.
Un resultado positivo es fin informado por el equipo, no exactitud metrológica
verificada. El informe mantiene desconocida la calibración realizada físicamente.

RX y auditoría se guardan en `gimbal.calibration_probe`, hasta 1 MiB y 180 segundos
como límites. La persistencia de parámetros por el firmware no está caracterizada.
No hay scripts de fábrica o reintentos automáticos ante un rechazo. [Detalle](../dji-repair-studio/DJI-FLIP.md).

373 pruebas de aplicación/interfaz y 11 de empaquetado aprobadas. EXE bajo Wine
con trazas sintéticas, sin Flip físico en cloud. Fuentes, licencias y verificaciones
incluidas. No se ejecutan programas DJI en desarrollo ni se redistribuyen sus
capturas o identificadores originales. Las funciones previas conservan sus límites.

[DJI Flip](../dji-repair-studio/DJI-FLIP.md) ·
[Mini 4 Pro](../dji-repair-studio/VISION-MINI4PRO.md) ·
[Air 3](../dji-repair-studio/VISION-AIR3.md) ·
[Código](../dji-repair-studio)
