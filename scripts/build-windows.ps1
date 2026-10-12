param([switch]$Installer)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not [Environment]::Is64BitOperatingSystem) { throw '需要 64 位元 Windows 11。' }
foreach ($name in @('ffmpeg.exe', 'ffprobe.exe')) {
    if (-not (Test-Path "tools\$name")) {
        throw "請先將 $name 放進 tools 資料夾。詳見 README.md。"
    }
}
& .\tools\ffmpeg.exe -version | Select-Object -First 1
if ($LASTEXITCODE -ne 0) { throw 'FFmpeg 無法執行。' }
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    & py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw '請先安裝 Python 3.12（64 位元）。' }
}
$SaxPython = Join-Path $PWD '.venv\Scripts\python.exe'
& $SaxPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw '套件安裝失敗。' }
& $SaxPython -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw '功能測試失敗，停止打包。' }
$SaxFfmpeg = Join-Path $PWD 'tools\ffmpeg.exe'
$SaxFfprobe = Join-Path $PWD 'tools\ffprobe.exe'
$SaxAssets = Join-Path $PWD 'assets'
$SaxIcon = Join-Path $SaxAssets 'app-icon.ico'
& $SaxPython -m PyInstaller --noconfirm --clean --windowed --name SaxCoverStudio `
    --add-binary "$SaxFfmpeg;tools" --add-binary "$SaxFfprobe;tools" `
    --icon $SaxIcon --add-data "$SaxAssets;assets" `
    --add-data 'THIRD_PARTY.md;.' `
    --hidden-import PySide6.QtMultimedia --hidden-import PySide6.QtMultimediaWidgets run.py
if ($LASTEXITCODE -ne 0) { throw '桌面程式打包失敗。' }
Copy-Item README.md dist\SaxCoverStudio\README.md
Copy-Item THIRD_PARTY.md dist\SaxCoverStudio\THIRD_PARTY.md
if (Test-Path 'tools\licenses') {
    Copy-Item tools\licenses dist\SaxCoverStudio\licenses -Recurse -Force
}
Write-Host '可攜版：dist\SaxCoverStudio\SaxCoverStudio.exe'
if ($Installer) {
    $SaxIscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($SaxIscc) {
        & $SaxIscc.Source installer\SaxCoverStudio.iss
    } else {
        $SaxIsccPath = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
        if (-not (Test-Path $SaxIsccPath)) { throw '請先安裝 Inno Setup 6，或省略 -Installer 建置可攜版。' }
        & $SaxIsccPath installer\SaxCoverStudio.iss
    }
    if ($LASTEXITCODE -ne 0) { throw '安裝檔建置失敗。' }
    Write-Host '安裝檔：dist\installer\SaxCoverStudio-Setup-0.1.2.exe'
}
