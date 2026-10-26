# DJI REPAIR Studio 1.2.4

Aplicación de una sola ventana con diagnóstico de archivos y recepción USB
pasiva Mini 4 Pro. La captura recibe desde IN 85 de la interfaz 4 sin emitir
peticiones de servicio. Perfil acotado a descriptores contrastados y firmware
01.00.1100 declarado desde DJI Fly. No implementa consulta activa de sensores,
calibración óptica activa, descarga de datos ni escritura. [Uso, arquitectura y bloqueos](VISION-MINI4PRO.md).

## Desarrollo

Python 3.13 con Tcl/Tk. En Windows, instala `requirements.txt` en un entorno virtual.
Desde esta carpeta ejecuta `python launch.py` y `python -m unittest discover -s tests -v`.
Para compilar el ejecutable independiente, ejecuta `build_windows.ps1` en Windows.
No requiere las DLL propietarias DJI ni DJI Test.exe. Incluye la biblioteca de
usuario libusb-win32 1.4.0.2 amd64 en native/, con procedencia, LGPL/GPL y fuente
correspondiente. Windows prioriza libusb0 para el servicio libusb0_device existente;
no instala ni reemplaza controladores. El informe registra errores por fase.

En el entorno de desarrollo preparado en la nube, las dependencias verificadas están
en `/workspace/DJI-REPAIR-Studio/vendor`. Las pruebas sin interfaz pueden ejecutarse
con `PYTHONPATH=.:/workspace/DJI-REPAIR-Studio/vendor python3.13 -m unittest discover -s tests -v`.
Para ejecutar también las pruebas gráficas hace falta una pantalla X local/virtual;
estas pruebas se omiten expresamente si no hay pantalla. La compilación Windows
se verificó bajo Wine; no equivale a validación en Windows nativo o con un dron real.

Código base GPLv3: ver LICENSE-GPL-3.txt y avisos en archivos originales. El ZIP
de distribución incluye además licencias de las bibliotecas de ejecución.

El lector histórico se contrastó con 89 registros reales recibidos: 734 tramas,
150 ACK distintos. El decodificador propio de sensores recupera 184 SN desde
payloads, con 184 coincidencias históricas; cuatro bloques inválidos siguen desconocidos. [Investigación y límites](INVESTIGACION-REGISTROS-MINI4PRO.md).
