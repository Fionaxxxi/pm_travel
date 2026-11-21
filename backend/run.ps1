$ErrorActionPreference = 'Stop'
$env:PYTHONNOUSERSITE = '1'
$env:TRAVELMATE_EXTRA_CORS_ORIGINS = 'http://127.0.0.1:5191'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot
$python = 'D:\miniconda3\envs\pm\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Conda environment pm was not found.' }
$envFile = Join-Path $PSScriptRoot '.env'
& $python -m uvicorn backend.app.main:app --env-file $envFile --host 127.0.0.1 --port 8031
