# Investigación de autocalibración de visión — Mini 4 Pro

Fecha: 26 de octubre de 2026. Firmware declarado por el usuario: 01.00.1100.
Objetivo: recalibrar la visión después de un accidente y del cambio del cristal
protector delantero derecho. El sensor electrónico original permanece instalado.

## Resultado de esta revisión

Hay una pista concreta para investigar: un protocolo antiguo de autocalibración
de visión con solicitud de inicio y mensajes de estado. Su compatibilidad con
Mini 4 Pro / 01.00.1100 **no está establecida**. No se ejecutó en el dron y no se
añadió un botón de calibración al ejecutable.

La revisión tampoco demuestra que ese procedimiento antiguo pueda compensar
el efecto óptico del cristal cambiado o resolver los avisos actuales.

## Evidencias nuevas

### 1. Protocolo antiguo de autocalibración

En una copia pública de código Android, revisión
`4c7bb40e5cc5daec67b39cc093235afb959a4bfe`, de abril de 2020:

- `DataEyeEasySelfCalibration` construye una solicitud `EasySelfCal` con un byte
  de selección de operación. La solicitud se dirige al dispositivo `DOUBLE`.
- `CmdIdEYE` identifica la solicitud como 48 y el mensaje de estado como 50
  (familia EYE, 10). Son las familias DUML `0a/30` y `0a/32`.
- `DataEyeGetPushEasySelfCalibration` contiene estados de espera, recolección de
  imágenes, cálculo y resultado, además de una lectura de progreso.
- El archivo distingue esos estados del ACK de aceptación. Un ACK por sí solo
  no acreditaría que una calibración terminó ni que sus parámetros se guardaron.

Fuentes fijadas a esa revisión:

- [Solicitud](https://github.com/district-michael/fpv_live/blob/4c7bb40e5cc5daec67b39cc093235afb959a4bfe/src/main/java/dji/midware/data/model/P3/DataEyeEasySelfCalibration.java)
- [Estado y progreso](https://github.com/district-michael/fpv_live/blob/4c7bb40e5cc5daec67b39cc093235afb959a4bfe/src/main/java/dji/midware/data/model/P3/DataEyeGetPushEasySelfCalibration.java)
- [Identificadores](https://github.com/district-michael/fpv_live/blob/4c7bb40e5cc5daec67b39cc093235afb959a4bfe/src/main/java/dji/midware/data/config/P3/CmdIdEYE.java)

Se verificó que los tres archivos descargados coinciden con la revisión fijada.
Este código precede al Mini 4 Pro: no constituye una prueba de compatibilidad.
Sus valores de estado tampoco deben interpretarse automáticamente en tráfico
de firmware moderno. Se conserva como referencia, sin copiarlo al producto.

### 2. Contraste con los datos ya recibidos

Se analizaron sin conexión siete capturas USB distintas por SHA-256:

- 1.494 tramas DUML válidas en total.
- Ninguna trama `0a/30` ni `0a/32`.
- Los 89 registros históricos contienen 734 tramas válidas y tampoco incluyen
  esas familias.

Estas capturas provienen de lecturas pasivas, SN y HMS; no documentan una sesión
de calibración. La ausencia de las familias buscadas no demuestra que el dron
las rechace: deja sin resolver la compatibilidad y el procedimiento.
No se necesita repetir esas mismas capturas para confirmar este resultado.

### 3. Documentación oficial del SDK moderno

Se revisó Mobile SDK Android V5, revisión
`a48aa4e7811d824c27abfa973f5655579bfb8a77` (README: 5.18.0), que lista
Mini4 PRO entre los productos compatibles. En el contenido de las ocho páginas
consultadas de `IPerceptionManager`/radar y en el ejemplo de percepción no se
encontró una API para iniciar la calibración de visión. Las menciones a
calibración en el menú común son de gimbal/IMU.

Esto limita esa vía pública de integración; no prueba que no exista una
función interna o un procedimiento de taller.

[Documentación de percepción revisada](https://github.com/dji-sdk/Mobile-SDK-Android-V5/blob/a48aa4e7811d824c27abfa973f5655579bfb8a77/Docs/Android_API/en/Components/IPerceptionManager/IPerceptionManager.html)

### 4. DLL aportada por el usuario

Se examinó estáticamente `dji_test_userlibs.dll`, SHA-256
`03a04ab846defd1be8fe5a36dd5c03b8c5389bf264f3ac3bb9782a5a033b0c83`.

`TSadbScriptGrepSelfcali` contiene referencias a `npi_tools.sh` y `selfcali`.
El nombre y las cadenas no acreditan que inicie una calibración ni proporcionan
el contenido del script. Los flujos de descarga/copia de archivos de percepción
ya identificados siguen siendo distintos de generar una calibración óptica.
`TsStartCali` presenta referencias a una plataforma de movimiento; no se ha
establecido que corresponda a calibración de visión.

Ninguna DLL se cargó ni ejecutó.

### 5. Incidencias públicas

La [incidencia 475 de dji-firmware-tools](https://github.com/o-gs/dji-firmware-tools/issues/475)
plantea expresamente calibración de gimbal/visión del Mini 4 Pro después de
reparación. En los comentarios visibles consultados no hay un procedimiento
técnico reproducible de calibración de visión. Las ofertas comerciales y los
enlaces de terceros no se consideran validación.

## Qué falta para convertir la pista en una función

1. Vincular una implementación de autocalibración o un procedimiento de taller
   al Mini 4 Pro y a su firmware, con sus condiciones previas y sus efectos.
2. Determinar si recalcula los parámetros que necesita este caso o si solamente
   verifica/recupera datos existentes. No asumir que borra un aviso o que un ACK
   equivale a calibrar.
3. Documentar la secuencia completa: inicio, movimiento o patrón requerido,
   progreso, fallo, cancelación y terminación; identificar los cambios
   persistentes y cómo conservar los datos originales.
4. Validar el resultado y su persistencia en hardware antes de presentarlo como
   una calibración funcional en DJI REPAIR.

La investigación puede continuar a partir de una implementación moderna o de
un registro de un procedimiento de calibración conocido y compatible. Los
datos actuales permiten formular esta hipótesis, pero aún no resolverla.

## Estado del programa

DJI REPAIR Studio 1.5.0 conserva sus funciones actuales de identificación y
diagnóstico. Esta investigación no cambia el ejecutable ni afirma haber
calibrado el equipo. Operaciones USB y escrituras al dispositivo durante esta
revisión: **0**.

## Segunda revisión: implementación reciente y dependencia pendiente

Se examinó otra referencia pública que se presenta como DJI Fly 1.21.4:
[`EmoLa63/DJI_Fly_1.21.4_Decompiled`](https://github.com/EmoLa63/DJI_Fly_1.21.4_Decompiled/tree/0eecc6cd8d9905acccb7965c2361dd05fa3c2908).
Su `apktool.yml` declara esa versión; no se verificó la autenticidad de un APK
oficial firmado. Se usa como pista estática y no como prueba de soporte.

- Las clases `DataEyeEasySelfCalibration` y
  `DataEyeGetPushEasySelfCalibration` permanecen incluidas. Esto no demuestra
  que se utilicen con Mini 4 Pro.
- `VisionCaliReplaceTask` enlaza `KeyCalibrationFileStatus`,
  `KeyUpdateCalibrationFile` y `KeyCalibrationFileUpdatingInfo`.
- `CaliUpgradeRepository` comprueba `KeyIsPerceptionCalibrationSupport`,
  obtiene archivos de servidor, los transfiere y espera instalación/reinicio.
  Ese flujo trata datos existentes; no contiene por sí mismo la generación
  de una calibración óptica nueva.
- En el SDK nativo ARM se identificó y desensambló estáticamente
  `FlightAssistantCalibrationFileModule`, incluyendo `Setup`,
  `CreateCharacteristics`, `OnStatusInfoPush` y `OnNotifyFlagPush`.
  Sus métodos de transferencia y notificación tampoco acreditan un algoritmo
  de calibración óptica compatible con este equipo.

No se ejecutaron las bibliotecas, no se usaron credenciales ni se hicieron
peticiones a servidores de DJI. Ningún binario de estas referencias se añadió
al producto ni al paquete que se entrega.

También se encontró una investigación de terceros sobre el motor de imagen de
DJI Assistant, [revisión
7e412b901824f965fe6c885da14848110ac6c22f](https://github.com/kewl-ua/m4_cli_flasher/blob/7e412b901824f965fe6c885da14848110ac6c22f/docs/vision-calibration.md).
Se refiere principalmente a Matrice 4T, un modelo distinto. Sus afirmaciones
sobre `DJIVisionCalibration3.dll` y `DJI_guidance.dll` son pistas para localizar
artefactos; no se adoptan como validación de compatibilidad del Mini 4 Pro.

**Dependencia pendiente:** no se ha identificado en los archivos disponibles
un procedimiento completo y compatible que adquiera las imágenes de visión,
calcule parámetros nuevos y permita verificar su instalación. Hace falta una
implementación aplicable o los componentes pertinentes para continuar ese
análisis. No basta con seguir capturando SN/HMS ni con enviar el comando antiguo.

Se preparó `research-tools/Recopilar-motor-vision.ps1` para buscar los candidatos
`DJIVisionCalibration{,2,3}.dll` y `DJI_guidance.dll` en las instalaciones locales
del usuario. Solo inventaría y copia archivos por una lista exacta de nombres;
no carga DLL, no calibra, no consulta USB y no usa servicios de red. Conserva
hashes/versiones y divide ZIP mayores de 30 MiB para facilitar su entrega.
El ZIP generado es material privado para análisis, no para publicación.

El objetivo de integración sigue pendiente: **DJI REPAIR no incorpora todavía
una calibración de visión operativa para Mini 4 Pro / 01.00.1100**.
