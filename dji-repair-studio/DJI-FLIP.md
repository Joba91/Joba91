# DJI Flip · gimbal de taller · proyecto pendiente

Firmware de aeronave **01.00.1500 declarado por el usuario el 13 de noviembre de
2026**. Solicitud: **JointCoarse y LinearHall**, no la calibración automática de
DJI Fly. **Estas dos rutinas todavía no están implementadas para el Flip.**

## Incluido en 1.8.0

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
