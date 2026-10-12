"""Desktop identity and bundled image resources.

Imports only Qt so the startup splash can appear before NumPy/SciPy load.
"""
from pathlib import Path
import os
import sys

from . import AUTHOR, VERSION_LABEL
from .qt import QT6, QtCore, QtGui, QtWidgets

APP_NAME = "Sax Cover Studio"
APP_ID = "SaxCoverStudio.Desktop"
# Physical pixel size shared by the PyInstaller boot image and the Qt splash,
# so the hand-off between them does not jump in size or position.
SPLASH_SIZE = (720, 405)  # PyInstaller boot splash allows at most 760x480


def asset_path(name):
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return root / "assets" / name


def application_icon():
    icon = QtGui.QIcon(str(asset_path("app-icon.ico")))
    if icon.isNull():
        icon = QtGui.QIcon(str(asset_path("app-icon.png")))
    return icon


def set_windows_identity():
    """Use the same identity as the installer shortcuts for taskbar grouping."""
    if os.name == "nt":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)


def dark_palette():
    palette = QtGui.QPalette()
    roles = QtGui.QPalette.ColorRole if QT6 else QtGui.QPalette
    for role, color in [("Window", "#101923"), ("WindowText", "#e5edf7"), ("Base", "#101d2b"),
                        ("AlternateBase", "#182635"), ("Text", "#e5edf7"), ("Button", "#24384c"),
                        ("ButtonText", "#e5edf7"), ("Highlight", "#28646a"), ("HighlightedText", "#ffffff"),
                        ("ToolTipBase", "#253d51"), ("ToolTipText", "#eff7ff")]:
        palette.setColor(getattr(roles, role), QtGui.QColor(color))
    return palette


def paint_splash(painter, width, height, progress=0.0, message="正在啟動…"):
    """Draw the splash text layer on a logical 960x540 canvas scaled to size."""
    painter.save()
    painter.scale(width/960, height/540)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    font = QtGui.QFont("Segoe UI")
    font.setPixelSize(10)
    font.setLetterSpacing(QtGui.QFont.AbsoluteSpacing, 2)
    painter.setFont(font)
    painter.setPen(QtGui.QColor("#75ded5"))
    painter.drawText(54, 158, "YOUR SAX. YOUR COVER.")
    font.setLetterSpacing(QtGui.QFont.AbsoluteSpacing, 0)
    font.setPixelSize(49)
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QtGui.QColor("#e6eff8"))
    painter.drawText(52, 214, "Sax Cover")
    painter.setPen(QtGui.QColor("#32cec5"))
    painter.drawText(52, 266, "Studio")
    font.setPixelSize(15)
    font.setBold(False)
    painter.setFont(font)
    painter.setPen(QtGui.QColor("#b7cadb"))
    painter.drawText(54, 307, "為你的演奏，調出好聲音。")
    font.setPixelSize(12)
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QtGui.QColor("#32cec5"))
    painter.drawText(54, 340, VERSION_LABEL)
    painter.setPen(QtCore.Qt.NoPen)
    painter.setBrush(QtGui.QColor("#203849"))
    painter.drawRoundedRect(QtCore.QRectF(54, 455, 226, 3), 1.5, 1.5)
    painter.setBrush(QtGui.QColor("#32cec5"))
    fill = 226 * max(.04, min(1.0, progress))
    painter.drawRoundedRect(QtCore.QRectF(54, 455, fill, 3), 1.5, 1.5)
    font.setPixelSize(11)
    font.setBold(False)
    painter.setFont(font)
    painter.setPen(QtGui.QColor("#91a8bd"))
    painter.drawText(54, 477, message)
    font.setPixelSize(9)
    painter.setFont(font)
    painter.setPen(QtGui.QColor("#718ea3"))
    painter.drawText(54, 515, f"本機影音混音工作室  ·  {AUTHOR}")
    painter.restore()


def splash_pixmap(width, height, progress=0.0, message="正在啟動…", with_text=True):
    canvas = QtGui.QPixmap(width, height)
    canvas.fill(QtGui.QColor("#0b1724"))
    art = QtGui.QPixmap(str(asset_path("splash-art.png")))
    painter = QtGui.QPainter(canvas)
    painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
    if not art.isNull():
        painter.drawPixmap(canvas.rect(), art)
    if with_text:
        paint_splash(painter, width, height, progress, message)
    painter.end()
    return canvas


class StartupSplash(QtWidgets.QSplashScreen):
    def __init__(self, icon=None):
        screen = QtWidgets.QApplication.primaryScreen()
        bounds = screen.availableGeometry() if screen else QtCore.QRect(0, 0, 1440, 900)
        ratio = screen.devicePixelRatio() if screen else 1.0
        # Same physical size as the boot image, limited to 80% of the screen.
        width = min(SPLASH_SIZE[0]/ratio, bounds.width()*.8, bounds.height()*.8*16/9)
        width = max(320, round(width))
        height = round(width*9/16)
        self.progress, self.message = 0.0, "正在啟動…"
        canvas = splash_pixmap(round(width*ratio), round(height*ratio), with_text=False)
        canvas.setDevicePixelRatio(ratio)
        super().__init__(canvas, QtCore.Qt.WindowStaysOnTopHint)
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(icon or application_icon())
        self.setAccessibleName(f"{APP_NAME} 啟動畫面")

    def set_progress(self, progress, message):
        self.progress, self.message = progress, message
        self.repaint()
        QtWidgets.QApplication.processEvents()

    def drawContents(self, painter):
        # Layout uses a logical canvas so text stays crisp at every screen size.
        paint_splash(painter, self.width(), self.height(), self.progress, self.message)
