# Sax Cover Studio：Windows 打包環境一次設定
# 安裝 Git、Python 3.12（含 Tcl/Tk）、Inno Setup 6，下載 FFmpeg，建立 .venv 並安裝套件。
# 可以重複執行：已安裝的項目會略過。
param([string]$Target = (Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'CoverStudio'))
$ErrorActionPreference = 'Stop'

function Step($text) { Write-Host ''; Write-Host "== $text ==" -ForegroundColor Cyan }
function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                [Environment]::GetEnvironmentVariable('Path', 'User')
}
function Have($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function Winget-Install($id, $name) {
    Write-Host "安裝 $name …"
    & winget install --id $id -e --source winget --accept-package-agreements --accept-source-agreements --silent
    # 已安裝時 winget 會回傳非 0，這裡不中斷，之後再檢查是否可用。
    Refresh-Path
}

if (-not [Environment]::Is64BitOperatingSystem) { throw '需要 64 位元 Windows 10/11。' }
if (-not (Have 'winget')) {
    throw '找不到 winget。請先從 Microsoft Store 安裝或更新「應用程式安裝程式（App Installer）」，再重新執行。'
}

Step '1/5 Git'
if (-not (Have 'git')) { Winget-Install 'Git.Git' 'Git' }
if (-not (Have 'git')) { throw 'Git 安裝失敗，請手動安裝後重新執行。' }
git --version

Step '2/5 Python 3.12（python.org 版，含 Tcl/Tk）'
$py312 = $false
if (Have 'py') { & py -3.12 -c "import sys" 2>$null; $py312 = ($LASTEXITCODE -eq 0) }
if (-not $py312) {
    Winget-Install 'Python.Python.3.12' 'Python 3.12'
    & py -3.12 -c "import sys" 2>$null
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 安裝失敗，請從 python.org 安裝 64 位元 3.12 後重新執行。' }
}
& py -3.12 --version

Step '3/5 Inno Setup 6（建立安裝檔用）'
$isccCandidates = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
                    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe")
if (-not ($isccCandidates | Where-Object { Test-Path $_ })) { Winget-Install 'JRSoftware.InnoSetup' 'Inno Setup 6' }
$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($iscc) { Write-Host "ISCC：$iscc" } else { Write-Warning '找不到 Inno Setup 6；仍可建置可攜版，安裝檔需手動安裝 Inno Setup 後再建。' }

Step '4/5 取得程式碼'
$here = Split-Path $PSScriptRoot -Parent
if (Test-Path (Join-Path $here 'run.py')) {
    $repo = $here
    Write-Host "使用目前的專案資料夾：$repo"
} elseif (Test-Path (Join-Path $Target '.git')) {
    $repo = $Target
    Write-Host "更新 $repo"
    git -C $repo pull --ff-only
} else {
    $repo = $Target
    Write-Host "下載到 $repo（第一次可能會跳出 GitHub 登入視窗）"
    git clone https://github.com/RexMu/CoverStudio.git $repo
    if ($LASTEXITCODE -ne 0) { throw '下載程式碼失敗，請確認已登入 GitHub 並有 RexMu/CoverStudio 的權限。' }
}
Set-Location $repo

Step '5/5 FFmpeg 與 Python 套件'
if ((Test-Path 'tools\ffmpeg.exe') -and (Test-Path 'tools\ffprobe.exe')) {
    Write-Host 'tools 資料夾已有 FFmpeg，略過下載。'
} else {
    $rel = Invoke-RestMethod 'https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/tags/latest'
    $asset = $rel.assets |
        Where-Object { $_.name -match '^ffmpeg-n(\d+)\.(\d+).*-win64-gpl-\d+\.\d+\.zip$' -and [int]$Matches[1] -ge 7 } |
        Sort-Object { [version]($_.name -replace '^ffmpeg-n(\d+\.\d+).*$','$1') } -Descending |
        Select-Object -First 1
    if (-not $asset) { throw '找不到合適的 FFmpeg 下載檔。' }
    $tmp = Join-Path $env:TEMP 'sax-ffmpeg'
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory $tmp | Out-Null
    $zip = Join-Path $tmp $asset.name
    Write-Host "下載 $($asset.name) …"
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest $asset.browser_download_url -OutFile $zip
    $sha = (Get-FileHash $zip -Algorithm SHA256).Hash
    Expand-Archive $zip -DestinationPath $tmp
    $root = Get-ChildItem $tmp -Directory | Select-Object -First 1
    Copy-Item "$($root.FullName)\bin\ffmpeg.exe", "$($root.FullName)\bin\ffprobe.exe" tools\
    New-Item -ItemType Directory -Force tools\licenses | Out-Null
    Copy-Item "$($root.FullName)\LICENSE.txt" tools\licenses\FFmpeg-LICENSE.txt
    $ver = (& .\tools\ffmpeg.exe -version) | Select-Object -First 1
    @('供應者：BtbN/FFmpeg-Builds（GPL static build，含 libx264）', "版本：$ver",
      "下載位置：$($asset.browser_download_url)", "SHA256（zip）：$sha",
      '原始碼：https://github.com/BtbN/FFmpeg-Builds 與 https://ffmpeg.org/download.html',
      "下載日期：$(Get-Date -Format 'yyyy-MM-dd')") | Set-Content tools\licenses\BUILD.txt -Encoding utf8
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
}
if (-not (Test-Path '.venv\Scripts\python.exe')) { & py -3.12 -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Python 套件安裝失敗。' }
& .\.venv\Scripts\python.exe -c "import tkinter"
if ($LASTEXITCODE -ne 0) { Write-Warning '缺少 Tcl/Tk，EXE 將沒有雙擊立即出現的開機畫面。' }

Write-Host ''
Write-Host '設定完成！' -ForegroundColor Green
Write-Host "專案資料夾：$repo"
Write-Host '之後打包：雙擊 build-windows.cmd（可攜版），或 build-installer.cmd（安裝檔）。'
Write-Host '更新程式碼：在專案資料夾執行 git pull，或重新執行這個設定檔。'
