# DJI REPAIR Studio 1.7.2

[Descargar ZIP con EXE · Windows 10/11 x64](https://raw.githubusercontent.com/Joba91/Joba91/main/downloads/DJI_Repair_Studio_1.7.2.zip)

Extrae en una carpeta nueva y abre **DJI REPAIR Studio 1.7.2.exe**.
**La calibración óptica sigue pendiente para Mini 4 Pro y Air 3.**

El perfil Air 3 recibido de 1.7.1 ya contiene ocho nodos PnP, un padre 2CA3:0020
y producto con prefijo `e3t`. No incluye endpoints ni evalúa salud de sensores.
1.7.2 añade al mismo botón la lectura de descriptores estándar para obtenerlos.
El texto e3t se conserva sin convertirlo en autorización para un perfil del motor.

## Prueba con Air 3

1. Conecta solo el Air 3 y selecciónalo en **Modelo seleccionado**.
2. En **Visión de sensores**, revisa firmware declarado **01.00.1600**.
3. Pulsa **Recopilar perfil USB** y guarda un ZIP nuevo.
4. Comparte el ZIP incluso si muestra un error.

No requiere PowerShell, exportar manualmente UsbTreeView o cambiar controladores.
Cierra otras herramientas DJI si mantienen ocupado el dispositivo. El inventario
conserva PnP y añade `descriptor_inventory`. Los endpoints observados aparecen en
la misma tabla y el ZIP, asociados por nodo actual al inventario de esa sesión.

La biblioteca libusb0 verificada puede emitir lecturas USB estándar GET_DESCRIPTOR.
No se reclama interfaz, consulta configuración activa, transfiere bulk, cambia
configuración o envían comandos de sensores. No se carga SDK DJI para esta acción.
El número exacto de operaciones de la biblioteca es desconocido; las órdenes de
servicio son cero. Los descriptores no validan transporte de visión o calibración.
El 100 % significa inventario guardado, con errores y límites en el informe.

## Verificación

333 pruebas de aplicación/interfaz y 11 de empaquetado aprobadas. EXE x64 probado
bajo Wine con datos sintéticos y corpus históricos; captura de pantalla marcada
como sintética. El lector PnP 1.7.1 obtuvo datos en el Windows del usuario; la ruta
nueva de descriptores todavía requiere prueba allí. CfgMgr32 de Wine devuelve
lista USB de tamaño cero y se registra como error, sin simular un inventario real.
No hay hardware DJI conectado en cloud ni se ejecutan DLL DJI durante desarrollo.
Fuentes, licencias y verificaciones incluidas. Huellas en `SHA256SUMS.txt`.

[Resultado del perfil](../dji-repair-studio/RESULTADO-PERFIL-AIR3-2026-11-06.md) ·
[Air 3](../dji-repair-studio/VISION-AIR3.md) ·
[Mini 4 Pro](../dji-repair-studio/VISION-MINI4PRO.md) ·
[Código](../dji-repair-studio)
