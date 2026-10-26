# DJI REPAIR Studio 1.2.6

[Descargar Windows 10/11 x64](https://raw.githubusercontent.com/Joba91/Joba91/main/downloads/DJI_Repair_Studio_1.2.6.zip)

Extrae el ZIP en una carpeta nueva y abre **DJI REPAIR Studio 1.2.6.exe**.

## Identificación del producto Mini 4 Pro

El informe de 1.2.5 demuestra que MI04 se seleccionó y se leyó la configuración,
pero se detuvo antes de recibir datos porque el nombre de la interfaz no pasó
la comprobación. No guardaba el valor recibido. UsbTreeView sigue indicando
Mini 4 Pro en el producto del dispositivo físico.

1.2.6 consulta el padre físico asociado exactamente al alias MI04. Un descriptor
hijo genérico o ausente solo se admite si ese padre acredita VID/PID 2CA3:0020
y producto Mini 4 Pro. La consulta de metadatos se cierra antes de la apertura
exclusiva USB. Otro modelo explícito o una asociación inválida bloquean la recepción.
El informe conserva ambas lecturas y los errores precisos. No cambia drivers.

## Prueba

1. Conecta el Mini 4 Pro en modo normal y cierra otros clientes USB del PC.
2. Abre **Visión Mini 4 Pro** y escribe **01.00.1100** en Firmware declarado,
   si esa es la versión de tu aeronave en DJI Fly.
3. Pulsa **Capturar USB pasivo**, elige un archivo **nuevo** `.bin` y espera.
4. Comparte el **ZIP Mini4Pro-USB-....zip** creado junto al `.bin`.
   Incluye captura e informe, incluso si no recibió datos o falló la apertura.

La recepción lee IN 85 de MI04 durante 5/10 segundos o hasta 1 MiB. El porcentaje
mide tiempo. Cero bytes no significa avería. No consulta activamente sensores ni
inicia calibración, fábrica, escritura o cambios de firmware/controladores.
No se suben archivos automáticamente. El informe local puede incluir el producto
con identificador de unidad; revísalo antes de publicarlo.

[Investigación](../dji-repair-studio/INVESTIGACION-REGISTROS-MINI4PRO.md) ·
[Uso y arquitectura](../dji-repair-studio/VISION-MINI4PRO.md) · [Código](../dji-repair-studio)

Validación: **170 pruebas de aplicación y 9 de empaquetado** aprobadas; arranque
del EXE y carga de APIs bajo Wine, con asociación de padre y buffers sintéticos.
La consulta del padre y recepción físicas siguen pendientes. No se declara prueba
en Windows nativo o con un dron. Incluye fuentes, licencias y fuente correspondiente
de libusb-win32, sin instaladores ni drivers binarios. Los adjuntos originales e
identificadores reales de unidad no se publican. Consulta **SHA256SUMS.txt**.
