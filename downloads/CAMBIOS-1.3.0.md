# DJI REPAIR Studio 1.3.0

Añade Consultar SN visión (prueba) para ensayar en modo normal las cuatro consultas
SN 24/26 reconstruidas independientemente. Cada petición coincide con los registros
históricos (188 coincidencias exactas). Se reutiliza el perfil USB que funcionó en
la captura pasiva 1.2.6 del usuario: MI04 y padre físico Mini 4 Pro.

Una petición por selector, sin reintentos, recepción previa y ventanas seriales de
3 segundos, límite global postapertura 15 segundos/1 MiB/10000 lecturas. No envía
comandos de fábrica, calibración, firmware o configuración. Un error de envío
registra entrega incierta y detiene la prueba, sin repetir o cambiar de modo.

La tabla muestra SN observados y distingue silencio, conflicto y ventanas incompletas.
No confirma identidad, correlación o salud; el filtro original no exige secuencia.
Guarda RX binario y un ZIP automático con el JSON y auditoría TX, incluso con error.
No sobrescribe ni sube archivos; los informes locales pueden contener series.

205 pruebas de aplicación/interfaz y 9 de empaquetado aprobadas. El EXE bajo Wine
prueba cuatro respuestas sintéticas, tabla, auditoría y ZIP; no abre USB físico.
La consulta activa real en modo normal/firmware 01.00.1100 sigue pendiente de probar.
No habilita diagnóstico de salud, descarga/instalación o calibración óptica.
