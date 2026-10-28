# Código del empaquetado

El código de la aplicación y del adaptador nativo está en `fuentes/`. El receptor
precompilado `fuentes/vision_receiver32.exe` es propio. `receiver32-build.json`
registra los activos oficiales, hashes y miembros de su archivo congelado.
No contiene bibliotecas o configuración DJI.

Para recompilar la aplicación principal en Windows usa `fuentes/build_windows.ps1`.
Ese script utiliza el receptor precompilado incluido.

Para construir de nuevo el receptor desde código en Windows, prepara CPython
**x86 3.13** con PyInstaller 6.16.0 y ejecuta desde esta carpeta:

```powershell
& $PythonX86 -m PyInstaller --noconfirm --clean --onefile --console --name vision_receiver32 --manifest windows.manifest --paths ..\fuentes receiver32\entry.py
Copy-Item dist\vision_receiver32.exe ..\fuentes\vision_receiver32.exe
```

`$PythonX86` debe ser la ruta de tu Python de 32 bits. No se requiere SDK DJI para
construirlo. Su autoprueba `vision_receiver32.exe --self-test resultado.json`
valida ctypes y metadatos sintéticos sin cargar DJI ni abrir USB.

Los scripts `build_receiver32.py` y `build_standalone.py` documentan la construcción
cruzada utilizada en cloud. Esperan una raíz con `src/`, `runtime/`, `vendor/` y
`build-tools/receiver32/` como indican sus constantes. Para reproducir esa variante,
coloca `fuentes/` como `src/` y prepara los activos oficiales de sus registros.
La variante cloud no pudo probar el arranque x86 porque el kernel deshabilita IA32;
ese límite está registrado en `validacion-1.6.0.json`.
