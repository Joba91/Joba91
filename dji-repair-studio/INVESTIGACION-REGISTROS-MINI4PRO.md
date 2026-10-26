# Investigación de DLL y registros · DJI REPAIR Studio 1.2.4

Se analizaron estáticamente los dos binarios recibidos y se contrastaron sus
estructuras con los 89 registros anteriores. No se cargaron ni ejecutaron las DLL.
No se contactó un dron ni los servidores históricos. Los originales, las series
reales y los datos de autenticación no se redistribuyen.

## Binarios comprobados

| Archivo | Tamaño | Arquitectura | Exportaciones | SHA-256 |
| --- | ---: | --- | ---: | --- |
| DJI_Protocol_Comm.dll | 527872 | PE32 x86 | 375 | `774f678f9b47684c0459edd256eb8e908373fc072ba56573fdd3379355f5aa8a` |
| dji_test_userlibs.dll | 8811520 | PE32 x86 | 1081 | `03a04ab846defd1be8fe5a36dd5c03b8c5389bf264f3ac3bb9782a5a033b0c83` |

Los recuentos coinciden con el informe anterior. Eso no demuestra por sí solo la
versión comercial del paquete ni compatibilidad con el firmware del usuario.
Ambos binarios necesitan dependencias C++ y contexto del framework; no son una API
C independiente que pueda llamarse directamente desde el EXE x64.

## Conversión de los números de serie

En `dji_test_userlibs.dll`, `TSGetPerceptionSensorSN` comienza en RVA `0x119c80`.
Construye una petición de la familia `24/26` y un payload de 15 bytes con una
máscara de sensor. En RVA `0x11a5da` comprueba que el registro recibido tenga al
menos 20 bytes, omite cuatro bytes y llama al conversor interno RVA `0x10f2f0`.
Este no trata el SN completo como ASCII directo: combina campos binarios.

El nuevo módulo propio `vision_sensor_records.py` interpreta únicamente el
formato de 20 bytes contrastado, con prefijo `00 a0 00` y selector conocido.
En el bloque siguiente de 16 bytes, los offsets empiezan en cero:

| Parte del SN | Campo y conversión observada |
| --- | --- |
| Prefijo de tres caracteres | Bytes 7, 6, 5 en ese orden |
| Código de proveedor | Byte 0; tabla nativa de cinco equivalencias o carácter alfanumérico |
| Tres caracteres de fecha | Bytes 8, 9, 10 con alfabetos acotados de año, mes y día |
| Dos caracteres adicionales | Bytes 2 y 1; cero binario se representa como ASCII `0` |
| Dígito decimal | Nibble bajo del byte 11 |
| Sufijo de cuatro caracteres | Bytes 12 a 15 |

Los bytes 3 y 4 y el nibble alto del byte 11 no se interpretan. No se infieren
modelo, fecha civil, estado de salud, calibración ni compatibilidad de esos campos.
Se rechazan valores que producirían NUL, interrogaciones o SN no alfanuméricos.
El parser no reproduce las sustituciones con pérdida de la DLL como identidades válidas.

En los registros recibidos:

- 188 bloques de la familia y tamaño observados.
- **184 SN recuperados del payload y 184 coincidencias exactas** con sus etiquetas,
  46 por cada posición histórica; ninguna discrepancia entre SN válidos y etiqueta.
- Cuatro bloques sin SN válido permanecen desconocidos.
- 188 selectores coinciden con la consulta adyacente registrada.

Los selectores `04`, `08`, `40` y `80` se asocian históricamente con `frontleft`,
`frontright`, `backleft` y `backright`. Esa posición no se asigna a un equipo actual.
La tabla **Sensores del registro** muestra la conversión, la línea y el contraste
con etiqueta cuando está disponible. La conversión no necesita una etiqueta.
El contraste usa la vista limitada de hasta 200 etiquetas; no cuenta etiquetas
que estén fuera de esa vista o después de la siguiente transacción.

## Correlación de las respuestas

Las 188 entradas ACK de percepción tienen flags `00` y secuencia distinta del CMD.
En la llamada nativa, RVA `0x11a4f8` a `0x11a534`, se observa el argumento `3` de
filtrado. `V1Protocol::SendCmdandAck`, RVA `0x45580`, lo combina con `0x40` antes
de construir `V1Filter` (RVA `0x414a0`): máscara `0x43`, bits 0, 1 y 6 activos.
Esto documenta un filtro específico del framework; no es motivo para relajar
el comprobador DUML genérico o declarar éxito sobre cualquier tráfico `24/26`.
La secuencia, la concurrencia y el contexto de recepción necesitan validación
antes de implementar una consulta activa propia.

Se conservan los resultados anteriores de framing: 367 CMD y 367 ACK, 734 tramas
con longitud y CRC correctos, 150 ACK diferentes, 175 asociaciones con cabeceras
concordantes, cuatro ecos y 188 asociaciones históricas sin esa correlación.
Ocho registros son UTF-8/ASCII y 81 se leyeron con GB18030. El análisis evita
contar dos veces la capa `cmd Send` y la capa CMD/ACK.

## Transporte USB

Hay dos rutas distintas en `DJI_Protocol_Comm.dll`:

- **BulkComm**, utilizada en las búsquedas de los registros, toma los endpoints
  de su configuración. El constructor obtiene `ep` y `in` (RVA `0x1cfea` y
  `0x1cff6`); `_SearchDevice` copia los valores configurados a los campos de lectura
  y escritura en RVA `0x20ab9` a `0x20acd`. `Read` y `Write` los pasan a
  `usb_bulk_read` y `usb_bulk_write`, respectivamente.
- **UsbComm** usa libusb 1.0. `_CheckNFindEP` (RVA `0x38e50`) recorre los
  descriptores; RVA `0x39544` a `0x39562` examina atributos/dirección y conserva
  endpoints de entrada/salida. `Read` (RVA `0x373b0`) y `Write` (RVA `0x37870`)
  los pasan a `libusb_bulk_transfer`.

Las DLL por sí solas no proporcionan una pareja numérica de endpoints
atribuible al dron actual. Después se recibió un reporte UsbTreeView del usuario:
Mini 4 Pro, configuración 1, High-Speed, interfaz 4 / alternativa 0, bulk
OUT `0x04` e IN `0x85`, ambos de 512 bytes. La configuración tiene ocho interfaces.
El usuario declara firmware de aeronave **01.00.1100** desde DJI Fly; `bcdDevice`
`0x0504` no se interpreta como esa versión. La configuración de otra velocidad
no se mezcla con la configuración High-Speed negociada. El controlador mostrado
corresponde al dispositivo compuesto padre (`usbccgp.sys`); el informe no acredita
el acceso del backend a la interfaz 4. No se recomiendan cambios de controladores.

El reporte original contiene un identificador de unidad y permanece privado.
Solo se conserva públicamente la descripción general de endpoints. Los registros indican VID `2CA3`, PID `0020` e interfaz
`4`, junto con otras interfaces; **MI_04 no es una dirección de endpoint**.
Las configuraciones suministradas están cifradas y no se han descifrado para
reutilizar autenticación. El EXE propio no necesita las DLL oficiales.

## Qué queda pendiente

Los descriptores del reporte actual y la versión declarada permiten preparar
una **recepción USB pasiva**. El transporte comprueba producto, configuración, interfaz, clase y endpoints antes
de reclamar la interfaz 4. Con libusb 1.0 verifica además la velocidad; libusb0
no la informa y el resultado se declara desconocido.
Solo expone lectura de IN 85 y liberación; no manda peticiones de servicio,
no utiliza OUT 04 y no cambia configuración, modo, drivers o firmware.

Para una consulta USB activa siguen faltando capturas de esa consulta en modo
normal y una correlación de respuestas específica validada. El flujo histórico también contiene modo fábrica,
transferencia y copia de calibración; no se ha reproducido ninguna de esas acciones.

Para seleccionar o descargar calibración faltan los archivos/manifiesto reales,
la correspondencia por sensor y un servicio autorizado vigente. La instalación
requiere además protocolo, recuperación ante fallos y pruebas físicas por unidad.
Se habilita únicamente la recepción USB pasiva. No se habilitan consultas activas,
descarga, fábrica ni escritura. Una captura vacía es esperable si no hay tráfico
espontáneo: no significa que los sensores hayan fallado. No es un monitor del
tráfico de otra aplicación y se deben cerrar otros clientes USB del PC.

## Validación de esta entrega

Las pruebas sintéticas cubren conversión sin etiquetas, cuatro selectores,
campos inválidos, límites de fecha, proveedor, nibble, CRC incorrecto, ecos,
etiquetas discordantes y tabla de sensores sin identificar el equipo conectado.
La ejecución del EXE bajo Wine analiza además los 89 registros reales; solo se
publican los recuentos. Véanse `validacion-1.2.4.json` y los resultados de pruebas.
La recepción pasiva se prueba con dependencias USB simuladas: timeout, desconexión,
configuración incorrecta, rechazo de otro modelo, cancelación, límite de bytes,
archivo existente y error de disco/cierre. El EXE bajo Wine recorre esa misma
captura con un receptor sintético; no se abre un dron.
Windows nativo y hardware real siguen sin probarse.

## Incidencia de apertura y revisión 1.2.4

El informe real de la versión 1.2.3 contiene cero bytes, cero intentos de lectura,
cero timeouts y error `Operation not supported or unimplemented on this platform`.
Ese texto corresponde a `LIBUSB_ERROR_NOT_SUPPORTED` (-12) en la biblioteca
incluida. El informe antiguo no registró la llamada exacta que falló. El usuario
aportó después el servicio de MI04: `libusb0_device`, estado OK, código de
Administrador de dispositivos 0. No se atribuye ese fallo a los sensores.

Se revisó el código oficial libusb-win32 de la revisión
`0987f983a89e5e60d3c2db2af46564239c1b0d37`: apertura con CreateFile y consulta
de configuración cacheada, reclamación de interfaz, GET estándar y lectura bulk.
No se invocan sus APIs de instalación, configuración, reset o escritura USB.
Se incluye únicamente su biblioteca de usuario 1.4.0.2 amd64, verificada contra
la huella publicada de la distribución. El servicio del usuario no se modifica.

El receptor prioriza esa API en Windows, registra fases y conserva excepciones
de inicialización. La ausencia de velocidad en PyUSB/libusb0 se registra como
desconocida, sin inventar High-Speed. Los demás campos del perfil siguen
verificándose. Las pruebas cubren elección de API, ausencia de velocidad,
fallback limitado, denegación de acceso, perfil equivocado y errores antes de leer.
Ambas bibliotecas cargaron bajo Wine. La recepción física con ese controlador
no se declara probada y las consultas activas de sensores siguen pendientes.
