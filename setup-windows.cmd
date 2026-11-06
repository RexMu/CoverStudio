@echo off
set "SAX_SETUP=%~dp0scripts\setup-windows.ps1"
if not exist "%SAX_SETUP%" set "SAX_SETUP=%~dp0setup-windows.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -File "%SAX_SETUP%" %*
if errorlevel 1 (
  echo Setup failed. Please read the error above.
  pause
  exit /b 1
)
pause
