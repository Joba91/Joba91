# Estado de visión · Mini 4 Pro y Air 3

6 de noviembre de 2026. La calibración de visión sigue pendiente para ambos.
DJI REPAIR 1.7.0 añade el destino Air 3, inventario PnP y manejo específico de
la espera de imágenes. No añade un generador ni un instalador de calibración.

## Captura Mini 4 Pro recibida

Se revisó el ZIP de prueba de imágenes del 28 de octubre: CRC válido y un solo
JSON de 5850 bytes, sin PGM. Su SHA-256 es
`de9875a5facf80645266e015f03b4dfb1a75543fde010802c5cb9caa106d78c3`.

El receptor propio x86 terminó con código 0; el SDK informó sus pares en línea.
Hubo 48 estados `0xd0010003` durante 10,209 segundos, dos cierres de suscripción
con retorno 0 y ninguna imagen. No se ejecutó calibración. Se conserva el archivo
original de forma privada; no se publican nombres de usuario o identificadores.

Se contrastó el código en `fs_dbus_lib.dll`, SHA-256
`f530863e700e37d18b35e7dbc23df1d007f76dff61be5e39afe0311115db43e8`.
En VA `0x1001bf60` se registra `Wait data timeout`, y en `0x1001bf75` se devuelve
`0xd0010003`. Esto acredita espera de datos vencida; no identifica la causa ni
una avería física. 1.7.0 conserva ese estado como desconocido y registra un
resumen específico. Otros códigos no interpretados detienen la recepción y
conservan el error en vez de repetirlos como si fueran esperas normales.

## Activación del productor de imágenes

La referencia Consumer `wa140`/`wa233` llama una rutina previa a las
suscripciones. En la copia analizada de `DJIVisionCalibration3.dll`, la llamada
aparece en `0x100c0b36` y la rutina está en `0x100d0c50`–`0x100d0f10`.
Construye una petición con el nombre `start_dji_perception.sh` y usa
`vp_message_send_sync`. El contenido del script reside en el firmware y sus
efectos no se han validado con este equipo. No se ha incorporado esa ejecución
al programa ni se ha alterado ningún servicio del dron durante el desarrollo.

La rutina nativa puede agotar tres intentos y devolver 0 al salir en
`0x100d0ef3`, incluso después de registrar fallos. Por eso un retorno 0 o un ACK
no bastan como prueba de que arranque el productor ni de que se calibre.
La falta de esa solicitud en 1.6.0 es una diferencia concreta respecto al flujo
nativo, no una causa ya demostrada de la ausencia de imágenes. Sigue pendiente
resolver la activación completa, sus respuestas y la recuperación de estado.

El perfil `wa140` examinado solo define una pareja inferior. Aunque entregue
fotogramas, no acredita calibración del sensor delantero derecho ni muestras
sincronizadas para calcular nuevos parámetros.

## Air 3

El usuario declara firmware 01.00.1600. Se añadió como destino independiente;
se requiere su inventario USB antes de definir un transporte. No se reutilizan
endpoints o peticiones del Mini 4 Pro ni se elige un código interno por analogía.
El nuevo recopilador solo lee metadatos presentes de Windows y crea un ZIP.

## Lo que sigue pendiente

- Recepción de imágenes compatible y validada físicamente para cada modelo.
- Cobertura de las parejas de sensores que realmente se quieren calibrar.
- Procedimiento de patrones, cálculo y condiciones de captura.
- Respaldo de datos originales, instalación y comprobación posterior de lo escrito.

La versión no presenta progreso 100, un descriptor, un ACK ni códigos HMS como
prueba de calibración. Los SDK recibidos permanecen privados y se analizan sin
ejecutarlos en cloud. El nuevo EXE se valida con fuentes, pruebas y evidencia
propias; no se reemplaza un procedimiento faltante con una orden adivinada.
