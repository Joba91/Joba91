# Visión Mini 4 Pro · DJI REPAIR Studio 1.2.4

Estado: diagnóstico de archivos y recepción USB pasiva implementados. La consulta
activa de sensores, descarga e instalación de calibraciones siguen pendientes.

## Uso

1. Abre la pestaña **Visión Mini 4 Pro**. El lateral se desplaza a sus acciones.
2. **Importar carpeta visión** o **Importar ZIP visión** inventaría el paquete en
   solo lectura. No se extraen ZIP, ejecutan programas, cargan DLL ni instalan datos.
3. Revisa **Inventario local** y **Resultados y evidencia**. Se calculan MD5 y
   SHA-256. Se distinguen estados confirmado, desconocido y error.
4. **Analizar captura visión** lee un registro o una captura sin conexión. Formatos:
   `binary` (bytes crudos), `hexlog` (texto HEX), `djilog` (registros DJI Test) y `auto`. `.bin/.raw/.dump` se
   consideran binarios en auto. Los registros admiten UTF-8/UTF-16/GB18030 y volcados HEX
   con marcas TX/RX o direcciones de línea. Para otros formatos, falta evidencia.
   Cuando contiene los registros binarios de percepción contrastados, abre
   **Sensores del registro**: SN desde payload, posición histórica, línea y contraste
   con etiqueta. Los datos no identifican el dron conectado. Los bloques inválidos
   permanecen desconocidos. Se muestran hasta 200; el contraste de etiquetas usa
   la vista limitada de etiquetas del archivo.
5. **Capturar USB pasivo** recibe datos de IN `85`, interfaz `4`, sin enviar
   peticiones de servicio. Requiere Mini 4 Pro, firmware **declarado** `01.00.1100`,
   configuración 1, alternativa 0 y endpoints bulk IN `85` / OUT `04`
   de 512 bytes. Escribe el firmware de DJI Fly en el campo correspondiente.
   Cierra otros clientes USB del PC y conserva el modo normal. Elige un archivo
   **nuevo** `.bin`; se conservan los archivos existentes.
   La ventana de recepción es de 5/10 segundos tras abrir el dispositivo y tiene
   límite de 1 MiB. El porcentaje mide ese tiempo, sin medir diagnóstico o calibración.
   El análisis y la apertura tienen su propio tiempo. Detener conserva los bytes
   recibidos. Una captura de cero bytes no demuestra avería: puede no existir tráfico
   espontáneo sin una consulta activa. No captura la sesión USB de otra aplicación.
   No se cambian drivers, configuración USB, alternativa, modo o firmware. No se
   desprende el controlador ni se limpia un halt; los errores se informan. El acceso
   exige un controlador ya compatible con libusb. La disponibilidad real se valida
   en el PC del usuario; este entorno no tiene el dron conectado.
6. **Identificación visión** informa por qué la consulta activa no está disponible.
7. Opcional: escribe un servidor autorizado `https://host:puerto` y pulsa
   **Comprobar servidor visión**. No hay dirección ni comprobación automática.
   El sondeo verifica solo TCP/TLS y su certificado, sin HTTP, autenticación ni
   descarga. No acepta credenciales, tokens ni cookies en la URL. Los errores no
   demuestran que el servidor esté apagado. Se limita a 3/5/10 segundos, incluyendo
   DNS e inicio del proceso. El proveedor no implementa todavía la API de descarga.
8. **Guardar informe** exporta los últimos resultados de cada categoría en JSON.
   El inventario visual muestra hasta 500 archivos y los detalles hasta 200;
   el informe conserva todo el inventario y hasta 200 tramas/incidencias de muestra,
   junto con los contadores totales. Solo se conserva el último paquete/captura/servidor.

## Integridad y compatibilidad

Se reconocen manifiestos de texto GNU `MD5SUMS`/`.md5` y BSD `MD5 (archivo) = hash`.
Las rutas son relativas a la carpeta del manifiesto. Las entradas duplicadas,
rutas no admitidas, archivos ausentes, MD5 distintos, lectura fallida o líneas no
reconocidas producen error. Sin manifiesto o con cobertura parcial, el estado es
desconocido. Otros formatos del paquete DJI requieren inspeccionar los archivos
reales y añadir su lector; no se presupone que utilicen uno de estos formatos.

**Una coincidencia MD5 solo acredita la coincidencia con ese manifiesto local.**
No verifica autoría, autenticidad, modelo, firmware, sensores ni números de serie.
SHA-256 registra una huella local, sin aportar autenticidad por sí solo.
Los archivos `.bin/.dat/.cal/.cali` se enumeran como candidatos sin compatibilidad
confirmada; no son seleccionables para instalación. No se interpretan números de
serie a partir de nombres ni se promete generar calibración óptica nueva.

Límites: 5000 archivos, 256 MiB por archivo, 2 GiB por paquete, 4 MiB por manifiesto;
capturas hasta 32 MiB y 100000 tramas. Se rechazan ZIP cifrados, enlaces, nombres
ambiguos para Windows y relaciones de compresión excesivas. La cancelación detiene
la lectura local; no actúa sobre el dron.

## Compatibilidad con libusb0 en Windows

El usuario informó que MI04 tiene servicio `libusb0_device`, estado OK y código
0. La captura de la versión 1.2.3 falló antes de cualquier lectura con el mensaje
`Operation not supported or unimplemented on this platform`, correspondiente a
`LIBUSB_ERROR_NOT_SUPPORTED` de la biblioteca usada. No se diagnosticaron sensores.

La versión 1.2.4 incluye la biblioteca de usuario **libusb-win32 1.4.0.2 amd64** y
prioriza `libusb0` en Windows. No instala, cambia ni sustituye el controlador.
El código permite probar libusb 1.0 si la primera biblioteca no carga, no encuentra
el dispositivo o comunica operación no soportada. No elude perfiles incorrectos,
dispositivos ambiguos, acceso denegado o dispositivo ocupado mediante otro backend.

PyUSB/libusb0 no informa la velocidad: `speed_verified` queda falso y el valor
es `no_informada_por_libusb0`. Producto, configuración 1, interfaz 4/alternativa 0,
clase y endpoints bulk IN 85 / OUT 04 de 512 bytes se siguen comprobando. Con
libusb 1.0 se mantiene además la comprobación de velocidad High-Speed.

El JSON guarda la API elegida en `usb_capture.usb.backend` y los errores por fase
en `usb_capture.opening_diagnostics`. Se distinguen carga de biblioteca, enumeración,
configuración, lectura de descriptor de producto, perfil y reclamación de interfaz.
Si falla después de abrir, conserva el error de lectura, los intentos y el archivo
parcial. Esto no acredita por sí solo una consulta de sensores válida.

La DLL original x64 se verificó contra la huella del ZIP publicada por su autor.
Procedencia, licencias y fuente completa correspondiente están en `native/` y en
el directorio de licencias del ZIP. Solo se incluye la biblioteca de usuario,
sin programas de instalación, filtros o controladores binarios. El acceso físico
al servicio del usuario sigue pendiente; la carga de ambas bibliotecas sí se
comprobó bajo Wine.

## Arquitectura

- `vision_packages.py`: inventario, huellas y verificación MD5, sin red ni interfaz.
- `vision_protocol.py`: tramas, codificaciones y detección de formato.
- `vision_history.py`: capa CMD/ACK de registros DJI; distingue duplicados, ecos y
  correlación. Reutiliza el CRC de `studio_protocol.py`.
- `vision_sensor_records.py`: conversión binaria de registros de sensores 24/26,
  independiente de las DLL y sin consultas USB.
- `vision_usb_passive.py`: receptor restringido a IN; no expone escritura, fábrica,
  reset, cambios de configuración o de driver. Guarda una captura nueva y sus métricas.
- `vision_interfaces.py`: contratos de transporte pasivo, identificación y proveedor
  de calibraciones. Proveedor local y estado explícito de identificación no disponible.
- `vision_services.py`: proveedor de servicios configurable y sondeo en un proceso
  separado con tiempo máximo. TLS conserva la validación de certificados.
- `vision_view.py`: controles Tk; no abre archivos, red ni USB por su cuenta.
- `studio_app.py`: acciones laterales, trabajo en segundo plano, progreso e informes.

No hay puente a DLL propietarias. Ninguna DLL del paquete se carga o redistribuye.
La implementación nueva no tiene instalador de calibraciones ni emisor de comandos
de servicio Mini 4 Pro. Al seleccionar **Mini 4 Pro**, se bloquean las acciones
activas genéricas
de la aplicación, para que no se reutilice por accidente un protocolo de otro modelo.
Los módulos anteriores para otros modelos conservan su comportamiento y restricciones.

## Evidencia y bloqueos reales

Se recibieron el informe de análisis y un ZIP reducido con 89 registros y dos
configuraciones cifradas. La revisión confirmó 734 tramas CMD/ACK con CRC válido,
150 ACK distintos y la presencia histórica de VID/PID/interfaz. Los registros
mezclan fechas/estaciones/modelos; no prueban compatibilidad con el dron actual.
Se recibieron y analizaron estáticamente DJI_Protocol_Comm.dll y
dji_test_userlibs.dll: el nuevo decodificador recupera 184 SN de payloads, todos
coincidentes con etiquetas históricas; cuatro bloques quedan desconocidos.
Se recibió después el reporte UsbTreeView del Mini 4 Pro actual: interfaz 4,
IN 85, OUT 04, 512 bytes; firmware 01.00.1100 declarado por el usuario. El receptor
comprueba esos descriptores al abrir. No se ha validado acceso físico real ni
consultas activas. Faltan los 16 archivos/manifiesto MD5 del informe.

[Resultados del análisis y evidencia pendiente](INVESTIGACION-REGISTROS-MINI4PRO.md).
Los nombres de funciones del informe no se usan como firmas para invocar DLL.
La arquitectura y las dependencias se deben verificar contra los binarios reales.
No se han consultado los servidores históricos ni se han utilizado sus credenciales.

Para habilitar **consultas USB activas**: capturas con peticiones y respuestas
completas en modo normal, correlación validada, identificadores y efectos de comandos
verificados. La recepción pasiva no acredita esos requisitos. Para **descarga**: API/servicio vigentes, acceso autorizado, autenticación
configurada sin reutilizar secretos del paquete y correspondencia demostrada entre
identificadores de módulos/sensores y datos. Para una futura **escritura**: además,
protocolo validado, correspondencia por unidad, secuencia transaccional, recuperación
ante fallos y pruebas físicas. Ninguna de estas etapas se declara completada.

## Verificación

Consulta `validacion-1.2.4.json` y `test-results-1.2.4.txt` para los resultados de
esta entrega. Las pruebas cubren tramas válidas, CRC dañados, truncadas, concatenadas,
longitudes incorrectas, recuperación, manifiestos, errores de importación, cancelación,
límites, bloqueo de USB, sondeo solo solicitado y exportación desde la interfaz.
El lector se contrastó con los registros recibidos; falta validar el paquete completo,
servidores DJI y hardware físico. La ruta pasiva se prueba con receptores sintéticos
y USB simulado, no con hardware. Las etiquetas de serie del registro son históricas,
no una identificación del equipo conectado.
