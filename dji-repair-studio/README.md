# DJI REPAIR Studio 1.6.0

Aplicación Windows x64 de una sola ventana, botones laterales y progreso medido.
La novedad es **Recibir imágenes (prueba)** para investigar la visión del Mini 4 Pro,
con firmware **01.00.1100 declarado por el usuario**. **Todavía no calibra**.

[Descarga y pasos](../downloads/LEEME.md) · [Uso y arquitectura](VISION-MINI4PRO.md) ·
[Resultado del motor y configuración](RESULTADO-DEPENDENCIAS-VISION-2026-10-28.md)

La prueba usa un receptor propio x86 oculto y el transporte Consumer ya instalado
en el PC del usuario. Comprueba SHA-256 de siete DLL y `dbus_pc.json`, valida el
perfil USB del Mini 4 Pro y copia los componentes a una sesión temporal. No se
redistribuyen los binarios ni el JSON DJI. No utiliza credenciales ni modifica
controladores. La inicialización nativa produce tráfico de control USB cuyos
efectos completos aún requieren validación física.

El JSON recibido asigna `wa140` a `dual_chip_a7`, MI05 V1 y MI03 DBus. Los temas
son `raw/down/left` y `raw/down/right`: referencia de visión **inferior**, sin
cobertura delantera derecha confirmada. Se admiten 640×480, 8 bits y 307200 bytes.
Los PGM verificados se muestran en la misma interfaz y se guardan junto al ZIP
con el informe. El 100 % exige dos imágenes verificadas y el ZIP guardado; no
representa calibración, salud, identidad desde imágenes ni sincronización.

La ejecución tiene límite y cancelación. Un job privado de Windows engloba el
bootloader y su hijo Python antes de reanudar el proceso; el cierre forzado afecta
al árbol del receptor para evitar dejar lectores USB activos.

Se conservan análisis de archivos, recepción pasiva MI04, cuatro consultas SN
24/26 y diagnóstico HMS experimental 21/05. HMS reconoce 21/06 y 21/08 sin inferir
fallos activos por la mera presencia de códigos. No hay calibración óptica,
descarga de coeficientes ni diagnóstico de salud validado para Mini 4 Pro.
Los originales y números de serie del usuario no se publican.

## Desarrollo y validación

Python 3.13 con Tcl/Tk; dependencias en `requirements.txt`. Ejecuta `python launch.py`.
Pruebas: `python -m unittest discover -s tests -v` con Windows o pantalla virtual.
Compilación Windows: `build_windows.ps1`; el receptor propio precompilado está
incluido. Código y registro de construcción del receptor en `recompilacion/` y
`receiver32-build.json`. No hace falta un SDK DJI para ejecutar los tests sintéticos.

280 pruebas de aplicación/interfaz y 11 de empaquetado aprobadas. El EXE x64 se
probó bajo Wine con datos sintéticos y corpus históricos, incluida vista previa,
manifest Common Controls v6 y supervisión de procesos. El kernel cloud tiene
`CONFIG_IA32_EMULATION` deshabilitado: no se pudo verificar el arranque x86.
La arquitectura, importaciones, manifiesto y archivo congelado del receptor se
verificaron estáticamente. Windows nativo, carga real del SDK e imágenes del dron
siguen pendientes; no se ejecutaron los binarios DJI recibidos en desarrollo.

Código base GPLv3: `LICENSE-GPL-3.txt` y avisos de los archivos originales.
Se conservan las licencias de dependencias. libusb-win32 de usuario es 1.4.0.2
amd64, con procedencia y fuente correspondiente; no se instalan drivers.
