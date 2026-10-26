# DJI REPAIR Studio 1.2.5

Corrige la selección de recepción pasiva que se detenía al encontrar seis entradas
libusb0 antes de distinguir la interfaz MI04. Identifica HardwareID del controlador
local mediante una consulta de metadatos de Windows; requiere coincidencia única
MI04 y mantiene las comprobaciones de producto/configuración/endpoints. No prueba
lecturas de otras interfaces ni instala o cambia drivers.

Crea automáticamente un ZIP local con captura e informe JSON, incluso con cero
bytes o fallo de apertura. No sobrescribe ni sube archivos. Guardar informe sigue
como alternativa manual. No habilita consultas activas, fábrica, calibración o escritura.

149 pruebas de aplicación y 9 de empaquetado aprobadas. El EXE bajo Wine carga las
bibliotecas y APIs y prueba selección de seis alias y ZIP con datos sintéticos.
Metadatos del controlador real y recepción física pendientes de validación.
