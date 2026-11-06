# Air 3 · proyecto de calibración de visión

Firmware de aeronave **01.00.1600 declarado por el usuario** el 6 de noviembre
de 2026. La selección del Air 3 y recopilación de metadatos están implementadas;
**la calibración de visión y el transporte de sus sensores aún no**.

## Obtener su perfil real

1. Conecta solo el **Air 3** al PC y selecciónalo en el programa 1.7.0.
2. En **Visión de sensores**, revisa el firmware declarado.
3. Pulsa **Recopilar perfil USB** y guarda `Air3-PerfilUSB-....zip` nuevo.
4. Comparte el ZIP incluso si informa un error.

Se consulta `Get-PnpDevice -PresentOnly` y propiedades fijas de dispositivos DJI:
nombre informado por el bus, padre, HardwareID, servicio del controlador, estado
y código de problema. Solo se admiten nodos USB del proveedor `2CA3`, con límites
de registros, tamaños y tiempo. No se carga el SDK DJI ni se envían solicitudes
de sensores, cambios de configuración, modos o controladores.

Los datos no demuestran endpoints ni autenticidad del modelo. Un único nombre
de padre USB coincidente se registra como coincidencia de descriptor, no como
identidad autenticada o compatibilidad de calibración. Air 3S y otros modelos no
se aceptan como Air 3 por coincidencia parcial. Múltiples padres quedan ambiguos.

El ZIP puede mostrar estado general desconocido aunque el inventario se haya
leído: lo desconocido es la compatibilidad de sensores/calibración. El 100 %
cuenta inventario guardado, no calibración. No hay subida automática de datos.

## Separación del Mini 4 Pro

La selección conserva firmware por modelo y limpia resultados del otro destino.
Air 3 no puede ejecutar las peticiones Mini 4 Pro de SN, HMS, recepción MI04 ni
imágenes nativas. Tampoco hereda calibraciones de gimbal, fábrica o parámetros
de otros modelos. Esas rutas se bloquean en interfaz y en despacho, antes de
abrir transportes o pedir archivos para una operación no implementada.

El motor recibido contiene códigos internos, pero no se asigna uno al Air 3 sin
contrastar el equipo y la implementación. El firmware declarado no acredita el
protocolo USB. El siguiente trabajo requiere validar su transporte y obtener
un procedimiento de generación, instalación y comprobación de parámetros de
visión compatible. Este inventario no satisface por sí solo esos requisitos.

## Pruebas

Se verifican respuestas sintéticas y casos de modelo distinto, Air 3S, padres
ambiguos, nodos repetidos, datos excesivos, cancelación, errores de Windows y
archivos existentes. La interfaz mantiene el Air 3 seleccionado y separa datos.
El script pasa el parser oficial PowerShell 7.4.6 y una ejecución con cmdlets
sintéticos en Linux. No se ha probado todavía en PnP real del Air 3/Windows.
