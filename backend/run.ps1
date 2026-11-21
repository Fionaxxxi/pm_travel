$ErrorActionPreference = 'Stop'
$env:PYTHONNOUSERSITE = '1'
if (-not $env:GUIDE_MODE) { $env:GUIDE_MODE = 'preset' }
$env:TRAVELMATE_EXTRA_CORS_ORIGINS = 'http://127.0.0.1:5191'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot
$python = 'D:\miniconda3\envs\pm\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Conda environment pm was not found.' }
& $python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8031
