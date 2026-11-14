#!/usr/bin/env bash
# Build "Sax Cover Studio.app" and a .dmg for Apple Silicon Macs.
#   bash scripts/build-mac.sh
# Needs: macOS 12+ on an M-series Mac, Python 3.12 (python.org installer),
# and internet for the first run (Python packages + FFmpeg download).
set -euo pipefail
cd "$(dirname "$0")/.."
fail() { echo "✗ $*" >&2; exit 1; }

[[ "$(uname -s)" == "Darwin" ]] || fail "這個腳本要在 Mac 上執行"
[[ "$(uname -m)" == "arm64" ]] || fail "這個腳本產生 M 系列（Apple Silicon）版本，請在 M 系列 Mac 上執行"

VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' saxstudio/__init__.py)"
APP="Sax Cover Studio"
echo "=== ${APP} Beta V${VERSION} · macOS Apple Silicon ==="

PY=""
for candidate in python3.12 /Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 /opt/homebrew/bin/python3.12; do
    if command -v "${candidate}" >/dev/null 2>&1; then PY="$(command -v "${candidate}")"; break; fi
done
[[ -n "${PY}" ]] || fail "找不到 Python 3.12。請從 https://www.python.org/downloads/macos/ 安裝 3.12 版"

if [[ ! -x .venv-mac/bin/python ]]; then
    echo "• 建立 Python 環境 .venv-mac"
    "${PY}" -m venv .venv-mac
fi
VPY=".venv-mac/bin/python"
"${VPY}" -m pip install --upgrade pip >/dev/null
"${VPY}" -m pip install -r requirements.txt || fail "套件安裝失敗"

bash scripts/fetch-ffmpeg-mac.sh || fail "FFmpeg 準備失敗，停止打包"
for tool in ffmpeg ffprobe; do
    "tools/${tool}" -hide_banner -version >/dev/null 2>&1 || fail "tools/${tool} 無法執行，請用 FORCE=1 bash scripts/fetch-ffmpeg-mac.sh 重新下載"
done

echo "• 執行功能測試"
"${VPY}" -m unittest discover -s tests -v || fail "功能測試失敗，停止打包"

echo "• 產生 App 圖示"
rm -rf build/AppIcon.iconset && mkdir -p build/AppIcon.iconset
for size in 16 32 128 256 512; do
    sips -z ${size} ${size} assets/app-icon.png --out "build/AppIcon.iconset/icon_${size}x${size}.png" >/dev/null
    double=$((size * 2))
    sips -z ${double} ${double} assets/app-icon.png --out "build/AppIcon.iconset/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns build/AppIcon.iconset -o build/AppIcon.icns

echo "• 打包 ${APP}.app"
"${VPY}" -m PyInstaller --noconfirm --clean --distpath dist --workpath build/pyinstaller scripts/SaxCoverStudio-mac.spec \
    || fail "App 打包失敗"
APP_PATH="dist/${APP}.app"
[[ -d "${APP_PATH}" ]] || fail "找不到 ${APP_PATH}"
# Ad-hoc signature: required for Apple Silicon; not a Developer ID signature.
codesign --force --deep --sign - "${APP_PATH}"
codesign --verify --deep "${APP_PATH}" || fail "App 簽章驗證失敗"

echo "• 製作 .dmg"
DMG="dist/SaxCoverStudio-BetaV${VERSION}-macOS-AppleSilicon.dmg"
STAGE="build/dmg"
rm -rf "${STAGE}" "${DMG}" && mkdir -p "${STAGE}"
cp -R "${APP_PATH}" "${STAGE}/"
ln -s /Applications "${STAGE}/Applications"
cp README.md "${STAGE}/README.md"
hdiutil create -volname "${APP}" -srcfolder "${STAGE}" -ov -format UDZO "${DMG}" >/dev/null
rm -rf "${STAGE}"

echo ""
echo "✓ 完成"
echo "  App：${APP_PATH}"
echo "  安裝檔：${DMG}"
echo "  第一次開啟：在 App 上按右鍵 →「打開」（未經 Apple 公證的 App 需要這一步）"
