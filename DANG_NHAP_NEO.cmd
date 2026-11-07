@echo off
title DANG NHAP NEO - NHAP SO LUU KY
setlocal
cd /d "%~dp0"
if not exist "%USERPROFILE%\.venv\Scripts\python.exe" (
  echo Khong tim thay moi truong Python. Xem README.md.
  pause
  exit /b 2
)
call "%USERPROFILE%\.venv\Scripts\activate.bat"
python -X utf8 -m src.neo_api.login_gui
set "neo_login_exit=%ERRORLEVEL%"
pause
exit /b %neo_login_exit%
