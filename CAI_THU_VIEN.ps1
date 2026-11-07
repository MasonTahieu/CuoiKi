param([string]$VenvPath = (Join-Path $HOME '.venv'))

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPython = Join-Path $VenvPath 'Scripts\python.exe'
$pythonCheck = "import platform, sys; sys.exit(0 if sys.platform == 'win32' and sys.version_info[:2] == (3, 13) and platform.machine().upper() == 'AMD64' else 1)"
if (-not (Test-Path -LiteralPath $taskPython -PathType Leaf)) {
    $runtimeFound = $false
    $basePython = Get-Command python -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($basePython -and $basePython.Source -notlike '*\WindowsApps\*') {
        & $basePython.Source -X utf8 -c $pythonCheck 2>$null
        if ($LASTEXITCODE -eq 0) {
            $runtimeFound = $true
            & $basePython.Source -m venv $VenvPath
        }
    }
    if (-not $runtimeFound -and (Get-Command py -ErrorAction SilentlyContinue)) {
        & py -3.13 -X utf8 -c $pythonCheck 2>$null
        if ($LASTEXITCODE -eq 0) {
            $runtimeFound = $true
            & py -3.13 -m venv $VenvPath
        }
    }
    if (-not $runtimeFound) {
        throw 'Can cai CPython 3.13 x64 cho Windows truoc.'
    }
    if ($LASTEXITCODE -ne 0) { throw 'Khong tao duoc moi truong Python 3.13.' }
}
& (Join-Path $VenvPath 'Scripts\Activate.ps1')
& $taskPython -X utf8 -c $pythonCheck
if ($LASTEXITCODE -ne 0) { throw 'Bo thu vien di kem can CPython 3.13 tren Windows x64. Hay chon -VenvPath phu hop.' }

$localWheels = Join-Path $PSScriptRoot 'offline_wheels'
$pipArgs = @('--disable-pip-version-check', '--progress-bar', 'off', '-r', 'requirements-win-py313.lock.txt')
if (Test-Path -LiteralPath $localWheels -PathType Container) {
    $pipArgs += @('--no-index', '--find-links', $localWheels)
}
& $taskPython -X utf8 -m pip install @pipArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $taskPython -X utf8 -m pip check
exit $LASTEXITCODE
