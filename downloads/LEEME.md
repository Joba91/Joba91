# DJI REPAIR Studio 1.2.1

[Descargar Windows 10/11 x64](https://raw.githubusercontent.com/Joba91/Joba91/main/downloads/DJI_Repair_Studio_1.2.1.zip)

Extrae todo el ZIP en una carpeta nueva y abre **DJI REPAIR Studio 1.2.1.exe**.
No necesita la instalación anterior ni Python instalado.

Esta revisión corrige el análisis de registros DJI Test en la pestaña **Visión Mini 4 Pro**:

- Detecta el formato DJI y su codificación GB18030/UTF-8/UTF-16.
- Evita contar dos veces CMD y su copia de la capa `cmd Send`.
- Distingue ecos, asociación histórica y correlación de cabeceras; no infiere éxito.
- Muestra etiquetas de sensores como datos históricos, sin atribuirlas al dron conectado.
- Conserva inventario ZIP/carpetas, MD5/SHA-256, capturas binarias y exportación JSON.

Para analizar, extrae tus registros y usa **Analizar captura visión**, formato `auto`
o `djilog`. Importar un ZIP inventaría sus archivos; no ejecuta automáticamente los registros.
Los informes locales pueden contener números de serie históricos aportados por el usuario.

**La lectura USB, descarga e instalación de calibraciones Mini 4 Pro siguen deshabilitadas.**
El lector se contrastó con los 89 registros recibidos: 367 CMD y 367 ACK etiquetados,
734 tramas con CRC válido y 150 ACK distintos. Cuatro entradas ACK son ecos y 188
asociaciones no cumplen la correlación de cabeceras. No se reproducen esos comandos.
No hay endpoints confirmados ni decodificación validada de los payloads de sensores.

[Informe de investigación](../dji-repair-studio/INVESTIGACION-REGISTROS-MINI4PRO.md) ·
[Uso y arquitectura](../dji-repair-studio/VISION-MINI4PRO.md) · [Código](../dji-repair-studio)

Validación: 85 pruebas de aplicación, 8 de empaquetado y ejecución del EXE bajo Wine
con los 89 registros. No probado en Windows nativo, servidores DJI ni hardware físico.
No se ejecuta DJI Test.exe ni se cargan DLL del paquete. Los registros originales,
credenciales y números de serie no se redistribuyen. MD5 no demuestra autenticidad
ni compatibilidad por unidad. Se conserva la corrección de inicio ordinal 380.

Los otros modelos mantienen sus funciones y restricciones previas. Las calibraciones
de gimbal siguen siendo experimentales; lee LEEME.txt antes de utilizarlas.

El ZIP incluye ejecutable, fuentes, pruebas, documentación y licencias.
Verifica su integridad con **SHA256SUMS.txt**.
