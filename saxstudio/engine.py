from __future__ import annotations

import math
import tempfile
from pathlib import Path

import numpy as np
from scipy import signal
from scipy.io import wavfile

from .media import binary, probe, run
from .model import Project

RATE = 48000
# Sample-peak ceiling (-1 dBFS) leaves headroom for AAC/MP3 inter-sample peaks.
LIMIT = 10 ** (-1 / 20)


def impulse(path, decay, predelay):
    """Deterministic stereo room response; decay is the RT60 in seconds."""
    rng = np.random.default_rng(7291)
    n = int(RATE * decay)
    t = np.arange(n) / RATE
    noise = rng.standard_normal((n, 2))
    noise = signal.sosfilt(signal.butter(2, 6000, fs=RATE, output="sos"), noise, axis=0)
    tail = noise * np.exp(-math.log(1000)*t[:, None]/decay)
    # L2 normalization keeps wet loudness relatively stable across decay settings.
    tail *= .38 / np.sqrt(np.sum(tail*tail, axis=0, keepdims=True))
    for delay, gain in [(.009, .28), (.023, .20), (.037, .15), (.061, .10)]:
        idx = int(delay * RATE)
        if idx < n:
            tail[idx] += [gain, gain*.9]
    tail = np.pad(tail, ((round(predelay*.001*RATE), 0), (0, 0)))
    wavfile.write(str(path), RATE, tail.astype(np.float32))


def audio_origin(info):
    """Audio's presentation start relative to the first video frame."""
    return float((info.get("audio") or {}).get("start_time", 0)) - float((info.get("video") or {}).get("start_time", 0))


def video_lead(info):
    """Video's first frame relative to the container start used by input -ss."""
    return max(0.0, float((info.get("video") or {}).get("start_time", 0) or 0) - info.get("start", 0.0))


def shift_filter(offset):
    if offset >= 0:
        # Sample-level precision, including fractional milliseconds.
        return f"adelay={round(offset*RATE)}S:all=1"
    return f"atrim=start={-offset:.9f},asetpts=PTS-STARTPTS"


def render_mix(project: Project, output, cancel=None, progress=None):
    """Render full source timeline. Edits are applied only at export/playback."""
    project.validate()
    if not project.source or project.duration <= 0:
        raise ValueError("請先錄音" if project.is_record else "請先匯入影片")
    info = probe(project.source, cancel)
    if not info["audio"]:
        raise ValueError("錄音沒有音訊" if project.is_record else "影片沒有音訊")
    fx = project.effects
    output = Path(output)
    with tempfile.TemporaryDirectory(prefix="sax-render-") as folder:
        ir = Path(folder) / "room.wav"
        args = [binary("ffmpeg"), "-v", "error", "-y", "-i", project.source]
        inputs = 1
        if project.backing:
            args += ["-i", project.backing]
            inputs += 1
        reverb = fx.reverb_enabled and fx.mix > 0
        if reverb:
            impulse(ir, fx.decay, fx.predelay)
            args += ["-i", str(ir)]
        filters = []
        chain = ["asetpts=PTS-STARTPTS", f"aresample={RATE}",
                 "aformat=sample_fmts=fltp:channel_layouts=stereo", shift_filter(audio_origin(info))]
        if fx.eq_enabled:
            if fx.highpass > 0:
                chain.append(f"highpass=f={fx.highpass}")
            chain.extend(f"equalizer=f={b.frequency}:t=q:w={b.q}:g={b.gain}" for b in fx.bands)
        if fx.compressor_enabled:
            chain.append(f"acompressor=threshold={10**(fx.threshold/20):.9f}:ratio={fx.ratio}:"
                         f"attack={fx.attack}:release={fx.release}:makeup={10**(fx.makeup/20):.9f}:knee=2.8")
        filters.append("[0:a:0]" + ",".join(chain) + "[processed]")
        if reverb:
            filters += ["[processed]asplit=2[dry][send]",
                        f"[{inputs}:a:0]aformat=sample_fmts=fltp:channel_layouts=stereo[ir]",
                        "[send][ir]afir=dry=1:wet=1:irnorm=-1:irfmt=input:minp=256[wet]",
                        f"[dry]volume={1-fx.mix:.9f}[drylevel]",
                        f"[wet]volume={fx.mix:.9f}[wetlevel]",
                        "[drylevel][wetlevel]amix=inputs=2:normalize=0:duration=first[effected]"]
        else:
            filters.append("[processed]anull[effected]")
        vg = 0 if project.video_muted else 10**(project.video_db/20)
        filters.append(f"[effected]volume={vg:.9f},apad,atrim=duration={project.duration:.9f}[sax]")
        if project.backing:
            bg = 0 if project.backing_muted else 10**(project.backing_db/20)
            filters.append(f"[1:a:0]asetpts=PTS-STARTPTS,aresample={RATE},"
                           "aformat=sample_fmts=fltp:channel_layouts=stereo,"
                           f"{shift_filter(project.offset)},volume={bg:.9f},apad,"
                           f"atrim=duration={project.duration:.9f}[backing]")
            filters.append("[sax][backing]amix=inputs=2:normalize=0:duration=first[mixed]")
        else:
            filters.append("[sax]anull[mixed]")
        if fx.limiter_enabled:
            filters.append(f"[mixed]alimiter=limit={LIMIT:.6f}:level=0:latency=1[out]")
        else:
            filters.append("[mixed]anull[out]")
        args += ["-filter_complex", ";".join(filters), "-map", "[out]", "-t", str(project.duration),
                 "-c:a", "pcm_f32le", "-f", "wav", str(output)]
        if progress:
            progress("正在處理 EQ、壓縮、混響與雙軌混音…")
        try:
            run(args, cancel)
        except BaseException:
            output.unlink(missing_ok=True)
            raise
    return str(output)


def export(project: Project, destination, cancel=None, progress=None):
    project.validate()
    destination = Path(destination)
    if not project.clips:
        raise ValueError("沒有保留片段，無法匯出")
    if destination.suffix.lower() not in (".mp4", ".wav", ".mp3"):
        raise ValueError("匯出格式請選擇 MP4、WAV 或 MP3")
    if project.is_record and destination.suffix.lower() == ".mp4":
        raise ValueError("錄音模式沒有畫面，請匯出 WAV 或 MP3")
    if destination.resolve() in [Path(p).resolve() for p in (project.video, project.backing, project.recording) if p]:
        raise ValueError("匯出檔不能覆蓋原始影片或伴奏")
    # Write next to the destination, then atomically replace after successful completion.
    with tempfile.TemporaryDirectory(prefix="sax-export-") as folder:
        mix = Path(folder) / "mix.wav"
        render_mix(project, mix, cancel, progress)
        args = [binary("ffmpeg"), "-v", "error", "-y"]
        video = destination.suffix.lower() == ".mp4"
        # Input -ss counts from the container start, while project time counts
        # from the first video frame; compensate so cuts stay in sync.
        lead = video_lead(probe(project.video, cancel)) if video else 0.0
        n = len(project.clips)
        filters = []
        # Independent seeks let FFmpeg apply backpressure per clip. Splitting a
        # single full-resolution video into concat branches can buffer minutes
        # of decoded future frames while the first retained clip is consumed.
        input_index = 0
        for i, c in enumerate(project.clips):
            seek = ["-ss", f"{c.start:.9f}", "-t", f"{c.end-c.start:.9f}"]
            if video:
                args += ["-ss", f"{c.start+lead:.9f}", "-t", f"{c.end-c.start:.9f}", "-i", project.video]
                filters.append(f"[{input_index}:v:0]setpts=PTS-STARTPTS,"
                               f"fps=30,scale=trunc(iw/2)*2:trunc(ih/2)*2,setsar=1[vcut{i}]")
                input_index += 1
            args += seek + ["-i", str(mix)]
            filters.append(f"[{input_index}:a:0]asetpts=PTS-STARTPTS[acut{i}]")
            input_index += 1
        labels = "".join((f"[vcut{i}]" if video else "") + f"[acut{i}]" for i in range(n))
        filters.append(labels + f"concat=n={n}:v={int(video)}:a=1" + ("[vout]" if video else "") + "[aout]")
        args += ["-filter_complex", ";".join(filters), "-map", "[aout]"]
        if video:
            args += ["-map", "[vout]", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
                     "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", "-f", "mp4"]
        elif destination.suffix.lower() == ".wav":
            args += ["-c:a", "pcm_s24le", "-f", "wav"]
        else:
            args += ["-c:a", "libmp3lame", "-b:a", "320k", "-f", "mp3"]
        with tempfile.NamedTemporaryFile(prefix=".sax-", suffix=destination.suffix,
                                         dir=destination.parent, delete=False) as temp:
            partial = Path(temp.name)
        args += [str(partial)]
        if progress:
            progress("正在剪輯與編碼輸出…（保留片段會依序接合）")
        try:
            run(args, cancel)
            partial.replace(destination)
        finally:
            partial.unlink(missing_ok=True)
    return str(destination)
