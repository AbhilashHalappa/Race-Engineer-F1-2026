$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

# Stable V2 deliberately builds a small dependency bootstrapper instead of a
# PyInstaller bundle. Python, Python packages, Piper voice, Whisper weights,
# Ollama and the LLM model are installed/downloaded only when missing and only
# after the user approves the download in RaceEngineer.exe.
$go = Get-Command go.exe -ErrorAction SilentlyContinue
if (-not $go) { $go = Get-Command go -ErrorAction SilentlyContinue }
if (-not $go) { throw 'Go is required only to BUILD RaceEngineer.exe. The prebuilt release does not require Go.' }

$stage = '.\dist\RaceEngineer'
Remove-Item -Recurse -Force $stage -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $stage | Out-Null

$env:GOOS = 'windows'
$env:GOARCH = 'amd64'
$env:CGO_ENABLED = '0'
# Proper Windows branding: when go-winres is installed on the build machine,
# generate the icon + manifest + version resource before compiling. The release
# still builds without it, but official Stable V2 builds should include it.
$winres = Get-Command go-winres.exe -ErrorAction SilentlyContinue
if (-not $winres) { $winres = Get-Command go-winres -ErrorAction SilentlyContinue }
$resource = '.\launcher\rsrc_windows_amd64.syso'
Remove-Item $resource -ErrorAction SilentlyContinue
if ($winres) {
    & $winres.Source simply --arch amd64 --manifest gui --icon '.\assets\brand\race_engineer.ico' --out '.\launcher\rsrc' --file-version '2.0.0.3' --product-version '2.0.0.3' --file-description 'Race Engineer Stable V2' --product-name 'Race Engineer' --copyright 'Race Engineer Project' --original-filename 'RaceEngineer.exe'
    if ($LASTEXITCODE -ne 0) { throw 'go-winres failed to generate Windows branding resources' }
} else {
    Write-Warning 'go-winres not found: launcher will build without embedded Explorer icon/version metadata. Install with: go install github.com/tc-hib/go-winres@v0.3.3'
}
& $go.Source build -trimpath -ldflags '-H=windowsgui -s -w' -o "$stage\RaceEngineer.exe" '.\launcher\bootstrapper_windows.go'
Remove-Item $resource -ErrorAction SilentlyContinue
if ($LASTEXITCODE -ne 0 -or !(Test-Path "$stage\RaceEngineer.exe")) { throw 'Go did not create RaceEngineer.exe' }

Copy-Item '.\src' "$stage\src" -Recurse
Copy-Item '.\assets' "$stage\assets" -Recurse
Get-ChildItem -Path "$stage\src" -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path "$stage\src" -Recurse -File -Include '*.pyc','*.pyo' | Remove-Item -Force -ErrorAction SilentlyContinue
Copy-Item '.\requirements.txt', '.\runtime_dependencies.json', '.\RACE_ENGINEER_STABLE_V2.md' $stage -ErrorAction SilentlyContinue

# Mutable/user folders stay outside the launcher binary and are preserved by
# the installer. They may be empty in a fresh portable release.
foreach ($d in @('settings','user_data','analysis','logs','references','recordings','maps','voices')) {
    New-Item -ItemType Directory -Force "$stage\$d" | Out-Null
}

Write-Host "Built external-dependency launcher: $stage\RaceEngineer.exe"
Write-Host 'No Python runtime, Piper voice, Whisper model, Ollama runtime or LLM model is embedded in the EXE.'
