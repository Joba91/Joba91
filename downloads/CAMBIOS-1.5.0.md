# DJI REPAIR Studio 1.5.0

Corrige la omisión de HMS 21/08 en 1.4.0. Los mensajes ya estaban en las tres
capturas aportadas: 121 paquetes, 234 cuerpos tag0/longitud20 y otro registro opaco.
El lector valida contador y longitudes TLV, conserva tipos/campos desconocidos y
separa ciclos 21/06 y 21/08. No colapsa variantes con metadatos distintos.

Muestra seis referencias breves de OSDK con actividad desconocida, sin aplicar
un mapa Mini 4 Pro validado o interpretar presencia de un código como fallo activo.
Índice/nivel de 21/08 se dejan vacíos y los dieciséis bytes adicionales quedan brutos.
Los códigos de referencia de calibración presentes no habilitan calibración ni
prueban necesidad de realizarla. No se recomienda formateo o reparación por el código solo.

Analizar captura visión permite reabrir el BIN existente sin conectar el dron.
La petición USB sigue siendo una 21/05 payload01; no agrega fábrica, reset o escritura.
262 pruebas de aplicación/interfaz y 9 de empaquetado aprobadas. El EXE bajo Wine
prueba ambos formatos y reanaliza los tres archivos privados, sin USB físico.
Los adjuntos e identificadores reales no se publican. Actividad/estado de alarmas
pendientes de contrastar con DJI Fly y campos del formato extendido.
