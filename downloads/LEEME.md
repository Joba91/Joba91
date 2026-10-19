# DJI REPAIR Studio 1.1.0

[Descargar para Windows x64](https://raw.githubusercontent.com/Joba91/Joba91/main/downloads/DJI_Repair_Studio_1.1.0.zip)

Extrae el ZIP en una carpeta nueva y abre **DJI REPAIR Studio 1.1.0.exe**.
Incluye su propio entorno; no necesita Python instalado ni los archivos de la versión anterior.

Una sola ventana, botones de ejecución en el lateral izquierdo, opciones en pestañas
y barra con porcentaje. Se retira el nombre anterior de todos los controles visibles.

El porcentaje de calibración cuenta hitos recibidos; no mide tiempo restante ni avance
físico continuo. Sin datos verificables se muestra una barra de espera. Un 100 % de
consultas de módulos solo indica que finalizaron las consultas.

Se conserva la corrección del error «ordinal 380». USB requiere un controlador
compatible de Windows; el programa no instala ni cambia controladores.

[Ver la interfaz](interfaz-1.1.0.png) · [Cambios](CAMBIOS-1.1.0.md)

Antes de calibrar lee **LEEME.txt** dentro del ZIP. Las calibraciones siguen siendo
experimentales y pueden provocar errores 40011/40021. Mavic 4 Pro y Classic conservan
consultas de información, sin estas calibraciones habilitadas. No se añade movimiento
manual por ejes ni se escriben coeficientes IMU fijos.

Validación: 38 pruebas de aplicación/interfaz y 8 de empaquetado; arranque del EXE bajo
Wine 10 sin comunicación con un dron. Pendiente de validar en Windows nativo y con
hardware DJI real. Incluye fuentes, pruebas, licencias y resultados de verificación.

La integridad de la descarga se comprueba con **SHA256SUMS.txt**.
