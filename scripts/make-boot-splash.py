"""Render the static boot splash shown by the PyInstaller bootloader.

The bootloader displays this image the instant the EXE starts, before Python
and Qt load; it is drawn with the same code as the in-app splash so the Qt
splash can take over seamlessly.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from saxstudio.branding import SPLASH_SIZE, splash_pixmap  # noqa: E402
from saxstudio.qt import QtWidgets  # noqa: E402


def main():
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "build/splash/boot-splash.png")
    output.parent.mkdir(parents=True, exist_ok=True)
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    image = splash_pixmap(*SPLASH_SIZE, progress=.08, message="正在啟動…")
    if not image.save(str(output)):
        raise SystemExit(f"could not write {output}")
    print(output)
    del app


if __name__ == "__main__":
    main()
