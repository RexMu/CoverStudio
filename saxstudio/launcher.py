"""Program entry point: show the splash first, then load the heavy modules.

In the packaged EXE, PyInstaller's bootloader shows a static copy of the splash
(`pyi_splash`) the moment the program is double-clicked, while Python, Qt and
NumPy/SciPy are still being unpacked and imported. The Qt splash then takes over
at the same size and position and reports each loading stage.
"""
import sys
import time

try:
    import pyi_splash  # Only present in a PyInstaller build made with --splash.
except ImportError:
    pyi_splash = None


def close_boot_splash():
    if pyi_splash is not None:
        try:
            pyi_splash.close()
        except Exception:
            pass


def main():
    from .qt import QT6, QtCore, QtWidgets
    from . import branding

    branding.set_windows_identity()
    app = QtWidgets.QApplication(sys.argv)
    # Fusion draws spin-box arrows consistently; the Windows 11 style lays them
    # out side by side and its hit areas do not match the custom stylesheet.
    app.setStyle("Fusion")
    app.setPalette(branding.dark_palette())
    app.setApplicationName(branding.APP_NAME)
    app.setOrganizationName("SaxStudio")
    app.setWindowIcon(branding.application_icon())
    splash = branding.StartupSplash(app.windowIcon())
    splash.show()
    app.processEvents()
    close_boot_splash()
    started = time.monotonic()

    try:
        splash.set_progress(.25, "正在載入音訊引擎…")
        from . import media
        from .app import MainWindow

        splash.set_progress(.55, "正在建立主畫面…")
        window = MainWindow()
    except Exception:
        # A windowed EXE has no console: report instead of leaving the splash up.
        import traceback
        splash.close()
        box = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Critical, branding.APP_NAME,
                                    "程式啟動失敗，請將下方詳細資訊提供給開發者。")
        box.setDetailedText(traceback.format_exc())
        box.exec() if QT6 else box.exec_()
        sys.exit(1)

    splash.set_progress(.8, "正在檢查 FFmpeg…")
    try:
        problems = media.check_ffmpeg()
    except Exception as exc:
        problems = [f"FFmpeg 無法執行：{exc}"]

    splash.set_progress(1.0, "準備完成")
    # Keep the finished state readable for a moment without delaying real work.
    remaining = .45 - (time.monotonic() - started)
    if remaining > 0:
        time.sleep(remaining)
    window.show()
    splash.finish(window)
    if problems:
        QtCore.QTimer.singleShot(150, lambda: window.show_error(
            "FFmpeg 不符合需求，部分功能會失敗\n" + "\n".join(problems) +
            "\n\n請將 FFmpeg 7.1 以上的完整版 ffmpeg.exe／ffprobe.exe 放進 tools 資料夾。"))
    sys.exit(app.exec() if QT6 else app.exec_())
