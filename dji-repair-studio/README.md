# DJI REPAIR Studio 1.7.2

Windows 10/11 x64, una ventana, botones laterales y progreso. Visión para
Mini 4 Pro y Air 3 en desarrollo. **La calibración óptica aún no está implementada.**

[Descarga](../downloads/LEEME.md) · [Air 3](VISION-AIR3.md) ·
[Mini 4 Pro](VISION-MINI4PRO.md) · [Estado](ESTADO-VISION-2026-11-06.md)

## Perfil Air 3 recibido

El informe 1.7.1 recibido del Windows del usuario contiene ocho nodos PnP,
un padre físico, VID/PID 2CA3:0020 y prefijo de producto `e3t`. Las interfaces
observadas son 00, 02 y 03–07. No hay códigos de problema PnP distintos de cero;
esto no evalúa salud de sensores. El nombre `e3t` se conserva sin convertirlo
en un alias de compatibilidad del Air 3, declarado por el usuario.

## Cambio 1.7.2

**Recopilar perfil USB** ahora añade descriptores USB estándar al ZIP existente
y muestra los endpoints observados en la misma interfaz. Enumera con la biblioteca
libusb0 verificada y lee su caché de configuraciones, interfaces, alternativas y
endpoints. La enumeración puede solicitar GET_DESCRIPTOR. Se compara el nodo
actual de cada alias con el inventario PnP de esa sesión; no se seleccionan alias
por posición ni se cambia el nombre `e3t` para habilitar otro perfil.

No reclama interfaces, lee bulk, envía órdenes de sensores, cambia configuración
o instala controladores. No se consulta configuración activa. Los descriptores
no prueban transporte de visión ni compatibilidad de calibración. El contador de
operaciones USB queda desconocido si la biblioteca solicita descriptores; no se
publica un cero de operaciones para esa fase. Las órdenes de servicio siguen en cero.

## Uso y validación

Extrae el ZIP nuevo y abre DJI REPAIR Studio 1.7.2.exe. Selecciona Air 3,
firmware declarado 01.00.1600, Visión de sensores → Recopilar perfil USB.
Guarda y comparte el nuevo ZIP, incluso si muestra error. No necesitas exportar
manualmente el reporte de UsbTreeView para esta prueba.

333 pruebas de aplicación/interfaz y 11 de empaquetado. EXE x64 probado bajo Wine
con fixtures y corpus históricos. La ruta nueva de descriptores requiere prueba
en el Windows del usuario; no hay un dron conectado en cloud. CfgMgr32 de Wine
devuelve tamaño USB cero y se conserva como error; no se simula un dispositivo.
El usuario sí aportó el inventario PnP completo de la versión 1.7.1 en Windows.

Desarrollo: Python 3.13/Tk, `python launch.py`,
`python -m unittest discover -s tests -v`; compilación `build_windows.ps1`.
Se conservan las funciones Mini 4 Pro anteriores con sus límites. El receptor
x86 propio no se modifica; su fuente y registro de construcción se incluyen.
No se ejecutan programas DJI en cloud ni se redistribuyen sus DLL, configuraciones
o capturas originales. Fuentes y licencias incluidas.
