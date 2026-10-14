"""Colour themes: the original dark look and a cream ("米黃") light look.

Every colour in the interface is written as its dark-theme hex. `c()` and
`css()` translate those hexes for the active theme, so stylesheets and custom
painted widgets (waveforms, EQ curve, switches, meters) switch together.
Widgets styled through `apply()` are re-styled automatically on a change.
"""
from __future__ import annotations

import re

DARK, LIGHT = "dark", "light"
NAMES = {DARK: "暗色", LIGHT: "米黃亮色"}

# dark hex -> cream light hex, grouped by role.
LIGHT_MAP = {
    # window, fields and lists
    "#101923": "#f5eedc", "#0f1b27": "#fffdf7", "#0f1d29": "#fffdf7", "#101d2b": "#fffdf7",
    "#111e2a": "#fbf5e6", "#152330": "#ece3cd", "#101b27": "#fbf5e6", "#0b121c": "#3a342a",
    "#132232": "#f7f0e0", "#142231": "#f8f2e4", "#16283a": "#efe6d2", "#182b3d": "#efe6d2",
    # cards, buttons, borders
    "#182635": "#fffaee", "#192d40": "#fffaee", "#1a2b3c": "#f3ead6", "#1b2e40": "#fffaee",
    "#1c2b3a": "#e6dabf", "#24384c": "#ede2c8", "#253d51": "#fffaee", "#25485b": "#d9ece6",
    "#28646a": "#cde6df", "#293c4e": "#e0d4ba", "#2a4054": "#e6dabf", "#2b3b4d": "#f1e1d9",
    "#2c3f53": "#d8c9a6", "#2c4156": "#d8c9a6", "#2a3e52": "#e2d3b2", "#304359": "#e2d3b2",
    "#304c65": "#e4d6b6", "#172f42": "#d8c8a2", "#31546b": "#d5e8e1", "#34495f": "#ddd0b2",
    "#3c526b": "#cdbb94", "#405a73": "#d3c19b", "#43657e": "#cdbb94", "#3a5670": "#cdbb94",
    "#4a3134": "#e8d3cf", "#527084": "#cdbb94", "#567087": "#b8a67f", "#56738b": "#b8a67f",
    "#17333a": "#dcefe9", "#223344": "#e9ddc2", "#263749": "#e6dabf", "#22344a": "#e6dabf",
    "#3a4b5e": "#cfc2a3", "#5b6c7f": "#b8a67f",
    # text
    "#e5edf7": "#2f2a20", "#dbe7f2": "#3a3428", "#dce7f2": "#fffdf7", "#eff7ff": "#2f2a20",
    "#e6eff8": "#2f2a20", "#c9d6e2": "#3a3428", "#b9c8d6": "#4a4232", "#b7cadb": "#4a4232",
    "#b4c5d5": "#6b604c", "#9db0c4": "#6b604c", "#91a4b9": "#6b604c", "#8fb4cc": "#6b604c",
    "#8d9fb3": "#7a6e57", "#7f92a8": "#7a6e57", "#8498ae": "#d9cdb4", "#6f8396": "#8a7d63",
    "#75889b": "#a39678", "#617386": "#a39678", "#d7e7fa": "#2f2a20", "#fafcff": "#2f2a20",
    "#d9e4ec": "#ffffff",
    # accents
    "#24bdb9": "#0b7a76", "#41d0ca": "#0e8f8a", "#082b32": "#ffffff", "#0b2a30": "#ffffff",
    "#32d4ce": "#086f6b", "#27c9c3": "#0e8a85", "#2ac5bf": "#0e8a85", "#78eee4": "#086f6b",
    "#0d393c": "#ffffff", "#e9b853": "#a8710c", "#ff8a7a": "#b2412f", "#ffb5ac": "#b2412f",
    "#d9534f": "#c8453c", "#e8645f": "#d45a50", "#ff5a4f": "#d0473c", "#8fe6de": "#086f6b",
    "#1d4249": "#cfe7e0",
}

_current = DARK
_styled = {}  # id(widget) -> (widget, sheet); strong refs keep wrappers alive
_listeners = []
_HEX = re.compile(r"#[0-9a-fA-F]{6}\b")


def current():
    return _current


def is_light():
    return _current == LIGHT


def c(hex_color):
    """A dark-theme colour translated for the active theme."""
    if _current == LIGHT:
        return LIGHT_MAP.get(hex_color.lower(), hex_color)
    return hex_color


def css(sheet):
    if _current != LIGHT:
        return sheet
    return _HEX.sub(lambda m: LIGHT_MAP.get(m.group(0).lower(), m.group(0)), sheet)


def shade():
    """Overlay for removed time ranges on waveforms: (r, g, b, alpha)."""
    return (120, 100, 60, 60) if _current == LIGHT else (6, 10, 16, 190)


def apply(widget, sheet):
    """setStyleSheet with dark-theme hexes; re-applied on theme changes."""
    _styled[id(widget)] = (widget, sheet)
    widget.setStyleSheet(css(sheet))


def on_change(callback):
    _listeners.append(callback)


def set_theme(name):
    global _current
    _current = LIGHT if name == LIGHT else DARK
    for key, (widget, sheet) in list(_styled.items()):
        try:
            widget.setStyleSheet(css(sheet))
        except RuntimeError:  # the C++ object was deleted
            _styled.pop(key, None)
    for callback in list(_listeners):
        callback(_current)
