# DJI REPAIR Studio 1.6.0

[Descargar Windows 10/11 x64](https://raw.githubusercontent.com/Joba91/Joba91/main/downloads/DJI_Repair_Studio_1.6.0.zip)

Extrae el ZIP en una carpeta nueva y abre **DJI REPAIR Studio 1.6.0.exe**.
Esta versión añade **recepción experimental de imágenes inferiores**.
**La calibración Mini 4 Pro todavía no está habilitada.**

## Probar recepción de imágenes

1. Conecta el Mini 4 Pro encendido y cierra DJI Assistant y otros clientes USB.
2. En **Visión Mini 4 Pro**, escribe **01.00.1100** en Firmware declarado.
3. Pulsa **Recibir imágenes (prueba)**, en el lateral.
4. Si pregunta por el motor, selecciona `DJIEngine` de **DJI Assistant 2 Consumer**:
   `C:\Program Files (x86)\DJI Product\DJI Assistant 2 (Consumer Drones Series)\DJIEngine`.
5. Guarda un ZIP nuevo **Mini4Pro-Vision-....zip** y comparte ese archivo, incluso si falla.

No añadas `dbus_pc.json` a la carpeta del EXE. Se lee de su ubicación original,
junto a las bibliotecas analizadas. Se comprueban sus SHA-256 y se copian a una
sesión temporal. No se redistribuyen los archivos DJI ni se cambian drivers.

El receptor propio x86 permanece oculto. Las imágenes que lleguen se muestran en
la misma ventana y se guardan como PGM junto al informe. La inicialización del
SDK produce tráfico nativo de control; sus efectos completos y compatibilidad con
el dron aún requieren prueba. No se solicitan calibración, fábrica ni escritura
de parámetros. La referencia es `raw/down/left` / `raw/down/right`: **no confirma
cobertura del sensor delantero derecho** ni sincronización de las imágenes.

El porcentaje mide imágenes verificadas: **100 % exige dos archivos y el ZIP
creado**, sin implicar salud o calibración. Hay límite de tiempo y cancelación;
el supervisor de Windows engloba el árbol de procesos del receptor.

## Validación y límites

280 pruebas de aplicación/interfaz y 11 de empaquetado aprobadas. El EXE x64,
la vista previa sintética, los lectores de registros y el supervisor de procesos
se probaron bajo Wine. El kernel cloud no permite procesos IA32: el receptor
x86 se verificó estáticamente pero **su arranque y recepción real necesitan
prueba en Windows**. No se ejecutaron bibliotecas DJI en desarrollo.
Consulta `validacion-1.6.0.json` y `SHA256SUMS.txt`.

Se conservan captura pasiva MI04, consulta SN y diagnóstico HMS experimental.
**Analizar captura visión** abre los BIN existentes sin consultar USB y reconoce
21/06 y 21/08. Un código presente no demuestra un fallo activo; salud, actividad
y calibración no se deducen de su mera presencia.

[Uso y arquitectura](../dji-repair-studio/VISION-MINI4PRO.md) ·
[Investigación del motor](../dji-repair-studio/RESULTADO-DEPENDENCIAS-VISION-2026-10-28.md) ·
[Código y fuentes](../dji-repair-studio). El ZIP incluye fuentes y licencias.
