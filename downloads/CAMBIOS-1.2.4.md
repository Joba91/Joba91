# DJI REPAIR Studio 1.2.4

La captura pasiva anterior fallaba antes de la primera lectura con operación no
soportada; MI04 usa el servicio libusb0_device. Esta revisión incluye la biblioteca
de usuario libusb-win32 1.4.0.2 amd64 verificada y prioriza libusb0 en Windows, sin
instalar ni sustituir el controlador existente.

Mantiene la validación de producto, configuración, interfaz y endpoints. La
velocidad ausente en libusb0 queda desconocida. Registra API y fase de cada fallo
de inicialización y limita el fallback para no eludir un perfil incorrecto,
dispositivos ambiguos, acceso denegado o dispositivo ocupado. No añade consultas
activas de sensores, fábrica, calibración o escritura.

126 pruebas de aplicación y 9 de empaquetado aprobadas. Ambas bibliotecas cargan
en el EXE bajo Wine; captura sintética y corpus histórico verificados. Acceso real
y Windows nativo pendientes. Incluye LGPL/GPL y fuente completa correspondiente
de libusb-win32, sin instaladores ni controladores binarios.
