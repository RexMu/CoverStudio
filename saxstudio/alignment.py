"""Spectral fingerprint alignment robust to gain and partial instrument overlap."""
from dataclasses import dataclass

import numpy as np
from scipy import signal

from .media import decode_mono


@dataclass
class Alignment:
    offset: float
    confidence: float
    agreement: float
    message: str


def features(x, rate=8000, hop=256):
    if len(x) < 1024 or np.sqrt(np.mean(x * x)) < 1e-6:
        raise ValueError("音訊太短或過於安靜，無法對齊")
    _, _, z = signal.stft(x, rate, nperseg=1024, noverlap=1024-hop, boundary=None, padded=False)
    power = np.abs(z)
    edges = np.unique(np.round(np.geomspace(8, 500, 33)).astype(int))
    bands = np.array([np.mean(power[a:b], axis=0) for a, b in zip(edges[:-1], edges[1:])])
    log = np.log(np.maximum(bands, 1e-7))
    # Remove static coloration and common broadband changes.
    log -= np.median(log, axis=1, keepdims=True)
    log -= np.mean(log, axis=0, keepdims=True)
    log /= np.maximum(np.std(log, axis=1, keepdims=True), .3)
    return np.clip(log, -3, 3)


def align_samples(video, backing, rate=8000, max_shift=90.0):
    hop = 256
    a, b = features(video, rate, hop), features(backing, rate, hop)
    score = sum(signal.correlate(x, y, mode="full", method="fft") for x, y in zip(a, b))
    ea = signal.correlate(np.sum(a*a, axis=0), np.ones(b.shape[1]), "full", method="fft")
    eb = signal.correlate(np.ones(a.shape[1]), np.sum(b*b, axis=0), "full", method="fft")
    overlap = signal.correlate(np.ones(a.shape[1]), np.ones(b.shape[1]), "full", method="fft")
    lags = signal.correlation_lags(a.shape[1], b.shape[1])
    score /= np.sqrt(np.maximum(ea * eb, 1e-12))
    min_overlap = min(a.shape[1], b.shape[1]) * .35
    valid = (np.abs(lags) * hop / rate <= max_shift) & (overlap >= max(30, min_overlap))
    score[~valid] = -np.inf
    i = int(np.argmax(score))
    if not np.isfinite(score[i]):
        raise ValueError("可比對的重疊音訊不足")
    lag = int(lags[i])
    confidence = float(np.clip(score[i], 0, 1))
    # Measure ambiguity outside the immediate neighboring bins.
    other = score.copy()
    other[max(0, i-8):i+9] = -np.inf
    second = np.max(other)
    agreement = float(confidence - second) if np.isfinite(second) else confidence
    coarse = lag * hop / rate
    # Phase correlation of high-passed waveform refines the best fingerprint lag.
    # Do not refine when microphone/acoustics give no unambiguous waveform peak.
    offset = coarse
    shift = round(coarse * rate)
    va, vb = max(0, shift), max(0, -shift)
    # Prefer the beginning of the overlap, where this recording workflow has
    # an accompaniment-only intro. Long solo sections dilute waveform coherence.
    n = min(len(video)-va, len(backing)-vb, rate*8)
    if n > rate:
        sos = signal.butter(3, [180, 3200], btype="bandpass", fs=rate, output="sos")
        x = signal.sosfilt(sos, video[va:va+n])
        y = signal.sosfilt(sos, backing[vb:vb+n])
        c = signal.correlate(x, y, "full", method="fft")
        center = n-1
        radius = round(rate * .12)
        window = c[center-radius:center+radius+1]
        k = int(np.argmax(np.abs(window)))
        peak = abs(window[k]) / max(1e-12, np.linalg.norm(x)*np.linalg.norm(y))
        if peak > .1:
            offset = (shift + k-radius) / rate
    reliable = confidence >= .32 and agreement >= .025
    message = "比對清楚，請播放前奏核對" if reliable else "可信度偏低；請核對前奏並手動微調"
    return Alignment(offset, confidence, agreement, message)


def align_files(video, backing, seconds=90, cancel=None):
    a = decode_mono(video, duration=seconds, cancel=cancel)
    b = decode_mono(backing, duration=seconds, cancel=cancel)
    return align_samples(a, b, max_shift=min(60, seconds*.6))
