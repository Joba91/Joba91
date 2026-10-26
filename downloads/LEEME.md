# DJI REPAIR Studio 1.5.0

[Descargar Windows 10/11 x64](https://raw.githubusercontent.com/Joba91/Joba91/main/downloads/DJI_Repair_Studio_1.5.0.zip)

Extrae el ZIP en una carpeta nueva y abre **DJI REPAIR Studio 1.5.0.exe**.

## Abrir la captura que ya tienes

1. Entra en **Visión Mini 4 Pro**.
2. Pulsa **Analizar captura visión** y abre tu `.bin` existente.
3. Revisa **Diagnóstico HMS**. Ahora incluye `21/06` y **`21/08`**, que 1.4.0 omitía.
4. **Guardar informe** exporta el análisis en JSON. Esta acción no consulta USB.

El problema estaba en el lector: los datos extendidos ya existían en las tres capturas.
Se contrastaron 121 mensajes con contador y TLV, 234 cuerpos conocidos y uno opaco.
La tabla muestra el formato y deja la actividad **desconocida**. Se conservan los
campos no interpretados y las variantes distintas de un mismo código.

**Un código presente no confirma una alarma activa.** Algunos códigos muestran
una referencia del SDK público. Los identificadores 1A510380/382/384/385 se describen
allí como calibración de visión inferior/posterior/izquierda/derecha; su presencia no
valida esa interpretación en Mini 4 Pro ni indica que deba calibrarse. Las referencias
SD tampoco provocan formateo o reparación. Los demás códigos quedan sin descripción.
Los campos de actividad, nivel, índice, componente y fecha de 21/08 siguen sin interpretar.
Ciclos vacíos o silencio no demuestran sensores sanos.

## Nueva recepción opcional

Con el Mini 4 Pro en modo normal, cierra otros clientes USB del PC y declara
**01.00.1100** si coincide con DJI Fly. **Diagnóstico visión (HMS)** solicita
publicación con la misma única petición 21/05 payload01 y escucha ocho segundos.
Guarda un `.bin` nuevo; se genera un ZIP local con RX e informe TX/ACK incluso con fallo.
No agrega órdenes de fábrica, reset de suscriptores, motores, firmware o calibración.
La publicación después de cerrar USB permanece desconocida. No cambia drivers.
No sobrescribe ni sube archivos. Los informes locales pueden contener series;
revísalos antes de publicarlos. Las acciones SN y captura pasiva se conservan.

262 pruebas de aplicación/interfaz y 9 de empaquetado aprobadas. El EXE bajo Wine
prueba ambos formatos y reanaliza los tres archivos originales con CRC válidos,
mostrando cuatro códigos de referencia de visión en cada uno. Es análisis offline,
sin una nueva consulta física o prueba de Windows nativo. Los originales permanecen privados.

[Uso y arquitectura](../dji-repair-studio/VISION-MINI4PRO.md) ·
[Investigación](../dji-repair-studio/INVESTIGACION-REGISTROS-MINI4PRO.md) ·
[Código](../dji-repair-studio). Fuentes y licencias incluidas. Consulta **SHA256SUMS.txt**.

## Investigación de calibración de visión

[Recopilador del motor de visión 1.0.0](https://raw.githubusercontent.com/Joba91/Joba91/main/downloads/DJI_Repair_Investigacion_Vision_1.0.0.zip) — busca componentes locales para análisis. **No calibra el dron y no sustituye DJI REPAIR Studio.** Extrae el ZIP y abre `Recopilar-motor-vision.cmd`.

[Recopilador de dependencias de visión 1.1.0](https://raw.githubusercontent.com/Joba91/Joba91/main/downloads/DJI_Repair_Dependencias_Vision_1.1.0.zip) — completa los binarios del motor Consumer identificado. Extrae y abre `Recopilar-dependencias-vision.cmd`. **Herramienta de investigación; no calibra.**
