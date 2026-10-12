"""Capture the real interface using generated diagnostic media, not a UI mockup."""
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from scipy.io import wavfile
from saxstudio.app import MainWindow, dark_palette
from saxstudio.branding import StartupSplash, application_icon
from saxstudio.media import binary, run
from saxstudio.qt import QtWidgets


def main():
    app = QtWidgets.QApplication([])
    app.setStyle("Fusion")
    app.setPalette(dark_palette())
    app.setWindowIcon(application_icon())
    splash = StartupSplash(app.windowIcon())
    splash.show()
    app.processEvents()
    docs = Path(__file__).resolve().parent.parent/"docs"
    splash.grab().save(str(docs/"startup-screenshot.png"))
    splash.close()
    w = MainWindow()
    # Isolate playback devices for a reproducible UI capture on an offline host.
    # Decode/mix/align still run against real FFmpeg-generated media below.
    w.video_player.blockSignals(True)
    w.audio_player.blockSignals(True)
    w.show()
    errors = []
    w.show_error = errors.append

    def wait():
        limit = time.monotonic()+30
        while w.busy and time.monotonic() < limit:
            app.processEvents()
            time.sleep(.01)
        app.processEvents()
        if errors or w.busy:
            raise RuntimeError(errors or "UI worker timeout")

    with tempfile.TemporaryDirectory(prefix="sax-ui-capture-") as tmp:
        root = Path(tmp)
        rate, seconds = 48000, 24
        t = np.arange(rate*seconds)/rate
        backing = np.zeros(len(t))
        rng = np.random.default_rng(48)
        for start in np.arange(.15, seconds-.5, .37):
            note_t = np.arange(int(rate*.32))/rate
            freq = rng.choice([110, 147, 196, 220, 294, 330, 392, 440])
            note = sum(np.sin(2*np.pi*freq*k*note_t+rng.random()*6.28)/k for k in (1, 2, 3, 5))
            note *= .2*np.exp(-note_t*8)*np.minimum(note_t/.005, 1)*rng.uniform(.2, .8)
            index = int(start*rate)
            backing[index:index+len(note)] += note
        delay = round(.437*rate)
        recorded = np.pad(backing, (delay, 0))[:len(t)]*.08
        recorded += .12*np.sin(2*np.pi*440*t)*np.maximum(0, np.sin(t*1.8))*(t > 8)
        wavfile.write(root/"原音.wav", rate, recorded.astype(np.float32))
        wavfile.write(root/"合成測試伴奏.wav", rate, backing.astype(np.float32))
        video = root/"合成測試影片.mp4"
        run([binary("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30:duration=24",
             "-i", str(root/"原音.wav"), "-c:v", "libx264", "-preset", "ultrafast", "-threads", "2", "-c:a", "aac", "-shortest", str(video)])
        with patch.object(QtWidgets.QFileDialog, "getOpenFileName", return_value=(str(video), "")):
            w.import_video()
        wait()
        with patch.object(QtWidgets.QFileDialog, "getOpenFileName", return_value=(str(root/"合成測試伴奏.wav"), "")):
            w.import_backing()
        wait()
        w.align()
        wait()
        w.seek(8)
        w.split()
        w.seek(12)
        w.split()
        w.clip_list.setCurrentRow(1)
        w.delete_clip()
        w.clip_list.setCurrentRow(0)
        w.seek(5)
        w.prepare_preview(False)
        wait()
        w.video_stack.setCurrentWidget(w.video_empty)
        w.statusBar().showMessage("實際程式介面 · 合成素材，影片以縮圖顯示（播放裝置隔離）")
        app.processEvents()
        output = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/ui-screenshot.png").resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        w.grab().save(str(output))
        w.fx_fields["compressor_enabled"].setChecked(True)
        for section in w.effect_sections.values():
            section.set_expanded(True)
        w.resize(1440, 1060)
        app.processEvents()
        w.grab().save(str(docs/"effects-expanded.png"))
        print(output)
        w.dirty = False
        w.close()


if __name__ == "__main__":
    main()
