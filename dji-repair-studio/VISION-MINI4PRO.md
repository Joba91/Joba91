# Visión Mini 4 Pro · DJI REPAIR Studio 1.6.0

Hay recepción USB pasiva, análisis de archivos y una nueva **consulta SN experimental**.
Se añade solicitud y lectura HMS experimental; la compatibilidad de esos datos con
Mini 4 Pro y la interpretación de sus alarmas siguen pendientes. Calibración óptica,
descarga e instalación no están implementadas.

## Recepción experimental de imágenes · 1.6.0

Selecciona **Visión Mini 4 Pro**, declara **01.00.1100** y pulsa
**Recibir imágenes (prueba)**. Elige la carpeta **DJIEngine** de DJI Assistant 2
Consumer si no se encuentra automáticamente y guarda un ZIP nuevo. Comparte
`Mini4Pro-Vision-....zip` incluso si no recibe imágenes. No copies el JSON a la
carpeta del EXE: se lee de su instalación, junto a las siete bibliotecas fijadas
por SHA-256. El informe distingue errores de archivos, identidad, arranque y recepción.

El receptor x86 es propio, oculto y separado del proceso x64 de la interfaz.
El JSON recibido asigna `wa140` a `dual_chip_a7`, MI05 (`v1`) y MI03 (`dbus`).
Se solicitan dos suscripciones de imágenes `raw/down/left` y `raw/down/right`;
no se llaman APIs de calibración ni se escribe una configuración de sensores.
La inicialización de transporte genera tráfico nativo; no se declara lectura
pasiva ni cero escrituras USB. Los efectos del SDK no están validados en hardware.

Se admiten únicamente metadatos de 640×480, 8 bits y 307200 bytes, con copia
acotada del búfer y validación posterior de los PGM y su SHA-256. Cada imagen se
muestra en la misma ventana y se guarda fuera de la carpeta temporal. No se
presume sincronización entre ambas ni se consideran un conjunto de calibración.
El arranque x86 no se ha probado en este host: su kernel no tiene habilitado
`CONFIG_IA32_EMULATION`. La cabecera PE, manifiesto, importaciones y archivos
congelados se verifican estáticamente; la lógica usa adaptadores sintéticos.
La primera prueba de arranque del receptor/SDK requiere Windows real.

El 100 % requiere dos imágenes verificadas y el ZIP creado; no significa salud
ni calibración. Hay límite de tiempo y cancelación del proceso receptor.

La referencia nativa es de visión **inferior**. No confirma cobertura del sensor
delantero derecho ni compatibilidad con Mini 4 Pro/01.00.1100. Aún faltan esa
validación física, el contrato completo del motor y verificación de escritura
antes de habilitar calibración. No se incluyen las bibliotecas ni el JSON DJI.

## Corrección de mensajes extendidos y análisis sin USB

1.4.0 interpretaba solamente `21/06`. La revisión del BIN de 3728 bytes mostró
15 mensajes `21/08` adicionales. También estaban en las dos capturas previas,
53 por archivo. El lector ahora conserva y presenta ambas familias.

Abre tu BIN existente con **Analizar captura visión** para verlos en **Diagnóstico
HMS**. Esta operación solo lee el archivo; no consulta el equipo actual. **Guardar
informe** exporta el JSON reanalizado. No hace falta repetir una recepción para
obtener los registros que ya están en el BIN.

Los 121 mensajes observados obedecen cabecera de cuatro bytes, contador de registros
seguido de TLV (tag uint8, tamaño uint8, cuerpo). Hay 234 cuerpos tag0/tamaño20 y
un cuerpo de otro tipo/tamaño, preservado opaco. Del tag0/20 solo se expone el primer
uint32 LE como código candidato; los otros 16 bytes se conservan sin asignarles
estado activo/resuelto, índice, nivel, componente o fecha. Un contador o TLV
inconsistente rechaza la interpretación de todo el paquete. Los ciclos `21/06` y
`21/08` se agrupan por separado para no rellenar huecos entre familias.

Una variación del cuerpo completo mantiene registros separados, incluso para
el mismo código. No se descartan bytes variables que podrían contener un estado
que todavía no entendemos. Los límites de ciclos/registros existentes siguen aplicándose.

Se muestran seis referencias breves del SDK público, identificadas como tales:
`1A510380`, `1A510382`, `1A510384` y `1A510385` se describen allí como errores de
calibración inferior/posterior/izquierda/derecha; `1C000404` como ausencia de SD y
`1C000408` como sistema de archivos de SD no compatible. El resto queda sin descripción.
**Presencia de un código no prueba que la alarma esté activa**, que esa equivalencia
sea válida para Mini 4 Pro, o que una calibración sea apropiada. La tabla incluye
actividad desconocida y deja índice/nivel de `21/08` sin interpretar. Las referencias
no se usan para habilitar calibración o recomendar borrado/formateo de datos.

Los cuatro identificadores de referencia de visión aparecen en las tres capturas;
se necesita contrastar el estado actual en DJI Fly y los campos no interpretados
antes de convertirlos en diagnóstico de fallos activos. No se publica el material
original ni se incorpora al ZIP de distribución.

## Probar diagnóstico HMS

1. Conecta el Mini 4 Pro en modo normal y cierra otros clientes USB del PC.
2. En Visión Mini 4 Pro declara el firmware **01.00.1100** de DJI Fly.
3. Pulsa **Diagnóstico visión (HMS)** y guarda un `.bin` **nuevo**.
4. Tras la apertura y ocho segundos de escucha, comparte el ZIP `Mini4Pro-HMS-....zip`.

Esta acción solicita publicación de estados con una petición **0a→1d, 21/05,
payload 01**. Solo se permite una por sesión, con timeout de envío 500 ms y sin
reintentos. Se deriva del constructor y lector HMS de la DLL aportada, no de un
barrido de comandos. No inicia fábrica, autotest, motores o calibración. No cambia
firmware, drivers o configuración USB. Sí solicita una publicación de telemetría.

El SDK público describe una desuscripción con payload 00 que reinicia otros
suscriptores. **No se envía ese reset global**. La publicación después de cerrar
USB no se presume detenida; se registra como desconocida. No se reproducen rutas
de autenticación, ADB, descarga o modificación del programa original.

El lector inspecciona `21/06` dirigido a `0a`, separa emisores y ciclos y conserva
los demás datos en RX. El formato de referencia es versión 0, cabecera de 3 bytes,
índice de paquete en los 7 bits bajos del tercero y cierre en el bit alto, según
los desplazamientos explícitos del lector nativo. Cada registro usa seis bytes:
código uint32 LE, índice uint8 y nivel uint8. Los campos son **brutos**; ni el índice
se asocia al selector SN ni se interpreta el nivel como gravedad clínica del sensor.
El rango de referencia del SDK es 0–4; los otros valores se conservan sin equivalencia.

No se cuenta un ciclo como completo con huecos, cierres contradictorios o paquetes
extra. Una contradicción posterior revoca la completitud previamente contada.
Las repeticiones idénticas no inflan ciclos o registros. Se muestran hasta 100
registros distintos, 20 paquetes y 32 ciclos; máximo 1024 mensajes, 16 pares de
emisores/destinatarios y 256 registros por ciclo. Los límites quedan en el informe.

**Un ciclo vacío, silencio o ningún código no prueban salud.** Las descripciones breves del SDK se muestran solo como referencias no validadas;
no se utilizan para diagnosticar Mini 4 Pro o afirmar actividad de alarmas. El lector informa su formato, incidencias y datos sin atribuirles una
compatibilidad que aún requiere prueba física. No todos los mensajes HMS son de visión.

Un ACK de suscripción se considera coincidente solo con origen/destino, familia,
flag de respuesta, secuencia y tamaño esperados. El retorno cero registra aceptación,
no salud; rechazo correlacionado detiene la prueba y conserva el código. Los ACK
no correlacionados se guardan sin confirmar aceptación. La recepción termina a los
ocho segundos, 1 MiB o 10000 lecturas; llamadas USB en curso pueden terminar después.
El BIN guarda RX y el JSON la auditoría TX, ACK, ciclos e incidencias. Se crea ZIP
incluso con error; no se sobrescribe o sube automáticamente. El porcentaje mide tiempo.

Analizar captura visión también muestra HMS de archivos binarios, con procedencia
local: no equivale a consultar el dron actual. Las capturas históricas DJI Test
mantienen su tratamiento anterior y no se reclasifican como salud actual.

## Probar la lectura de SN

1. Conecta el Mini 4 Pro encendido en modo normal y cierra otros clientes USB del PC.
2. Abre **Visión Mini 4 Pro** e indica **01.00.1100** en Firmware declarado,
   únicamente si coincide con la versión de aeronave que muestra DJI Fly.
3. Pulsa **Consultar SN visión (prueba)** y elige un archivo **nuevo** `.bin`.
4. Revisa **Consulta SN (prueba)** y comparte el ZIP `Mini4Pro-SN-....zip`
   generado junto al `.bin`. Incluye recepción e informe con el registro de envíos.

Esta acción envía cuatro peticiones 24/26 de número de serie, selectores 04/08/40/80,
una por vez. El payload y la trama reconstruida coinciden byte por byte con las
188 consultas históricas disponibles: 47 por selector. Se revisaron estáticamente
TSGetPerceptionSensorSN y V1Filter sin ejecutar ni redistribuir las DLL oficiales.
**Dos pruebas aportadas por el usuario con firmware declarado 01.00.1100 dieron
cuatro SN estables.** Se reanalizaron 15936/15641 bytes, 272/267 tramas válidas,
cuatro registros SN por captura, sin CRC erróneo. Eso no prueba salud ni generaliza
compatibilidad a otras aeronaves. La correlación sigue siendo experimental.
No se reproducen los cambios de modo del flujo histórico; si necesita otro contexto,
la prueba termina sin respuesta identificable y sin intentar entrar en fábrica.

## Interpretar el resultado

- **SN observado:** el formato conocido produjo un número de serie durante la ventana
  de ese selector. Todavía no es una respuesta correlacionada o identidad confirmada.
- **Sin registro identificable:** no hubo un registro del formato esperado en esa ventana.
  No demuestra fallo del sensor, incompatibilidad o necesidad de calibración.
- **Ambiguo:** se observaron varios SN diferentes para el mismo selector.
- **Ventana incompleta:** cancelación, límite o error; los datos parciales se conservan.

El filtro original usa máscara 0x43: no exige secuencia o flags de respuesta iguales
a una transacción estándar. El cliente propio conserva el emparejamiento como
**no validado**, incluso si coinciden las secuencias o aparecen cuatro SN válidos.
Exige dirección histórica 12→2a, familia 24/26, flags 00, longitud y CRC válidos,
prefijo/selector y un SN alfanumérico del formato contrastado. No acepta un registro
de otro selector como resultado del solicitado. Las etiquetas frontleft/frontright/
backleft/backright solo expresan asociaciones históricas, no posición física actual.

Hay una recepción inicial de 0,6 segundos antes de enviar, para distinguir tráfico
previo. Las ventanas duran 3 segundos por selector; el límite global es 15 segundos
tras abrir USB, hasta 1 MiB o 10000 lecturas. Lecturas USB de 200 ms, envío de 500 ms.
Puede haber hasta una llamada USB en curso al vencer el límite. No se unen fragmentos
incompletos de una ventana a la siguiente. El BIN guarda todo el RX en orden, incluso
tráfico ajeno a las consultas. El informe contiene auditoría TX, tiempos, secuencias,
observaciones previas, candidatos y errores; no mezcla TX dentro del BIN de recepción.

No hay reintentos. Un timeout o envío corto deja la entrega como desconocida y detiene
la prueba: un error de transporte no prueba que ningún byte llegara al dispositivo.
El porcentaje cuenta ventanas completadas; 100 % no indica diagnóstico o calibración.
Detener conserva el resultado parcial. No se envían comandos de fábrica, configuración,
calibración, motores o firmware. No hay API de envío arbitrario en este módulo.

## Recepción pasiva y selección de dispositivo

**Capturar USB pasivo** sigue leyendo sin consultas de servicio durante 5/10 segundos.
Ambas operaciones validan Mini 4 Pro, VID 2CA3/PID 0020, configuración 1, interfaz 4
alternativa 0, clase FF/43/01, OUT 04 e IN 85 bulk de 512 bytes. La selección manual
del modelo no basta. En Windows se prioriza libusb0 para el servicio libusb0_device
existente; no instala o sustituye controladores. libusb0 no informa velocidad y se
declara desconocida. libusb1 exige High-Speed.

Se consultan HardwareID locales de cada alias y se exige una única MI04. Si el alias
informa un nombre genérico como BULK Interface, se valida su nodo PnP y padre físico
directo mediante metadatos Windows y BusReportedDeviceDesc. Solo un padre USB físico
2CA3:0020 con producto Mini 4 Pro permite ese caso; otro modelo explícito se rechaza.
Los metadatos se leen y cierran antes de abrir el handle USB exclusivo de PyUSB.
No se elige el primer alias ni se buscan equipos por nombre. No se reinicia, desprende,
reconfigura o limpia el halt de un dispositivo para lograr acceso.

El usuario aportó un ZIP de 1.2.6 que acredita en su informe esa selección y asociación:
6123 bytes recibidos en 5,021 s, 104 tramas válidas, sin errores CRC o timeouts.
El binario se reanalizó independientemente. La interfaz decía BULK Interface y el
padre Mini 4 Pro. No contenía registros SN 24/26 y no valida las nuevas consultas.
Los originales e identificadores de unidad no se publican.

## Archivos, ZIP e integridad

Ambas operaciones crean exclusivamente archivos nuevos `.bin` y un ZIP con ese BIN y
`DJI-REPAIR-informe.json`, incluso con recepción vacía o error. Se conservan los
existentes, sin sobrescribir ni subir archivos. Si falla el ZIP, usa Guardar informe.
El JSON puede contener series; revísalo antes de publicarlo. Las rutas PnP se registran
como SHA-256. Los adjuntos originales no se incluyen en el programa o repositorio.

Importar carpeta/ZIP inventaría sin extraer ni ejecutar. MD5 y SHA-256 comprueban
integridad, no autenticidad o compatibilidad por unidad. Analizar captura visión
admite `binary`, `hexlog`, `djilog` y `auto`; registros UTF-8/UTF-16/GB18030 y HEX.
La vista histórica limita la presentación a 200 registros y distingue CMD/ACK, ecos,
envíos duplicados y correlación desconocida. Los datos históricos no identifican
al dron conectado. El corpus tiene 89 archivos, 734 tramas y 184 SN válidos que
coinciden con etiquetas; cuatro registros permanecen sin SN válido.

La comprobación de servidor solo se ejecuta sobre una URL HTTPS introducida a mano.
Verifica TCP/TLS y certificados, con tiempo acotado, sin autenticación o descargas.
No se contactan servidores históricos ni se reutilizan credenciales/cookies/tokens.

## Desarrollo y validación

`vision_sensor_query.py` separa constructor SN, transporte restringido y coordinador
con límites. Reutiliza el perfil verificado de `vision_usb_passive.py` y los lectores
independientes `vision_sensor_records.py`/`studio_protocol.py`. La interfaz usa un
único trabajador y raíz Tk; mantiene activas solo las acciones Mini 4 Pro previstas.
La consulta no abre automáticamente al arrancar, importar o elegir un modelo.

280 pruebas de aplicación/interfaz, pruebas de empaquetado y arranque bajo Wine.
Los tests cubren solicitudes históricas, perfil equivocado, paquetes inválidos,
selector ajeno, fragmentos, silencio, conflicto de SN, cancelación, límites,
envío corto/timeout, desconexión, error de disco/cierre, UI y ZIP con TX/RX.
Wine ejecuta el coordinador y la pantalla con cuatro respuestas sintéticas, sin USB real.
No se realizó aquí una consulta física HMS ni prueba de Windows nativo. Los dos
ensayos SN son evidencia aportada por el usuario, no hardware conectado al entorno.
Wine comprueba además una suscripción HMS simulada, dos ciclos de referencia y
un registro sin descripción validada, la tabla y el ZIP. Las fuentes públicas
OSDK se consultan como referencia, no como garantía de compatibilidad Mini 4 Pro.
Ver `validacion-1.6.0.json`, resultados incluidos y
[análisis de DLL y registros](INVESTIGACION-REGISTROS-MINI4PRO.md).
