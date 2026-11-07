param(
    [ValidateSet('kiemtra', 'smoke', 'lichsu', 'phien', 'danhgia')][string]$Lenh = 'kiemtra',
    [string]$VenvPath = (Join-Path $HOME '.venv'),
    [ValidateRange(5, 600)][int]$Giay = 60,
    [ValidateRange(1, 60)][int]$SoPhien = 10,
    [ValidateSet('', 'none', 'prompt', 'smart')][string]$Otp = ''
)
# Lenh:
#   kiemtra  - doc cau hinh, khong goi mang
#   smoke    - dang nhap, doc thanh phan nhom + securitiesSummary, stream $Giay giay, ghi evidence/v3_smoke
#   lichsu   - lay $SoPhien phien securitiesSummary cua VN30 vao runtime/ssi_daily.sqlite (REST, khong OTP)
#   phien    - thu ca ngay giao dich: 08:58-11:31 va 12:59-14:46, doi chieu REST luc 15:05
#   danhgia  - danh gia nhieu phien tu kho cuc bo (khong goi mang)
# Khong luu OTP, API Key hay token vao tep. Chay trong cua so PowerShell de nhap OTP khi duoc hoi.

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $VenvPath 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'Chua co moi truong Python. Chay CAI_THU_VIEN.ps1 truoc.'
}
& (Join-Path $VenvPath 'Scripts\Activate.ps1')

$map = @{ kiemtra = 'readiness'; smoke = 'smoke-v3'; lichsu = 'history-v3'; phien = 'session-v3'; danhgia = 'evaluate-v3' }
$cliArgs = @('-X', 'utf8', '-m', 'src.cli', $map[$Lenh])
if ($Lenh -eq 'smoke') { $cliArgs += @('--seconds', $Giay) }
if ($Lenh -eq 'lichsu') { $cliArgs += @('--sessions', $SoPhien) }
if ($Otp -ne '') { $cliArgs += @('--otp-mode', $Otp) }
if ($Lenh -eq 'phien') {
    Write-Host 'Giu cua so nay mo den khoang 15:05. Dung may tinh khong ngu (sleep) trong gio giao dich.'
}
& $python @cliArgs
exit $LASTEXITCODE
