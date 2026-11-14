"""Render the static boot splash shown by the PyInstaller bootloader.

The bootloader displays this image the instant the EXE starts, before Python
and Qt load; it is drawn with the same code as the in-app splash so the Qt
splash can take over seamlessly.
"""
import os
import sys
from pathlib import Path

if sys.platform == "win32":
    # The image needs real system fonts (Chinese text). The headless
    # "offscreen" platform used for CI tests has no font database and would
    # draw every CJK character as a box.
    os.environ["QT_QPA_PLATFORM"] = "windows"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from saxstudio.branding import BOOT_PROGRESS, SPLASH_SIZE, splash_pixmap  # noqa: E402
from saxstudio.qt import QtWidgets  # noqa: E402


def main():
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "build/splash/boot-splash.png")
    output.parent.mkdir(parents=True, exist_ok=True)
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    if sys.platform == "win32":
        from saxstudio.qt import QtGui
        families = set(QtGui.QFontDatabase.families() if hasattr(QtGui.QFontDatabase, "families")
                       else QtGui.QFontDatabase().families())
        if not families & {"Microsoft JhengHei", "Microsoft JhengHei UI"}:
            raise SystemExit("找不到微軟正黑體，開機畫面的中文會變成方框")
    image = splash_pixmap(*SPLASH_SIZE, progress=BOOT_PROGRESS, message="正在啟動…")
    if not image.save(str(output)):
        raise SystemExit(f"could not write {output}")
    print(output)
    del app


if __name__ == "__main__":
    main()
