# DJI REPAIR Studio 1.4.0

Añade Diagnóstico visión (HMS), una prueba experimental que solicita publicación
de estados con una sola petición 0a→1d, 21/05 payload 01, reconstruida del lector
nativo recibido. Escucha ocho segundos, hasta 1 MiB/10000 lecturas, sin reintentos,
fábrica, autotest, calibración o cambios de firmware/controlador. No envía reset
global de suscriptores; la publicación después de cerrar USB es desconocida.

El lector 21/06 valida framing, versión y estructura de referencia; separa emisores,
ciclos y paquetes. Duplicados no inflan registros, huecos impiden cierre y una
contradicción revoca la completitud. Presenta códigos, índices y niveles brutos,
sin asignarlos a visión o usar descripciones de otros modelos. Silencio o ciclos
vacíos no indican salud. La compatibilidad HMS Mini 4 Pro requiere prueba física.

Analizar captura visión también muestra HMS de archivos binarios con procedencia
local. La consulta actual conserva RX y auditoría TX/ACK en un ZIP automático.
No sobrescribe ni sube archivos. Mantiene las lecturas SN y recepción pasiva.

246 pruebas de aplicación/interfaz y 9 de empaquetado aprobadas. El EXE bajo Wine
prueba una suscripción y dos ciclos sintéticos, tabla y ZIP, sin abrir USB físico.
Las dos capturas SN del usuario muestran cuatro series estables; no contienen HMS
ni confirman salud o calibración. Los adjuntos/identificadores reales permanecen privados.
