# DJI REPAIR Studio 1.7.1

[Descargar Windows 10/11 x64](https://raw.githubusercontent.com/Joba91/Joba91/main/downloads/DJI_Repair_Studio_1.7.1.zip)

Extrae el ZIP en una carpeta nueva y abre **DJI REPAIR Studio 1.7.1.exe**.
La calibración óptica sigue pendiente para Mini 4 Pro y Air 3.

El perfil Air 3 recibido de 1.7.0 agotó la consulta de Windows a los 25 segundos,
sin devolver dispositivos. Eso no diagnostica una avería del dron. 1.7.1 sustituye
PowerShell/WMI por lectura directa de metadatos CfgMgr32 y conserva nodos parciales
y la última etapa si se detiene o agota el tiempo.

## Probar el nuevo lector con Air 3

1. Conecta solo el **Air 3** al PC y selecciónalo en **Modelo seleccionado**.
2. En **Visión de sensores**, revisa **01.00.1600** en Firmware declarado.
3. Pulsa **Recopilar perfil USB** y guarda un ZIP nuevo.
4. Comparte **Air3-PerfilUSB-….zip**, incluso si informa un error.

No necesita PowerShell ni cambios de controlador. Esta acción no carga SDK DJI,
consulta sensores ni envía órdenes de servicio. Un inventario incompleto no
confirma modelo ni llega al 100 %. El 100 % de un inventario completo significa
archivo guardado; no acredita calibración. Firmware y resultados de la vista
permanecen separados al cambiar de modelo.

## Validación y límites

315 pruebas de aplicación/interfaz y 11 de empaquetado aprobadas. El EXE x64 se
probó bajo Wine con datos sintéticos y registros históricos. Su lector oculto
arranca y guarda errores: CfgMgr32 de Wine devuelve longitud USB 0 y no se acepta
como inventario válido. El ABI WCHAR de 2 bytes también se prueba con un fixture
dentro del EXE. Falta probar la enumeración real en el Windows del usuario.
No se ejecutan bibliotecas DJI en cloud ni se redistribuyen sus binarios o
registros originales. Las capturas de interfaz se identifican como sintéticas.

El ensayo Mini 4 Pro de 1.6.0 recibido contiene 0 imágenes y 48 esperas de datos;
la activación del productor y el procedimiento de calibración siguen pendientes.
No se reutiliza su transporte para Air 3.

[Resultado Air 3](../dji-repair-studio/RESULTADO-PERFIL-AIR3-2026-11-06.md) ·
[Estado](../dji-repair-studio/ESTADO-VISION-2026-11-06.md) ·
[Air 3](../dji-repair-studio/VISION-AIR3.md) ·
[Mini 4 Pro](../dji-repair-studio/VISION-MINI4PRO.md) ·
[Código](../dji-repair-studio). Fuentes y licencias incluidas; huellas en `SHA256SUMS.txt`.
