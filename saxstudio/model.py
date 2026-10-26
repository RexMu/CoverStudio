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
class Punch:
    """A punch-in: everything from `start` (recording time) on is take `number`."""
    start: float
    number: int


@dataclass
class PunchUndo:
    """Track-1 state before a punch-in, restored by undo."""
    recording: str
    duration: float
    clips: list[Clip] = field(default_factory=list)


def take_segments(duration, punches):
    """[(start, end, take number)] over a recording; 0 = original take."""
    segments = [[0.0, duration, 0]]
    for punch in punches:
        # A later punch replaces everything after its start, even earlier punches.
        segments = [s for s in segments if s[0] < punch.start]
        if segments:
            segments[-1][1] = punch.start
        segments.append([punch.start, duration, punch.number])
    return [tuple(s) for s in segments if s[1] - s[0] > 1e-6]


@dataclass
class Track:
    """An extra recording track (record mode, tracks 2 and 3).

    Each track is recorded against the backing on its own timeline;
    `backing_offset` is where backing sample 0 lies on that timeline, so the
    track sits at `project.offset - backing_offset` on track 1's timeline and
    follows the backing when the project offset is adjusted.
    """
    name: str = "Tenor"
    recording: str = ""
    duration: float = 0.0
    backing_offset: float = 0.0
    db: float = 0.0
    muted: bool = False
    pan: float = 0.0
    effects: Effects = field(default_factory=Effects)
    punches: list[Punch] = field(default_factory=list)
    punch_undo: list[PunchUndo] = field(default_factory=list)

    def take_segments(self):
        return take_segments(self.duration, self.punches)


class MainTrack:
    """Track 1 seen through the same interface as `Track` (fields live on Project)."""
    _map = {"name": "track1_name", "recording": "recording", "duration": "duration",
            "backing_offset": "offset", "db": "video_db", "muted": "video_muted", "pan": "video_pan",
            "effects": "effects", "punches": "punches", "punch_undo": "punch_undo"}

    def __init__(self, project):
        object.__setattr__(self, "_project", project)

    def __getattr__(self, name):
        if name in MainTrack._map:
            return getattr(self._project, MainTrack._map[name])
        raise AttributeError(name)

    def __setattr__(self, name, value):
        setattr(self._project, MainTrack._map[name], value)

    def take_segments(self):
        return take_segments(self.duration, self.punches)


MAX_TRACKS = 3
TRACK_NAMES = ("Alto", "Tenor", "Soprano", "Baritone", "人聲")
MODES = ("video", "record")


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
    # "video": track 1 is the imported video's audio. "record": track 1 is a
    # WAV recorded in the app while the backing played (no picture).
    mode: str = "video"
    recording: str = ""
    # Record mode: punch-ins applied to `recording` (oldest first) and the
    # states before each of them, so they can be undone one by one.
    punches: list[Punch] = field(default_factory=list)
    punch_undo: list[PunchUndo] = field(default_factory=list)
    # Multi-track (record mode): name/pan of track 1, extra tracks, backing pan.
    track1_name: str = "Alto"
    video_pan: float = 0.0
    backing_pan: float = 0.0
    tracks: list[Track] = field(default_factory=list)

    def track(self, index):
        """0 = track 1 (fields on the project), 1.. = extra tracks."""
        return MainTrack(self) if index == 0 else self.tracks[index - 1]

    @property
    def track_count(self):
        return 1 + len(self.tracks)

    def track_shift(self, index):
        """Where a track's own time 0 lies on track 1's timeline."""
        return 0.0 if index == 0 else self.offset - self.tracks[index - 1].backing_offset

    @property
    def source(self):
        """The file feeding track 1."""
        return self.recording if self.mode == "record" else self.video

    @property
    def is_record(self):
        return self.mode == "record"

    def take_segments(self):
        """[(start, end, take number)] over track 1's recording; 0 = original take."""
        return take_segments(self.duration, self.punches)

    @property
    def output_duration(self):
        return sum(c.end - c.start for c in self.clips)

    def validate(self):
        def bounded(value, lo, hi, label):
            if not isinstance(value, (int, float)) or not math.isfinite(value) or not lo <= value <= hi:
                raise ValueError(f"{label} 超出允許範圍")
        if self.mode not in MODES:
            raise ValueError("不支援的專案模式")
        bounded(self.duration, 0, 86400, "影片長度")
        bounded(self.offset, -86400, 86400, "伴奏位移")
        for v in (self.video_db, self.backing_db):
            bounded(v, -60, 12, "音量")
        for fx in [self.effects] + [t.effects for t in self.tracks]:
            self._validate_effects(fx, bounded)
        prev = 0.0
        for c in self.clips:
            bounded(c.start, prev, self.duration, "片段起點")
            bounded(c.end, c.start + 0.001, self.duration + 0.001, "片段終點")
            prev = c.end
        self._validate_tracks(bounded)

    @staticmethod
    def _validate_effects(fx, bounded):
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

    def _validate_tracks(self, bounded):
        for punch in self.punches:
            bounded(punch.start, 0, self.duration, "重錄起點")
        if len(self.punch_undo) != len(self.punches):
            raise ValueError("重錄紀錄不完整")
        if self.tracks and not self.is_record:
            raise ValueError("只有錄音模式可以有多軌")
        if self.track_count > MAX_TRACKS:
            raise ValueError(f"最多 {MAX_TRACKS} 軌")
        for v in (self.video_pan, self.backing_pan):
            bounded(v, -1, 1, "聲道位置")
        for t in self.tracks:
            bounded(t.db, -60, 12, "音量")
            bounded(t.pan, -1, 1, "聲道位置")
            bounded(t.duration, 0, 86400, "錄音長度")
            bounded(t.backing_offset, -86400, 86400, "伴奏位移")
            for punch in t.punches:
                bounded(punch.start, 0, t.duration, "重錄起點")
            if len(t.punch_undo) != len(t.punches):
                raise ValueError("重錄紀錄不完整")

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
        for key in ("video", "backing", "recording"):
            if data[key]:
                # Absolute paths support drives different from the project drive.
                data[key] = str(Path(data[key]).resolve())
        for undo in data["punch_undo"]:
            undo["recording"] = str(Path(undo["recording"]).resolve())
        for track in data["tracks"]:
            if track["recording"]:
                track["recording"] = str(Path(track["recording"]).resolve())
            for undo in track["punch_undo"]:
                undo["recording"] = str(Path(undo["recording"]).resolve())
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
            def effects_of(raw):
                raw = dict(raw)
                raw["bands"] = [EQBand(**b) for b in raw["bands"]]
                return Effects(**raw)

            def undo_of(items):
                return [PunchUndo(u["recording"], u["duration"], [Clip(**c) for c in u.get("clips", [])])
                        for u in items]
            punches = [Punch(**x) for x in data.pop("punches", [])]
            undo = undo_of(data.pop("punch_undo", []))
            tracks = []
            for raw in data.pop("tracks", []):
                raw = dict(raw)
                raw["effects"] = effects_of(raw["effects"])
                raw["punches"] = [Punch(**x) for x in raw.get("punches", [])]
                raw["punch_undo"] = undo_of(raw.get("punch_undo", []))
                tracks.append(Track(**raw))
            p = cls(**data, effects=Effects(**effects), clips=clips, punches=punches, punch_undo=undo,
                    tracks=tracks)
        except (KeyError, TypeError, AttributeError) as exc:
            raise ValueError("專案檔格式不正確或缺少必要欄位") from exc
        for name in ("video", "backing", "recording"):
            value = getattr(p, name)
            if value and not Path(value).is_absolute():
                setattr(p, name, str((Path(path).parent / value).resolve()))
        p.validate()
        return p
