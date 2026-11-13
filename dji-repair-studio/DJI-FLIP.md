# DJI Flip · pruebas de taller del gimbal · 1.9.1

Firmware de aeronave **01.00.1500 declarado por el usuario**. Se incorporan
**JointCoarse y LinearHall como pruebas experimentales** con la petición común
DJI. **Su compatibilidad y sus efectos en el Flip aún no están validados.**
No se presentan como un procedimiento de taller certificado o probado físicamente.

## Evidencia recibida

El perfil 1.8.0 obtuvo ocho nodos PnP y seis alias con descriptores completos.
MI04: configuración 1, alternativa 0, clase FF/43/01, OUT04/IN85 bulk512. Nombre
USB genérico DJI-…; no se convierte en identidad comercial autenticada.

La consulta 1.8.1 recibida tiene 185 bytes RX y tres tramas de CRC válido: un
broadcast 03/43 y dos respuestas 00/01 correlacionadas por emisor/destino/secuencia.
El controlador informa versión de módulo **01.00.0057** y el gimbal **00.00.2052**
según el formato común del proyecto. No sustituyen el firmware de aeronave de DJI
Fly. Hubo dos peticiones completas (26 bytes OUT), ninguna orden de calibración
ni fábrica. El orden de alias cambió y se identificó MI04 por metadatos.

## Ejecutar una prueba

La captura JointCoarse de 1.9.0 se detuvo antes de transmitir la calibración:
400 bytes RX, seis tramas de CRC válido y las dos versiones coincidentes, pero
cero peticiones 04/08. El error fue el timeout de libusb0 durante el vaciado
previo. El informe antiguo no guardaba su código numérico. En la biblioteca
fijada 1.4.0.2, esa rama devuelve ETRANSFER_TIMEDOUT (-116); PyUSB en Windows
puede convertirlo en USBError genérico por la diferencia con errno.ETIMEDOUT.
1.9.1 reconoce ese código exacto y USBTimeoutError como lectura sin datos.
Otros errores siguen deteniendo la prueba. El informe guarda códigos y contador
de timeouts. Esto corrige la preparación; no confirma compatibilidad Flip.

Repite primero JointCoarse con el mismo **DJIFlip-Modulos-20261113-134015.zip**.
El ZIP de JointCoarse fallido no sustituye la referencia de módulos. No necesitas
recopilar otro perfil USB si el mismo dispositivo sigue asociado a la referencia.

1. Extrae la versión nueva y abre DJI REPAIR Studio 1.9.1.exe.
2. Selecciona **DJI Flip / USB bulk** y revisa firmware declarado **01.00.1500**.
3. Pulsa **JointCoarse · prueba Flip** o **LinearHall · prueba Flip**.
4. Elige tu **DJIFlip-Modulos-….zip** con las dos respuestas de versión recibidas.
   No es el ZIP de perfil USB. Guarda el ZIP nuevo con el nombre de la rutina.
5. Lee la confirmación y ejecútala únicamente con el gimbal libre de su protector
   y con el recorrido despejado. El gimbal puede moverse y el firmware puede
   guardar ajustes. Comparte el ZIP de resultado, incluso si informa un error.

Para esta primera comprobación del Flip se recomienda probar JointCoarse y revisar
su captura antes de ejecutar LinearHall. El programa no encadena ambas rutinas.
La existencia de los botones no significa que la compatibilidad esté confirmada.

## Petición y restricciones

Se valida el ZIP de módulos: CRC de las respuestas presentes también en el BIN,
peticiones 00/01 válidas, correlación, dos módulos y metadatos de apertura MI04.
Se compara el padre/nodo actual con la referencia y se verifican los endpoints.
Antes de la calibración se vuelven a consultar ambos módulos, una vez cada uno,
y se comparan los primeros 26 bytes de versión/hardware con la referencia.
Un cambio impide enviar la petición de calibración.

Se descarta tráfico previo y se comprueba que no haya informes de calibración
activa antes de iniciar. Después se permite **una sola petición 04/08** al gimbal:
`01` para JointCoarse o `02` para LinearHall. Este formato existe en otros gimbals
DJI; se prueba su compatibilidad aquí, no se la deduce de las versiones recibidas.
No se reenvía, se cambia de interfaz, entra/sale automáticamente de fábrica,
resetea el USB, fuerza otra configuración o escriben tablas IMU fijas.

El modo de taller actual no está identificado. Si la rutina requiere un modo que
no está activo, puede no iniciar. La entrada/salida de fábrica del Flip sigue sin
implementación contrastada. No se llama a start_factory de otro producto.

## Qué acepta como fin

Un ACK correlacionado con payload admitido por la política de prueba (00/01 para
JointCoarse; 00/01/02 para LinearHall) solo cuenta como confirmación inicial.
Se exige además progreso **posterior** conocido de 04/30 y un fin `64 00`.
Las etapas se registran en bruto; no se asignan a ejes del Flip sin evidencia.
Un ACK solo, `64 00` sin progreso, secuencia distinta, estado desconocido o tiempo
agotado no se convierten en éxito ni en 100 %. `64 03` se registra como fallo
informado por el equipo, sin diagnosticar una causa física. Una respuesta inicial
FB se guarda como inicio no confirmado, sin reintentar o ejecutar scripts.

El progreso 25/50/75/100 cuenta hitos: versiones coincidentes, petición entregada,
progreso observado y fin informado más ZIP guardado. No mide avance mecánico.
Los informes 04/30 son asíncronos y su secuencia no es un vínculo criptográfico
con la petición. El resultado es lo informado por el dispositivo y observado
tras la solicitud, no una validación física/metrológica de la calibración.

## Captura, cancelación y persistencia

Se reciben hasta 1 MiB y se monitoriza hasta 180 segundos como límite, no como
duración prevista. El ZIP guarda BIN crudo y `gimbal.calibration_probe`, con
preflight, petición, ACK, etapas y resultado. Auditoría JSON limitada a 1024
registros y vistas de etapas a 300; el BIN conserva el tráfico capturado completo
hasta el límite. Se libera MI04 al finalizar.

**Detener lectura no envía una orden de parada y no frena los motores.** Después
de una petición intentada, `calibration_performed` queda desconocido; si hubo
ACK/progreso/fin admitidos se usa `equipo_informa_fin`, sin afirmar exactitud.
El firmware podría guardar parámetros como parte de su rutina. Ese efecto no
se ha caracterizado; únicamente se afirma que no se escriben coeficientes IMU
fijos desde la herramienta. Ante entrega USB incierta tampoco se reenvía.

## Validación y procedencia

379 pruebas de aplicación/interfaz y 11 de empaquetado. Casos de dos rutinas,
progreso previo, referencia alterada, versión actual distinta, ACK solo, rechazo,
secuencia errónea, timeout, desconexión, cancelación y entrega incompleta.
El EXE se ejecuta bajo Wine con transporte sintético. No hay calibración física
de Flip en cloud y los datos sintéticos se identifican como tales.
Incluye regresiones de timeout libusb0 genérico, silencio repetido sin éxito,
error USB real antes de calibrar y reproducción de la conversión PyUSB en Windows.

Las formas comunes de petición/informes se contrastan con la referencia pública:
https://github.com/o-gs/dji-firmware-tools/blob/master/comm_og_service_tool.py
No se copian programas DJI, se ejecutan sus DLL o se asigna un código interno de
otro modelo al Flip. No se redistribuyen los ZIP originales o identificadores de
la unidad del usuario. Las funciones anteriores conservan sus límites.
