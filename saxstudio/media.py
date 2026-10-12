from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np


class Cancelled(Exception):
    pass


def binary(name):
    suffix = ".exe" if os.name == "nt" else ""
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    bundled = root / "tools" / (name + suffix)
    result = str(bundled) if bundled.is_file() else shutil.which(name)
    if not result:
        raise RuntimeError(f"找不到 {name}。請將 ffmpeg.exe 與 ffprobe.exe 放到 tools 資料夾。")
    return result


def run(args, cancel=None):
    kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs) as proc:
        while True:
            try:
                out, err = proc.communicate(timeout=.15)
                break
            except subprocess.TimeoutExpired:
                if cancel and cancel.is_set():
                    proc.kill()
                    proc.communicate()
                    raise Cancelled("作業已取消")
        if cancel and cancel.is_set():
            raise Cancelled("作業已取消")
        if proc.returncode:
            message = err.decode("utf-8", errors="replace")[-3000:]
            raise RuntimeError(f"影音處理失敗：\n{message}")
        return out


def probe(path, cancel=None):
    raw = run([binary("ffprobe"), "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)], cancel)
    data = json.loads(raw)
    streams = data.get("streams", [])
    durations = [float(s["duration"]) for s in streams if s.get("duration") not in (None, "N/A")]
    try:
        duration = float(data["format"]["duration"])
    except (KeyError, ValueError):
        duration = max(durations, default=0)
    if duration <= 0 or duration > 86400:
        raise ValueError("無法讀取長度，或檔案超過 24 小時")
    def number(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
    # Cover art in MP3/M4A files is reported as a video stream; ignore it.
    video = next((s for s in streams if s.get("codec_type") == "video"
                  and not (s.get("disposition") or {}).get("attached_pic")), None)
    return {"duration": duration, "video": video,
            "audio": next((s for s in streams if s.get("codec_type") == "audio"), None),
            "start": number(data.get("format", {}).get("start_time"))}


MIN_FFMPEG = (7, 1)
REQUIRED_FILTERS = ("afir", "acompressor", "alimiter", "equalizer", "highpass", "adelay", "amix", "apad")
REQUIRED_ENCODERS = ("libx264", "libmp3lame", "aac", "pcm_s24le")


def check_ffmpeg():
    """Return a list of problems with the available FFmpeg; empty when usable."""
    import re
    try:
        ffmpeg, _ = binary("ffmpeg"), binary("ffprobe")
    except RuntimeError as exc:
        return [str(exc)]
    problems = []
    banner = run([ffmpeg, "-hide_banner", "-version"]).decode("utf-8", "replace")
    match = re.search(r"ffmpeg version n?(\d+)\.(\d+)", banner)
    if match and (int(match[1]), int(match[2])) < MIN_FFMPEG:
        problems.append(f"FFmpeg 版本 {match[1]}.{match[2]} 太舊，需要 7.1 或更新版")
    filters = run([ffmpeg, "-hide_banner", "-filters"]).decode("utf-8", "replace")
    names = {line.split()[1] for line in filters.splitlines() if len(line.split()) > 2}
    problems += [f"FFmpeg 缺少濾鏡 {f}" for f in REQUIRED_FILTERS if f not in names]
    if "afir" in names and "irnorm" not in run([ffmpeg, "-hide_banner", "-h", "filter=afir"]).decode("utf-8", "replace"):
        problems.append("FFmpeg 的 afir 濾鏡不支援 irnorm（混響需要 FFmpeg 7.1 以上）")
    encoders = run([ffmpeg, "-hide_banner", "-encoders"]).decode("utf-8", "replace")
    names = {line.split()[1] for line in encoders.splitlines() if len(line.split()) > 2}
    problems += [f"FFmpeg 缺少編碼器 {e}" for e in REQUIRED_ENCODERS if e not in names]
    return problems


def decode_mono(path, rate=8000, duration=None, cancel=None):
    args = [binary("ffmpeg"), "-v", "error", "-i", str(path)]
    if duration is not None:
        args += ["-t", str(duration)]
    args += ["-vn", "-ac", "1", "-ar", str(rate), "-f", "f32le", "pipe:1"]
    samples = np.frombuffer(run(args, cancel), dtype="<f4").copy()
    if not len(samples):
        raise ValueError("檔案沒有可解碼的音訊")
    return samples


def active_range(path, rate=8000, threshold_db=-40.0, cancel=None):
    """First/last moment the track is audibly playing, in seconds.

    Leading/trailing digital silence and the inaudible end of a fade-out are
    ignored: a 10 ms window counts as playing when its peak is within
    `threshold_db` of the track's loudest peak.
    """
    x = decode_mono(path, rate=rate, cancel=cancel)
    window = max(1, rate // 100)
    padded = np.pad(np.abs(x), (0, (-len(x)) % window))
    peaks = padded.reshape(-1, window).max(axis=1)
    loudest = float(peaks.max(initial=0))
    if loudest < 1e-4:
        raise ValueError("伴奏幾乎沒有聲音")
    threshold = max(loudest * 10 ** (threshold_db / 20), 1e-3)
    playing = np.flatnonzero(peaks >= threshold)
    return float(playing[0] * window / rate), float(min(len(x), (playing[-1] + 1) * window) / rate)


def waveform(path, cancel=None):
    # 1 kHz is enough for a display envelope; alignment decodes independently.
    x = decode_mono(path, rate=1000, cancel=cancel)
    width = max(1, int(np.ceil(len(x) / 1800)))
    padded = np.pad(x, (0, (-len(x)) % width))
    peaks = np.max(np.abs(padded.reshape(-1, width)), axis=1)
    peaks /= max(.01, float(np.quantile(peaks, .995)))
    return peaks.clip(0, 1)


def thumbnail(path, output, cancel=None):
    run([binary("ffmpeg"), "-v", "error", "-y", "-ss", "0", "-i", str(path),
         "-frames:v", "1", "-vf", "scale=640:-2", str(output)], cancel)
