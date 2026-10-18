from __future__ import annotations

import numpy as np
from scipy import signal

from .qt import QtCore, QtGui, QtWidgets, Signal
from . import theme


class EQGraph(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.effects = None
        self.setMinimumHeight(120)

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        r = self.rect().adjusted(40, 12, -16, -26)
        p.fillRect(self.rect(), QtGui.QColor(theme.c("#101b27")))
        p.setPen(QtGui.QColor(theme.c("#263749")))
        for gain in (-18, -9, 0, 9, 18):
            y = r.top() + (18-gain)/36*r.height()
            p.drawLine(QtCore.QPointF(r.left(), y), QtCore.QPointF(r.right(), y))
            p.setPen(QtGui.QColor(theme.c("#8d9fb3")))
            p.drawText(0, int(y)-7, 36, 16, QtCore.Qt.AlignRight, str(gain))
            p.setPen(QtGui.QColor(theme.c("#263749")))
        def xpos(hz):
            return r.left() + np.log(hz/20)/np.log(1000)*r.width()
        for hz, text in [(20, "20"), (100, "100"), (1000, "1k"), (10000, "10k"), (20000, "20k Hz")]:
            x = xpos(hz)
            p.drawLine(QtCore.QPointF(x, r.top()), QtCore.QPointF(x, r.bottom()))
            p.setPen(QtGui.QColor(theme.c("#8d9fb3")))
            p.drawText(int(x)-20, r.bottom()+5, 45, 18, QtCore.Qt.AlignCenter, text)
            p.setPen(QtGui.QColor(theme.c("#263749")))
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
        p.setPen(QtGui.QPen(QtGui.QColor(theme.c("#32d4ce")), 2))
        p.drawPath(path)


# Record mode colours. Each recording track has a clearly different first
# colour (teal / orange / violet; the backing is gold). Punch-ins draw from a
# separate high-contrast palette containing none of those, starting at a
# different place per track; repeats after six are fine.
TRACK_COLORS = ("#27c9c3", "#ff8a3d", "#a77bff")
PUNCH_COLORS = ("#ff6fae", "#7bd88f", "#5aa9ff", "#f25f5c", "#d4e36b", "#e6e9ef")


def take_color(number, track=0):
    if number <= 0:
        return TRACK_COLORS[track % len(TRACK_COLORS)]
    return PUNCH_COLORS[(track * 2 + number - 1) % len(PUNCH_COLORS)]


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
        # During a punch-in: (start, times, peaks, colour) of the new take, drawn
        # over track 1 from `start`; the old take is shown only before it.
        self.punch_live = None
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

    def take_segments(self):
        """Coloured track-1 segments; empty unless a finished recording has punch-ins."""
        p = self.project
        if not p or not p.is_record or not p.punches or self.video_duration or self.override_duration:
            return []
        return p.take_segments()

    def mouseMoveEvent(self, event):
        if event.buttons() & QtCore.Qt.LeftButton:
            self.mousePressEvent(event)
            return
        segments = self.take_segments()
        if not segments:
            return
        t = self.x_time(event.pos().x())
        seg = next((s for s in segments if s[0] <= t < s[1]), None)
        if seg is None:
            return
        text = "原始錄音" if seg[2] == 0 else f"第 {seg[2]} 次重錄 · {int(seg[0])//60:02}:{seg[0]%60:04.1f} 起"
        pos = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()
        QtWidgets.QToolTip.showText(pos, text, self)

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), QtGui.QColor(theme.c("#101b27")))
        if not self.project or self.total() <= 0:
            p.setPen(QtGui.QColor(theme.c("#7f92a8")))
            p.drawText(self.rect(), QtCore.Qt.AlignCenter, self.empty_text)
            return
        d = self.total()
        top = 27
        track_h = (self.height()-top-12)/2
        p.setPen(QtGui.QColor(theme.c("#7f92a8")))
        for t in np.linspace(0, d, 9):
            x = self.time_x(t)
            text = f"{t:.1f}s" if d < 16 else f"{int(t)//60}:{int(t)%60:02}"
            p.drawText(int(x)-22, 2, 48, 20, QtCore.Qt.AlignCenter, text)
            p.setPen(QtGui.QColor(theme.c("#223344")))
            p.drawLine(QtCore.QPointF(x, top), QtCore.QPointF(x, self.height()-8))
            p.setPen(QtGui.QColor(theme.c("#7f92a8")))
        segments = self.take_segments()
        for row, (wave, duration, offset, color) in enumerate([
            (self.video_wave, self.video_duration or self.project.duration, 0, "#27c9c3"),
            (self.back_wave, self.back_duration, self.project.offset, "#e9b853")]):
            mid = top+(row+.5)*track_h
            p.setPen(QtGui.QPen(QtGui.QColor(theme.c(color)), 1))
            if len(wave):
                for pixel in range(12, self.width()-12):
                    t = self.x_time(pixel)-offset
                    if row == 0 and self.punch_live is not None and t >= self.punch_live[0]:
                        start, times, peaks, live_color = self.punch_live
                        if len(times) and t <= times[-1]:
                            i = min(len(peaks) - 1, int(np.searchsorted(times, t)))
                            height = float(peaks[i]) * track_h * .38
                            p.setPen(QtGui.QPen(QtGui.QColor(theme.c(live_color)), 1))
                            p.drawLine(QtCore.QPointF(pixel, mid - height), QtCore.QPointF(pixel, mid + height))
                        continue
                    if 0 <= t < duration:
                        if row == 0 and self.punch_live is not None:
                            p.setPen(QtGui.QPen(QtGui.QColor(theme.c(color)), 1))
                        if row == 0 and segments:
                            number = next((s[2] for s in segments if s[0] <= t < s[1]), segments[-1][2])
                            p.setPen(QtGui.QPen(QtGui.QColor(theme.c(take_color(number))), 1))
                        index = min(len(wave)-1, int(t/max(.001, duration)*len(wave)))
                        height = float(wave[index])*track_h*.38
                        p.drawLine(QtCore.QPointF(pixel, mid-height), QtCore.QPointF(pixel, mid+height))
        # Seams between takes.
        for start, _end, _number in segments[1:]:
            x = self.time_x(start)
            p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 130), 1))
            p.drawLine(QtCore.QPointF(x, top - 2), QtCore.QPointF(x, top + track_h))
        # Gray shading on deleted regions, selection outline on a retained clip.
        last = 0
        clips = [] if self.override_duration else self.project.clips
        if self.override_duration:
            last = d
        for i, c in enumerate(clips):
            if c.start > last:
                p.fillRect(QtCore.QRectF(self.time_x(last), top, self.time_x(c.start)-self.time_x(last), self.height()-top), QtGui.QColor(*theme.shade()))
            if i == self.selected:
                p.setPen(QtGui.QPen(QtGui.QColor(theme.c("#d7e7fa")), 1))
                p.drawRect(QtCore.QRectF(self.time_x(c.start), top, self.time_x(c.end)-self.time_x(c.start), self.height()-top-2))
            last = c.end
        if last < d:
            p.fillRect(QtCore.QRectF(self.time_x(last), top, self.time_x(d)-self.time_x(last), self.height()-top), QtGui.QColor(*theme.shade()))
        p.setPen(QtGui.QPen(QtGui.QColor(theme.c("#fafcff")), 2))
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


class MirrorTimeline(Timeline):
    """A second view of the main timeline (used in the edit window).

    Waveform data lives on the master so both views always show the same
    material; position, selection and size are per view.
    """

    def __init__(self, master, parent=None):
        super().__init__(parent)  # its default assignments hit the no-op setters
        self._master = master
        self.setMinimumHeight(190)


def _shared(name):
    def get(self):
        return getattr(self._master, name)

    def set_(self, value):
        pass  # the master owns the data; Timeline.__init__ defaults are ignored
    return property(get, set_)


for _name in ("video_wave", "back_wave", "back_duration", "video_duration",
              "override_duration", "empty_text", "punch_live"):
    setattr(MirrorTimeline, _name, _shared(_name))
