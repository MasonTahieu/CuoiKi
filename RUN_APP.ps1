param(
    [string]$VenvPath = (Join-Path $HOME '.venv'),
    [ValidateRange(1024, 65535)][int]$Port = 8501,
    [switch]$Headless,
    [switch]$Streamlit
)
# Mac dinh: giao dien web moi (Python thu vien chuan + HTML/CSS/JS, chay offline).
# -Streamlit: mo giao dien Streamlit cu (du phong).
# Che do va nguon du lieu doc tu .env (APP_MODE=demo/replay/live, DATA_PROVIDER=ssi).

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$venvScripts = Join-Path $VenvPath 'Scripts'
$python = Join-Path $venvScripts 'python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Chua co moi truong ~/.venv. Xem README.md de chuan bi.'
}
& (Join-Path $venvScripts 'Activate.ps1')
if ($Streamlit) {
    $headlessValue = $Headless.IsPresent.ToString().ToLowerInvariant()
    & $python -X utf8 -m streamlit run app.py --server.address 127.0.0.1 --server.port $Port --server.headless $headlessValue
    exit $LASTEXITCODE
}
if (-not $Headless) {
    Start-Job -ScriptBlock { param($url) Start-Sleep -Seconds 2; Start-Process $url } -ArgumentList "http://127.0.0.1:$Port" | Out-Null
}
& $python -X utf8 -m src.web.server --port $Port
exit $LASTEXITCODE
