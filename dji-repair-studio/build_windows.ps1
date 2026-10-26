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
$LegacyUsb = Join-Path $PSScriptRoot 'native\libusb0.dll'
if ((Get-FileHash $LegacyUsb -Algorithm SHA256).Hash -ne '0cd18719d5701e9cc642fc93a83f13830931d6f29f664fedbdf212bcb7c349bd') { throw 'La biblioteca libusb0.dll no coincide con el binario oficial verificado.' }
& $Python -m PyInstaller --noconfirm --clean --onefile --windowed --name 'DJI REPAIR Studio 1.4.0' --add-binary "$LibUsb;." --add-binary "$LegacyUsb;." --add-data 'native\licenses;licenses\libusb-win32' launch.py
Check-Exit
Write-Host "EXE independiente: $PSScriptRoot\dist\DJI REPAIR Studio 1.4.0.exe"
