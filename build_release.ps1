$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot
& .\build_exe.ps1
$portable='.\dist\RaceEngineer_Stable_V2_RC3_Portable.zip'
Remove-Item $portable -ErrorAction SilentlyContinue
Compress-Archive -Path '.\dist\RaceEngineer\*' -DestinationPath $portable -CompressionLevel Optimal
Write-Host "Portable package: $portable"
Write-Host 'The portable ZIP contains the small RaceEngineer.exe bootstrapper + application source, not bundled AI/voice models.'
$iscc=(Get-Command ISCC.exe -ErrorAction SilentlyContinue)
if ($iscc) {
  & $iscc.Source '.\installer\RaceEngineer.iss'
  Write-Host 'Installer created in dist\installer'
} else {
  Write-Warning 'Inno Setup compiler (ISCC.exe) not found. EXE + portable ZIP were built; install Inno Setup 6 and rerun for the installer.'
}
