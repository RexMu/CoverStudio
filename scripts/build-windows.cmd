@echo off
cd /d "%~dp0\.."
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build-windows.ps1 %*
if errorlevel 1 (
  echo Build failed. Please read the error above and README.md.
  pause
  exit /b 1
)
echo Build complete. Check the dist folder.
pause
