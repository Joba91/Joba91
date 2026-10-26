# DJI REPAIR Studio 1.5.0

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
El diagnóstico HMS experimental solicita publicación de estados con una petición
21/05 payload 01 al perfil nativo 0a→1d y escucha ocho segundos. El parser 21/06
agrupa emisores, ciclos, fragmentos y registros de seis bytes. Muestra códigos y
niveles brutos, sin aplicar a Mini 4 Pro el mapa de alarmas de otros modelos.
Ciclos vacíos, huecos o silencio no prueban salud. No implementa clasificación
de salud validada, descarga/instalación o calibración óptica. No envía reset global
de suscriptores; la publicación después de cerrar USB es desconocida. Su soporte
HMS en modo normal con este firmware requiere prueba física.

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
receptores simulados y una sola raíz Tk. No equivale a Windows nativo o prueba física HMS.
Dos capturas SN del usuario se reanalizaron: cuatro series estables, 272/267
tramas válidas. No contienen HMS y no validan la nueva solicitud. 262 pruebas de aplicación/interfaz y 9 de empaquetado.

Se contrastaron las peticiones contra 188 tramas históricas completas. El lector
interpreta 89 registros/734 tramas y convierte 184 SN coincidentes con sus etiquetas;
cuatro bloques siguen desconocidos. El BIN pasivo 1.2.6 del usuario se reanalizó:
6123 bytes, 104 tramas válidas, sin SN 24/26. Eso acredita recepción, no consulta activa.
No se publican adjuntos ni identificadores reales de unidad.

Código base GPLv3: LICENSE-GPL-3.txt y avisos de los archivos originales.
El ZIP incluye licencias de dependencias y fuentes de libusb-win32.

`vision_hms.py` es un parser propio sin USB; `vision_hms_query.py` expone solo la
petición HMS permitida y el receptor con límites. Datos desconocidos conservan su
procedencia. Se consultaron como referencia de datos fuentes públicas OSDK y
disectores DUML, con las diferencias de destino/bitfields documentadas en la
investigación. No se incorpora código propietario ni cabeceras SDK a la aplicación.

## Corrección 21/08 en 1.5.0

1.4.0 omitía mensajes extendidos que ya estaban en las capturas. Ahora se reconocen
ambas familias, sin mezclar sus ciclos. En tres archivos se contrastaron 121 mensajes,
234 cuerpos tag0/longitud20 y un registro de otro tipo conservado opaco. El BIN existente
se abre con Analizar captura visión, sin USB. Los originales no se redistribuyen.

Del cuerpo de veinte bytes se expone el primer uint32 LE como código candidato.
Los otros campos permanecen opacos. Un cambio de cuerpo conserva variantes separadas;
no se asume qué significa un bit de actividad, nivel, índice o fecha. Se muestran seis
referencias del SDK calificadas y actividad desconocida. Los cuatro identificadores
1A510380/382/384/385 no prueban por presencia un fallo activo o necesidad de calibración.
Las referencias son contexto histórico, sin validar la clasificación Mini 4 Pro.
El EXE bajo Wine reanaliza los tres archivos y prueba ambos formatos con datos sintéticos.
No cambia la petición USB de HMS ni habilita comandos adicionales o calibraciones.
