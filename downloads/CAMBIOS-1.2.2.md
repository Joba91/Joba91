# DJI REPAIR Studio 1.2.2

El analizador histórico ahora convierte el registro binario de percepción 24/26 en
un SN de sensor sin depender de las DLL oficiales. La estructura se contrastó
estáticamente y con 184 etiquetas históricas coincidentes; cuatro bloques inválidos
siguen desconocidos. La nueva tabla conserva línea, selector y contraste con etiqueta.

Las operaciones USB Mini 4 Pro siguen bloqueadas: el análisis de las DLL explica
las rutas de endpoints, pero no aporta los descriptores del equipo actual ni valida
la consulta en su modo normal y firmware. No se activan descarga, fábrica o escritura.

Validación: 98 pruebas de aplicación y 8 de empaquetado; el EXE bajo Wine procesa
los 89 registros con 734 tramas válidas, 150 ACK distintos y 184 SN coincidentes.
No hay pruebas en Windows nativo o con hardware físico. Consulta el informe de
investigación y validacion-1.2.2.json. Los binarios oficiales no se redistribuyen.
