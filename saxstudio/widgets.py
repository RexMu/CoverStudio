from __future__ import annotations

import numpy as np
from scipy import signal

from .qt import QtCore, QtGui, QtWidgets, Signal


class EQGraph(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.effects = None
        self.setMinimumHeight(120)

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        r = self.rect().adjusted(40, 12, -16, -26)
        p.fillRect(self.rect(), QtGui.QColor("#101b27"))
        p.setPen(QtGui.QColor("#263749"))
        for gain in (-18, -9, 0, 9, 18):
            y = r.top() + (18-gain)/36*r.height()
            p.drawLine(QtCore.QPointF(r.left(), y), QtCore.QPointF(r.right(), y))
            p.setPen(QtGui.QColor("#8d9fb3"))
            p.drawText(0, int(y)-7, 36, 16, QtCore.Qt.AlignRight, str(gain))
            p.setPen(QtGui.QColor("#263749"))
        def xpos(hz):
            return r.left() + np.log(hz/20)/np.log(1000)*r.width()
        for hz, text in [(20, "20"), (100, "100"), (1000, "1k"), (10000, "10k"), (20000, "20k Hz")]:
            x = xpos(hz)
            p.drawLine(QtCore.QPointF(x, r.top()), QtCore.QPointF(x, r.bottom()))
            p.setPen(QtGui.QColor("#8d9fb3"))
            p.drawText(int(x)-20, r.bottom()+5, 45, 18, QtCore.Qt.AlignCenter, text)
            p.setPen(QtGui.QColor("#263749"))
        if not self.effects:
            return
        freqs = np.geomspace(20, 20000, 360)
        response = np.ones(len(freqs), dtype=complex)
        fx = self.effects
        if fx.eq_enabled:
            if fx.highpass:
                sos = signal.butter(2, fx.highpass, btype="highpass", fs=48000, output="sos")
                response *= signal.sosfreqz(sos, worN=freqs, fs=48000)[1]
            for band in fx.bands:
                a = 10**(band.gain/40)
                w = 2*np.pi*band.frequency/48000
                alpha = np.sin(w)/(2*band.q)
                b = [1+alpha*a, -2*np.cos(w), 1-alpha*a]
                den = [1+alpha/a, -2*np.cos(w), 1-alpha/a]
                response *= signal.freqz(b, den, worN=freqs, fs=48000)[1]
        db = np.clip(20*np.log10(np.maximum(abs(response), 1e-10)), -18, 18)
        path = QtGui.QPainterPath()
        for i, (hz, value) in enumerate(zip(freqs, db)):
            point = QtCore.QPointF(xpos(hz), r.top()+(18-value)/36*r.height())
            path.moveTo(point) if i == 0 else path.lineTo(point)
        p.setPen(QtGui.QPen(QtGui.QColor("#32d4ce"), 2))
        p.drawPath(path)


class Timeline(QtWidgets.QWidget):
    seek = Signal(float)
    select = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project = None
        self.video_wave = np.array([])
        self.back_wave = np.array([])
        self.back_duration = 0
        # Record mode: length of the track-1 waveform when it is still growing,
        # and a display length while there is no recording yet (or during one).
        self.video_duration = None
        self.override_duration = None
        self.empty_text = "匯入影片與伴奏後，波形會顯示在這裡"
        self.position = 0
        self.selected = -1
        self.setMinimumHeight(170)
        self.setMouseTracking(True)
        self.setToolTip("點擊波形移動播放位置並選取片段；青綠色為影片原音，金色為伴奏")

    def total(self):
        if self.override_duration:
            return self.override_duration
        return self.project.duration if self.project else 0

    def time_x(self, t):
        return 12 + t/max(.001, self.total())*max(1, self.width()-24)

    def x_time(self, x):
        if not self.project:
            return 0
        return max(0, min(self.total(), (x-12)/max(1, self.width()-24)*self.total()))

    def mousePressEvent(self, event):
        if not self.project or not self.project.duration or self.override_duration:
            return
        t = self.x_time(event.pos().x())
        self.selected = next((i for i, c in enumerate(self.project.clips) if c.start <= t <= c.end), -1)
        self.select.emit(self.selected)
        self.seek.emit(t)
        self.update()

    def mouseMoveEvent(self, event):
        if event.buttons() & QtCore.Qt.LeftButton:
            self.mousePressEvent(event)

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), QtGui.QColor("#101b27"))
        if not self.project or self.total() <= 0:
            p.setPen(QtGui.QColor("#7f92a8"))
            p.drawText(self.rect(), QtCore.Qt.AlignCenter, self.empty_text)
            return
        d = self.total()
        top = 27
        track_h = (self.height()-top-12)/2
        p.setPen(QtGui.QColor("#7f92a8"))
        for t in np.linspace(0, d, 9):
            x = self.time_x(t)
            text = f"{t:.1f}s" if d < 16 else f"{int(t)//60}:{int(t)%60:02}"
            p.drawText(int(x)-22, 2, 48, 20, QtCore.Qt.AlignCenter, text)
            p.setPen(QtGui.QColor("#223344"))
            p.drawLine(QtCore.QPointF(x, top), QtCore.QPointF(x, self.height()-8))
            p.setPen(QtGui.QColor("#7f92a8"))
        for row, (wave, duration, offset, color) in enumerate([
            (self.video_wave, self.video_duration or self.project.duration, 0, "#27c9c3"),
            (self.back_wave, self.back_duration, self.project.offset, "#e9b853")]):
            mid = top+(row+.5)*track_h
            p.setPen(QtGui.QPen(QtGui.QColor(color), 1))
            if len(wave):
                for pixel in range(12, self.width()-12):
                    t = self.x_time(pixel)-offset
                    if 0 <= t < duration:
                        index = min(len(wave)-1, int(t/max(.001, duration)*len(wave)))
                        height = float(wave[index])*track_h*.38
                        p.drawLine(QtCore.QPointF(pixel, mid-height), QtCore.QPointF(pixel, mid+height))
        # Gray shading on deleted regions, selection outline on a retained clip.
        last = 0
        clips = [] if self.override_duration else self.project.clips
        if self.override_duration:
            last = d
        for i, c in enumerate(clips):
            if c.start > last:
                p.fillRect(QtCore.QRectF(self.time_x(last), top, self.time_x(c.start)-self.time_x(last), self.height()-top), QtGui.QColor(6, 10, 16, 190))
            if i == self.selected:
                p.setPen(QtGui.QPen(QtGui.QColor("#d7e7fa"), 1))
                p.drawRect(QtCore.QRectF(self.time_x(c.start), top, self.time_x(c.end)-self.time_x(c.start), self.height()-top-2))
            last = c.end
        if last < d:
            p.fillRect(QtCore.QRectF(self.time_x(last), top, self.time_x(d)-self.time_x(last), self.height()-top), QtGui.QColor(6, 10, 16, 190))
        p.setPen(QtGui.QPen(QtGui.QColor("#fafcff"), 2))
        x = self.time_x(self.position)
        p.drawLine(QtCore.QPointF(x, top-4), QtCore.QPointF(x, self.height()))


class Worker(QtCore.QThread):
    result = Signal(object)
    failed = Signal(str)
    progress = Signal(str)

    def __init__(self, function, parent=None):
        super().__init__(parent)
        import threading
        self.cancel = threading.Event()
        self.function = function

    def run(self):
        try:
            self.result.emit(self.function(self.cancel, self.progress.emit))
        except Exception as exc:
            self.failed.emit(str(exc))
