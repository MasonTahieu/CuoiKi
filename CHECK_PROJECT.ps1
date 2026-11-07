param([string]$VenvPath = (Join-Path $HOME '.venv'))

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$venvScripts = Join-Path $VenvPath 'Scripts'
if (-not (Test-Path -LiteralPath (Join-Path $venvScripts 'python.exe'))) {
    throw 'Chua co moi truong ~/.venv. Xem README.md de chuan bi.'
}
& (Join-Path $venvScripts 'Activate.ps1')
& (Join-Path $venvScripts 'python.exe') -X utf8 -m src.cli check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& (Join-Path $venvScripts 'python.exe') -X utf8 -m pytest -q
exit $LASTEXITCODE

