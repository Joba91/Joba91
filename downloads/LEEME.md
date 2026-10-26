# DJI REPAIR Studio 1.2.4

[Descargar Windows 10/11 x64](https://raw.githubusercontent.com/Joba91/Joba91/main/downloads/DJI_Repair_Studio_1.2.4.zip)

Extrae el ZIP en una carpeta nueva y abre **DJI REPAIR Studio 1.2.4.exe**.
No necesita la instalación anterior ni Python. Conserva una sola ventana.

## Corrección para el controlador libusb0_device existente

La versión anterior intentaba libusb 1.0 y el informe recibido mostraba
`Operation not supported or unimplemented on this platform` antes de leer.
El usuario confirmó que MI04 usa `libusb0_device`, estado OK y código 0.
Esta entrega incluye la biblioteca de usuario oficial **libusb-win32 1.4.0.2 x64**
y prioriza libusb0 en Windows. **No instala ni cambia el controlador del PC.**

Si la apertura vuelve a fallar, el JSON registra la API, fase y excepción exactas.
libusb0 no informa la velocidad: se declara desconocida. Se siguen verificando
producto Mini 4 Pro, configuración 1, interfaz 4 / alternativa 0, clase y endpoints
bulk IN `85` / OUT `04` de 512 bytes. No se inventa una velocidad confirmada.

## Prueba con el dron

1. Cierra otros programas del PC que usen su USB y conecta el dron en modo normal.
2. Abre **Visión Mini 4 Pro** y escribe **01.00.1100** en **Firmware declarado (DJI Fly)**
   si esa es la versión de tu aeronave.
3. Pulsa **Capturar USB pasivo**, elige un archivo **nuevo** `.bin` y espera a que termine.
4. Usa **Guardar informe** para exportar el **JSON** de esa prueba.

La captura solo recibe desde IN 85, durante 5/10 segundos tras abrir o hasta 1 MiB.
El porcentaje mide tiempo de recepción. Detener conserva bytes parciales y no se
sobrescriben archivos. Una captura vacía no demuestra avería ni garantiza que se
abrió USB; el JSON permite distinguir falta de tráfico y error de apertura.
**La consulta activa de sensores y la calibración Mini 4 Pro siguen pendientes.**
No se envían peticiones de servicio, fábrica o calibración ni se alteran drivers,
configuración USB o firmware. No es un monitor del tráfico de otra aplicación.

Se conserva el analizador de archivos, las conversiones de SN del formato
contrastado y los informes anteriores. Las identidades de registros históricos
no se asignan al dron actual. Los otros modelos conservan sus restricciones.

[Investigación](../dji-repair-studio/INVESTIGACION-REGISTROS-MINI4PRO.md) ·
[Uso y arquitectura](../dji-repair-studio/VISION-MINI4PRO.md) · [Código](../dji-repair-studio)

Validación: **126 pruebas de aplicación y 9 de empaquetado**, arranque del EXE y
carga de ambas bibliotecas USB bajo Wine. La captura usa receptores sintéticos
en esas pruebas; la recepción con hardware real y Windows nativo sigue pendiente.
El ZIP contiene fuentes, licencias y fuente correspondiente de libusb-win32.
No incluye controladores binarios, instaladores ni DLL propietarias DJI.
Los registros, identificadores de unidad y credenciales del usuario no se publican.
Verifica la huella del ZIP en **SHA256SUMS.txt**.
