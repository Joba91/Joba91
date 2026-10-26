[CmdletBinding()]
param(
    [string[]]$SearchRoot = @(),
    [string]$OutputRoot = '',
    [switch]$EngineBundle
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

# This script reads files only. It never loads a DJI library, queries USB,
# contacts a server, installs a driver, or requests administrator rights.
$wanted = @('DJIVisionCalibration.dll', 'DJIVisionCalibration2.dll',
            'DJIVisionCalibration3.dll', 'DJI_guidance.dll')
$consumerEngineHash = '7105076d6c72e50b823d0bec9c7696c2aa7fdd50578361e68dec3a838bf41044'
if ($EngineBundle) { $wanted = @() }
$maxDirectories = 10000
$maxFiles = 100000
$maxFileBytes = 128MB
$partBytes = 30MB

function Test-PortableExecutable([string]$Path) {
    $stream = [IO.File]::Open($Path, [IO.FileMode]::Open,
        [IO.FileAccess]::Read, [IO.FileShare]::Read)
    try {
        if ($stream.Length -lt 64) { return $false }
        $reader = New-Object IO.BinaryReader($stream)
        if ($reader.ReadUInt16() -ne 0x5A4D) { return $false }
        $stream.Position = 0x3c
        $offset = $reader.ReadUInt32()
        if ($offset -lt 64 -or $offset -gt ($stream.Length - 24)) { return $false }
        $stream.Position = $offset
        return ($reader.ReadUInt32() -eq 0x00004550)
    } finally { $stream.Dispose() }
}

if ($SearchRoot.Count -eq 0) {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        throw 'La busqueda automatica requiere Windows. Para pruebas usa -SearchRoot.'
    }
    $SearchRoot = @('C:\DJI')
    foreach ($base in @($env:ProgramFiles, ${env:ProgramFiles(x86)})) {
        if ($base -and (Test-Path -LiteralPath $base -PathType Container)) {
            $SearchRoot += @(Get-ChildItem -LiteralPath $base -Directory -Force `
                -ErrorAction SilentlyContinue | Where-Object { $_.Name -like '*DJI*' } |
                ForEach-Object { $_.FullName })
        }
    }
    if ($env:LOCALAPPDATA) { $SearchRoot += (Join-Path $env:LOCALAPPDATA 'DJI') }
}
if (-not $OutputRoot) {
    $OutputRoot = [Environment]::GetFolderPath('Desktop')
    if (-not $OutputRoot) { $OutputRoot = (Get-Location).Path }
}
if (-not (Test-Path -LiteralPath $OutputRoot -PathType Container)) {
    throw 'La carpeta de salida no existe.'
}

$prefix = 'DJI-Vision-Motor-'
if ($EngineBundle) { $prefix = 'DJI-Vision-Dependencias-' }
$label = $prefix + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' +
    [Guid]::NewGuid().ToString('N').Substring(0, 8)
$output = Join-Path $OutputRoot $label
$stage = Join-Path $output 'contenido'
$null = New-Item -ItemType Directory -Path $stage
$seen = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
$hashes = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
$queue = New-Object 'System.Collections.Generic.Queue[string]'
$bundleFolders = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
$matchedEngines = @()
$roots = @()
$records = @()
$excluded = @()
$limitsReached = $false
$directories = 0
$files = 0
$unreadable = 0

foreach ($root in $SearchRoot) {
    if (-not (Test-Path -LiteralPath $root -PathType Container)) { continue }
    $item = Get-Item -LiteralPath $root -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { continue }
    $roots += $item.FullName
    $queue.Enqueue($item.FullName)
}

Write-Host 'Buscando el motor de vision en instalaciones locales de DJI...'
while ($queue.Count -gt 0) {
    if ($directories -ge $maxDirectories -or $files -ge $maxFiles) {
        $limitsReached = $true
        break
    }
    $folder = $queue.Dequeue()
    if (-not $seen.Add($folder)) { continue }
    $directories++
    Write-Progress -Activity 'Buscar motor de vision' -Status $folder
    try { $children = @(Get-ChildItem -LiteralPath $folder -Force -ErrorAction Stop) }
    catch { $unreadable++; continue }
    if ($EngineBundle) {
        # Select the exact Consumer engine already supplied and analyzed.
        # Do not mix it with the unrelated Enterprise/legacy installations.
        foreach ($candidate in $children) {
            if ($candidate.PSIsContainer -or $candidate.Name -ine 'DJIVisionCalibration3.dll' -or
                ($candidate.Attributes -band [IO.FileAttributes]::ReparsePoint)) { continue }
            try {
                $candidateHash = (Get-FileHash -LiteralPath $candidate.FullName -Algorithm SHA256).Hash
                if ($candidateHash -ine $consumerEngineHash) { continue }
                $null = $bundleFolders.Add($folder)
                $matchedEngines += @{ directory = $folder; sha256 = $consumerEngineHash }
                foreach ($subfolder in @('platforms', 'imageformats')) {
                    $null = $bundleFolders.Add((Join-Path $folder $subfolder))
                }
            } catch { $unreadable++ }
        }
    }
    foreach ($child in $children) {
        if ($child.FullName -eq $output) { continue }
        if ($child.Attributes -band [IO.FileAttributes]::ReparsePoint) { continue }
        if ($child.PSIsContainer) { $queue.Enqueue($child.FullName); continue }
        $files++
        if ($files -gt $maxFiles) { $limitsReached = $true; break }
        $isBundleFile = $EngineBundle -and $bundleFolders.Contains($folder) -and
            ($child.Extension -ieq '.dll' -or $child.Name -ieq 'VisionStarter3.exe')
        if (($wanted -notcontains $child.Name) -and -not $isBundleFile) { continue }
        $destination = $null
        try {
            if ($child.Length -gt $maxFileBytes) {
                $excluded += @{ name = $child.Name; reason = 'Supera 128 MiB'; path = $child.FullName }
                continue
            }
            if (-not (Test-PortableExecutable $child.FullName)) {
                $excluded += @{ name = $child.Name; reason = 'Formato PE no reconocido'; path = $child.FullName }
                continue
            }
            $sourceHash = (Get-FileHash -LiteralPath $child.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
            $identity = $child.Name + ':' + $sourceHash
            if ($hashes.Contains($identity)) { continue }
            $entryName = '{0:D3}/{1}' -f ($records.Count + 1), $child.Name
            $destination = Join-Path $stage $entryName
            $null = New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($destination))
            [IO.File]::Copy($child.FullName, $destination, $false)
            $copyHash = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($copyHash -ne $sourceHash) { throw 'El archivo cambio durante la copia.' }
            $version = [Diagnostics.FileVersionInfo]::GetVersionInfo($destination)
            $records += @{
                name = $child.Name; archive_entry = $entryName; source_path = $child.FullName
                bytes = (Get-Item -LiteralPath $destination).Length; sha256 = $copyHash
                file_version = $version.FileVersion; product_version = $version.ProductVersion
                file_version_is_aircraft_firmware = $false
            }
            $null = $hashes.Add($identity)
        } catch {
            # A failed/incomplete copy must not enter the archive.
            if ($destination -and (Test-Path -LiteralPath $destination -PathType Leaf)) {
                Remove-Item -LiteralPath $destination -Force
            }
            $excluded += @{ name = $child.Name; reason = $_.Exception.Message; path = $child.FullName }
        } finally { $destination = $null }
    }
}
Write-Progress -Activity 'Buscar motor de vision' -Completed

$manifest = @{
    schema = 'dji-repair-vision-engine-inventory-v1'; collector_version = '1.1.0'
    created_local = (Get-Date).ToString('o'); search_roots = @($roots)
    files = @($records); excluded = @($excluded); directories_scanned = $directories
    files_scanned = $files; unreadable_directories = $unreadable; limits_reached = $limitsReached
    engine_candidates_found = $records.Count
    include_engine_dependencies = [bool]$EngineBundle; matched_engines = @($matchedEngines)
    calibration_implemented = $false; mini4_compatibility_confirmed = $false
    device_operations = 0; network_operations = 0; dji_libraries_executed = 0
    note = 'Inventario para analisis estatico. Nombres y versiones no prueban compatibilidad ni calibracion.'
}
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $stage 'inventario.json') -Encoding UTF8
$zip = Join-Path $output ($label + '.zip')
Add-Type -AssemblyName System.IO.Compression.FileSystem
[IO.Compression.ZipFile]::CreateFromDirectory($stage, $zip, [IO.Compression.CompressionLevel]::Optimal, $false)
$zipHash = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant()
$artifacts = @()
if ((Get-Item -LiteralPath $zip).Length -le $partBytes) {
    $artifacts += @{ file = [IO.Path]::GetFileName($zip); sha256 = $zipHash }
} else {
    $input = [IO.File]::OpenRead($zip)
    try {
        $buffer = New-Object byte[] (1MB)
        $number = 1
        while ($input.Position -lt $input.Length) {
            $part = $zip + ('.part{0:D3}' -f $number)
            $stream = [IO.File]::Open($part, [IO.FileMode]::CreateNew)
            try {
                $remaining = [long]$partBytes
                while ($remaining -gt 0) {
                    $read = $input.Read($buffer, 0, [int][Math]::Min($remaining, $buffer.Length))
                    if ($read -eq 0) { break }
                    $stream.Write($buffer, 0, $read)
                    $remaining -= $read
                }
            } finally { $stream.Dispose() }
            $artifacts += @{ file = [IO.Path]::GetFileName($part)
                sha256 = (Get-FileHash -LiteralPath $part -Algorithm SHA256).Hash.ToLowerInvariant() }
            $number++
        }
    } finally { $input.Dispose() }
    # Keep the full ZIP locally too; upload only its numbered parts.
}
@{ archive_sha256 = $zipHash; files_to_share = @($artifacts) } | ConvertTo-Json -Depth 5 |
    Set-Content -LiteralPath (Join-Path $output 'archivos-para-compartir.json') -Encoding UTF8
Write-Host ''
Write-Host ('Componentes candidatos encontrados: ' + $records.Count)
if ($records.Count -eq 0) {
    Write-Host 'No se encontro el motor en las carpetas revisadas; el ZIP contiene el inventario.'
    if ($EngineBundle) { Write-Host 'No se encontro la misma version Consumer analizada. No se mezclaron otras versiones.' }
}
Write-Host ('Resultado: ' + $output)
Write-Host 'Comparte el ZIP. Si aparecen partes .part001, .part002..., comparte todas esas partes.'
Write-Host 'Este recopilador no calibra el dron.'
