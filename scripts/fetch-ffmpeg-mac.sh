#!/usr/bin/env bash
# Download the pinned FFmpeg/FFprobe for Apple Silicon into tools/.
# Each zip is checked against the SHA256 the server publishes next to it, and
# against tools/ffmpeg-macos-arm64.lock (written on the first successful
# download) so later builds fail loudly if the file ever changes.
set -euo pipefail
cd "$(dirname "$0")/.."
source tools/ffmpeg-macos-arm64.env
LOCK="tools/ffmpeg-macos-arm64.lock"

fail() { echo "✗ $*" >&2; exit 1; }
sha256() {
    if command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | awk '{print $1}'
    else sha256sum "$1" | awk '{print $1}'; fi
}

if [[ -f tools/ffmpeg && -x tools/ffmpeg && -f tools/ffprobe && -x tools/ffprobe && "${FORCE:-0}" != "1" ]]; then
    echo "• tools/ 已有 ffmpeg 與 ffprobe，略過下載（要重新下載請用 FORCE=1）"
    exit 0
fi
command -v curl >/dev/null 2>&1 || fail "找不到 curl"
command -v unzip >/dev/null 2>&1 || fail "找不到 unzip"

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
mkdir -p tools/licenses
for name in ffmpeg ffprobe; do
    echo "• 下載 ${name} ${FFMPEG_VERSION}（Apple Silicon）…"
    curl -fL --progress-bar --retry 3 --connect-timeout 20 -o "${tmp}/${name}.zip" "${FFMPEG_BASE}/${name}.zip" \
        || fail "${name} 下載失敗，請確認網路，或把 ffmpeg／ffprobe 手動放進 tools/"
    curl -fsSL --retry 3 --connect-timeout 20 -o "${tmp}/${name}.zip.sha256" "${FFMPEG_BASE}/${name}.zip.sha256" \
        || fail "${name} 的 SHA256 檔下載失敗"
    expected="$(grep -Eo '[0-9a-fA-F]{64}' "${tmp}/${name}.zip.sha256" | head -n1 | tr 'A-F' 'a-f' || true)"
    actual="$(sha256 "${tmp}/${name}.zip")"
    [[ -n "${expected}" ]] || fail "${name} 的 SHA256 檔格式不正確"
    [[ "${expected}" == "${actual}" ]] || fail "${name} 驗證失敗：檔案與官方 SHA256 不符（可能下載不完整或被竄改）"
    locked="$(grep -E "^${name} " "${LOCK}" 2>/dev/null | awk '{print $2}' || true)"
    if [[ -n "${locked}" && "${locked}" != "${actual}" ]]; then
        fail "${name} 與 ${LOCK} 記錄的版本不同。若是刻意升級 FFmpeg，請刪除鎖定檔後重試"
    fi
    unzip -o -q "${tmp}/${name}.zip" -d "${tmp}/${name}"
    binary="$(find "${tmp}/${name}" -type f -name "${name}" | head -n1)"
    [[ -n "${binary}" ]] || fail "${name}.zip 裡找不到 ${name}"
    install -m 755 "${binary}" "tools/${name}"
    [[ -n "${locked}" ]] || echo "${name} ${actual}" >> "${LOCK}"
    echo "  ✓ SHA256 ${actual}"
done

# Files fetched by curl carry no quarantine flag, but clear it in case the
# folder was copied from a browser download.
xattr -d com.apple.quarantine tools/ffmpeg tools/ffprobe 2>/dev/null || true
if command -v lipo >/dev/null 2>&1; then
    lipo -archs tools/ffmpeg | grep -q arm64 || fail "下載的 ffmpeg 不是 Apple Silicon（arm64）版本"
fi
tools/ffmpeg -hide_banner -version | head -n1
cat > tools/licenses/BUILD.txt <<NOTE
FFmpeg ${FFMPEG_VERSION} for macOS arm64
Builder: Martin Riedl, https://ffmpeg.martin-riedl.de/
Download: ${FFMPEG_BASE}/ffmpeg.zip, ffprobe.zip
SHA256 (zip): $(tr '\n' ' ' < "${LOCK}")
Licence: GPL (the build includes libx264). Corresponding source:
https://ffmpeg.org/releases/ffmpeg-${FFMPEG_VERSION}.tar.xz
NOTE
echo "✓ FFmpeg 已放入 tools/"
