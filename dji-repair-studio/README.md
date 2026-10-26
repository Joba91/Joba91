# DJI REPAIR Studio 1.3.0

Herramienta Windows de una sola ventana con recepción USB pasiva Mini 4 Pro,
análisis de archivos y **consulta SN experimental** en modo normal. La consulta
se limita a cuatro peticiones 24/26 reconstruidas de los registros, una por selector,
sin reintentos ni comandos de fábrica, calibración, configuración o firmware.
El funcionamiento en modo normal con firmware 01.00.1100 está pendiente de prueba.

[Descarga y prueba](../downloads/LEEME.md) · [Uso y arquitectura](VISION-MINI4PRO.md) ·
[Investigación](INVESTIGACION-REGISTROS-MINI4PRO.md)

La selección valida el perfil USB y la asociación MI04/padre físico. El resultado
muestra SN observados, sin declarar correlación, identidad o salud confirmadas.
La tabla conserva por separado datos actuales experimentales e históricos.
Cada prueba genera un ZIP local con RX binario y JSON con auditoría TX y errores.
No sube archivos. No carga ni redistribuye DLL propietarias o credenciales DJI.
No implementa diagnóstico de salud, descarga/instalación o calibración óptica.

## Desarrollo

Python 3.13 con Tcl/Tk. Instala `requirements.txt` en un entorno virtual y ejecuta
`python launch.py`. Pruebas: `python -m unittest discover -s tests -v`.
Compilación Windows: `build_windows.ps1`, PyInstaller onefile/windowed.
Incluye libusb-win32 1.4.0.2 amd64 de usuario, verificado y sin modificar, con
procedencia y fuente correspondiente. No instala o cambia controladores.

En el entorno cloud preparado, las dependencias están en
`/workspace/DJI-REPAIR-Studio/vendor`: usa
`PYTHONPATH=.:/workspace/DJI-REPAIR-Studio/vendor python3.13 -m unittest discover -s tests -v`.
Las pruebas gráficas requieren DISPLAY o Windows. El EXE se valida bajo Wine con
receptores simulados y una sola raíz Tk. No equivale a Windows nativo o prueba
física de consultas activas. 205 pruebas de aplicación/interfaz y 9 de empaquetado.

Se contrastaron las peticiones contra 188 tramas históricas completas. El lector
interpreta 89 registros/734 tramas y convierte 184 SN coincidentes con sus etiquetas;
cuatro bloques siguen desconocidos. El BIN pasivo 1.2.6 del usuario se reanalizó:
6123 bytes, 104 tramas válidas, sin SN 24/26. Eso acredita recepción, no consulta activa.
No se publican adjuntos ni identificadores reales de unidad.

Código base GPLv3: LICENSE-GPL-3.txt y avisos de los archivos originales.
El ZIP incluye licencias de dependencias y fuentes de libusb-win32.
