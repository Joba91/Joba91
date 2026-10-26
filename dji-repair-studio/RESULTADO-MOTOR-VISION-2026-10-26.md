# Componentes de visión recibidos el 26 de octubre de 2026

## Resultado

Las dos partes recibidas reconstruyen un ZIP de 51.997.238 bytes con CRC
correcto. Los 23 archivos PE coinciden con los SHA-256 declarados en el
inventario. Todos son x86 (máquina PE `0x014c`). Se analizaron sin cargarlos ni
ejecutarlos; no hubo operaciones USB ni cambios en el dron.

El paquete contiene versiones de `DJIVisionCalibration.dll`,
`DJIVisionCalibration2.dll`, `DJIVisionCalibration3.dll` y `DJI_guidance.dll`
de distintas instalaciones de DJI Assistant. Hay que mantener separadas las
versiones: no son intercambiables por tener el mismo nombre.

## Hallazgo específico del perfil wa140

En la copia de `DJIVisionCalibration3.dll` de **Consumer Drones Series**,
SHA-256 `7105076d6c72e50b823d0bec9c7696c2aa7fdd50578361e68dec3a838bf41044`,
se identificó una comparación explícita de la cadena de modelo `wa140`:

- Comparación y rama: VA `0x1008d9ef`–`0x1008da5e`.
- En esa rama se asignan ancho `0x280` y alto `0x1e0` (640 × 480).
- Se utilizan el nombre `cali_ab.txt` y las rutas `raw/down/left` y
  `raw/down/right`.
- Otra comparación de `wa140` participa en la ruta de inicialización del
  sistema de percepción, alrededor de VA `0x100c0a95`.

`wa140` coincide con el código del proyecto de Mini 4 Pro presente en el
material de taller compartido anteriormente. Esta asociación y la rama
estática son pistas concretas; no prueban funcionamiento con firmware
01.00.1100 ni que ese perfil cubra la visión delantera derecha.

La variante Enterprise recibida, SHA-256
`248a9a2b3876cfd10c254240af3b407b4b3485a4a304aeb0c9ce22d13086e0bd`,
no contiene la misma cadena `wa140` en la búsqueda realizada. No se debe usar
como sustituta de la copia Consumer analizada.

## Flujo localizado

El motor dispone de seguimiento, patrones, imágenes y progreso. Se identifican
las rutas de `DJIVisionCalibrationWorker::calculateCheckPush` y las referencias
a comprobación de parámetros, escritura de resultados y reinicio de percepción.
Por tanto, activar el cálculo puede terminar escribiendo parámetros: no es una
simple consulta de estado.

La API exportada `NewCalibration_Start` no recibe un código de modelo: utiliza
un trabajador global inicializado por el entorno Qt. Cargar la DLL y llamar a
esa función sin reconstruir la inicialización no constituye una integración
válida. La variante Consumer 3 tampoco exporta `NewCalibration_Stop`; la parada
aparece en la interfaz de mensajes Qt/JSON. Hay que resolver esa interfaz y sus
condiciones de terminación antes de habilitar una operación en DJI REPAIR.

## Dependencia concreta pendiente

La DLL Consumer importa **`fs_dbus_lib.dll`**. Sus importaciones incluyen:

- `ss_dbus_pc_init`
- `ss_dbus_all_peer_node_is_online`
- `ss_dbus_shm_subscriber_new`
- `ss_dbus_shm_subscriber_wait_data`
- `ss_dbus_shm_stop_subscribe`
- `ss_dbus_shm_restart_subscribe`
- `vp_message_send_sync`

Se confirmaron los trampolines de importación y llamadas de inicialización en
la ruta de imágenes. `DJI_guidance.dll` no proporciona estas funciones y no
debe tratarse como un reemplazo. `fs_dbus_lib.dll` no estaba en este paquete.

También faltan los componentes del entorno Qt y el lanzador
`VisionStarter3.exe`, si está presente en esa instalación. El lanzador permite
estudiar el contrato de inicio del motor sin inventar la ABI ni ejecutar la DLL.

Se preparó una recopilación adicional que selecciona **el hash Consumer exacto
ya analizado** y recoge únicamente los binarios nativos de su carpeta y los
plugins Qt de `platforms`/`imageformats`, además de `VisionStarter3.exe`.
No recoge configuraciones, registros, contraseñas ni archivos `.encr`.
No ejecuta los archivos, no inicia servicios ni se comunica con el dron.

## Estado de integración

No se ha habilitado una calibración funcional en DJI REPAIR. Quedan por
verificar la comunicación con el sistema de visión, el contrato de inicio y
parada, la cobertura del sensor delantero y el resultado en el firmware del
usuario. Una integración de estos componentes x86 en la aplicación x64
necesitaría un proceso auxiliar de 32 bits; puede mantenerse sin ventana visible.

Los archivos propietarios recibidos se conservan para análisis privado y no
se incluyen en los paquetes públicos de DJI REPAIR.
