@echo off
setlocal
if not exist "%~dp0Recopilar-motor-vision.ps1" (
  echo Extrae todos los archivos del ZIP antes de ejecutar este programa.
  pause
  exit /b 1
)
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Recopilar-motor-vision.ps1"
if errorlevel 1 echo La recopilacion no termino. Copia el error que aparece arriba.
pause
