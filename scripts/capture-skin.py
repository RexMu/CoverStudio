"""Screenshots of the record-mode interface in both themes (for checking the look in CI)."""
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # CI sets "windows" for real CJK fonts
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from scipy.io import wavfile
from saxstudio import theme
from saxstudio.app import MainWindow, dark_palette
from saxstudio.qt import QtCore, QtWidgets
from saxstudio.recorder import TakeResult


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "skin").resolve()
    out.mkdir(parents=True, exist_ok=True)
    app = QtWidgets.QApplication([])
    app.setStyle("Fusion")
    with tempfile.TemporaryDirectory(prefix="sax-skin-") as tmp:
        root = Path(tmp)
        QtCore.QSettings.setDefaultFormat(QtCore.QSettings.IniFormat)
        QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, str(root/"settings"))
        rate, seconds = 48000, 20
        t = np.arange(rate*seconds)/rate
        rng = np.random.default_rng(7)
        backing = .15*np.sin(2*np.pi*220*t)*(0.5+0.5*np.sin(t*2.3))*(t > .5)
        wavfile.write(root/"月亮代表我的心.wav", rate, backing.astype(np.float32))
        def take(name, seed):
            r = np.random.default_rng(seed)
            env = np.clip(np.sin(t*r.uniform(.6, 1.4))+r.uniform(-.2, .3), 0, 1)
            x = .25*env*np.sin(2*np.pi*r.uniform(300, 600)*t)*(t > 1.5)
            wavfile.write(root/name, rate, x.astype(np.float32))
            return str(root/name)
        for name in (theme.DARK, theme.LIGHT):
            QtCore.QSettings("SaxStudio", "SaxStudio").setValue("ui/theme", name)
            theme.set_theme(name)
            app.setPalette(dark_palette())
            with patch("saxstudio.app.source"), patch("saxstudio.recorder.audio_available", return_value=False):
                w = MainWindow()
                w.show_error = lambda text: print("ERROR", text)
                w.resize(1440, 900)
                w.show()
                def wait():
                    limit = time.monotonic()+60
                    while (w.busy or w.preview_job is not None) and time.monotonic() < limit:
                        app.processEvents()
                        time.sleep(.01)
                    app.processEvents()
                w.grab().save(str(out/f"start-{name}.png"))
                with patch.object(QtWidgets.QFileDialog, "getOpenFileName",
                                  return_value=(str(root/"月亮代表我的心.wav"), "")):
                    w.new_record_project()
                wait()
                w.finish_recording(TakeResult(take("alto.wav", 1), seconds, rate, 1.0, .5))
                wait()
                with patch.object(QtWidgets.QInputDialog, "getItem", return_value=("Tenor", True)), \
                        patch.object(QtWidgets.QMessageBox, "question", return_value=QtWidgets.QMessageBox.No):
                    w.add_track()
                w.fresh = {"track": 1, "length": seconds, "times": [], "peaks": [], "heard": None}
                w.recording_active = True
                w.finish_recording(TakeResult(take("tenor.wav", 2), seconds, rate, 1.0, .4))
                wait()
                w.eq_toggle.setChecked(True)
                w.seek(6)
                app.processEvents()
                w.grab().save(str(out/f"record-{name}.png"))
                w.dirty = False
                w.close()
                app.processEvents()
    print(out)


if __name__ == "__main__":
    main()
