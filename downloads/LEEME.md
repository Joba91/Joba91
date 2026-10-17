# DJI REPAIR Studio

[Descargar el programa para Windows x64](https://github.com/Joba91/Joba91/raw/refs/heads/main/downloads/DJI_Repair_Studio.zip)

Extrae el ZIP en una carpeta nueva y abre **DJI REPAIR Studio.exe**.
Incluye su propio entorno de ejecucion; no necesita la instalacion anterior,
Python instalado ni la carpeta `_internal` anterior. USB requiere un controlador
compatible de Windows; el programa no instala ni cambia controladores.

Conserva DJI REPAIR y el panel YanDron reconstruido. Incluye analizador/generador
de paquetes, lectura de progreso y calibraciones experimentales JointCoarse y
LinearHall para los modelos declarados por el programa de origen. No implementa
movimiento manual por ejes ni copia los coeficientes IMU fijos de YanDron.

**Antes de calibrar, lee LEEME.txt dentro del ZIP.** El programa de origen advierte
posibles errores 40011/40021. No se promete corregir esos errores.

Se ejecutaron 26 pruebas de protocolo/transporte simulado y una prueba de arranque
bajo Wine. No se ha validado en Windows nativo ni con hardware DJI real.
El ZIP incluye fuentes, licencias e instrucciones detalladas.

La integridad de la descarga se puede verificar con `SHA256SUMS.txt`.
