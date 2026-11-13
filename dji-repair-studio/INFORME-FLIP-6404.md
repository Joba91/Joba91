# DJI Flip: investigación de 64 04 · 13 de noviembre de 2026

La captura de JointCoarse recibida de 1.9.1 contiene 37.357 bytes y 1.068 tramas
con CRC válido. Se observan dos respuestas de versión coincidentes con la
referencia anterior y un ACK 00 correlacionado con la única solicitud 04/08.
Después del ACK hay 599 informes 52 01 y diez 64 04, sin 64 00. El informe
registra 58 lecturas sin datos (-116) y un error final de lectura USB -5.
El usuario confirma movimiento de pitch, ausencia de movimiento de yaw/roll y
que mantuvo el dron encendido y el cable conectado.

## Qué se encontró

La referencia pública de DJI Fly declarada 1.21.4 define el estado común 4 como
TIMEOUT en GimbalCommonCalibrationStatus y GimbalCalibrationFailedReason.
El modelo de datos DataGimbalGetPushAutoCalibrationStatus lee el segundo byte
completo como estado, sin máscara. En el análisis estático de libsdk_jni.so,
OnGimbalCalibrationStatePush lee ese segundo byte y lo pasa al decodificador
de estados, conservando estado y motivo de fallo. No se ejecutó código DJI.

Es evidencia para **TIMEOUT según referencia común**, no una validación de la
semántica del firmware Flip 01.00.1500 ni un diagnóstico de motor, atasco,
flex, sensor o requisito de modo fábrica. La autenticidad del APK de esa
referencia de terceros no se ha verificado. El byte 64 no convierte el
resultado en éxito ni en 100 % de una calibración física.

La referencia distingue TIMEOUT (4) de los códigos denominados
ROLL_MOTOR_FAIL (32), PITCH_MOTOR_FAIL (33) y YAW_MOTOR_FAIL (34).
Esa distinción impide atribuir un motor averiado a partir del valor 4.
Tampoco demuestra que aumentar el tiempo del programa permita completar la rutina.

## Integración 1.9.2

- El informe conserva el último estado, sus recuentos y la interpretación común.
- Si llega 64 04 y falla después la lectura, conserva ambos hechos. Continúa
  monitorizando dentro de los límites existentes: no da por validado un fin del
  Flip por esa referencia. 64 04 seguido de 64 00 queda ambiguo y no produce 100 %.
- Los ACK con forma de 04/30 no se aceptan como informes espontáneos.
- El lateral ofrece Analizar prueba Flip (ZIP). Relee BIN/CRC y busca el ACK
  correlacionado; cuenta solo informes posteriores a él. No abre USB ni escribe
  al dron. El 100 % de esta acción significa análisis del archivo finalizado.
- Se conservan los límites, las peticiones y las restricciones de calibración.

**Esta versión mejora el diagnóstico. No resuelve todavía la falta de movimiento
de yaw y roll ni valida una calibración completa del Flip.** Para revisar la
captura existente no hay que repetir JointCoarse ni ejecutar LinearHall.

## Referencias y límites de reproducción

Repositorio de terceros, commit 0eecc6cd8d9905acccb7965c2361dd05fa3c2908:

- [Estado común](https://github.com/EmoLa63/DJI_Fly_1.21.4_Decompiled/blob/0eecc6cd8d9905acccb7965c2361dd05fa3c2908/smali_classes8/uav/sdk/keyvalue/value/gimbal/GimbalCommonCalibrationStatus.smali)
- [Motivos de fallo](https://github.com/EmoLa63/DJI_Fly_1.21.4_Decompiled/blob/0eecc6cd8d9905acccb7965c2361dd05fa3c2908/smali_classes8/uav/sdk/keyvalue/value/gimbal/GimbalCalibrationFailedReason.smali)
- [Lector del estado](https://github.com/EmoLa63/DJI_Fly_1.21.4_Decompiled/blob/0eecc6cd8d9905acccb7965c2361dd05fa3c2908/smali_classes8/uav/midware/data/model/P3/DataGimbalGetPushAutoCalibrationStatus.smali)

No se incluyen APK, bibliotecas DJI, capturas originales ni identificadores de
la unidad del usuario. Las pruebas distribuidas usan datos sintéticos y el EXE
se verifica bajo Wine, sin calibrar un Flip físico en el entorno cloud.
