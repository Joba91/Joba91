# DJI REPAIR Studio 1.2.3

Añade Capturar USB pasivo a la interfaz Mini 4 Pro. El usuario aportó descriptores
actuales de configuración 1 High-Speed, interfaz 4 / alternativa 0, bulk IN 85 y
OUT 04 de 512 bytes y declara firmware de aeronave 01.00.1100 desde DJI Fly.
El receptor comprueba ese perfil y solo lee IN 85, durante 5/10 segundos o 1 MiB.
No emite comandos DJI, cambia modo, configuración, drivers o firmware.

Guarda una captura nueva sin sobrescribir archivos, conserva los datos parciales
al detener y exporta bytes, duración, timeouts, errores y tramas al informe JSON.
Cero bytes no se interpreta como avería. La consulta activa de sensores permanece
sin validar, al igual que descarga e instalación de calibración.

Validación: 118 pruebas de aplicación y 8 de empaquetado. El EXE bajo Wine recorre
la captura con un receptor sintético y vuelve a analizar los 89 registros recibidos.
Hardware y acceso real al driver pendientes; no hay prueba en Windows nativo.
Los originales de UsbTreeView con identificadores de unidad no se distribuyen.
