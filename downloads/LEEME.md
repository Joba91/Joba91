# DJI REPAIR Studio 1.2.3

[Descargar Windows 10/11 x64](https://raw.githubusercontent.com/Joba91/Joba91/main/downloads/DJI_Repair_Studio_1.2.3.zip)

Extrae el ZIP en una carpeta nueva y abre **DJI REPAIR Studio 1.2.3.exe**.
No necesita la instalación anterior, Python ni las DLL oficiales de DJI.

## Nueva prueba: recepción USB pasiva

1. Conecta el Mini 4 Pro en modo normal. Cierra otros programas del PC que usen su USB.
2. Abre **Visión Mini 4 Pro** y escribe **01.00.1100** en **Firmware declarado (DJI Fly)**,
   si esa es la versión que muestra la aplicación para tu aeronave.
3. Pulsa **Capturar USB pasivo** y elige un archivo **nuevo** `.bin`.
4. Espera 5 segundos y usa **Guardar informe** para exportar el JSON de resultados.

Se comprueba el descriptor de producto, configuración 1 High-Speed, interfaz 4 /
alternativa 0 y endpoints bulk IN `85` / OUT `04` de 512 bytes antes de reclamar
la interfaz. El programa solo recibe de IN `85`: no envía peticiones de servicio,
modo fábrica, calibración, reset o cambio de configuración/driver. El firmware
es declarado por el usuario, no leído ni validado por una consulta al dron.

**Esta es una prueba del canal de recepción, no una consulta activa de SN o salud.**
Puede recibir cero bytes si no existe tráfico espontáneo. Una captura vacía no
significa que los sensores fallen. No es un monitor del tráfico de otra aplicación.
Si el acceso falla, conserva el error en el informe; no instala ni cambia drivers.
Se limita a 5/10 segundos tras la apertura o 1 MiB. El porcentaje mide tiempo de
recepción. Detener guarda datos parciales; no se sobrescriben archivos existentes.

Conserva el analizador de archivos: GB18030/UTF-8/UTF-16, CRC, detección de ecos,
conversión de SN desde el formato contrastado y exportación JSON. En los registros
recibidos se verificaron 184 SN con 184 etiquetas coincidentes, sin atribuirlos al
equipo actual. La descarga e instalación de calibraciones siguen sin habilitarse.

[Investigación](../dji-repair-studio/INVESTIGACION-REGISTROS-MINI4PRO.md) ·
[Uso y arquitectura](../dji-repair-studio/VISION-MINI4PRO.md) · [Código](../dji-repair-studio)

Validación: 118 pruebas de aplicación, 8 de empaquetado y arranque del EXE bajo Wine.
La ruta de captura se verifica con receptores sintéticos y dependencias USB simuladas.
No se ha probado con hardware real ni Windows nativo. No se ejecutan programas ni
DLL oficiales DJI; tampoco se publican registros originales, credenciales o series reales.
Se mantiene la corrección del ordinal 380, una sola ventana, acciones laterales y progreso.

Los otros modelos conservan sus funciones y restricciones previas. Consulta LEEME.txt.
El ZIP contiene EXE, fuentes, pruebas, documentación y licencias. Su huella está en
**SHA256SUMS.txt**.
