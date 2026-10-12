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
BOOT_PROGRESS = .1


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


def paint_splash(painter, width, height, progress=0.1, message="正在啟動…"):
    """Draw the splash text layer on a logical 720x405 canvas scaled to size.

    Positions and sizes follow the approved 720x405 mockup (baselines in px).
    """
    painter.save()
    painter.scale(width/720, height/405)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.setRenderHint(QtGui.QPainter.TextAntialiasing)

    def text(x, y, value, size, color, bold=False, spacing=0.0):
        font = QtGui.QFont("Segoe UI")
        font.setPixelSize(size)
        font.setBold(bold)
        font.setLetterSpacing(QtGui.QFont.AbsoluteSpacing, spacing)
        painter.setFont(font)
        painter.setPen(QtGui.QColor(color))
        painter.drawText(QtCore.QPointF(x, y), value)

    text(40, 108, "YOUR SAX. YOUR COVER.", 11, "#75ded5", spacing=1.5)
    text(38, 158, "Sax Cover", 46, "#e6eff8", bold=True)
    text(38, 205, "Studio", 46, "#32cec5", bold=True)
    text(40, 244, "為你的演奏，調出好聲音。", 16, "#b7cadb")
    text(40, 274, VERSION_LABEL, 13, "#32cec5", bold=True)
    painter.setPen(QtCore.Qt.NoPen)
    painter.setBrush(QtGui.QColor("#203849"))
    painter.drawRoundedRect(QtCore.QRectF(40, 330, 220, 4), 2, 2)
    painter.setBrush(QtGui.QColor("#32cec5"))
    fill = 220 * max(.04, min(1.0, progress))
    painter.drawRoundedRect(QtCore.QRectF(40, 330, fill, 4), 2, 2)
    text(40, 359, message, 14, "#91a8bd")
    text(40, 387, f"本機影音混音工作室  ·  {AUTHOR}", 12, "#96acc0")
    painter.restore()


def splash_pixmap(width, height, progress=0.1, message="正在啟動…", with_text=True):
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
        # Same state as the boot image so the hand-off looks like one screen.
        self.progress, self.message = BOOT_PROGRESS, "正在啟動…"
        canvas = splash_pixmap(round(width*ratio), round(height*ratio), with_text=False)
        canvas.setDevicePixelRatio(ratio)
        super().__init__(canvas, QtCore.Qt.WindowStaysOnTopHint)
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(icon or application_icon())
        self.setAccessibleName(f"{APP_NAME} 啟動畫面")
        # Center on the primary screen like the bootloader splash does; Qt would
        # otherwise pick the screen under the mouse on multi-monitor setups.
        if screen:
            self.move(screen.geometry().center() - self.rect().center())

    def set_progress(self, progress, message):
        self.progress, self.message = progress, message
        self.repaint()
        QtWidgets.QApplication.processEvents()

    def drawContents(self, painter):
        # Layout uses a logical canvas so text stays crisp at every screen size.
        paint_splash(painter, self.width(), self.height(), self.progress, self.message)
