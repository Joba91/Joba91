# DJI REPAIR Studio 1.7.1

Proyecto Windows x64 de una sola ventana. Destinos de visión: **Mini 4 Pro**
y **Air 3**. **La calibración óptica todavía no está implementada para ninguno**.

[Descarga y pasos](../downloads/LEEME.md) · [Mini 4 Pro](VISION-MINI4PRO.md) ·
[Air 3](VISION-AIR3.md) · [Estado del desarrollo](ESTADO-VISION-2026-11-06.md)

## Cambios de esta versión

El perfil Air 3 de 1.7.0 recibido agotó la consulta PowerShell a los 25 segundos
sin obtener nodos. 1.7.1 sustituye ese recopilador por lectura directa CfgMgr32,
sin PowerShell/WMI. Un proceso propio oculto conserva instantáneas y la última
etapa si se detiene o agota el tiempo. No se cambia el tiempo máximo para ocultar
el fallo. [Resultado revisado](RESULTADO-PERFIL-AIR3-2026-11-06.md).

- Air 3 se selecciona por separado, con firmware **01.00.1600 declarado** por
  el usuario. La selección no habilita peticiones de sensores de otro modelo.
- **Recopilar perfil USB** obtiene propiedades de dispositivos DJI presentes
  en Windows y crea un ZIP local. No carga el SDK DJI, cambia controladores,
  entra en fábrica o consulta sensores. Endpoints y calibración quedan pendientes.
- Al cambiar entre Mini 4 Pro y Air 3 se separan firmware y resultados de la vista.
- Se interpreta específicamente `0xd0010003` como espera vencida de datos del SDK;
  no demuestra un sensor averiado. Otros estados desconocidos detienen la sesión.

El ZIP Mini 4 Pro recibido de la prueba 1.6.0 confirma arranque del receptor x86
y llamadas al SDK, pero contiene **0 imágenes, 48 esperas y 10,209 segundos**.
Los pares en línea informados por el SDK no prueban entrega de imágenes.
La referencia nativa solicita previamente arrancar un servicio de percepción;
el receptor no lo solicita. La activación y sus efectos aún necesitan validación.
No se ejecutan scripts del dron como sustituto de un procedimiento resuelto.

El perfil `wa140` de la DLL examinada configura una pareja **inferior**. No
acredita calibración del sensor delantero derecho. No se asigna un código
interno al Air 3 por analogía. Se conservan las funciones Mini 4 Pro experimentales
previas de captura pasiva, SN, HMS y recepción de imágenes, con sus límites.

## Desarrollo y validación

Python 3.13/Tk, dependencias de `requirements.txt`, entrada `python launch.py`.
Pruebas: `python -m unittest discover -s tests -v`, con Windows o pantalla virtual.
Compilación Windows: `build_windows.ps1`. Se incluye el receptor propio x86
precompilado; su código y procedencia están en `recompilacion/` y
`receiver32-build.json`. No se requiere SDK DJI para los tests sintéticos.

315 pruebas de aplicación/interfaz y 11 de empaquetado aprobadas. El EXE x64 se
valida bajo Wine con datos sintéticos y corpus históricos, incluida separación
de modelos y supervisión del árbol de procesos. El lector CfgMgr32 se valida con
fixtures del ABI y el proceso oculto se ejecuta bajo Wine; aún no se ha probado
con PnP real del Air 3 en Windows. El kernel cloud no tiene IA32,
así que el receptor x86 de esta versión se verifica estáticamente y con adaptadores.
El arranque x86 de la versión anterior sí está acreditado por el informe del usuario.

Los binarios/configuraciones DJI y los registros originales permanecen privados;
no se ejecutan en desarrollo ni se redistribuyen. Las capturas de interfaz se
identifican como sintéticas. No hay calibración o diagnóstico de salud simulado.
Código base GPLv3 y avisos originales conservados. Se incluyen licencias y fuente
correspondiente de libusb-win32 de usuario 1.4.0.2; no se instalan drivers.

Límite de la prueba Wine 1.7.1: el proceso del EXE arranca y guarda su resultado,
pero CfgMgr32 de Wine devuelve tamaño de lista USB 0. Se conserva como error;
no se presenta como inventario Windows válido. El ABI WCHAR de 2 bytes y las
propiedades se verifican además con un fixture sintético dentro del EXE.
