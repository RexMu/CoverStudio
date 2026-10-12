from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class EQBand:
    frequency: float
    gain: float = 0.0
    q: float = 1.0


@dataclass
class Effects:
    eq_enabled: bool = False
    bands: list[EQBand] = field(default_factory=lambda: [
        EQBand(100), EQBand(350), EQBand(2500), EQBand(8000)])
    highpass: float = 60.0
    compressor_enabled: bool = False
    threshold: float = -18.0
    ratio: float = 3.0
    attack: float = 15.0
    release: float = 120.0
    makeup: float = 0.0
    reverb_enabled: bool = False
    mix: float = 0.18
    decay: float = 1.6
    predelay: float = 20.0
    limiter_enabled: bool = True


@dataclass
class Clip:
    start: float
    end: float


@dataclass
class Project:
    video: str = ""
    backing: str = ""
    duration: float = 0.0
    # Positive offset: backing sample 0 belongs at this video source time.
    offset: float = 0.0
    video_db: float = 0.0
    backing_db: float = -6.0
    video_muted: bool = False
    backing_muted: bool = False
    effects: Effects = field(default_factory=Effects)
    clips: list[Clip] = field(default_factory=list)

    @property
    def output_duration(self):
        return sum(c.end - c.start for c in self.clips)

    def validate(self):
        def bounded(value, lo, hi, label):
            if not isinstance(value, (int, float)) or not math.isfinite(value) or not lo <= value <= hi:
                raise ValueError(f"{label} 超出允許範圍")
        bounded(self.duration, 0, 86400, "影片長度")
        bounded(self.offset, -86400, 86400, "伴奏位移")
        for v in (self.video_db, self.backing_db):
            bounded(v, -60, 12, "音量")
        fx = self.effects
        for name, lo, hi in [("highpass", 0, 400), ("threshold", -60, 0),
                             ("ratio", 1, 20), ("attack", 0.1, 200),
                             ("release", 10, 2000), ("makeup", 0, 24),
                             ("mix", 0, 1), ("decay", 0.2, 5), ("predelay", 0, 150)]:
            bounded(getattr(fx, name), lo, hi, name)
        if len(fx.bands) != 4:
            raise ValueError("EQ 必須有四個頻段")
        for b in fx.bands:
            bounded(b.frequency, 20, 20000, "EQ 頻率")
            bounded(b.gain, -18, 18, "EQ 增益")
            bounded(b.q, 0.1, 10, "EQ Q")
        prev = 0.0
        for c in self.clips:
            bounded(c.start, prev, self.duration, "片段起點")
            bounded(c.end, c.start + 0.001, self.duration + 0.001, "片段終點")
            prev = c.end

    def split(self, position):
        for i, c in enumerate(self.clips):
            if c.start + .02 < position < c.end - .02:
                self.clips[i:i + 1] = [Clip(c.start, position), Clip(position, c.end)]
                return True
        return False

    def trim(self, start, end):
        if end - start < .05:
            raise ValueError("保留範圍至少需要 0.05 秒")
        self.clips = [Clip(max(c.start, start), min(c.end, end)) for c in self.clips
                      if min(c.end, end) - max(c.start, start) >= .001]
        if not self.clips:
            raise ValueError("範圍內沒有可保留片段")

    def trim_to_backing(self, start, end, before=3.0, after=2.0):
        """Keep only the performance: `before` seconds ahead of the audible
        backing start to `after` seconds past its audible end.

        `start`/`end` are in backing-track time; `offset` maps them onto the
        video timeline. Replaces all existing clips and returns the kept range.
        """
        if end <= start:
            raise ValueError("伴奏有聲範圍不正確")
        keep_start = max(0.0, self.offset + start - before)
        keep_end = min(self.duration, self.offset + end + after)
        if keep_end - keep_start < .05:
            raise ValueError("伴奏不在影片的時間範圍內，請先確認伴奏對齊")
        self.clips = [Clip(keep_start, keep_end)]
        return keep_start, keep_end

    def save(self, path):
        self.validate()
        path = Path(path)
        data = asdict(self)
        data["version"] = 1
        for key in ("video", "backing"):
            if data[key]:
                # Absolute paths support drives different from the project drive.
                data[key] = str(Path(data[key]).resolve())
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    @classmethod
    def load(cls, path):
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("專案檔無法讀取，檔案可能已損毀") from exc
        if not isinstance(data, dict) or data.pop("version", None) != 1:
            raise ValueError("不支援這個專案版本")
        try:
            effects = data.pop("effects")
            effects["bands"] = [EQBand(**b) for b in effects["bands"]]
            clips = [Clip(**c) for c in data.pop("clips")]
            p = cls(**data, effects=Effects(**effects), clips=clips)
        except (KeyError, TypeError, AttributeError) as exc:
            raise ValueError("專案檔格式不正確或缺少必要欄位") from exc
        for name in ("video", "backing"):
            value = getattr(p, name)
            if value and not Path(value).is_absolute():
                setattr(p, name, str((Path(path).parent / value).resolve()))
        p.validate()
        return p
