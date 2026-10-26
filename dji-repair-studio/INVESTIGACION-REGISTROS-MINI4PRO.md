# Investigación de DLL y registros · DJI REPAIR Studio 1.5.0

**Estado hasta 1.4.0:** recepción pasiva y dos lecturas SN del usuario reanalizadas;
cuatro SN estables. Se añade lectura HMS experimental, con interpretación específica
de alarmas Mini 4 Pro todavía pendiente. Las restricciones descritas abajo reflejan
las etapas de investigación anteriores; la última sección recoge los cambios actuales.

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
publican los recuentos. Véanse `validacion-1.2.6.json` y los resultados de pruebas.
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

## Seis entradas libusb0 y revisión 1.2.5

El nuevo informe de la versión 1.2.4 confirma carga/enumeración por libusb0: seis
entradas 2CA3:0020, cero intentos de lectura y detención en enumerate_devices.
El informe no identifica esas seis entradas como seis aeronaves. El error estaba
en exigir una sola entrada antes de distinguir interfaces del dispositivo compuesto.

La revisión 1.2.5 añade identificación por metadatos locales del controlador.
Se contrastó GET_DEVICE_PROPERTY (0x222400), HardwareID (propiedad 1), petición
packed de 24 bytes y retorno MULTI_SZ con el código público driver_api.h,
ioctl.c y driver_registry.c. El handler lee IoGetDeviceProperty del PDO, sin
peticiones al firmware. Se valida el alias, se consultan hasta 32 y solo continúa
una MI04 inequívoca. La configuración, producto y endpoints se comprueban después.
No se elimina el rechazo de ambigüedades ni se selecciona la primera entrada.

El ZIP automático contiene captura e informe incluso con cero bytes, para evitar
que un .bin vacío sea la única evidencia compartida. Guarda datos locales de esa
prueba, no se sube y no sobrescribe archivos. Se conservan las restricciones de
recepción pasiva y consultas activas/calibración pendientes. Las pruebas usan seis
alias simulados y una API Windows simulada; falta confirmar la consulta de
metadatos y la recepción con el controlador físico del usuario.

## Identificación del producto y revisión 1.2.6

El informe de usuario de 1.2.5 alcanza la configuración después de seleccionar
MI04, pero se detiene en el producto antes de cualquier lectura bulk. No guardaba
el texto devuelto por la interfaz; no permite atribuir la causa a un valor concreto.
UsbTreeView sigue mostrando la familia Mini 4 Pro en el dispositivo físico.

1.2.6 conserva los valores observados incluso si falla la apertura. Para libusb0
consulta el nodo exacto del alias con GET_OBJECT_NAME (0x2223fc, petición fija de
24 bytes, índice 0), valida su VID/PID/MI04 y obtiene su padre directo mediante
Configuration Manager. Exige un padre físico USB 2CA3:0020 sin MI y consulta solo
DEVPKEY_Device_BusReportedDeviceDesc. No busca por nombre entre otros equipos.
Solo permite un descriptor de interfaz genérico o ausente si ese padre acredita
el producto Mini 4 Pro; rechaza un descriptor explícito de otro modelo.
La consulta local se cierra antes de que PyUSB abra el alias de forma exclusiva.
Las APIs y la propiedad se contrastaron con libusb-win32 y Microsoft WinSDK.
No se incluye ningún encabezado Microsoft ni se efectúan escrituras PnP.

Las pruebas con buffers y errores simulados cubren asociación, formato, límites,
fallos y orden de apertura. Wine comprueba las exportaciones y buffers nativos.
La consulta del padre y recepción bulk reales siguen pendientes de probar en el
equipo del usuario. No se habilitan consultas activas ni calibración. Los informes
locales pueden contener el producto con identificador de unidad; no se publican
los adjuntos originales. Las rutas PnP se conservan solo como huellas SHA-256.

## Consulta SN experimental y revisión 1.3.0

El ZIP pasivo 1.2.6 aportado por el usuario contiene 6123 bytes y 104 tramas CRC
válidas; se reanalizó y coincidió con el JSON. Acredita en ese informe selección
MI04 y asociación al padre físico. No incluye mensajes 24/26 ni valida su consulta.

Se examinó ahora el constructor V1Filter RVA 0x414a0: los siete bits del argumento
se descomponen en filtros. SendCmdandAck combina el argumento 3 de GetPerceptionSN
con 0x40. En la ruta analizada, la máscara 0x43 selecciona familia/contexto, sin
exigir secuencia ni flags estándar de respuesta. Esto explica por qué no debe
utilizarse el correlador DUML genérico para declarar identidad.

El constructor propio sn_request reproduce exactamente las 188 tramas CMD de SN
del corpus (47 por cada selector 04,08,40,80), incluyendo CRC y secuencia. Los tests
conservan cuatro huellas de peticiones sin datos de unidad. El coordinador permite
una petición por selector, ventanas seriales de tres segundos, recepción previa
de 0,6 segundos, límite postapertura de 15 segundos/1 MiB/10000 lecturas, sin
reintentos ni cambios de modo. No se exponen comandos arbitrarios.

La nueva acción Consultar SN visión (prueba) habilita exclusivamente este ensayo
en modo normal, con firmware declarado 01.00.1100 y perfil USB contrastado. No se
da por validado su soporte en ese modo/firmware antes de probarlo. SN convertidos
se muestran como observaciones, nunca como identidad/salud confirmada, incluso
si coinciden las secuencias. Se registran también candidatos ambiguos, tráfico
previo, selector ajeno, datos incompletos y entrega incierta tras fallo TX.
No hay fallback a fábrica ni reproducción de otros comandos del flujo histórico.
El ZIP automático contiene RX binario y JSON con auditoría TX.

205 pruebas de aplicación/interfaz y arranque del EXE bajo Wine con USB simulado.
La prueba física de la nueva consulta y su correlación siguen pendientes. No se
habilitan diagnóstico de salud, descarga/instalación o calibración óptica.

## Diagnóstico HMS experimental · revisión 1.4.0

El constructor HMS en RVA 0x559410 de dji_test_userlibs.dll fija el encabezado
0a/00/1d/00 (VA 0x105595e1), familia 21 (0x105595ed) y flags 40. HMSBegin
RVA 0x559780 fija id 05 y vector de un byte 01 antes de enviar. HMSCheck
RVA 0x559c60 fija id 06 y espera sin enviar una nueva petición. Se reconstruye
solo esa solicitud de publicación, sin ejecutar la DLL ni otras órdenes.

El lector nativo extrae índice con &0x7f en 0x1055a218 y fin con >>7 en
0x1055a39e. En 0x1055a854 calcula (longitud-3)/6; en 0x1055ab8d avanza seis
bytes por registro y omite tres de cabecera. El parser propio conserva versión,
emisor, ciclo, fragmentos y códigos en lugar de copiar sus supuestos de éxito.

Como referencia pública se revisó DJI Onboard SDK, commit
118e2825a347499efb8ed253146552c5b9b10779:
- osdk-core/api/inc/dji_hms.hpp documenta código uint32, índice y nivel uint8.
- dji_hms_impl.cpp copia tres bytes de cabecera y registros de seis bytes.
- dji_hms.cpp identifica payload 01 como solicitud de publicación y 00 como
  reset de otros suscriptores. No se reproduce la orden global de reset.
- El destino OSDK y su declaración de bitfields no coinciden con el lector nativo:
  no se sustituyen silenciosamente por el perfil de la DLL aportada.
- La API pública está documentada para M300; su tabla de 700 alarmas no se aplica
  como descripción validada de Mini 4 Pro.

También se revisaron disectores públicos o-gs/dji-firmware-tools, commit
1db36ddf45d8018ea849f0c03c5e45d2f3068844. Sus campos de visión se refieren a
versiones/productos anteriores y no se usan para dictaminar salud de Mini 4 Pro.
Get Device State 00/0c describe ejecución loader/app, no diagnóstico de salud.
CheckPerceptionCaliNotDefault usa archivos/ADB; no se transforma en una consulta
USB de calibración o en una operación de fábrica.

La versión 1.4.0 permite una petición HMS al perfil nativo y ocho segundos de
recepción, con límites, cancelación y auditoría TX/RX. Rechazos, formato desconocido,
fragmentos faltantes, conflictos y ciclos vacíos no producen un diagnóstico sano.
Los registros se muestran sin mapa de alarmas Mini 4 Pro validado. El estado de
publicación después de cerrar USB es desconocido; no se garantiza desuscripción.

246 pruebas de aplicación/interfaz y arranque bajo Wine con datos sintéticos.
Las dos capturas SN del usuario contienen cuatro series estables, pero ningún
21/06; no validan HMS. Su prueba física y la clasificación de códigos siguen
pendientes. Ningún original o identificador real de unidad se publica.

## Corrección de la omisión 21/08 · revisión 1.5.0

La revisión ampliada del BIN Mini4Pro-HMS-20261026-152835.bin encontró 72 tramas
válidas y 15 mensajes 21/08 no procesados en 1.4.0. Se volvieron a examinar los dos
ZIP anteriores: cada BIN contiene 53 de esos mensajes. La limitación era del lector,
no ausencia de esos registros en la aeronave. Se mantiene la validación CRC completa.

En total, 121 mensajes cumplen una cabecera de cuatro bytes: versión 0, ciclo,
índice/fin y contador. Cada registro lleva dos bytes de envoltura y su longitud
exacta de cuerpo. Los 234 tag0/longitud20 comparten primer uint32 LE compatible
con identificadores de la tabla HMS pública; un registro tag1/longitud13 no se
interpreta como código. No se extrapolan significados para los demás campos.
El cierre bit7 se usa como estructura observada, no como validación de salud.

En las tres capturas aparecen identificadores 1A510380/382/384/385, descritos en
OSDK como calibración de visión inferior/posterior/izquierda/derecha. Los cuerpos
contienen más campos: su presencia no demuestra estado activo, vigente o retenido.
Los índices, niveles, componentes y tiempos de 21/08 permanecen sin interpretar.
La equivalencia de OSDK tampoco se generaliza como mapa Mini 4 Pro validado.

El nuevo módulo propio vision_hms_extended.py valida TLV y conserva metadatos
completos; no colapsa variantes del mismo código con cuerpos distintos. HmsTracker
separa también por familia para evitar completar un ciclo con 21/06 y 21/08 mezclados.
La interfaz presenta referencias calificadas y una columna de actividad desconocida.
La recepción física usa la misma petición, sin comandos adicionales.

262 pruebas de aplicación/interfaz. El EXE bajo Wine prueba ambos formatos con
fixtures sintéticos y reanaliza las tres capturas privadas: 259/259/72 tramas y
53/53/15 mensajes extendidos, con cuatro códigos de referencia de visión en cada
archivo. Se publican solo recuentos. Es análisis offline; no una nueva prueba física,
validación de actividad de alarmas o confirmación de necesidad de calibración.
