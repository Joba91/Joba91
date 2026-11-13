# DJI REPAIR Studio 1.8.1

[Descargar ZIP con EXE · Windows 10/11 x64](https://raw.githubusercontent.com/Joba91/Joba91/main/downloads/DJI_Repair_Studio_1.8.1.zip)

Extrae en una carpeta nueva y abre **DJI REPAIR Studio 1.8.1.exe**.
**JointCoarse y LinearHall del DJI Flip siguen pendientes de implementación.**
Esta versión añade una consulta experimental de versión al controlador y al gimbal.

## Prueba del Flip · firmware declarado 01.00.1500

El ZIP 1.8.0 recibido contiene ocho nodos PnP y seis alias con descriptores completos.
MI04 ofrece OUT04/IN85 bulk512. No contiene respuestas de módulos o calibración.
No hace falta repetir ese inventario para obtener los mismos datos.

1. Selecciona **DJI Flip** y **USB bulk**.
2. Pulsa **Consultar FC y gimbal (Flip)** en el lateral.
3. Selecciona tu ZIP previo **DJIFlip-PerfilUSB-….zip** como referencia.
4. Guarda **DJIFlip-Modulos-….zip** y compártelo, incluso si aparece un error.

Se comprueban producto y nodo actual contra el perfil elegido y se revisan los
endpoints antes de reclamar MI04. Si cambiaste de puerto y no coinciden, recopila
un perfil nuevo. Cierra otras herramientas que mantengan ocupado el USB.

Solo se permiten dos solicitudes 00/01 sin payload, una al controlador y otra al
gimbal, sin reenvíos. La ruta rechaza órdenes de fábrica/calibración y paquetes
arbitrarios. Se guarda RX crudo, auditoría y versiones observadas en el mismo ZIP.
Las versiones de módulo no sustituyen el firmware de aeronave de DJI Fly, no
autentican el modelo ni prueban salud. El 100 % exige dos respuestas con formato
reconocido y el ZIP guardado. No es calibración.

La conexión del informe anterior se ha inventariado; esta nueva consulta todavía
necesita probarse en el Flip. Resolver la calibración requiere además contrastar
el protocolo de taller, sus respuestas y estados. [Detalle](../dji-repair-studio/DJI-FLIP.md).

## Verificación

362 pruebas de aplicación/interfaz y 11 de empaquetado aprobadas. EXE x64 bajo Wine
con fixtures sintéticos: 2 respuestas, 78 bytes RX, 26 bytes OUT, cero órdenes de
fábrica/calibración y MI04 liberada. No hay hardware Flip en cloud ni se ejecutan
programas DJI durante desarrollo. Fuentes/licencias, evidencia y huellas incluidas.
Se conservan las funciones previas; calibración óptica Mini 4 Pro/Air 3 pendiente.

[DJI Flip](../dji-repair-studio/DJI-FLIP.md) ·
[Mini 4 Pro](../dji-repair-studio/VISION-MINI4PRO.md) ·
[Air 3](../dji-repair-studio/VISION-AIR3.md) ·
[Código](../dji-repair-studio)
