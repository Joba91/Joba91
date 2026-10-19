# DJI REPAIR Studio 1.0.1

[Descargar el programa para Windows x64](https://github.com/Joba91/Joba91/raw/refs/heads/main/downloads/DJI_Repair_Studio_1.0.1.zip)

Extrae el ZIP en una carpeta nueva y abre **DJI REPAIR Studio 1.0.1.exe**.
Incluye su propio entorno de ejecucion; no necesita la instalacion anterior,
Python instalado ni la carpeta `_internal` anterior. USB requiere un controlador
compatible de Windows; el programa no instala ni cambia controladores.

Conserva DJI REPAIR y el panel YanDron reconstruido. Incluye analizador/generador
de paquetes, lectura de progreso y calibraciones experimentales JointCoarse y
LinearHall para los modelos declarados por el programa de origen. No implementa
movimiento manual por ejes ni copia los coeficientes IMU fijos de YanDron.

**Antes de calibrar, lee LEEME.txt dentro del ZIP.** El programa de origen advierte
posibles errores 40011/40021. No se promete corregir esos errores.

La version 1.0.1 corrige el error de inicio **ordinal 380**: incorpora el manifiesto
que selecciona Microsoft.Windows.Common-Controls v6. No cambia DLL del sistema
ni solicita privilegios de administrador. El codigo y protocolos de la aplicacion
se conservan sin cambios.

Pasaron 7 comprobaciones nuevas del empaquetado (recursos PE, checksum, dependencias
y preservacion del payload). La prueba anterior bajo Wine no detecto la ausencia
del manifiesto. Falta comprobar esta correccion en Windows nativo; tampoco se ha
validado con hardware DJI real.
El ZIP incluye fuentes, licencias e instrucciones detalladas.

La integridad de la descarga se puede verificar con `SHA256SUMS.txt`.
