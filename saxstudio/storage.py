"""Where recordings are written, and moving a project into its own folder.

Layout under 文件/Sax Cover Studio/錄音/:
    2026-10-31/                         one folder per day
        月亮代表我的心-20-04.wav         backing name + hour-minute
        月亮代表我的心-20-21-合成1.wav   punch-in result
        重錄片段/                        raw punch-in takes
        月亮代表我的心-多軌專案/         a multi-track project's own folder
Pure functions only (no Qt), so they are unit tested directly.
"""
from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

PUNCH_FOLDER = "重錄片段"
MULTI_SUFFIX = "多軌專案"
_ILLEGAL = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def safe_stem(backing, limit=40):
    """File-name-safe backing name without extension."""
    stem = Path(backing).stem if backing else "錄音"
    stem = _ILLEGAL.sub("_", stem).strip(" .") or "錄音"
    return stem[:limit].rstrip(" .") or "錄音"


def day_folder(base, when=None):
    return Path(base) / (when or datetime.now()).strftime("%Y-%m-%d")


def unique_path(folder, stem, suffix):
    """folder/stem+suffix, or "stem (2)+suffix"… when taken."""
    folder = Path(folder)
    path = folder / f"{stem}{suffix}"
    n = 2
    while path.exists():
        path = folder / f"{stem} ({n}){suffix}"
        n += 1
    return path


def take_path(base, backing, folder="", track_name="", kind="", number=0, when=None):
    """Path for a new recording file (the folder is created).

    folder: the project's multi-track folder, or "" for the day folder.
    kind: "" for a whole take, "重錄" for a raw punch-in take (goes into
    重錄片段/), "合成" for the spliced result.
    """
    when = when or datetime.now()
    target = Path(folder) if folder else day_folder(base, when)
    if kind == "重錄":
        target = target / PUNCH_FOLDER
    target.mkdir(parents=True, exist_ok=True)
    stem = f"{safe_stem(backing)}-{when.strftime('%H-%M')}"
    if track_name:
        stem += f"-{safe_stem(track_name, 20)}"
    if kind:
        stem += f"-{kind}{number}"
    return unique_path(target, stem, ".wav")


def multitrack_folder(base, backing, when=None):
    """New, not yet existing folder for a multi-track project."""
    day = day_folder(base, when)
    return unique_path(day, f"{safe_stem(backing)}-{MULTI_SUFFIX}", "")


def move_into(path, folder):
    """Move a file into folder (or its 重錄片段/ subfolder is chosen by caller).

    Returns the new path; a file already inside `folder` is left alone.
    """
    path, folder = Path(path), Path(folder)
    if path.parent.resolve() == folder.resolve():
        return path
    folder.mkdir(parents=True, exist_ok=True)
    target = unique_path(folder, path.stem, path.suffix)
    shutil.move(str(path), str(target))
    return target


def move_project_files(project, folder):
    """Move every recording the project uses into `folder`, updating its paths.

    Covers each track's current recording, the earlier versions kept for
    undo, and raw punch-in takes (into 重錄片段/). Recordings the project no
    longer references are left where they are. Returns [(path, error)] for
    files that could not be moved; those keep their old path.
    """
    folder = Path(folder)
    failed = []
    moved = {}      # a file referenced twice is moved once

    def move(path, target):
        if not path:
            return path
        if path in moved:
            return moved[path]
        if not Path(path).is_file():
            return path
        try:
            moved[path] = str(move_into(path, target))
        except OSError as exc:
            failed.append((path, str(exc)))
            moved[path] = path
        return moved[path]
    for index in range(project.track_count):
        track = project.track(index)
        track.recording = move(track.recording, folder)
        for undo in track.punch_undo:
            undo.recording = move(undo.recording, folder)
        for punch in track.punches:
            punch.take = move(punch.take, folder / PUNCH_FOLDER)
    project.folder = str(folder)
    return failed
