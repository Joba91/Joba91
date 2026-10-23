# DJI REPAIR Studio 1.2.0

[Descargar Windows 10/11 x64](https://raw.githubusercontent.com/Joba91/Joba91/main/downloads/DJI_Repair_Studio_1.2.0.zip)

Extrae todo el ZIP en una carpeta nueva y abre **DJI REPAIR Studio 1.2.0.exe**.
No necesita la instalación anterior ni Python instalado.

Nueva pestaña **Visión Mini 4 Pro**, integrada en la única ventana del programa:

- Inventario de carpetas/ZIP y verificación de manifiestos MD5 de texto GNU/BSD.
- Huellas SHA-256 y estados confirmado, desconocido y error.
- Análisis sin conexión de capturas binarias y registros HEX.
- Sondeo TCP/TLS con tiempo limitado, únicamente al solicitarlo.
- Informe JSON y interfaces independientes para archivos, protocolo, identificación y proveedores.

**MD5 coincidente no demuestra autenticidad ni compatibilidad.** Para Mini 4 Pro,
lectura USB, descarga, selección para instalación y escritura siguen deshabilitadas.
No se ejecuta DJI Test.exe ni se cargan o distribuyen las DLL propietarias del paquete.

[Uso y bloqueos pendientes](../dji-repair-studio/VISION-MINI4PRO.md) ·
[Ver interfaz](interfaz-1.2.0.png) · [Código fuente](../dji-repair-studio)

Pasaron 71 pruebas de aplicación/interfaz y 8 de empaquetado. El EXE arrancó bajo
Wine con datos sintéticos; el proceso de sondeo se comprobó solo contra localhost.
No se han recibido el paquete Mini 4 Pro real ni el informe externo; tampoco se
han probado servidores DJI, Windows nativo o hardware físico. No se declara
completo el módulo de calibración de visión.

Se conserva la corrección del error ordinal 380. Las operaciones anteriores para
otros modelos mantienen sus restricciones. Antes de calibrar un gimbal compatible,
lee LEEME.txt dentro del ZIP: esas calibraciones son experimentales y pueden
provocar errores 40011/40021. No se añade calibración a Mini 4 Pro, Classic o Mavic 4 Pro.

El ZIP incluye el ejecutable, fuentes, pruebas, documentación y licencias.
La integridad de la descarga se comprueba con **SHA256SUMS.txt**.
