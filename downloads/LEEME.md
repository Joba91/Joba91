# DJI REPAIR Studio 1.7.0

[Descargar Windows 10/11 x64](https://raw.githubusercontent.com/Joba91/Joba91/main/downloads/DJI_Repair_Studio_1.7.0.zip)

Extrae el ZIP en una carpeta nueva y abre **DJI REPAIR Studio 1.7.0.exe**.
**La calibración de visión sigue pendiente para Mini 4 Pro y Air 3.** Esta
versión añade el destino Air 3 y el inventario necesario para contrastar su conexión.

## Air 3 · firmware declarado 01.00.1600

1. Conecta solo el **Air 3** al PC y selecciónalo en **Modelo seleccionado**.
2. En **Visión de sensores**, revisa **01.00.1600** en Firmware declarado.
3. Pulsa **Recopilar perfil USB** y guarda un ZIP nuevo.
4. Comparte **Air3-PerfilUSB-….zip**, incluso si Windows informa un error.

Se leen dispositivos y controladores presentes mediante Windows PowerShell/PnpDevice.
No carga el SDK DJI, consulta sensores, cambia controladores ni envía peticiones
Mini 4 Pro. Los endpoints y el protocolo del Air 3 todavía requieren contraste.
El porcentaje 100 mide inventario guardado; no significa calibración o sensores sanos.
Los resultados y firmware de la vista se separan al cambiar entre ambos modelos.

## Mini 4 Pro · prueba de imágenes revisada

El ZIP recibido de 1.6.0 acredita el arranque del receptor x86, pero contiene
**0 imágenes y 48 esperas `0xd0010003` en 10,209 segundos**. Se confirmó el
significado de espera vencida en la biblioteca. Eso no diagnostica una avería.
No hace falta repetir esa misma prueba para revisar sus datos ya recibidos.

La referencia nativa solicita previamente arrancar un servicio de percepción;
el receptor no lo solicita. Su activación y sus efectos siguen sin validar.
La rutina original puede devolver 0 tras intentos fallidos, por lo que tampoco
basta un retorno de éxito para probar que entregue imágenes o calibre.
El perfil examinado configura una pareja inferior, sin cobertura delantera derecha
acreditada. Se mantienen las pruebas previas con sus límites; no se ejecuta un
script del dron ni se escriben parámetros como sustituto de un procedimiento resuelto.

## Verificación

299 pruebas de aplicación/interfaz y 11 de empaquetado aprobadas. El EXE x64 se
probó bajo Wine con datos sintéticos y registros históricos. El script PnP pasa
el analizador PowerShell 7.4.6 y una ejecución con cmdlets sintéticos en Linux;
aún necesita prueba con PnP real del Air 3 en Windows. Las capturas de interfaz
están marcadas como sintéticas. No se ejecutan bibliotecas DJI en cloud ni se
redistribuyen sus binarios, configuraciones o registros originales.

[Estado actual](../dji-repair-studio/ESTADO-VISION-2026-11-06.md) ·
[Air 3](../dji-repair-studio/VISION-AIR3.md) ·
[Mini 4 Pro](../dji-repair-studio/VISION-MINI4PRO.md) ·
[Código](../dji-repair-studio). Fuentes y licencias incluidas. Consulta `SHA256SUMS.txt`.
