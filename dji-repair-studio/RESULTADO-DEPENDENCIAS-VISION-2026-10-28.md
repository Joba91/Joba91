# Análisis de dependencias de visión — 28 de octubre de 2026

Las dos partes recibidas reconstruyen un ZIP de 34.407.968 bytes. Su CRC es
correcto y los SHA-256 de los 95 archivos coinciden con el inventario. Los
archivos PE son x86. La DLL Consumer de calibración coincide con el hash ya
analizado, sin mezclar la variante Enterprise.

Se comprobaron estáticamente las importaciones transitivas de
`VisionStarter3.exe`: 26 componentes locales y 7.771 importaciones locales
resueltas, sin nombres de función pendientes en esos componentes. Las
bibliotecas del sistema operativo se consideran externas; este resultado no
equivale a una prueba de ejecución en Windows o de compatibilidad con el dron.

No se ejecutaron los EXE ni las DLL recibidas. No hubo consultas USB, comandos
de calibración ni escrituras al equipo. Los binarios se conservan para análisis
privado y no se añaden a distribuciones públicas.

## Arranque y comunicación local

`VisionStarter3.exe` construye una aplicación Qt y una instancia de
`VisionCalibrationViewTest`. Lee cuatro argumentos de texto de la línea de
comandos. La comprobación inicial de cantidad de argumentos no basta como
documentación de sus funciones: no se deben inventar sus valores.

El motor expone una interfaz de mensajes con campos `CMD` y `SEQ`; diferencia
la aceptación de comandos de los eventos posteriores. La ruta de inicialización
lee `WIDTH`, `HEIGHT`, `SCREEN_WIDTH`, `SCREEN_HEIGHT`, `DEVICE` y `VERSION`.
Se identificaron comandos distintos para inicialización, ajuste al patrón,
seguimiento, cálculo, selección de pareja y parada.

El servidor nativo utiliza el puerto 19871 y rechaza conexiones cuya dirección
no sea de loopback. Ese control debe conservarse. También existe una rutina
periódica con `QSharedMemory`; su contrato de supervisión debe resolverse antes
de reutilizar el lanzador. No se han alterado comprobaciones del motor ni se
han utilizado credenciales de DJI.

## Transporte de imágenes

`fs_dbus_lib.dll` utiliza `fs_usb.dll`. Se identificaron las funciones de
apertura, lectura, escritura y búsqueda del transporte. La fábrica USB de esta
versión dispone de variantes que cargan `libusb0.dll` y `libusb0_dji.dll`.
La existencia de ambas no autoriza a intercambiarlas ni a cambiar controladores.

La configuración `dbus_pc.json` ya se recibió y analizó: SHA-256
`5b0106d86e669c1ff9073ea0e5634244d4b6c99e6e4fa6516e122c38e3a8fc9b`.
Su modo `wa140` pertenece a `dual_chip_a7`. Declara VID/PID `2ca3:0020`,
interfaz 5 para `v1` e interfaz 3 para `dbus`. No se infieren endpoints de ese
JSON. La selección de endpoints corresponde al transporte nativo y los
respectivos descriptores, sin reconfigurar controladores.

## Integración experimental de recepción

DJI REPAIR 1.6.0 añade un receptor propio x86 separado de la interfaz x64.
Solo expone inicialización DBus, consulta de pares, suscripciones, recepción y
destrucción de suscripciones. No invoca VisionStarter3, cálculo, escritura,
credenciales ni cambios de modo. El SDK permanece en la instalación del usuario;
se verifican siete DLL y el JSON, y se copian a una sesión temporal. VCRUNTIME140
lo proporciona el runtime oficial de Python x86 que ya utiliza el receptor.

Los metadatos de referencia sitúan ancho/alto uint16 LE en offsets 6/8,
bits por píxel en 14 y longitud uint32 LE en 24. Se acepta solo 640×480,
8 bits, 307200 bytes. La copia de memoria es acotada y el archivo PGM se
valida por tamaño, cabecera y SHA-256 antes de mostrarlo o empaquetarlo.
Los temas `raw/down/left` y `raw/down/right` no acreditan posición física,
sincronización ni un conjunto de calibración en esta aeronave.

La inicialización nativa produce tráfico de control: no se presenta como USB
pasivo ni se declara un número cero de escrituras USB desconocidas. El informe
registra cero llamadas solicitadas de calibración/escritura de parámetros y
cantidad de tráfico nativo desconocida. La prueba física sigue pendiente.

El arranque del proceso x86 no se pudo comprobar en este host: su kernel tiene
`CONFIG_IA32_EMULATION` deshabilitado. Tanto CPython x86 oficial como nuestro
receptor fallan antes del código Python. Se validan arquitectura PE, manifiesto,
importaciones, contenido congelado y lógica mediante adaptadores sintéticos.
Esto no equivale a una prueba de Windows nativo ni a la carga del SDK DJI.

## Estado del objetivo

La calibración de visión no está habilitada en DJI REPAIR. Además de validar
la recepción física y completar el control del motor, siguen pendientes la cobertura del sensor
delantero derecho, la compatibilidad con firmware 01.00.1100 y la verificación
de los parámetros guardados. El perfil `wa140` localizado anteriormente contiene
rutas de visión inferior; no se presenta como prueba de calibración delantera.
