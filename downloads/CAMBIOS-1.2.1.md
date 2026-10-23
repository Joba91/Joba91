# DJI REPAIR Studio 1.2.1

El lector anterior trataba texto y copias de comandos de DJI Test como tráfico:
contabilizaba 1107 tramas y 66 incidencias en los registros recibidos. Se añade
un lector por marcas CMD/ACK que conserva la procedencia, evita doble conteo y
lee GB18030. Ahora contabiliza 734 tramas válidas y cero incidencias de framing.

El resultado distingue cuatro ecos y 188 asociaciones sin correlación de
cabeceras. Las etiquetas de serie son históricas. No se declara éxito de
calibración ni identificación actual. USB y escritura Mini 4 Pro siguen bloqueados.

El EXE se contrastó bajo Wine con los 89 registros: 367 CMD, 367 ACK etiquetados,
150 ACK distintos. Pasaron 85 pruebas de aplicación y 8 de empaquetado. No hay
pruebas en Windows nativo, con hardware ni con servidores DJI.

[Investigación y evidencia pendiente](../dji-repair-studio/INVESTIGACION-REGISTROS-MINI4PRO.md).
