# Visión Mini 4 Pro · DJI REPAIR Studio 1.3.0

Hay recepción USB pasiva, análisis de archivos y una nueva **consulta SN experimental**.
El diagnóstico de salud, calibración óptica, descarga e instalación siguen pendientes.

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
**El funcionamiento de esas consultas en modo normal con este firmware aún no se ha probado.**
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

205 pruebas de aplicación/interfaz, pruebas de empaquetado y arranque bajo Wine.
Los tests cubren solicitudes históricas, perfil equivocado, paquetes inválidos,
selector ajeno, fragmentos, silencio, conflicto de SN, cancelación, límites,
envío corto/timeout, desconexión, error de disco/cierre, UI y ZIP con TX/RX.
Wine ejecuta el coordinador y la pantalla con cuatro respuestas sintéticas, sin USB real.
No se realizó aquí una consulta activa física ni prueba de Windows nativo.
Ver `validacion-1.3.0.json`, resultados incluidos y
[análisis de DLL y registros](INVESTIGACION-REGISTROS-MINI4PRO.md).
