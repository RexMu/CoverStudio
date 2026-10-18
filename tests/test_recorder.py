"""Recording logic against a simulated sound card (no Qt or audio device needed).

The fake Qt layer models what matters for timing: a playback device that
plays a buffer in real time, a capture device that delivers audio in 10 ms
periods, and a fixed round-trip latency between them. The real
`AudioSession` state machine runs on top of it with a simulated clock.
"""
import tempfile
import types
import unittest
from pathlib import Path

import numpy as np
from scipy.io import wavfile

import sys

try:
    import saxstudio.qt as qt
except ImportError:  # no Qt installed: the session only needs the fake layer below
    import saxstudio
    qt = types.ModuleType("saxstudio.qt")
    qt.QT6, qt.QtCore, qt.QtMultimedia, qt.Signal = True, None, None, None
    sys.modules["saxstudio.qt"] = qt
    saxstudio.qt = qt
from saxstudio import recorder
from saxstudio.recorder import (WavWriter, click_track, measure_latency, recording_offset,
                                to_mono, to_pcm)

RATE = 48000
PERIOD = 480  # 10 ms capture period


class Sim:
    def __init__(self, latency, sax=None):
        self.now = 0            # world sample index
        self.timers = []
        self.latency = int(round(latency * RATE))
        self.output = np.zeros(RATE * 400, np.float32)  # what the speaker/headphone emits
        self.sax = sax          # callable(world_index_array) -> samples, the player

    def advance(self, seconds):
        end = self.now + int(seconds * RATE)
        while self.now < end:
            self.now += 48  # 1 ms steps
            for timer in list(self.timers):
                if timer.active and self.now >= timer.due:
                    if timer.single:
                        timer.active = False
                    else:
                        timer.due += timer.interval
                    timer.timeout.emit()


SIM = None


class BoundSignal:
    def __init__(self):
        self.slots = []

    def connect(self, slot):
        self.slots.append(slot)

    def emit(self, *args):
        for slot in list(self.slots):
            slot(*args)


class Signal:
    def __init__(self, *types_):
        self.name = None

    def __set_name__(self, owner, name):
        self.name = "_sig_" + name

    def __get__(self, obj, owner):
        if obj is None:
            return self
        if not hasattr(obj, self.name):
            setattr(obj, self.name, BoundSignal())
        return getattr(obj, self.name)


class QObject:
    def __init__(self, parent=None):
        pass

    def deleteLater(self):
        pass


class QTimer(QObject):
    timeout = Signal()

    def __init__(self, parent=None):
        self.interval, self.single, self.active, self.due = 0, False, False, 0
        SIM.timers.append(self)

    def setInterval(self, ms):
        self.interval = int(ms * RATE / 1000)

    def setSingleShot(self, value):
        self.single = value

    def start(self, ms=None):
        if ms is not None:
            self.setInterval(ms)
        self.active, self.due = True, SIM.now + self.interval

    def stop(self):
        self.active = False


class QByteArray:
    def __init__(self, data=b""):
        self._data = bytes(data)

    def data(self):
        return self._data


class QBuffer(QObject):
    def setData(self, array):
        self.array = array

    def open(self, mode):
        return True

    def close(self):
        pass


Enum = types.SimpleNamespace
QtAudio = Enum(Error=Enum(NoError=0, OpenError=1), State=Enum(ActiveState=0, IdleState=2, StoppedState=1))
SampleFormat = Enum(Float="float", Int32="int32", Int16="int16")


class QAudioFormat:
    SampleFormat = SampleFormat

    def __init__(self):
        self.rate, self.channels, self.fmt = RATE, 1, SampleFormat.Float

    def setSampleRate(self, v): self.rate = v
    def setChannelCount(self, v): self.channels = v
    def setSampleFormat(self, v): self.fmt = v
    def sampleRate(self): return self.rate
    def channelCount(self): return self.channels
    def sampleFormat(self): return self.fmt
    def bytesPerFrame(self): return 4 * self.channels


class Device:
    def __init__(self, name, channels=2):
        self.name, self.channels = name, channels

    def isFormatSupported(self, fmt):
        return fmt.sampleFormat() == SampleFormat.Float and fmt.channelCount() <= self.channels

    def preferredFormat(self):
        return QAudioFormat()

    def maximumChannelCount(self):
        return self.channels

    def description(self):
        return self.name

    def id(self):
        return QByteArray(self.name.encode())


class CaptureIO:
    def __init__(self, source):
        self.source = source

    def readAll(self):
        # Only whole 10 ms periods captured so far are available.
        available = (SIM.now // PERIOD) * PERIOD
        a, b = self.source.read_pos, available
        self.source.read_pos = b
        if b <= a:
            return QByteArray(b"")
        n = np.arange(a, b)
        heard = np.where(n - SIM.latency >= 0, SIM.output[np.clip(n - SIM.latency, 0, None)], 0)
        signal = heard + (SIM.sax(n) if SIM.sax else 0)
        channels = self.source.fmt.channelCount()
        frames = np.zeros((len(n), channels), np.float32)
        frames[:, min(1, channels - 1)] = signal  # player is on input 2
        return QByteArray(frames.astype("<f4").tobytes())


class QAudioSource(QObject):
    def __init__(self, device, fmt, parent=None):
        self.fmt = fmt
        self.read_pos = 0

    def setBufferSize(self, n): pass

    def start(self):
        self.read_pos = (SIM.now // PERIOD) * PERIOD
        return CaptureIO(self)

    def stop(self): pass
    def error(self): return QtAudio.Error.NoError


class QAudioSink(QObject):
    stateChanged = Signal()

    def __init__(self, device, fmt, parent=None):
        self.fmt = fmt
        self.volume = 1.0

    def setVolume(self, v):
        self.volume = v

    def start(self, buffer):
        data = np.frombuffer(buffer.array.data(), "<f4").reshape(-1, self.fmt.channelCount())[:, 0]
        start = SIM.now
        SIM.sink_start = start
        SIM.output[start:start + len(data)] = data * self.volume
        end = start + len(data)
        self.idle = QTimer()
        self.idle.setSingleShot(True)
        self.idle.timeout.connect(lambda: self.stateChanged.emit(QtAudio.State.IdleState))
        self.idle.start((end - SIM.now) * 1000 / RATE)

    def stop(self):
        if hasattr(self, "idle"):
            self.idle.stop()


def fake_qt():
    core = types.SimpleNamespace(QObject=QObject, QTimer=QTimer, QBuffer=QBuffer, QByteArray=QByteArray,
                                 QIODevice=Enum(OpenModeFlag=Enum(ReadOnly=1)))
    media = types.SimpleNamespace(QtAudio=QtAudio, QAudioFormat=QAudioFormat, QAudioSource=QAudioSource,
                                  QAudioSink=QAudioSink)
    return core, media


class SessionTestCase(unittest.TestCase):
    def setUp(self):
        self.saved = (qt.QtCore, qt.QtMultimedia, qt.Signal, recorder._SESSION)
        qt.QtCore, qt.QtMultimedia = fake_qt()
        qt.Signal = Signal
        recorder._SESSION = None
        self.temp = tempfile.TemporaryDirectory()

    def tearDown(self):
        qt.QtCore, qt.QtMultimedia, qt.Signal, recorder._SESSION = self.saved
        self.temp.cleanup()

    def session(self, latency, sax=None):
        global SIM
        SIM = Sim(latency, sax)
        s = recorder.AudioSession()
        self.events = {"failed": [], "done": [], "cal": [], "count": []}
        s.failed.connect(self.events["failed"].append)
        s.take_finished.connect(self.events["done"].append)
        s.calibration_finished.connect(lambda *a: self.events["cal"].append(a))
        s.countdown.connect(self.events["count"].append)
        self.assertTrue(s.open_input(Device("介面"), channel=1))
        SIM.advance(.3)
        return s


class SessionTests(SessionTestCase):
    def test_calibration_measures_round_trip_latency(self):
        for latency in (.0123, .0385, .0871):
            s = self.session(latency)
            s.calibrate(Device("耳機"))
            SIM.advance(6)
            self.assertEqual(self.events["failed"], [])
            median, spread, found = self.events["cal"][0]
            self.assertEqual(found, 8)
            # Capture periods add at most one period of jitter.
            self.assertAlmostEqual(median, latency * 1000, delta=PERIOD / RATE * 1000 + .1)

    def test_take_with_countdown_stops_after_backing_and_aligns(self):
        latency = .0412
        # Calibrate first with the same session, as the app does.
        s = self.session(latency)
        s.calibrate(Device("耳機"))
        SIM.advance(6)
        measured = self.events["cal"][0][0]
        # The "player" plays a note exactly 2.0 s into the backing as heard.
        heard_at = {}
        backing = np.zeros((RATE * 5, 2), np.float32)
        backing[RATE * 2:RATE * 2 + 480] = .5

        def sax(n):
            out = np.zeros(len(n), np.float32)
            if "t" in heard_at:
                hit = (n >= heard_at["t"]) & (n < heard_at["t"] + 480)
                out[hit] = .7
            return out
        SIM.sax = sax
        path = Path(self.temp.name) / "錄音.wav"
        s.start_take(str(path), Device("耳機"), backing, volume=1.0, countdown=3)
        SIM.advance(3.05)  # countdown done, playback started
        self.assertEqual(self.events["count"], [3, 2, 1, 0])
        # The player hears the backing's 2.0 s mark after output latency and
        # plays along; capture adds input latency. Here the whole round trip
        # is modelled by SIM.latency, so the note enters the mic when the
        # backing's 2.0 s sample does.
        heard_at["t"] = SIM.sink_start + RATE * 2 + SIM.latency
        SIM.advance(8)
        self.assertEqual(self.events["failed"], [])
        result = self.events["done"][0]
        self.assertGreater(result.seconds, 3 + 5)  # count-in + backing + 2 s tail
        rate, audio = wavfile.read(result.path)
        offset = recording_offset(result.start_offset, measured)
        # The note sits 2.0 s after the backing start on the recording timeline.
        note = np.flatnonzero(np.abs(audio) > .6)[0] / rate
        self.assertAlmostEqual(note - offset, 2.0, delta=.012)

    def test_stop_during_countdown_discards_file(self):
        s = self.session(.03)
        path = Path(self.temp.name) / "短.wav"
        s.start_take(str(path), Device("耳機"), np.zeros((RATE, 2), np.float32), 1.0, 3)
        SIM.advance(1.2)
        s.stop_take()
        self.assertTrue(self.events["failed"])
        self.assertFalse(path.exists())

    def test_cancelled_calibration_reports_nothing(self):
        s = self.session(.03)
        s.calibrate(Device("耳機"))
        SIM.advance(1)
        s.cancel()
        SIM.advance(5)
        self.assertEqual(self.events["cal"], [])
        self.assertEqual(self.events["failed"], [])


class HelperTests(unittest.TestCase):
    def test_wav_writer_survives_crash_and_closes_cleanly(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "錄音" / "a.wav"
            w = WavWriter(path, RATE)
            w.write(np.full(1000, .5))
            w.flush()
            w.write(np.full(300, -.25))
            rate, data = wavfile.read(path)  # "crash" before close: flushed part is valid
            self.assertEqual((rate, len(data)), (RATE, 1000))
            w.close()
            rate, data = wavfile.read(path)
            self.assertEqual(len(data), 1300)
            self.assertAlmostEqual(float(data[-1]), -.25)

    def test_measure_latency_matched_filter(self):
        clicks, times = click_track(RATE)
        for latency in (.012, .0385, .21):
            rec = np.zeros(RATE * 6, np.float32)
            for t in times:
                i = int(round((.73 + t + latency) * RATE))
                j = int(round(t * RATE))
                rec[i:i + 192] += clicks[j:j + 192] * .2
            rec += np.random.default_rng(3).normal(0, .003, len(rec)).astype(np.float32)
            median, spread, found = measure_latency(rec, RATE, .73, times)
            self.assertEqual(found, 8)
            self.assertAlmostEqual(median, latency * 1000, delta=.1)
        with self.assertRaises(ValueError):
            measure_latency(np.zeros(RATE * 6, np.float32), RATE, .73, times)

    def test_pcm_round_trip_and_channel_pick(self):
        frames = np.array([[.5, -.5], [.25, -.25]], np.float32)
        for fmt in ("float", "int32", "int16"):
            raw = to_pcm(frames.reshape(-1), fmt)
            np.testing.assert_allclose(to_mono(raw, fmt, 2, 1), [-.5, -.25], atol=1e-4)

    def test_offset_adds_latency(self):
        self.assertAlmostEqual(recording_offset(3.0, 38.5), 3.0385)


if __name__ == "__main__":
    unittest.main()


class ClipDetectionTest(unittest.TestCase):
    def test_single_hot_samples_are_not_clipping(self):
        self.assertFalse(recorder.is_clipping(np.array([0, 1, 0, -1, 0, 1], np.float32)))
        self.assertFalse(recorder.is_clipping(np.full(100, .9, np.float32)))

    def test_sustained_full_scale_is_clipping(self):
        block = np.zeros(200, np.float32)
        block[50:53] = -1
        self.assertTrue(recorder.is_clipping(block))
