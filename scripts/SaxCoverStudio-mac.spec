# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the macOS app bundle (Apple Silicon). Run through
# scripts/build-mac.sh, which prepares tools/ffmpeg, tools/ffprobe and the icon.
import re
from pathlib import Path

root = Path(SPECPATH).parent
version = re.search(r'__version__ = "([^"]+)"', (root / "saxstudio" / "__init__.py").read_text()).group(1)
name = "Sax Cover Studio"

datas = [(str(root / "assets"), "assets"), (str(root / "THIRD_PARTY.md"), ".")]
if (root / "tools" / "licenses").is_dir():
    datas.append((str(root / "tools" / "licenses"), "licenses"))

a = Analysis(
    [str(root / "run.py")],
    pathex=[str(root)],
    binaries=[(str(root / "tools" / "ffmpeg"), "tools"), (str(root / "tools" / "ffprobe"), "tools")],
    datas=datas,
    hiddenimports=["PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=name, console=False,
          target_arch="arm64", argv_emulation=False, codesign_identity=None)
coll = COLLECT(exe, a.binaries, a.datas, name=name)
app = BUNDLE(
    coll,
    name=f"{name}.app",
    icon=str(root / "build" / "AppIcon.icns"),
    bundle_identifier="com.rexfactory.saxcoverstudio",
    version=version,
    info_plist={
        "CFBundleDisplayName": name,
        "CFBundleShortVersionString": version,
        "CFBundleVersion": version,
        "NSHumanReadableCopyright": "Rex Mu | RexFactory",
        "LSApplicationCategoryType": "public.app-category.music",
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
        # Required by macOS before any app may use the microphone.
        "NSMicrophoneUsageDescription": "Sax Cover Studio 需要使用麥克風，才能在錄音模式錄下你的薩克斯風演奏。",
    },
)
