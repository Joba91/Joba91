# DJI Flip · gimbal de taller · proyecto pendiente

Firmware de aeronave **01.00.1500 declarado por el usuario el 13 de noviembre de
2026**. Solicitud: **JointCoarse y LinearHall**, no la calibración automática de
DJI Fly. **Estas dos rutinas todavía no están implementadas para el Flip.**

## Incluido desde 1.8.0

- DJI Flip en el selector, con espacio propio en la pestaña Calibración.
- Firmware declarado conservado por modelo; la casilla de preparación de fábrica
  se limpia al cambiar de equipo y no se usa como validación del Flip.
- Recopilar perfil USB guarda un ZIP de gimbal con PnP y los descriptores estándar
  accesibles. Los datos se muestran en la misma ventana y se pueden exportar.
- La selección no se cambia a Mini 4 Pro por eventos de la pestaña de visión.
- JointCoarse, LinearHall, fábrica, parámetros, cámara, consultas heredadas y
  operaciones de sensores quedan bloqueadas antes de abrir el transporte de servicio.

El ZIP usa `gimbal.usb_profile`, no `vision.usb_profile`. Un nombre de producto
coincidente solo es coincidencia de descriptor, no identidad autenticada ni
prueba de compatibilidad. El 100 % indica inventario guardado, no calibración.
No hay cambio de firmware o de controlador ni órdenes de fábrica/calibración.
La enumeración puede emitir GET_DESCRIPTOR estándar; no se conoce el número
exacto de esas operaciones. No se reclaman interfaces ni se transfiere bulk.

## Próximo dato del equipo

Extrae el ZIP de la versión nueva. Selecciona **DJI Flip**, revisa el firmware
**01.00.1500** y pulsa **Recopilar perfil USB** en el lateral. Guarda y comparte
`DJIFlip-PerfilUSB-….zip`, incluso si informa un error. Conecta solo el Flip y
cierra otras aplicaciones que mantengan ocupado su USB.

No se presupone su código interno, PID o endpoints. PnP recoge nodos DJI para
cualquier PID; la fase actual de descriptores libusb0 solo reconoce 2CA3:0020.
Otro PID se conserva en PnP con el límite explícito de la fase de descriptores.
No se cambia su PID ni se aplica un perfil de otro producto para hacerlo pasar.

## Falta para ejecutar JointCoarse/LinearHall

El inventario USB no basta. Hay que contrastar con este modelo y firmware:
entrada/salida del modo de taller, peticiones de ambas rutinas, significado de
sus respuestas, etapas, fin y rechazo. Una captura de un procedimiento que
funcione con Flip o una implementación documentada específica permitiría
contrastar esos datos. No se presentan ACK o movimiento como calibración terminada.

Referencia pública consultada el 13 de noviembre de 2026:
https://github.com/o-gs/dji-firmware-tools/blob/master/comm_og_service_tool.py
La copia revisada tiene procedimientos modernos para Air 3/Mini 3, pero no
incluye Flip. Eso no demuestra que sea imposible calibrarlo ni que esas rutinas
sean compatibles por analogía. No se copió ese código al motor de esta entrega.
No se pudo consultar el manual oficial en este entorno por su política de red;
no se da una guía de calibración automática como sustituto de las rutinas pedidas.

Pruebas propias con fixtures de USB y de interfaz, y arranque del EXE bajo Wine.
No hay dron Flip conectado en cloud; no se ha probado esta lectura en su hardware.

## Perfil 1.8.0 recibido el 13 de noviembre

ZIP válido de 2205 bytes con un JSON de 17817 bytes. Ocho nodos PnP, un padre
2CA3:0020, seis alias con descriptores completos y sin errores de esa fase.
Nombre de producto genérico DJI-…; no se convierte en identidad comercial Flip.
Firmware de aeronave 01.00.1500 declarado, no leído del descriptor USB 0x0504.

| Interfaz | OUT | IN | Tipo | Tamaño máximo |
| --- | --- | --- | --- | --- |
| MI02 (almacenamiento) | 02 | 83 | bulk | 512 |
| MI03 | 03 | 84 | bulk | 512 |
| MI04 | 04 | 85 | bulk | 512 |
| MI05 | 05 | 86 | bulk | 512 |
| MI06 | 06 | 87 | bulk | 512 |
| MI07 | 07 | 88 | bulk | 512 |

Esto acredita el inventario de descriptores en el Windows del usuario; no hay
tráfico de módulos, modo de taller o calibración en ese archivo. No hace falta
repetir ese inventario para obtener los mismos datos ya recibidos.

## Consulta experimental de módulos en 1.8.1

1. Extrae el ZIP nuevo, abre su EXE y selecciona DJI Flip / USB bulk.
2. Pulsa **Consultar FC y gimbal (Flip)** en el lateral.
3. Selecciona tu **DJIFlip-PerfilUSB-….zip de 1.8.0** como referencia.
4. Guarda un ZIP nuevo **DJIFlip-Modulos-….zip** y compártelo, incluso si hay error.

Antes de transmitir se relee el padre actual de MI04. Producto y hashes de nodo
hijo/padre deben coincidir exactamente con el perfil seleccionado. Se vuelven a
comprobar configuración activa 1, alternativa 0, clase FF/43/01 y OUT04/IN85 bulk
512. No se usa el orden de los alias ni se cambia configuración para forzarlo.
Si cambiaste de puerto y no coincide el nodo, recopila un perfil nuevo.

Esta prueba reclama MI04 localmente y permite únicamente dos peticiones DUML
estándar **00/01 sin payload**, una al controlador (03) y otra al gimbal (04),
sin reenvíos. No admite 04/08, 00/44, destinos alternativos o paquetes arbitrarios.
La consulta común de versiones procede del lector propio ya incluido; su
compatibilidad real con este Flip aún debe probarse. No se habilita el modo de
taller ni JointCoarse/LinearHall a partir de un descriptor.

La recepción es de hasta 64 KiB y cada respuesta espera hasta 3 segundos, con
lecturas USB de 200 ms. Los datos se guardan en un BIN nuevo y en el ZIP, junto
con el informe `gimbal.module_query`, consultas/respuestas correlacionadas y
entrega USB incierta si hay error. Se compara CRC, emisor, destino y secuencia.
El BIN contiene también tráfico no relacionado, sin interpretarlo como calibración.
La interfaz se libera y los recursos se cierran al terminar.

Los campos de hardware/loader/versión usan el formato común del proyecto y se
conservan también los bytes crudos. Son observaciones de módulo; no autentican
el modelo ni sustituyen la versión de aeronave de DJI Fly. Una respuesta ausente,
un formato distinto o un error de apertura no demuestran una avería del gimbal.
El 100 % exige dos respuestas con formato reconocido y el ZIP guardado.

La calibración de taller sigue pendiente. Esta consulta comprueba la comunicación
de información; no acredita peticiones, modo de fábrica, etapas o fin de calibración.
Pruebas sintéticas y del EXE bajo Wine; nueva ruta sin prueba física en Flip.
