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


def balance(pan):
    """Left/right gains for a stereo balance control; centre keeps unity gain."""
    pan = max(-1.0, min(1.0, float(pan)))
    return 1.0 - max(0.0, pan), 1.0 + min(0.0, pan)


def pan_filter(pan):
    if abs(pan) < 1e-6:
        return None
    left, right = balance(pan)
    return f"pan=stereo|c0={left:.6f}*c0|c1={right:.6f}*c1"


def effect_filters(fx, source, label, ir_input, tag):
    """EQ / compressor / reverb on `source`; result in `label`."""
    chain = []
    if fx.eq_enabled:
        if fx.highpass > 0:
            chain.append(f"highpass=f={fx.highpass}")
        chain.extend(f"equalizer=f={b.frequency}:t=q:w={b.q}:g={b.gain}" for b in fx.bands)
    if fx.compressor_enabled:
        chain.append(f"acompressor=threshold={10**(fx.threshold/20):.9f}:ratio={fx.ratio}:"
                     f"attack={fx.attack}:release={fx.release}:makeup={10**(fx.makeup/20):.9f}:knee=2.8")
    processed = f"[p{tag}]"
    filters = [f"{source}{','.join(chain) or 'anull'}{processed}"]
    if ir_input is not None:
        filters += [f"{processed}asplit=2[dry{tag}][send{tag}]",
                    f"[{ir_input}:a:0]aformat=sample_fmts=fltp:channel_layouts=stereo[ir{tag}]",
                    f"[send{tag}][ir{tag}]afir=dry=1:wet=1:irnorm=-1:irfmt=input:minp=256[wet{tag}]",
                    f"[dry{tag}]volume={1-fx.mix:.9f}[dl{tag}]",
                    f"[wet{tag}]volume={fx.mix:.9f}[wl{tag}]",
                    f"[dl{tag}][wl{tag}]amix=inputs=2:normalize=0:duration=first{label}"]
    else:
        filters.append(f"{processed}anull{label}")
    return filters


def render_mix(project: Project, output, cancel=None, progress=None):
    """Render full source timeline. Edits are applied only at export/playback."""
    project.validate()
    if not project.source or project.duration <= 0:
        raise ValueError("請先錄音" if project.is_record else "請先匯入影片")
    info = probe(project.source, cancel)
    if not info["audio"]:
        raise ValueError("錄音沒有音訊" if project.is_record else "影片沒有音訊")
    output = Path(output)
    head = ["asetpts=PTS-STARTPTS", f"aresample={RATE}", "aformat=sample_fmts=fltp:channel_layouts=stereo"]
    with tempfile.TemporaryDirectory(prefix="sax-render-") as folder:
        args = [binary("ffmpeg"), "-v", "error", "-y"]
        inputs = []

        def add_input(path):
            nonlocal args
            args += ["-i", str(path)]
            inputs.append(path)
            return len(inputs) - 1
        # (input index, effects, shift on track 1's timeline, gain, pan) per recording track.
        sources = [(add_input(project.source), project.effects, audio_origin(info),
                    0 if project.video_muted else 10**(project.video_db/20), project.video_pan)]
        for k, track in enumerate(project.tracks, start=1):
            if track.recording and track.duration > 0:
                sources.append((add_input(track.recording), track.effects, project.track_shift(k),
                                0 if track.muted else 10**(track.db/20), track.pan))
        backing = add_input(project.backing) if project.backing else None
        filters, labels = [], []
        for n, (index, fx, shift, gain, pan) in enumerate(sources):
            ir_input = None
            if fx.reverb_enabled and fx.mix > 0:
                ir = Path(folder) / f"room{n}.wav"
                impulse(ir, fx.decay, fx.predelay)
                ir_input = add_input(ir)
            source = f"[{index}:a:0]" + ",".join(head + [shift_filter(shift)]) + ","
            filters += effect_filters(fx, source, f"[fx{n}]", ir_input, n)
            tail = [f"volume={gain:.9f}"] + ([pan_filter(pan)] if pan_filter(pan) else []) + \
                ["apad", f"atrim=duration={project.duration:.9f}"]
            filters.append(f"[fx{n}]" + ",".join(tail) + f"[t{n}]")
            labels.append(f"[t{n}]")
        if backing is not None:
            bg = 0 if project.backing_muted else 10**(project.backing_db/20)
            extra = [pan_filter(project.backing_pan)] if pan_filter(project.backing_pan) else []
            filters.append(f"[{backing}:a:0]" + ",".join(head + [shift_filter(project.offset), f"volume={bg:.9f}"]
                                                      + extra + ["apad", f"atrim=duration={project.duration:.9f}"])
                           + "[backing]")
            labels.append("[backing]")
        if len(labels) > 1:
            filters.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=first[mixed]")
        else:
            filters.append(f"{labels[0]}anull[mixed]")
        if project.effects.limiter_enabled:
            filters.append(f"[mixed]alimiter=limit={LIMIT:.6f}:level=0:latency=1[out]")
        else:
            filters.append("[mixed]anull[out]")
        args += ["-filter_complex", ";".join(filters), "-map", "[out]", "-t", str(project.duration),
                 "-c:a", "pcm_f32le", "-f", "wav", str(output)]
        if progress:
            progress("正在處理 EQ、壓縮、混響與多軌混音…" if len(sources) > 1 else
                     "正在處理 EQ、壓縮、混響與雙軌混音…")
        try:
            run(args, cancel)
        except BaseException:
            output.unlink(missing_ok=True)
            raise
    return str(output)


def dry_stem(path, destination, shift, duration, clips, mono, cancel=None):
    """One untouched stem: shifted onto the project timeline, cut to the kept
    clips, 48 kHz / 24-bit. No effects, volume, pan or limiter."""
    info = probe(path, cancel)
    if not info["audio"]:
        raise ValueError("檔案沒有音訊")
    channels = int(info["audio"].get("channels") or 1)
    chain = ["asetpts=PTS-STARTPTS", f"aresample={RATE}"]
    if mono and channels > 1:
        # Equal-weight downmix (the recorder normally writes mono already).
        chain.append("pan=mono|c0=" + "+".join(f"{1/channels:.6f}*c{i}" for i in range(channels)))
    elif not mono:
        chain.append("aformat=channel_layouts=stereo")
    chain += [shift_filter(shift), "apad", f"atrim=duration={duration:.9f}", "asetpts=PTS-STARTPTS"]
    n = len(clips)
    filters = ["[0:a:0]" + ",".join(chain) + "[full]"]
    if n == 1:
        c = clips[0]
        filters.append(f"[full]atrim=start={c.start:.9f}:end={c.end:.9f},asetpts=PTS-STARTPTS[out]")
    else:
        filters.append(f"[full]asplit={n}" + "".join(f"[s{i}]" for i in range(n)))
        for i, c in enumerate(clips):
            filters.append(f"[s{i}]atrim=start={c.start:.9f}:end={c.end:.9f},asetpts=PTS-STARTPTS[c{i}]")
        filters.append("".join(f"[c{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[out]")
    args = [binary("ffmpeg"), "-v", "error", "-y", "-i", str(path), "-filter_complex", ";".join(filters),
            "-map", "[out]", "-ar", str(RATE), "-c:a", "pcm_s24le", "-f", "wav", str(destination)]
    try:
        run(args, cancel)
    except BaseException:
        Path(destination).unlink(missing_ok=True)
        raise


def stem_plan(project: Project, include_backing=True):
    """[(file name, source path, shift, mono)] for the dry-stem export."""
    from .storage import safe_stem
    plan = []
    if include_backing and project.backing:
        plan.append(("00-伴奏.wav", project.backing, project.offset, False))
    for k in range(project.track_count):
        track = project.track(k)
        if track.recording and track.duration > 0:
            name = safe_stem(track.name or f"音軌{k + 1}", 30)
            shift = project.track_shift(k) if k else None   # track 1: origin of its own file
            plan.append((f"{k + 1:02}-{name}.wav", track.recording, shift, True))
    return plan


def export_stems(project: Project, folder, include_backing=True, cancel=None, progress=None):
    """Write each recording (and optionally the backing) as its own dry WAV.

    The stems share start and length, so they line up when dropped into any
    DAW. Time edits (cuts) are applied; EQ, compression, reverb, volume, pan,
    mute and the limiter are not. Returns the folder actually written.
    """
    project.validate()
    if not project.is_record:
        raise ValueError("分軌乾聲只能在錄音模式匯出")
    if not project.clips:
        raise ValueError("沒有保留片段，無法匯出")
    plan = stem_plan(project, include_backing)
    if not [p for p in plan if not p[0].startswith("00-")]:
        raise ValueError("還沒有錄音，沒有可匯出的乾聲")
    from .storage import unique_path
    folder = Path(folder)
    final = unique_path(folder.parent, folder.name, "")
    final.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=".sax-stems-", dir=final.parent))
    try:
        for n, (name, path, shift, mono) in enumerate(plan, start=1):
            if progress:
                progress(f"正在輸出乾聲 {n}/{len(plan)}：{name}")
            if shift is None:
                shift = audio_origin(probe(path, cancel))
            dry_stem(path, work / name, shift, project.duration, project.clips, mono, cancel)
        work.rename(final)
    except BaseException:
        import shutil
        shutil.rmtree(work, ignore_errors=True)
        raise
    return str(final)


def export(project: Project, destination, cancel=None, progress=None):
    project.validate()
    destination = Path(destination)
    if not project.clips:
        raise ValueError("沒有保留片段，無法匯出")
    if destination.suffix.lower() not in (".mp4", ".wav", ".mp3"):
        raise ValueError("匯出格式請選擇 MP4、WAV 或 MP3")
    if project.is_record and destination.suffix.lower() == ".mp4":
        raise ValueError("錄音模式沒有畫面，請匯出 WAV 或 MP3")
    sources = [project.video, project.backing, project.recording] + [t.recording for t in project.tracks]
    if destination.resolve() in [Path(p).resolve() for p in sources if p]:
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
