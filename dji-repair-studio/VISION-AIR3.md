# Air 3 · visión en desarrollo · versión 1.7.2

Firmware 01.00.1600 declarado por el usuario. La calibración óptica no está
implementada y el transporte de sensores aún no está validado.

## Inventario recibido de Windows

Studio 1.7.1 terminó su proceso de lectura con código 0 y obtuvo ocho nodos PnP:
- Un padre físico 2CA3:0020, servicio usbccgp, producto con prefijo `e3t`.
- MI00: RNDIS, servicio usbrndis6.
- MI02: Mass Storage, servicio libusb0.
- MI03, MI04, MI05, MI06 y MI07: BULK Interface, servicio libusb0_device.

Todos los códigos PnP de problema son cero. Siete consultas FriendlyName devolvieron
CR_NO_SUCH_VALUE (0x25); se usó DeviceDesc como alternativa y la lectura terminó.
No es un fallo de sensores. No hay direcciones de endpoints en ese informe.
`e3t` es el texto observado; Air 3 es el modelo declarado. Falta una referencia
que acredite esa asociación comercial. No se usa el prefijo para enviar comandos.

## Obtener los descriptores con 1.7.2

1. Extrae el ZIP nuevo y abre su EXE.
2. Conecta solo el Air 3; selecciónalo con firmware declarado 01.00.1600.
3. Visión de sensores → Recopilar perfil USB → guarda un ZIP nuevo.
4. Comparte el ZIP incluso si muestra error. Cierra otras herramientas DJI si
   mantienen ocupado el dispositivo; no se pide cambiar controladores.

El proceso oculto conserva el PnP obtenido y añade `descriptor_inventory`.
La biblioteca libusb0 incluida se comprueba por SHA-256 antes de cargarla.
Su enumeración lee descriptores estándar; las consultas PyUSB posteriores usan
la caché analizada de esa biblioteca. No se consulta configuración activa, se
reclaman interfaces ni se realizan transferencias bulk o comandos DJI.

Cada alias se contrasta por HardwareID y por su nodo PnP actual, que debe coincidir
exactamente con el de esa sesión. Varios padres físicos, nodos contradictorios,
conteos excesivos y descriptores mal formados se conservan como error. Un timeout
mantiene los nodos y descriptores parciales y registra la última etapa.

La tabla muestra Cn/An (configuración/alternativa) y endpoints observados. No
selecciona esa configuración ni abre un transporte. El 100 % significa inventario
guardado. El estado de calibración permanece desconocido/no disponible.

## Lo que sigue pendiente

Probar esta nueva lectura en el Windows del usuario, interpretar los canales
con evidencia específica del modelo, obtener imágenes y resolver el procedimiento
de cálculo, instalación y comprobación de calibración. No se aplican las peticiones
Mini 4 Pro de SN/HMS, imágenes o gimbal al Air 3. El dato `bcdDevice=0x0504` es
una revisión USB y no sustituye el firmware declarado desde DJI Fly.

La nueva ruta se prueba con fixtures y en el EXE bajo Wine; no está validada en
hardware Air 3. Los informes originales y los identificadores quedan privados.
