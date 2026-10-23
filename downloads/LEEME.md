# DJI REPAIR Studio 1.2.2

[Descargar Windows 10/11 x64](https://raw.githubusercontent.com/Joba91/Joba91/main/downloads/DJI_Repair_Studio_1.2.2.zip)

Extrae todo el ZIP en una carpeta nueva y abre **DJI REPAIR Studio 1.2.2.exe**.
No necesita la instalación anterior, Python instalado ni las DLL propietarias DJI.

Esta revisión incorpora la conversión de números de serie desde los registros
binarios de percepción, reconstruida mediante análisis estático de las dos DLL
aportadas. No se cargan ni distribuyen esas DLL.

- La nueva tabla **Sensores del registro** muestra SN desde payload, posición histórica,
  línea del registro y contraste con la etiqueta cuando existe.
- Se validaron 184 SN convertidos con 184 coincidencias exactas en los registros recibidos.
  Cuatro bloques sin SN válido permanecen desconocidos.
- Conserva la lectura GB18030/UTF-8/UTF-16, CRC, detección de ecos y exportación JSON.
- No asigna las identidades históricas al equipo conectado ni infiere salud o calibración.

Extrae tus registros y usa **Visión Mini 4 Pro → Analizar captura visión**, formato
`auto` o `djilog`. El ZIP importado solo se inventaría; sus programas no se ejecutan.
Los informes exportados localmente pueden contener los números de serie del archivo elegido.

**La lectura USB, descarga e instalación de calibraciones Mini 4 Pro siguen deshabilitadas.**
El análisis identificó rutas USB con endpoints configurables o descubiertos por descriptores;
faltan los descriptores del dron actual y la validación de la consulta en modo normal.
No se reproducen los flujos históricos de modo fábrica o escritura.

[Informe de investigación](../dji-repair-studio/INVESTIGACION-REGISTROS-MINI4PRO.md) ·
[Uso y arquitectura](../dji-repair-studio/VISION-MINI4PRO.md) · [Código](../dji-repair-studio)

Validación: 98 pruebas de aplicación, 8 de empaquetado y arranque del EXE bajo Wine
con los 89 registros recibidos. No probado en Windows nativo, servidores DJI ni hardware físico.
Se mantiene la corrección del ordinal 380, una sola ventana, acciones laterales y progreso.
Los registros originales, credenciales y números de serie reales no se publican.

Los otros modelos mantienen sus funciones y restricciones previas; lee LEEME.txt.
El ZIP incluye EXE, fuentes, pruebas, documentación y licencias. Verifica su integridad
con **SHA256SUMS.txt**.
