$ErrorActionPreference = "Stop"
$source = Join-Path $PSScriptRoot "server_deploy"
$dest = "R:\server\deploy"
if (-not (Test-Path "R:\")) { throw "Race Engineer server share R: is not available." }
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item -Path (Join-Path $source "*") -Destination $dest -Recurse -Force
Write-Host "Server deployment files copied to $dest" -ForegroundColor Green
Write-Host "Now SSH to race-server and run:" -ForegroundColor Cyan
Write-Host "  cd /srv/race-engineer/server/deploy && bash install_s14.sh"
