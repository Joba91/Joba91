# DJI REPAIR Studio 1.2.5

[Descargar Windows 10/11 x64](https://raw.githubusercontent.com/Joba91/Joba91/main/downloads/DJI_Repair_Studio_1.2.5.zip)

Extrae el ZIP en una carpeta nueva y abre **DJI REPAIR Studio 1.2.5.exe**.

## Corrección de selección MI04

El informe de 1.2.4 muestra que libusb0 enumera seis entradas 2CA3:0020 y se
detiene antes de leer. Ese número no acredita seis aeronaves: puede representar
interfaces de un dispositivo compuesto. La revisión identifica cada alias por
sus HardwareID locales de Windows y exige **una única MI04**. No elige el primer
resultado ni abre otras interfaces para probarlas. Mantiene las comprobaciones
de producto, configuración y endpoints y no instala ni sustituye controladores.

También genera automáticamente un ZIP con la captura y el informe JSON, incluso
cuando falla la apertura o el .bin queda vacío. No se sube ningún archivo de forma
automática. Los archivos existentes se conservan.

## Prueba

1. Conecta el Mini 4 Pro en modo normal y cierra otros clientes USB del PC.
2. Abre **Visión Mini 4 Pro** y escribe **01.00.1100** en Firmware declarado,
   si esa es la versión de tu aeronave en DJI Fly.
3. Pulsa **Capturar USB pasivo**, elige un archivo **nuevo** `.bin` y espera.
4. Comparte el **ZIP Mini4Pro-USB-....zip** que se crea junto al `.bin`.
   Incluye `DJI-REPAIR-informe.json`; no hace falta comprimir el .bin manualmente.

Guardar informe sigue disponible como exportación JSON manual. Si no se puede
crear el ZIP, el resultado indica el error y permite guardar ese JSON.

La captura solo recibe de IN 85 en la interfaz 4, durante 5/10 segundos tras abrir
o hasta 1 MiB. El porcentaje mide tiempo de recepción. No consulta activamente
sensores ni inicia fábrica, calibración, reset, escritura o cambios de firmware.
Una captura vacía no demuestra avería: el informe distingue la falta de tráfico
del fallo al abrir. Las consultas activas y calibraciones Mini 4 Pro siguen pendientes.

[Investigación](../dji-repair-studio/INVESTIGACION-REGISTROS-MINI4PRO.md) ·
[Uso y arquitectura](../dji-repair-studio/VISION-MINI4PRO.md) · [Código](../dji-repair-studio)

Validación: **149 pruebas de aplicación y 9 de empaquetado** aprobadas. El EXE
arranca bajo Wine, carga ambas bibliotecas USB y las APIs Windows, selecciona
MI04 entre seis entradas simuladas y crea un ZIP con captura e informe sintéticos.
La consulta física al controlador y la recepción real siguen pendientes; no se
declara prueba en Windows nativo o con un dron. El ZIP contiene fuentes, licencias
y fuente correspondiente de libusb-win32, sin instaladores ni drivers binarios.
Los adjuntos originales e identificadores de unidad no se publican.
Consulta **SHA256SUMS.txt** para la huella del paquete.
