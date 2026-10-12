"""Desktop identity and bundled image resources."""
from pathlib import Path
import os
import sys

from .qt import QtCore, QtGui, QtWidgets

APP_NAME = "Sax Cover Studio"
APP_ID = "SaxCoverStudio.Desktop"


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


class StartupSplash(QtWidgets.QSplashScreen):
    def __init__(self, icon=None):
        screen = QtWidgets.QApplication.primaryScreen()
        bounds = screen.availableGeometry() if screen else QtCore.QRect(0, 0, 1440, 900)
        width = min(960, max(320, round(min(bounds.width()*.8, bounds.height()*.8*16/9))))
        height = round(width*9/16)
        art = QtGui.QPixmap(str(asset_path("splash-art.png")))
        canvas = QtGui.QPixmap(width, height)
        canvas.fill(QtGui.QColor("#0b1724"))
        if not art.isNull():
            painter = QtGui.QPainter(canvas)
            painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
            painter.drawPixmap(canvas.rect(), art)
            painter.end()
        super().__init__(canvas, QtCore.Qt.WindowStaysOnTopHint)
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(icon or application_icon())
        self.setAccessibleName(f"{APP_NAME} 啟動畫面")

    def drawContents(self, painter):
        # Layout uses a logical canvas so text stays crisp at every screen size.
        painter.save()
        painter.scale(self.width()/960, self.height()/540)
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
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor("#203849"))
        painter.drawRoundedRect(QtCore.QRectF(54, 455, 226, 3), 1.5, 1.5)
        painter.setBrush(QtGui.QColor("#32cec5"))
        painter.drawRoundedRect(QtCore.QRectF(54, 455, 52, 3), 1.5, 1.5)
        font.setPixelSize(11)
        painter.setFont(font)
        painter.setPen(QtGui.QColor("#91a8bd"))
        painter.drawText(54, 477, "正在啟動…")
        font.setPixelSize(9)
        painter.setFont(font)
        painter.setPen(QtGui.QColor("#718ea3"))
        painter.drawText(54, 515, "本機影音混音工作室")
        painter.restore()
