"""Recording while the backing track plays in the headphones.

Pure helpers (WAV writer, click track, latency measurement) have no Qt
dependency and are unit-tested. `AudioSession` drives the sound card through
Qt 6 Multimedia (QAudioSource / QAudioSink).

Timing model: the recording timeline counts captured samples from the moment a
take starts. The backing starts after the count-in; `start_offset` is the
recording time at which playback was started. Sound scheduled at backing time t
shows up in the recording at start_offset + t + latency, where latency (output
+ input buffering) is measured once with the same code path by `calibrate`.
Hence the project offset is start_offset + latency.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np


# --------------------------------------------------------------------- WAV

class WavWriter:
    """Float32 mono/stereo WAV written while recording.

    The RIFF sizes are patched on every `flush()`, so after a crash the file
    is a valid WAV holding everything up to the last flush.
    """

    def __init__(self, path, rate, channels=1):
        self.path = Path(path)
        self.rate, self.channels = int(rate), int(channels)
        self.frames = 0
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self.path, "wb")
        self._file.write(self._header(0))
        self._file.flush()

    def _header(self, data_bytes):
        block = 4 * self.channels
        return (b"RIFF" + struct.pack("<I", 36 + data_bytes) + b"WAVE"
                + b"fmt " + struct.pack("<IHHIIHH", 16, 3, self.channels, self.rate,
                                        self.rate * block, block, 32)
                + b"data" + struct.pack("<I", data_bytes))

    def write(self, samples):
        samples = np.asarray(samples, dtype="<f4")
        if samples.size:
            self._file.write(samples.tobytes())
            self.frames += samples.size // self.channels

    def flush(self):
        data_bytes = self.frames * 4 * self.channels
        position = self._file.tell()
        self._file.seek(0)
        self._file.write(self._header(data_bytes))
        self._file.seek(position)
        self._file.flush()

    def close(self):
        if not self._file.closed:
            self.flush()
            self._file.close()

    @property
    def seconds(self):
        return self.frames / self.rate


# --------------------------------------------------------------- latency

def click_burst(rate):
    length = int(round(.004 * rate))
    t = np.arange(length) / rate
    return (.8 * np.sin(2 * np.pi * 2000 * t) * np.hanning(length)).astype(np.float32)


def click_track(rate, count=8, interval=.5, lead=.5, tail=.6):
    """Short 2 kHz bursts. Returns (mono samples, click start times)."""
    total = int(round((lead + interval * (count - 1) + tail) * rate))
    out = np.zeros(total, np.float32)
    burst = click_burst(rate)
    length = len(burst)
    times = [lead + k * interval for k in range(count)]
    for start in times:
        i = int(round(start * rate))
        out[i:i + length] += burst
    return out, times


def measure_latency(captured, rate, start_offset, click_times, max_latency=.45):
    """Delay between scheduled clicks and their arrival in the recording.

    `start_offset` (seconds) is the recording time playback started at.
    Returns (median_ms, spread_ms, found). Raises ValueError when too few
    clicks are heard.
    """
    raw = np.asarray(captured, np.float32)
    x = np.abs(raw)
    if not len(x):
        raise ValueError("沒有收到麥克風的聲音")
    noise = float(np.percentile(x, 50))
    template = click_burst(rate)
    delays = []
    for t in click_times:
        a = int(round((start_offset + t) * rate))
        b = min(len(x), a + int(round(max_latency * rate)) + len(template))
        if a >= len(x) or b - a < 2 * len(template):
            continue
        if float(x[a:b].max()) < max(.01, noise * 8):
            continue
        # Matched filter against the known burst gives the click's start even
        # when the speaker/mic colour the sound; the envelope keeps it robust
        # to polarity and phase changes.
        score = np.abs(np.correlate(raw[a:b], template, mode="valid"))
        envelope = np.convolve(score, np.ones(len(template)//4 or 1), mode="same")
        delays.append(int(np.argmax(envelope)) / rate)
    if len(delays) < max(3, len(click_times) // 2):
        raise ValueError("沒有偵測到足夠的節拍聲，請把耳機貼近麥克風、調大耳機音量後再試一次")
    delays = np.array(delays)
    median = float(np.median(delays))
    spread = float((delays.max() - delays.min()) / 2)
    return median * 1000, spread * 1000, len(delays)


def recording_offset(start_offset, latency_ms):
    """Backing position on the recording timeline (project offset, seconds)."""
    return start_offset + latency_ms / 1000


PREROLL = 3.0      # seconds heard before a punch-in point
PUNCH_FADE = .02   # crossfade at the punch-in seam


def punch_playback(backing, recording, offset, start, rate=48000, preroll=PREROLL,
                   backing_gain=1.0):
    """Headphone mix for a punch-in.

    backing: float32 (frames, 2); recording: float32 mono, both at `rate`.
    `offset` is the project offset (backing sample 0 on the recording
    timeline); `start` the punch-in point on that timeline. Returns
    (stereo float32, playback start on the recording timeline). The existing
    recording is heard only until `start`, where it fades out.
    """
    begin = max(0.0, start - preroll)
    b0 = int(round((begin - offset) * rate))      # backing frame at `begin`
    frames = max(0, len(backing) - b0) if b0 >= 0 else len(backing) - b0
    frames = max(frames, int(round((start - begin) * rate)) + rate // 10)
    out = np.zeros((frames, 2), np.float32)
    src0, dst0 = max(0, b0), max(0, -b0)
    count = min(len(backing) - src0, frames - dst0)
    if count > 0:
        out[dst0:dst0 + count] = backing[src0:src0 + count] * backing_gain
    r0, r1 = int(round(begin * rate)), int(round(start * rate))
    old = np.asarray(recording[r0:r1], np.float32).copy()
    fade = min(len(old), int(rate * .01))
    if fade:
        old[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
    out[:len(old)] += old[:, None]
    return np.clip(out, -1, 1), begin


def splice_punch(recording, take, start, begin, start_offset, latency_ms, rate=48000,
                 fade=PUNCH_FADE):
    """New track-1 audio: `recording` up to `start`, then the punch-in `take`.

    The take's playback began at `begin` (recording timeline) after
    `start_offset` seconds of take audio; the musician is heard
    `latency_ms` later. Raises ValueError when the take ends before `start`.
    """
    # Take sample that belongs at recording time t: t - begin + start_offset + latency.
    shift = int(round((start_offset + latency_ms / 1000 - begin) * rate))
    s = int(round(start * rate))
    half = int(round(fade * rate / 2))
    a = max(0, s - half)
    if a + shift < 0:
        a = -shift
    if len(take) - (s + shift) < rate // 10:
        raise ValueError("在重錄起點之前就停止了，沒有錄到新的內容")
    new = np.asarray(take[a + shift:], np.float32)
    keep = np.asarray(recording[:a], np.float32)
    n = min(2 * half, len(new), max(0, len(recording) - a))
    if n:
        w = np.linspace(0, 1, n, dtype=np.float32)
        new = new.copy()
        new[:n] = recording[a:a + n] * (1 - w) + new[:n] * w
    return np.concatenate([keep, new])


CLIP_LEVEL = .999   # |sample| at or above this counts as full scale
CLIP_RUN = 3        # consecutive full-scale samples needed to call it clipping


def is_clipping(mono, level=CLIP_LEVEL, run=CLIP_RUN):
    """True when the block holds `run` consecutive full-scale samples.

    A single hot sample is usually a transient the converter handled fine;
    real clipping flattens the waveform for several samples in a row.
    """
    hot = np.abs(np.asarray(mono, np.float32)) >= level
    if hot.sum() < run:
        return False
    # Longest run of True values.
    edges = np.diff(np.concatenate(([0], hot.astype(np.int8), [0])))
    starts, ends = np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)
    return bool(np.max(ends - starts) >= run)


def to_mono(raw, sample_format, channels, channel):
    """Decode interleaved PCM bytes to one float32 channel."""
    if sample_format == "float":
        data = np.frombuffer(raw, dtype="<f4")
    elif sample_format == "int32":
        data = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    else:
        data = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    usable = len(data) - len(data) % channels
    if not usable:
        return np.zeros(0, np.float32)
    return data[:usable].reshape(-1, channels)[:, min(channel, channels - 1)].copy()


def to_pcm(samples, sample_format):
    """Float32 interleaved samples to device bytes."""
    samples = np.clip(np.asarray(samples, np.float32), -1, 1)
    if sample_format == "float":
        return samples.astype("<f4").tobytes()
    if sample_format == "int32":
        return (samples * 2147483647.0).astype("<i4").tobytes()
    return (samples * 32767.0).astype("<i2").tobytes()


@dataclass
class TakeResult:
    path: str
    seconds: float
    rate: int
    start_offset: float
    peak: float


# ------------------------------------------------------------- Qt session

def audio_available():
    from .qt import QT6
    if not QT6:
        return False
    from .qt import QtMultimedia
    return hasattr(QtMultimedia, "QAudioSource") and hasattr(QtMultimedia, "QMediaDevices")


def input_devices():
    if not audio_available():
        return []
    from .qt import QtMultimedia
    return list(QtMultimedia.QMediaDevices.audioInputs())


def output_devices():
    if not audio_available():
        return []
    from .qt import QtMultimedia
    return list(QtMultimedia.QMediaDevices.audioOutputs())


def device_key(device):
    try:
        return bytes(device.id().data()).hex()
    except Exception:
        return str(device.description())


def _make_session_class():
    from .qt import QtCore, QtMultimedia, Signal

    audio_ns = getattr(QtMultimedia, "QtAudio", None) or QtMultimedia.QAudio
    SF = QtMultimedia.QAudioFormat.SampleFormat

    def pick_format(device, rate, channels):
        for sample_format, name in ((SF.Float, "float"), (SF.Int32, "int32"), (SF.Int16, "int16")):
            fmt = QtMultimedia.QAudioFormat()
            fmt.setSampleRate(rate)
            fmt.setChannelCount(channels)
            fmt.setSampleFormat(sample_format)
            if device.isFormatSupported(fmt):
                return fmt, name
        fmt = device.preferredFormat()
        name = {SF.Float: "float", SF.Int32: "int32"}.get(fmt.sampleFormat(), "int16")
        if fmt.sampleFormat() not in (SF.Float, SF.Int32, SF.Int16):
            fmt.setSampleFormat(SF.Int16)
            name = "int16"
        return fmt, name

    class AudioSession(QtCore.QObject):
        """Input monitoring, takes with backing playback, and calibration."""
        level = Signal(float)              # peak of the latest block, linear
        clipped = Signal()                 # sustained full-scale samples in a block
        progress = Signal(float, float)    # recorded seconds, backing seconds left (-1 before start)
        countdown = Signal(int)            # seconds left before the backing starts
        take_finished = Signal(object)     # TakeResult
        calibration_finished = Signal(float, float, int)
        failed = Signal(str)

        def __init__(self, parent=None):
            super().__init__(parent)
            self.source = self.source_io = None
            self.sink = self.buffer = None
            self.in_format = "float"
            self.in_channels, self.channel, self.rate = 1, 0, 48000
            self.writer = None
            self.capture = None          # list of arrays during calibration
            self.recorded = 0            # samples captured since the take started
            self.recording = False
            self.start_offset = None
            self.backing_seconds = 0.0
            self.peak = 0.0
            self.mode = None             # None | "take" | "calibrate"
            self.click_times = []
            self.timer = QtCore.QTimer(self)
            self.timer.setInterval(15)
            self.timer.timeout.connect(self._drain)
            self.count_timer = QtCore.QTimer(self)
            self.count_timer.setInterval(1000)
            self.count_timer.timeout.connect(self._tick)
            self.count_left = 0
            self.tail_timer = QtCore.QTimer(self)
            self.tail_timer.setSingleShot(True)
            self.tail_timer.timeout.connect(self._tail_done)
            self.output_device = None
            self.volume = 1.0
            self.pending_pcm = None

        # ---- input monitoring
        def open_input(self, device, channel=0):
            self.close_input()
            channels = max(1, min(device.maximumChannelCount() or 1, max(channel + 1, 1)))
            fmt, name = pick_format(device, 48000, channels)
            self.in_format, self.in_channels, self.rate = name, fmt.channelCount(), fmt.sampleRate()
            self.channel = min(channel, self.in_channels - 1)
            self.source = QtMultimedia.QAudioSource(device, fmt, self)
            self.source.setBufferSize(int(self.rate * fmt.bytesPerFrame() * .05))
            self.source_io = self.source.start()
            if self.source_io is None or self.source.error() != audio_ns.Error.NoError:
                self.close_input()
                self.failed.emit("無法開啟麥克風。請到 Windows「設定 → 隱私權與安全性 → 麥克風」"
                                 "允許桌面應用程式存取麥克風，並確認錄音介面已連接。")
                return False
            self.timer.start()
            return True

        def close_input(self):
            self.timer.stop()
            if self.source is not None:
                self.source.stop()
                self.source.deleteLater()
            self.source = self.source_io = None

        @property
        def input_open(self):
            return self.source is not None

        def _drain(self):
            if self.source_io is None:
                return
            raw = self.source_io.readAll()
            data = raw.data() if hasattr(raw, "data") else bytes(raw)
            if not data:
                return
            mono = to_mono(data, self.in_format, self.in_channels, self.channel)
            if not len(mono):
                return
            peak = float(np.max(np.abs(mono)))
            self.level.emit(peak)
            if peak >= CLIP_LEVEL and is_clipping(mono):
                self.clipped.emit()
            if self.recording:
                self.peak = max(self.peak, peak)
                self.recorded += len(mono)
                if self.writer is not None:
                    self.writer.write(mono)
                    if self.recorded % (self.rate // 2) < len(mono):
                        self.writer.flush()
                if self.capture is not None:
                    self.capture.append(mono)
                left = -1.0
                if self.start_offset is not None:
                    left = max(0.0, self.backing_seconds - (self.recorded / self.rate - self.start_offset))
                self.progress.emit(self.recorded / self.rate, left)

        # ---- playback
        def _start_playback(self, pcm, out_format, out_name):
            self._drain()  # count everything captured before playback starts
            self.start_offset = self.recorded / self.rate
            self.sink = QtMultimedia.QAudioSink(self.output_device, out_format, self)
            self.sink.setVolume(self.volume)
            self.buffer = QtCore.QBuffer(self)
            self.buffer.setData(QtCore.QByteArray(pcm))
            flags = getattr(QtCore.QIODevice, "OpenModeFlag", QtCore.QIODevice)
            self.buffer.open(flags.ReadOnly)
            self.sink.stateChanged.connect(self._sink_state)
            self.sink.start(self.buffer)

        def _sink_state(self, state):
            if state == audio_ns.State.IdleState and self.mode is not None:
                # Backing (or clicks) finished: keep recording a short tail.
                self.tail_timer.start(2000 if self.mode == "take" else 600)

        def _stop_playback(self):
            if self.sink is not None:
                self.sink.stop()
                self.sink.deleteLater()
            if self.buffer is not None:
                self.buffer.close()
                self.buffer.deleteLater()
            self.sink = self.buffer = None

        def prepare_output(self, device, samples, channels):
            """samples: float32 (frames, channels) at 48 kHz or mono."""
            fmt, name = pick_format(device, 48000, channels)
            if fmt.sampleRate() != 48000 or fmt.channelCount() != channels:
                from scipy import signal as sps
                data = np.asarray(samples, np.float32).reshape(len(samples), -1)
                if fmt.sampleRate() != 48000:
                    data = sps.resample_poly(data, fmt.sampleRate(), 48000, axis=0).astype(np.float32)
                if data.shape[1] != fmt.channelCount():
                    data = np.repeat(data[:, :1], fmt.channelCount(), axis=1)
                samples = data
            frames = len(samples)
            self.output_device = device
            return to_pcm(np.asarray(samples, np.float32).reshape(-1), name), fmt, name, frames / fmt.sampleRate()

        # ---- takes
        def start_take(self, path, out_device, backing, volume, countdown):
            """backing: float32 (frames, 2) at 48 kHz."""
            if not self.input_open:
                self.failed.emit("請先選擇可用的輸入裝置")
                return False
            pcm, fmt, name, seconds = self.prepare_output(out_device, backing, 2)
            self.pending_pcm = (pcm, fmt, name)
            self.backing_seconds = seconds
            self.volume = max(0.0, min(1.0, volume))
            self.writer = WavWriter(path, self.rate, 1)
            self._begin("take", countdown)
            return True

        def stop_take(self):
            if self.mode != "take":
                return
            self._finish()
            writer, self.writer = self.writer, None
            writer.close()
            if self.start_offset is None:
                Path(writer.path).unlink(missing_ok=True)
                self.failed.emit("錄音在伴奏開始前就停止了")
                return
            self.take_finished.emit(TakeResult(str(writer.path), writer.seconds, self.rate,
                                               self.start_offset, self.peak))

        def cancel(self):
            """Stop without reporting a result (window closing, dialog closed)."""
            mode, self.mode = self.mode, None
            self.count_timer.stop()
            self.tail_timer.stop()
            self.recording = False
            self._stop_playback()
            self.capture = None
            self.pending_pcm = None
            if self.writer is not None:
                self.writer.close()
                self.writer = None
            return mode

        # ---- calibration
        def calibrate(self, out_device):
            if not self.input_open:
                self.failed.emit("請先選擇可用的輸入裝置")
                return False
            clicks, self.click_times = click_track(48000)
            stereo = np.repeat(clicks[:, None], 2, axis=1)
            pcm, fmt, name, _ = self.prepare_output(out_device, stereo, 2)
            self.pending_pcm = (pcm, fmt, name)
            self.volume = 1.0
            self.capture = []
            self._begin("calibrate", 0)
            return True

        def _finish_calibration(self):
            captured = np.concatenate(self.capture) if self.capture else np.zeros(0, np.float32)
            self.capture = None
            try:
                median, spread, found = measure_latency(captured, self.rate, self.start_offset or 0,
                                                        self.click_times)
            except ValueError as exc:
                self.failed.emit(str(exc))
                return
            self.calibration_finished.emit(median, spread, found)

        # ---- shared
        def _begin(self, mode, countdown):
            self.mode = mode
            self.recorded, self.peak, self.start_offset = 0, 0.0, None
            self._drain()           # discard audio captured before the take
            self.recorded = 0
            self.recording = True
            self.count_left = int(countdown)
            if self.count_left > 0:
                self.countdown.emit(self.count_left)
                self.count_timer.start()
            else:
                self._start_playback(*self.pending_pcm)

        def _tick(self):
            self.count_left -= 1
            if self.count_left > 0:
                self.countdown.emit(self.count_left)
                return
            self.count_timer.stop()
            self.countdown.emit(0)
            self._start_playback(*self.pending_pcm)

        def _finish(self):
            self.count_timer.stop()
            self.tail_timer.stop()
            self._drain()
            self.recording = False
            self._stop_playback()
            mode, self.mode = self.mode, None
            self.pending_pcm = None
            if mode == "calibrate":
                self._finish_calibration()

        def _tail_done(self):
            if self.mode == "take":
                self.stop_take()
            elif self.mode == "calibrate":
                self._finish()

    return AudioSession


_SESSION = None


def AudioSession(parent=None):
    """Factory: the Qt class is built lazily so this module imports without Qt 6."""
    global _SESSION
    if _SESSION is None:
        _SESSION = _make_session_class()
    return _SESSION(parent)
