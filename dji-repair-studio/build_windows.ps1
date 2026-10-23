$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
function Check-Exit { if ($LASTEXITCODE -ne 0) { throw "Fallo del comando anterior: $LASTEXITCODE" } }
py -3.13 -m venv .venv
Check-Exit
$Python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $Python -m pip install -r requirements.txt 'pyinstaller==6.16.0'
Check-Exit
& $Python -m unittest discover -s tests -v
Check-Exit
$LibUsb = & $Python -c "import pathlib, libusb_package; print(pathlib.Path(libusb_package.__file__).parent / 'libusb-1.0.dll')"
Check-Exit
& $Python -m PyInstaller --noconfirm --clean --onefile --windowed --name 'DJI REPAIR Studio 1.2.2' --add-binary "$LibUsb;." launch.py
Check-Exit
Write-Host "EXE independiente: $PSScriptRoot\dist\DJI REPAIR Studio 1.2.2.exe"
