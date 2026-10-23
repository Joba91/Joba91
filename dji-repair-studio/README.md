# DJI REPAIR Studio 1.2.0

Aplicación de una sola ventana con módulo de diagnóstico de visión Mini 4 Pro
sin conexión. No implementa calibración óptica activa, lectura USB Mini 4 Pro,
descarga de datos ni escritura. [Uso, arquitectura y bloqueos](VISION-MINI4PRO.md).

## Desarrollo

Python 3.13 con Tcl/Tk. En Windows, instala `requirements.txt` en un entorno virtual.
Desde esta carpeta ejecuta `python launch.py` y `python -m unittest discover -s tests -v`.
Para compilar el ejecutable independiente, ejecuta `build_windows.ps1` en Windows.
No requiere las DLL propietarias DJI ni DJI Test.exe.

En el entorno de desarrollo preparado en la nube, las dependencias verificadas están
en `/workspace/DJI-REPAIR-Studio/vendor`. Las pruebas sin interfaz pueden ejecutarse
con `PYTHONPATH=.:/workspace/DJI-REPAIR-Studio/vendor python3.13 -m unittest discover -s tests -v`.
Para ejecutar también las pruebas gráficas hace falta una pantalla X local/virtual;
estas pruebas se omiten expresamente si no hay pantalla. La compilación Windows
se verificó bajo Wine; no equivale a validación en Windows nativo o con un dron real.

Código base GPLv3: ver LICENSE-GPL-3.txt y avisos en archivos originales. El ZIP
de distribución incluye además licencias de las bibliotecas de ejecución.
