# DJI REPAIR Studio 1.2.0

Añade diagnóstico sin conexión de visión Mini 4 Pro: inventario de carpetas y ZIP,
MD5/SHA-256, análisis de registros y tramas, estados de evidencia y exportación JSON.
La pestaña integrada muestra sus acciones en el lateral. Para este modelo las
acciones USB y de escritura genéricas también aparecen bloqueadas.

El sondeo opcional de un servidor HTTPS comprueba TCP/TLS con un límite que incluye
DNS. No realiza autenticación, llamadas HTTP de descarga ni instalación. No hay
servidores predeterminados ni uso de credenciales encontradas en el paquete.

La implementación no depende de ejecutar DJI Test.exe ni cargar DLL propietarias.
Lectura USB Mini 4 Pro, descarga real, correspondencia por sensor y escritura
siguen pendientes de evidencia. El paquete y el informe locales de Windows aún
no están disponibles en el entorno de desarrollo.

Verificación: 71 pruebas de aplicación y 8 de empaquetado; inicio del ejecutable
bajo Wine, inventario sintético y auxiliar de sondeo contra localhost. No hay
validación con paquete real Mini 4 Pro, servidores DJI, Windows nativo ni dron.
[Detalles y requisitos pendientes](../dji-repair-studio/VISION-MINI4PRO.md).
