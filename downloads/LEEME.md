# DJI REPAIR Studio 1.8.0

[Descargar ZIP con EXE · Windows 10/11 x64](https://raw.githubusercontent.com/Joba91/Joba91/main/downloads/DJI_Repair_Studio_1.8.0.zip)

Extrae el ZIP en una carpeta nueva y abre **DJI REPAIR Studio 1.8.0.exe**.
Se añade el perfil **DJI Flip**, firmware **01.00.1500 declarado** por el usuario.
**JointCoarse y LinearHall del Flip todavía no están implementadas.**

## Lectura de conexión del DJI Flip

1. Selecciona **DJI Flip** en Modelo seleccionado.
2. Se abre su espacio de gimbal en **Calibración**; revisa **01.00.1500**.
3. Conecta solo el Flip y pulsa **Recopilar perfil USB** en el lateral.
4. Guarda y comparte **DJIFlip-PerfilUSB-….zip**, incluso si hay un error.

El ZIP guarda `gimbal.usb_profile` con PnP y descriptores accesibles. El 100 %
significa inventario guardado. No se mueve o calibra el gimbal, entra en fábrica,
consulta sensores o cambia firmware/driver. La enumeración puede leer descriptores
estándar GET_DESCRIPTOR. Otro PID queda registrado en PnP aunque la fase de
descriptores actual solo admita 2CA3:0020.

Falta contrastar para Flip la entrada/salida del modo de taller, las peticiones
de ambas rutinas y sus respuestas, progreso y fin. El perfil USB es preparación;
no basta por sí solo para resolver esas calibraciones. Las rutinas de otros
modelos quedan bloqueadas para Flip antes de abrir transporte de servicio.
[Estado detallado del DJI Flip](../dji-repair-studio/DJI-FLIP.md).

## Validación y modelos anteriores

344 pruebas de aplicación/interfaz y 11 de empaquetado. EXE x64 probado bajo Wine
con datos sintéticos y corpus históricos; captura de interfaz sin dron conectado.
No hay prueba física en un DJI Flip. CfgMgr32 de Wine devuelve tamaño USB cero y
se conserva como error. Fuentes, licencias y verificaciones incluidas;
huellas en SHA256SUMS.txt. No se ejecutan programas DJI en cloud ni se redistribuyen
sus DLL/configuraciones/capturas originales.

Se mantienen las funciones anteriores con sus límites. La calibración óptica de
Mini 4 Pro y Air 3 sigue pendiente. El receptor de imágenes propio x86 se conserva.

[Mini 4 Pro](../dji-repair-studio/VISION-MINI4PRO.md) ·
[Air 3](../dji-repair-studio/VISION-AIR3.md) ·
[Código](../dji-repair-studio)
