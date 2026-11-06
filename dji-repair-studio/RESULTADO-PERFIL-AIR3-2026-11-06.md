# Perfil Air 3 recibido y corrección 1.7.1

El archivo recibido tiene 609 bytes y CRC ZIP válido; contiene únicamente un
informe JSON de 922 bytes de Studio 1.7.0. Declara Air 3 y firmware 01.00.1600,
sin lectura independiente del firmware. La consulta PowerShell agotó 25 segundos,
con lista vacía. No se obtuvieron interfaces ni se ejecutó calibración.
Esto describe un fallo del recopilador, no una avería de sensores o del dron.
El informe original permanece privado.

1.7.1 consulta CfgMgr32: lista USB presente con flags 0x101, filtro VID 2CA3 antes
de propiedades, nombre de bus, nombre local, servicio, HardwareID, padre y estado
PnP en bruto. No abre endpoints ni envía órdenes al dron. Los errores CONFIGRET
no se convierten en un diagnóstico de salud. Tipos y tamaños se validan.

Un proceso propio x64 oculto escribe instantáneas atómicas por etapa. La ventana
permanece disponible; detener o agotar el plazo termina su árbol de procesos y
guarda los nodos parciales y la etapa. Un inventario incompleto nunca confirma
una coincidencia única de modelo ni llega al 100 % de inventario completado.
El 100 % de un inventario completo tampoco significa calibración.

Prueba en el PC: extraer el ZIP 1.7.1 nuevo, abrir su EXE, seleccionar Air 3,
firmware declarado 01.00.1600, Visión de sensores → Recopilar perfil USB,
guardar y compartir el ZIP, incluso si muestra error. No necesita administrador,
PowerShell o un cambio de controlador.

Las pruebas incluyen fixtures C API y el proceso real del EXE bajo Wine; no
son validación de PnP en Windows físico ni de compatibilidad del Air 3.
La calibración óptica sigue pendiente para Mini 4 Pro y Air 3.

Referencias de ABI consultadas, sin redistribuir cabeceras:
- https://github.com/microsoft/win32metadata/blob/main/generation/WinSDK/RecompiledIdlHeaders/um/cfgmgr32.h
- https://github.com/microsoft/win32metadata/blob/main/generation/WinSDK/RecompiledIdlHeaders/shared/devpkey.h

Límite de la prueba Wine 1.7.1: el proceso del EXE arranca y guarda su resultado,
pero CfgMgr32 de Wine devuelve tamaño de lista USB 0. Se conserva como error;
no se presenta como inventario Windows válido. El ABI WCHAR de 2 bytes y las
propiedades se verifican además con un fixture sintético dentro del EXE.
