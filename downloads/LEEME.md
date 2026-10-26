# DJI REPAIR Studio 1.4.0

[Descargar Windows 10/11 x64](https://raw.githubusercontent.com/Joba91/Joba91/main/downloads/DJI_Repair_Studio_1.4.0.zip)

Extrae el ZIP en una carpeta nueva y abre **DJI REPAIR Studio 1.4.0.exe**.

## Probar diagnóstico HMS

1. Conecta el Mini 4 Pro encendido en modo normal. Cierra DJI Assistant y otros
   clientes USB del PC; conserva el controlador existente.
2. En **Visión Mini 4 Pro**, escribe **01.00.1100** en Firmware declarado,
   si coincide con la versión de aeronave de DJI Fly.
3. Pulsa **Diagnóstico visión (HMS)** y guarda un `.bin` **nuevo**.
4. Espera la apertura y ocho segundos de escucha. Comparte el **ZIP Mini4Pro-HMS-....zip**
   creado junto al BIN, incluso si no recibió mensajes o falló la apertura.

La nueva acción envía **una solicitud de publicación de estados**, familia 21/05,
payload 01, al perfil del programa nativo aportado. No realiza un barrido o repite
envíos. No inicia modo fábrica, autotest, calibración, motores o escritura de firmware.
No se envía el reset global de suscriptores del SDK; el estado de publicación al
cerrar USB queda desconocido. No se cambia el controlador.

**Es experimental: el soporte HMS y sus códigos en Mini 4 Pro aún requieren validación.**
La tabla muestra código recibido, emisor, índice, nivel bruto y completitud del ciclo.
No se aplican descripciones de otros modelos ni se asignan automáticamente códigos
a visión. El formato de referencia se reconstruyó del lector nativo y se contrastaron
campos con OSDK; existen diferencias documentadas de destino y bitfields.

Un ciclo vacío, ningún código o silencio no significan sensores sanos. El 100 % mide
el tiempo de escucha. Un ACK aceptado tampoco determina salud o calibración.
Fragmentos, formatos desconocidos, contradicciones y errores quedan en el informe.
La recepción tiene límite de 1 MiB/10000 lecturas; una llamada USB en curso puede
terminar después del plazo. Detener conserva el resultado parcial.

El ZIP incluye recepción binaria y JSON con petición, ACK, ciclos y datos brutos.
Se crea incluso con fallo y no se sobrescribe o sube automáticamente. Si falla el
ZIP, usa Guardar informe. Los informes locales pueden contener series; revísalos
antes de publicarlos. Las acciones SN y recepción pasiva siguen disponibles.

246 pruebas de aplicación/interfaz y 9 de empaquetado aprobadas. El EXE bajo Wine
prueba HMS simulado, tabla y ZIP. No se realizó aquí una consulta HMS física o
prueba de Windows nativo. Las dos capturas SN del usuario se reanalizaron: cuatro
series estables y sin HMS; no validan la nueva ruta ni la salud de los sensores.

[Uso y arquitectura](../dji-repair-studio/VISION-MINI4PRO.md) ·
[Investigación](../dji-repair-studio/INVESTIGACION-REGISTROS-MINI4PRO.md) ·
[Código](../dji-repair-studio). Fuentes, licencias y fuente de libusb-win32 incluidas.
Sin DLL propietarias DJI, credenciales, capturas originales, instaladores o drivers.
Consulta **SHA256SUMS.txt** para verificar la descarga.
