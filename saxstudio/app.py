from __future__ import annotations

import copy
import sys
import tempfile
from pathlib import Path

import numpy as np

from . import AUTHOR, VERSION_LABEL, __version__, theme
from .branding import APP_NAME, application_icon, asset_path, dark_palette
from .edit_dialog import EditDialog
from .effect_panels import CollapsibleEffect, PresetBar
from .help_dialog import HelpDialog
from .help_text import COMP_HELP, EQ_HELP, PRESETS, REVB_HELP
from .alignment import align_files
from .engine import audio_origin, export, render_mix
from . import recorder
from .media import active_range, decode_mono, decode_stereo, probe, thumbnail, waveform
from .model import MAX_TRACKS, TRACK_NAMES, Clip, Effects, Project, Punch, PunchUndo, Track
from .record_panel import CalibrationDialog, NewProjectDialog, PanDialog, RecordPanel
from .qt import QT6, QtCore, QtGui, QtMultimedia, QtWidgets as W, QtMultimediaWidgets, Signal, player, source, state_stopped
from .widgets import EQGraph, Timeline, Worker, take_color

VIDEO_FILTER = "影片 (*.mp4 *.mov *.mkv *.avi *.webm);;所有檔案 (*)"
AUDIO_FILTER = "伴奏 (*.mp3 *.wav *.flac *.m4a *.aac *.ogg);;所有檔案 (*)"

STYLE = """
QMainWindow, QWidget { background: #101923; color: #e5edf7; font-family: 'Segoe UI', 'PingFang TC', 'Microsoft JhengHei UI', 'Noto Sans CJK TC'; font-size: 13px; }
QFrame#card, QGroupBox { background: #182635; border: 1px solid #304359; border-radius: 9px; }
QGroupBox { margin-top: 12px; padding: 12px 10px 8px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; }
QLabel { background: transparent; }
QLabel#title { font-size: 24px; font-weight: 700; }
QLabel#muted { color: #91a4b9; font-size: 12px; }
QPushButton { background: #24384c; border: 1px solid #405a73; border-radius: 6px; padding: 8px 12px; }
QPushButton:hover { background: #304c65; }
QPushButton:pressed { background: #172f42; }
QPushButton:disabled { color: #617386; border-color: #293c4e; }
QPushButton#primary { background: #24bdb9; color: #082b32; border: none; font-weight: 700; }
QPushButton#primary:hover { background: #41d0ca; }
QPushButton#danger { color: #ffb5ac; }
QPushButton:checked { background: #31546b; border-color: #32d4ce; }
QDoubleSpinBox, QSpinBox, QComboBox { background: #101d2b; border: 1px solid #3c526b; border-radius: 4px; padding: 2px 4px; min-height: 22px; }
QDoubleSpinBox, QSpinBox { padding-right: 18px; }
QDoubleSpinBox::up-button, QSpinBox::up-button { subcontrol-origin: border; subcontrol-position: top right; width: 17px; border-left: 1px solid #3c526b; border-top-right-radius: 4px; background: #1a2b3c; }
QDoubleSpinBox::down-button, QSpinBox::down-button { subcontrol-origin: border; subcontrol-position: bottom right; width: 17px; border-left: 1px solid #3c526b; border-top: 1px solid #2c3f53; border-bottom-right-radius: 4px; background: #1a2b3c; }
QDoubleSpinBox::up-button:hover, QSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover, QSpinBox::down-button:hover { background: #2a4054; }
QDoubleSpinBox::up-button:pressed, QSpinBox::up-button:pressed, QDoubleSpinBox::down-button:pressed, QSpinBox::down-button:pressed { background: #31546b; }
QDoubleSpinBox::up-arrow, QSpinBox::up-arrow { image: url("@UP@"); width: 9px; height: 6px; }
QDoubleSpinBox::up-arrow:disabled, QSpinBox::up-arrow:disabled, QDoubleSpinBox::up-arrow:off, QSpinBox::up-arrow:off { image: url("@UPD@"); }
QDoubleSpinBox::down-arrow, QSpinBox::down-arrow { image: url("@DOWN@"); width: 9px; height: 6px; }
QDoubleSpinBox::down-arrow:disabled, QSpinBox::down-arrow:disabled, QDoubleSpinBox::down-arrow:off, QSpinBox::down-arrow:off { image: url("@DOWND@"); }
QToolButton#info { background: transparent; color: #8fb4cc; border: 1px solid #56738b; border-radius: 10px; font-weight: 700; font-size: 11px; }
QToolButton#info:hover { color: #0b2a30; background: #32d4ce; border-color: #32d4ce; }
QFrame#infoPopup { background: #1b2e40; border: 1px solid #43657e; border-radius: 8px; }
QLabel#infoText { color: #dbe7f2; font-size: 12px; }
QPushButton#preset { padding: 6px 12px; border-radius: 14px; }
QPushButton#preset:checked { background: #24bdb9; color: #082b32; border-color: #24bdb9; font-weight: 700; }
QLabel#presetCustom { color: #617386; padding: 0 6px; }
QLabel#presetCustom:enabled { color: #e9b853; font-weight: 600; }
QPushButton#record { background: #d9534f; color: #ffffff; border: none; border-radius: 8px; padding: 13px; font-size: 16px; font-weight: 700; }
QPushButton#record:hover { background: #e8645f; }
QPushButton#record:disabled { background: #4a3134; color: #a99; }
QPushButton#stopRecord { background: #2b3b4d; color: #ffffff; border: 1px solid #ff8a7a; border-radius: 8px; padding: 13px; font-size: 16px; font-weight: 700; }
QPushButton#modeCard { text-align: left; padding: 16px; background: #182635; border: 1px solid #304359; border-radius: 10px; font-size: 13px; }
QPushButton#modeCard:checked { background: #17333a; border: 2px solid #32d4ce; }
QLabel#modeBadge { background: #0f1b27; border: 1px solid #304359; border-radius: 8px; padding: 6px 12px; font-weight: 600; }
QPushButton#editButton { background: #17333a; border: 1px solid #24bdb9; font-weight: 700; }
QPushButton#editButton:hover { background: #1d4249; }
QPushButton#themeButton { border-radius: 16px; padding: 7px 14px; }
QSplitter::handle { background: #1c2b3a; }
QSplitter::handle:hover { background: #2ac5bf; }
QToolButton#section { background: transparent; border: none; font-weight: 600; padding: 4px 2px; text-align: left; }
QToolButton#section:hover { color: #32d4ce; }
QWidget#effectHead, QWidget#effectBody { background: transparent; }
QToolButton#effectArrow { background: transparent; border: none; color: #b4c5d5; border-radius: 4px; }
QToolButton#effectArrow:hover { background: #2a4054; }
QWidget#effectBody QLabel:disabled, QWidget#effectBody QDoubleSpinBox:disabled { color: #75889b; }
QComboBox QAbstractItemView { background: #192d40; selection-background-color: #28646a; }
QSlider::groove:horizontal { background: #34495f; height: 5px; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #2ac5bf; border-radius: 2px; }
QSlider::handle:horizontal { background: #dce7f2; width: 13px; margin: -5px 0; border-radius: 6px; }
QCheckBox { background: transparent; spacing: 7px; }
QCheckBox::indicator { width: 15px; height: 15px; border: 1px solid #567087; border-radius: 4px; background: #0f1d29; }
QCheckBox::indicator:checked { background: #2ac5bf; border-color: #2ac5bf; }
QListWidget { background: #111e2a; border: 1px solid #304359; border-radius: 5px; }
QListWidget::item { padding: 6px; }
QListWidget::item:selected { background: #25485b; }
QProgressBar { border: 1px solid #304359; height: 8px; border-radius: 4px; background: #152330; }
QProgressBar::chunk { background: #27c9c3; border-radius: 4px; }
QScrollArea { border: none; }
QStatusBar { color: #9db0c4; }
QToolTip { background: #253d51; color: #eff7ff; border: 1px solid #527084; }
"""


def style_sheet():
    """STYLE with absolute arrow-image paths (works from source and the EXE)."""
    sheet = STYLE
    for token, name in (("@UP@", "spin-up.png"), ("@UPD@", "spin-up-disabled.png"),
                        ("@DOWN@", "spin-down.png"), ("@DOWND@", "spin-down-disabled.png")):
        sheet = sheet.replace(token, asset_path(name).as_posix())
    return theme.css(sheet)


def button(text, callback, primary=False):
    b = W.QPushButton(text)
    b.clicked.connect(callback)
    if primary:
        b.setObjectName("primary")
    return b


def spin(lo, hi, value, decimals=1, suffix=""):
    s = W.QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(decimals)
    s.setValue(value)
    s.setSuffix(suffix)
    s.setKeyboardTracking(False)
    return s


def backing_range(path, cancel=None):
    """Audible span of the backing track, or None when it is silent."""
    try:
        return active_range(path, cancel=cancel)
    except ValueError:
        return None


def waveform_or_empty(path):
    if not path:
        return np.array([])
    try:
        return waveform(path)
    except Exception:
        return np.array([])


def clock(seconds):
    ms = round(max(0, seconds)*1000)
    return f"{ms//60000:02}:{ms//1000%60:02}.{ms%1000:03}"


class TrackFrame(W.QFrame):
    """A track's control row; clicking it selects the track."""
    clicked = Signal()

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)


def pan_text(pan):
    value = round(pan * 100)
    return "中" if value == 0 else (f"左 {-value}" if value < 0 else f"右 {value}")


class MainWindow(W.QMainWindow):
    def __init__(self):
        super().__init__()
        self.project = Project()
        self.project_path = None
        self.dirty = False
        self.preview_dirty = True
        self.preview_path = ""
        self.loading = False
        self.busy = False
        self.job = None
        self.position = 0.0
        self.playing = False
        self.jumping = False
        self.undo_stack = []
        self.temp = tempfile.TemporaryDirectory(prefix="sax-studio-")
        self.preview_revision = 0
        self.preview_peaks = np.array([])
        self.pending_play = False
        self.pending_position = 0.0
        self.resume_after_render = False
        self.resume_timer = QtCore.QTimer(self)
        self.resume_timer.setSingleShot(True)
        self.resume_timer.setInterval(600)
        self.resume_timer.timeout.connect(self.resume_render)
        self.video_failed = False
        self.backing_range = None
        self.alignment_reliable = None
        self.session = None
        self.recording_active = False
        self.calibration_dialog = None
        self.live_peaks = []
        self.live_update = 0
        self.punch = None        # {"start", "begin"} while a punch-in take runs
        self.fresh = None        # a new take on an extra track: {"track", "length", "times", "peaks", "heard"}
        self.take_track = 0      # track the current/last take records into
        self.selected_track = 0  # track shown in the effects panel and recorded into
        self.extra_rows = []     # control rows of the extra tracks
        self.inputs, self.outputs = [], []
        self.pending_since = 0.0
        self.last_resync = 0.0
        self.settings = QtCore.QSettings("SaxStudio", "SaxStudio")
        theme.set_theme(str(self.settings.value("ui/theme", theme.DARK)))
        app = W.QApplication.instance()
        if app is not None:
            app.setPalette(dark_palette())
        self.setWindowTitle(f"{APP_NAME} {VERSION_LABEL}")
        self.setWindowIcon(application_icon())
        self.resize(1440, 980)
        self.setMinimumSize(1120, 800)
        self.setStyleSheet(style_sheet())
        self.build_ui()
        self.video_player = player(self, self.video_widget, muted=True)
        self.audio_player = player(self)
        # The playback clock is the video in video mode and the mix in record mode.
        self.video_player.positionChanged.connect(
            lambda ms: None if self.project.is_record else self.on_position(ms))
        self.audio_player.positionChanged.connect(
            lambda ms: self.on_position(ms) if self.project.is_record else None)
        if QT6:
            self.video_player.errorOccurred.connect(lambda *a: self.playback_error("影片", self.video_player.errorString()))
            self.audio_player.errorOccurred.connect(lambda *a: self.playback_error("音訊", self.audio_player.errorString()))
        else:
            self.video_player.error.connect(lambda *a: self.playback_error("影片", self.video_player.errorString()))
            self.audio_player.error.connect(lambda *a: self.playback_error("音訊", self.audio_player.errorString()))
        self.sync_timer = QtCore.QTimer(self)
        self.sync_timer.setInterval(150)
        self.sync_timer.timeout.connect(self.sync_players)
        self.sync_timer.start()
        self.load_controls()
        self.apply_mode()
        self.refresh()
        self.setup_shortcuts()

    def build_ui(self):
        root = W.QWidget()
        self.setCentralWidget(root)
        layout = W.QVBoxLayout(root)
        layout.setContentsMargins(18, 14, 18, 12)
        layout.setSpacing(10)
        header = W.QHBoxLayout()
        brand_icon = W.QLabel()
        brand_icon.setPixmap(self.windowIcon().pixmap(44, 44))
        brand_icon.setFixedSize(44, 44)
        header.addWidget(brand_icon)
        title = W.QLabel(APP_NAME)
        title.setObjectName("title")
        header.addWidget(title)
        label = W.QLabel("薩克斯風影片混音工作室  ·  本機處理")
        label.setObjectName("muted")
        header.addWidget(label)
        version = W.QLabel(f"{VERSION_LABEL}  ·  {AUTHOR}")
        version.setObjectName("version")
        theme.apply(version, "color: #32d4ce; font-size: 12px; font-weight: 600; padding-left: 8px;")
        header.addWidget(version)
        header.addStretch()
        self.theme_button = button("", self.toggle_theme)
        self.theme_button.setObjectName("themeButton")
        header.addWidget(self.theme_button)
        self.export_button = button("匯出影片 / 音訊", self.export_dialog, True)
        header.addWidget(self.export_button)
        layout.addLayout(header)
        toolbar = W.QHBoxLayout()
        self.mode_badge = W.QLabel("尚未建立專案")
        self.mode_badge.setObjectName("modeBadge")
        self.mode_badge.setToolTip("模式在開新專案時決定；要換模式請按「新專案」")
        toolbar.addWidget(self.mode_badge)
        self.new_button = button("新專案", self.new_project)
        self.import_back_button = button("匯入伴奏", self.import_backing)
        self.open_button = button("開啟專案", self.open_project)
        self.save_button = button("儲存專案", self.save_project)
        self.pan_button = button("🎚 聲道位置…", self.open_pan_dialog)
        self.pan_button.setToolTip("另開視窗調整各軌左右聲道位置")
        for b in [self.new_button, self.import_back_button, self.open_button, self.save_button, self.pan_button]:
            toolbar.addWidget(b)
        self.project_label = W.QLabel("尚未匯入影片")
        self.project_label.setObjectName("muted")
        toolbar.addWidget(self.project_label, 1)
        reset_layout = button("重設版面", self.reset_layout)
        reset_layout.setToolTip("把效果區、影片區與音訊條恢復為預設大小")
        toolbar.addWidget(reset_layout)
        toolbar.addWidget(button("功能說明", self.show_help))
        toolbar.addWidget(button("關於", self.show_about))
        layout.addLayout(toolbar)
        self.controls = W.QWidget()
        controls_layout = W.QVBoxLayout(self.controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(10)
        fx_area = W.QWidget()
        fx_layout = W.QVBoxLayout(fx_area)
        fx_layout.setContentsMargins(0, 0, 0, 0)
        fx_layout.setSpacing(8)
        fx_header = W.QHBoxLayout()
        fx_title = self.fx_title = W.QLabel("第一軌 · 影片原音 效果")
        theme.apply(fx_title, "color: #27c9c3; font-weight: 600;")
        fx_title.setToolTip("EQ、壓縮、混響只處理影片原音；匯入的伴奏不會套用這些效果")
        fx_header.addWidget(fx_title)
        self.track_tabs = W.QTabBar()
        self.track_tabs.setObjectName("trackTabs")
        self.track_tabs.setDrawBase(False)
        self.track_tabs.setExpanding(False)
        self.track_tabs.setToolTip("切換要調整效果（與錄音）的軌")
        self.track_tabs.currentChanged.connect(self.on_track_tab)
        self.track_tabs.hide()
        fx_header.addWidget(self.track_tabs)
        fx_header.addStretch()
        fx_layout.addLayout(fx_header)
        preset_row = W.QHBoxLayout()
        preset_label = W.QLabel("快速音色")
        preset_label.setObjectName("muted")
        preset_row.addWidget(preset_label)
        self.preset = PresetBar(PRESETS)
        self.preset.currentIndexChanged.connect(self.apply_preset)
        preset_row.addWidget(self.preset, 1)
        self.preset_undo = button("↶ 還原套用前設定", self.undo_preset)
        self.preset_undo.setToolTip("回到套用快速音色之前的效果設定")
        self.preset_undo.setEnabled(False)
        preset_row.addWidget(self.preset_undo)
        fx_layout.addLayout(preset_row)
        self.preset_backup = None
        self.preset_chain = False
        self.effect_sections = {}
        eq_section = CollapsibleEffect("EQ 等化器", info=EQ_HELP)
        self.effect_sections["eq_enabled"] = eq_section
        self.eq_toggle = eq_section.toggle
        eq_layout = W.QVBoxLayout()
        eq_section.grid.addLayout(eq_layout, 0, 0)
        eq_top = W.QHBoxLayout()
        eq_top.addStretch()
        eq_top.addWidget(W.QLabel("高通"))
        self.highpass = spin(0, 400, 60, 0, " Hz")
        eq_top.addWidget(self.highpass)
        eq_layout.addLayout(eq_top)
        eq_content = W.QHBoxLayout()
        self.eq_graph = EQGraph()
        eq_content.addWidget(self.eq_graph, 1)
        eq_table = W.QGridLayout()
        for j, text in enumerate(["Hz", "dB", "Q"]):
            eq_table.addWidget(W.QLabel(text), 0, j)
        self.bands = []
        for i, band in enumerate(self.project.effects.bands):
            fields = [spin(20, 20000, band.frequency, 0), spin(-18, 18, 0), spin(.1, 10, 1, 2)]
            fields[1].setSingleStep(.5)
            fields[2].setSingleStep(.1)
            self.bands.append(fields)
            for j, field in enumerate(fields):
                field.setMinimumWidth(96 if j == 0 else 82)
                eq_table.addWidget(field, i+1, j)
                field.valueChanged.connect(self.change_effects)
        eq_content.addLayout(eq_table)
        eq_layout.addLayout(eq_content)
        fx_layout.addWidget(eq_section)
        effects_row = W.QHBoxLayout()
        effects_row.setAlignment(QtCore.Qt.AlignTop)
        self.fx_fields = {}
        for name, enabled_name, info, params in [
            ("Comp 壓縮", "compressor_enabled", COMP_HELP, [
                ("threshold", "門檻", -60, 0, -18, " dB"),
                ("ratio", "比例", 1, 20, 3, " : 1"),
                ("attack", "啟動", .1, 200, 15, " ms"),
                ("release", "釋放", 10, 2000, 120, " ms"),
                ("makeup", "補償", 0, 24, 0, " dB")]),
            ("Revb 混響", "reverb_enabled", REVB_HELP, [
                ("mix", "乾濕 Mix", 0, 100, 18, " %"),
                ("decay", "衰減 RT60", .2, 5, 1.6, " s"),
                ("predelay", "預延遲", 0, 150, 20, " ms")])]:
            group = CollapsibleEffect(name, info=info)
            self.effect_sections[enabled_name] = group
            grid = group.grid
            toggle = group.toggle
            self.fx_fields[enabled_name] = toggle
            toggle.toggled.connect(self.change_effects)
            for row, (key, label, lo, hi, value, suffix) in enumerate(params):
                field = spin(lo, hi, value, 1, suffix)
                slider = W.QSlider(QtCore.Qt.Horizontal)
                slider.setRange(round(lo*10), round(hi*10))
                slider.setValue(round(value*10))
                slider.valueChanged.connect(lambda v, f=field: f.setValue(v/10))
                field.valueChanged.connect(lambda v, s=slider: s.setValue(round(v*10)))
                field.valueChanged.connect(self.change_effects)
                self.fx_fields[key] = field
                grid.addWidget(W.QLabel(label), row, 0)
                grid.addWidget(slider, row, 1)
                grid.addWidget(field, row, 2)
            effects_row.addWidget(group, 0, QtCore.Qt.AlignTop)
        fx_layout.addLayout(effects_row)
        note = W.QLabel("只處理第一軌（影片原音）；匯入的伴奏只調音量與位移。錄影時麥克風收到的現場伴奏屬於原音，會一起被處理。調整後按播放，會先更新音效預覽。")
        note.setObjectName("muted")
        note.setWordWrap(True)
        fx_layout.addWidget(note)
        fx_layout.addStretch()
        scroll = W.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(fx_area)
        scroll.setMinimumWidth(460)
        self.h_split = W.QSplitter(QtCore.Qt.Horizontal)
        self.h_split.setChildrenCollapsible(False)
        self.h_split.setHandleWidth(6)
        self.h_split.addWidget(scroll)
        right_widget = W.QWidget()
        right_widget.setMinimumWidth(300)
        right = W.QVBoxLayout(right_widget)
        right.setContentsMargins(0, 0, 0, 0)
        self.video_stack = W.QStackedWidget()
        self.video_empty = W.QLabel("影片預覽\n\n匯入演奏影片後，可在此核對聲畫")
        self.video_empty.setAlignment(QtCore.Qt.AlignCenter)
        self.video_empty.setObjectName("muted")
        theme.apply(self.video_empty, "background: #0b121c; color: #8498ae; border: 1px solid #304359; border-radius: 8px;")
        self.video_widget = QtMultimediaWidgets.QVideoWidget()
        self.video_widget.setMinimumSize(240, 135)
        self.video_stack.setMinimumSize(240, 135)
        self.video_stack.addWidget(self.video_empty)
        self.video_stack.addWidget(self.video_widget)
        self.video_section = W.QWidget()
        video_layout = W.QVBoxLayout(self.video_section)
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.addWidget(self.video_stack, 1)
        self.video_name = W.QLabel("影片預覽 · 尚未匯入")
        self.video_name.setObjectName("muted")
        self.video_name.setWordWrap(True)
        video_layout.addWidget(self.video_name)
        self.record_panel = RecordPanel()
        self.record_scroll = W.QScrollArea()
        self.record_scroll.setWidgetResizable(True)
        self.record_scroll.setWidget(self.record_panel)
        self.right_stack = W.QStackedWidget()
        self.right_stack.addWidget(self.video_section)
        self.right_stack.addWidget(self.record_scroll)
        right.addWidget(self.right_stack, 1)
        self.record_panel.device_changed.connect(self.on_record_device_changed)
        self.record_panel.record_requested.connect(self.start_recording)
        self.record_panel.stop_requested.connect(self.stop_recording)
        self.record_panel.calibrate_requested.connect(self.open_calibration)
        self.record_panel.play_requested.connect(self.toggle_play)
        self.record_panel.volume_changed.connect(self.on_record_volume)
        self.record_panel.punch_requested.connect(self.start_punch)
        self.record_panel.undo_punch_requested.connect(self.undo_punch)
        expanded = self.settings.value("record/settings_expanded", True)
        # First use: open the settings so devices get picked; remembered afterwards.
        self.record_panel.set_settings_expanded(expanded in (True, "true", "1", 1))
        self.record_panel.settings_toggled.connect(
            lambda on: self.settings.setValue("record/settings_expanded", bool(on)))
        self.h_split.addWidget(right_widget)
        self.h_split.setStretchFactor(0, 3)
        self.h_split.setStretchFactor(1, 2)
        lower_widget = self.lower_widget = W.QWidget()
        lower = W.QVBoxLayout(lower_widget)
        lower.setContentsMargins(0, 6, 0, 0)
        lower.setSpacing(10)
        self.v_split = W.QSplitter(QtCore.Qt.Vertical)
        self.v_split.setChildrenCollapsible(False)
        self.v_split.setHandleWidth(6)
        self.v_split.addWidget(self.h_split)
        self.v_split.addWidget(lower_widget)
        self.v_split.setStretchFactor(0, 3)
        self.v_split.setStretchFactor(1, 1)
        controls_layout.addWidget(self.v_split, 1)
        align_row = W.QHBoxLayout()
        self.add_track_button = button("＋ 新增錄音軌", self.add_track)
        self.add_track_button.setObjectName("addTrack")
        theme.apply(self.add_track_button, "QPushButton#addTrack { background: #2a1a10; border: 1px solid #ff8a3d; "
                                           "color: #ffd2ad; font-weight: 600; }"
                                           "QPushButton#addTrack:disabled { color: #6f5a4a; border-color: #4a3a2e; background: #1c2430; }")
        align_row.addWidget(self.add_track_button)
        self.edit_button = button("✂  時間剪輯…", self.open_edit_dialog)
        self.edit_button.setObjectName("editButton")
        self.edit_button.setToolTip("開啟時間剪輯視窗：看著畫面與波形設定起訖、分割、刪除片段")
        align_row.addWidget(self.edit_button)
        self.edits_summary = W.QLabel("未剪輯")
        self.edits_summary.setObjectName("muted")
        align_row.addWidget(self.edits_summary)
        self.align_button = button("自動對齊前奏", self.align)
        align_row.addWidget(self.align_button)
        self.autotrim_button = button("依伴奏自動裁剪", self.auto_trim)
        self.autotrim_button.setToolTip("以伴奏實際有聲音的範圍為準，保留伴奏開始前與結束後的設定秒數，其餘剪掉（可復原）")
        align_row.addWidget(self.autotrim_button)
        self.align_label = W.QLabel("匯入伴奏後可比對前 90 秒")
        self.align_label.setObjectName("muted")
        align_row.addWidget(self.align_label, 1)
        self.record_offset_label = W.QLabel("錄音後會自動計算伴奏位移")
        self.record_offset_label.setObjectName("muted")
        self.record_offset_label.hide()
        align_row.addWidget(self.record_offset_label, 1)
        align_row.addWidget(W.QLabel("伴奏位移（＋延後／－提前）"))
        self.offset = spin(-86400000, 86400000, 0, 1, " ms")
        self.offset.setSingleStep(1)
        self.offset.setMinimumWidth(145)
        self.offset.valueChanged.connect(self.change_mix)
        align_row.addWidget(self.offset)
        lower.addLayout(align_row)
        tracks = W.QHBoxLayout()
        track_controls = self.track_controls = W.QVBoxLayout()
        # Same top/bottom/gap as the timeline lanes, so each row sits beside its waveform.
        track_controls.setContentsMargins(0, Timeline.TOP, 0, Timeline.BOTTOM)
        track_controls.setSpacing(Timeline.GAP)
        self.volume_fields = []
        self.track_names, self.track_hints, self.track_frames = [], [], []
        for index, (label, color, value, hint) in enumerate([
                ("第一軌 · 影片原音", "#27c9c3", 0, "套用上方 EQ／壓縮／混響"),
                ("第二軌 · 伴奏", "#e9b853", -6, "只調整音量與位移，不套用音效")]):
            row = self.make_track_row(label, color, value, hint, 0 if index == 0 else None)
            track_controls.addWidget(row["frame"], 1)
            self.track_names.append(row["name"])
            self.track_hints.append(row["hint"])
            self.track_frames.append(row["frame"])
            self.volume_fields.append((row["field"], row["mute"]))
        self.main_menu_button = self.track_frames[0].menu_button
        track_widget = self.track_widget = W.QWidget()
        track_widget.setLayout(track_controls)
        track_widget.setFixedWidth(310)
        tracks.addWidget(track_widget)
        self.timeline = Timeline()
        self.timeline.seek.connect(self.seek)
        self.timeline.track_clicked.connect(self.select_track)
        tracks.addWidget(self.timeline, 1)
        self.build_edit_dialog()  # creates clip_list (inside the edit window)
        self.timeline.select.connect(self.clip_list.setCurrentRow)
        lower.addLayout(tracks, 1)
        layout.addWidget(self.controls, 1)
        transport = W.QHBoxLayout()
        self.play_button = button("▶ 播放", self.toggle_play, True)
        transport.addWidget(self.play_button)
        self.stop_button = button("■ 停止", self.stop)
        transport.addWidget(self.stop_button)
        self.preview_button = button("更新音效預覽", lambda: self.prepare_preview(False))
        transport.addWidget(self.preview_button)
        self.time_label = W.QLabel("原片時間 00:00.000")
        transport.addWidget(self.time_label)
        transport.addStretch()
        self.preview_label = W.QLabel("尚未建立預覽")
        self.preview_label.setObjectName("muted")
        transport.addWidget(self.preview_label)
        self.level = W.QProgressBar()
        self.level.setRange(0, 100)
        self.level.setTextVisible(False)
        self.level.setFixedWidth(120)
        transport.addWidget(self.level)
        self.limiter = W.QCheckBox("總輸出限幅器")
        self.limiter.setToolTip("作用於兩軌混音後的總輸出，限制峰值至 -1 dBFS，避免破音；關閉時請自行降低音量")
        self.limiter.toggled.connect(self.change_effects)
        transport.addWidget(self.limiter)
        layout.addLayout(transport)
        self.transport = transport
        self.busy_bar = W.QProgressBar()
        self.busy_bar.setRange(0, 0)
        self.busy_bar.hide()
        busy_row = W.QHBoxLayout()
        busy_row.addWidget(self.busy_bar, 1)
        self.cancel_button = button("取消作業", self.cancel_job)
        self.cancel_button.hide()
        busy_row.addWidget(self.cancel_button)
        layout.addLayout(busy_row)
        self.eq_toggle.toggled.connect(self.change_effects)
        self.highpass.valueChanged.connect(self.change_effects)
        self.update_theme_button()
        self.restore_layout()
        self.h_split.splitterMoved.connect(lambda *a: self.save_layout())
        self.v_split.splitterMoved.connect(lambda *a: self.save_layout())

    DEFAULT_SPLIT = ([900, 520], [600, 300])

    def float_setting(self, key, default):
        try:
            return float(self.settings.value(key, default))
        except (TypeError, ValueError):
            return default

    def restore_layout(self):
        restored = False
        for name, split in (("ui/h_split", self.h_split), ("ui/v_split", self.v_split)):
            state = self.settings.value(name)
            if state is not None and split.restoreState(state):
                restored = True
        if not restored:
            self.h_split.setSizes(self.DEFAULT_SPLIT[0])
            self.v_split.setSizes(self.DEFAULT_SPLIT[1])

    def save_layout(self):
        self.settings.setValue("ui/h_split", self.h_split.saveState())
        self.settings.setValue("ui/v_split", self.v_split.saveState())

    def reset_layout(self):
        self.settings.remove("ui/h_split")
        self.settings.remove("ui/v_split")
        width = max(1, self.h_split.width())
        height = max(1, self.v_split.height())
        self.h_split.setSizes([round(width*.64), round(width*.36)])
        self.v_split.setSizes([round(height*.67), round(height*.33)])

    def show_about(self):
        W.QMessageBox.about(self, f"關於 {APP_NAME}", (
            f"<h3>{APP_NAME}</h3>"
            f"<p><b>版本：</b>{VERSION_LABEL}<br><b>作者：</b>{AUTHOR}</p>"
            "<p>薩克斯風翻奏影片／伴奏混音工作室。所有影音處理都在本機執行。</p>"
            "<p style='color:#91a4b9'>使用 Qt (PySide6)、NumPy、SciPy 與 FFmpeg；授權資訊見隨附的 THIRD_PARTY.md。</p>"))

    def build_edit_dialog(self):
        dlg = self.edit_dialog = EditDialog(self.timeline, self)
        self.edit_timeline = dlg.timeline
        self.mark_start, self.mark_end = dlg.mark_start, dlg.mark_end
        self.clip_list, self.undo_button = dlg.clip_list, dlg.undo_button
        self.duration_label = dlg.duration_label
        self.pre_roll, self.post_roll = dlg.pre_roll, dlg.post_roll
        self.pre_roll.setValue(self.float_setting("edit/pre_roll", 3.0))
        self.post_roll.setValue(self.float_setting("edit/post_roll", 2.0))
        self.pre_roll.valueChanged.connect(lambda v: self.settings.setValue("edit/pre_roll", v))
        self.post_roll.valueChanged.connect(lambda v: self.settings.setValue("edit/post_roll", v))
        dlg.start_button.clicked.connect(lambda: self.mark_start.setValue(self.position))
        dlg.end_button.clicked.connect(lambda: self.mark_end.setValue(self.position))
        dlg.trim_button.clicked.connect(self.trim)
        dlg.split_button.clicked.connect(self.split)
        dlg.delete_button.clicked.connect(self.delete_clip)
        dlg.autotrim_button.clicked.connect(self.auto_trim)
        dlg.undo_button.clicked.connect(self.undo)
        dlg.reset_button.clicked.connect(self.reset_edits)
        dlg.play_button.clicked.connect(self.toggle_play)
        dlg.prev_button.clicked.connect(lambda: self.step_frame(-1))
        dlg.next_button.clicked.connect(lambda: self.step_frame(1))
        self.clip_list.currentRowChanged.connect(self.select_clip)
        self.edit_timeline.seek.connect(self.seek)
        self.edit_timeline.select.connect(self.clip_list.setCurrentRow)
        dlg.finished.connect(self.edit_dialog_closed)
        shortcut_type = QtGui.QShortcut if QT6 else W.QShortcut
        for key, fn in (("Ctrl+B", self.split), ("Ctrl+Z", self.undo)):
            shortcut_type(QtGui.QKeySequence(key), dlg).activated.connect(fn)
        self.edit_snapshot = None

    def open_edit_dialog(self):
        if self.busy or self.recording_active or not self.project.source or self.edit_dialog.isVisible():
            return
        self.edit_snapshot = (copy.deepcopy(self.project.clips), copy.deepcopy(self.undo_stack), self.dirty,
                              self.windowTitle())
        rec = self.project.is_record
        if not rec and not self.video_failed:
            self.video_player.setVideoOutput(self.edit_dialog.video_widget)
            self.edit_dialog.show_video(True)
        else:
            self.edit_dialog.show_video(False, "錄音模式沒有畫面，請以波形與播放聲音剪輯" if rec else
                                        "影片預覽無法播放，仍可用波形剪輯")
        self.refresh()
        self.edit_dialog.open()
        self.edit_dialog.set_zoom(self.edit_dialog.zoom.value())
        self.seek(self.position)

    def edit_dialog_closed(self, result):
        snapshot, self.edit_snapshot = self.edit_snapshot, None
        if int(result) != 1 and snapshot is not None:  # 1 = QDialog.Accepted
            # 取消：放棄這次在視窗裡做的剪輯。
            self.pause()
            clips, undo, dirty, title = snapshot
            self.project.clips, self.undo_stack, self.dirty = clips, undo, dirty
            self.setWindowTitle(title)
            self.statusBar().showMessage("已取消這次的剪輯")
        if not self.project.is_record:
            self.video_player.setVideoOutput(self.video_widget)
        self.refresh()
        self.seek(self.position)

    def step_frame(self, direction):
        self.pause()
        self.seek(self.position + direction / 30)

    def show_help(self):
        dialog = HelpDialog(self)
        dialog.exec() if QT6 else dialog.exec_()

    def update_theme_button(self):
        if theme.is_light():
            self.theme_button.setText("☾  暗色")
            self.theme_button.setToolTip("切換成暗色")
        else:
            self.theme_button.setText("☀  米黃亮色")
            self.theme_button.setToolTip("切換成米黃亮色")

    def toggle_theme(self):
        name = theme.DARK if theme.is_light() else theme.LIGHT
        self.settings.setValue("ui/theme", name)
        theme.set_theme(name)
        app = W.QApplication.instance()
        if app is not None:
            app.setPalette(dark_palette())
        self.setStyleSheet(style_sheet())
        self.update_theme_button()
        for widget in [self, *self.findChildren(W.QWidget)]:
            # Item views override update(index); call QWidget's repaint request directly.
            W.QWidget.update(widget)
        self.statusBar().showMessage(f"已切換為{theme.NAMES[name]}")

    def setup_shortcuts(self):
        shortcut_type = QtGui.QShortcut if QT6 else W.QShortcut
        for key, fn in [("Ctrl+S", self.save_project), ("Ctrl+O", self.open_project),
                        ("Ctrl+Z", self.undo), ("Ctrl+B", self.split)]:
            s = shortcut_type(QtGui.QKeySequence(key), self)
            s.activated.connect(fn)

    # ------------------------------------------------------------ tracks
    def make_track_row(self, label, color, value, hint, track_index):
        frame = TrackFrame()
        frame.setObjectName("card")
        frame.setSizePolicy(W.QSizePolicy.Preferred, W.QSizePolicy.Expanding)
        f = W.QVBoxLayout(frame)
        f.setContentsMargins(10, 6, 10, 6)
        f.setSpacing(4)
        head = W.QHBoxLayout()
        name = W.QLabel(label)
        theme.apply(name, f"color: {color}; font-weight: 600;")
        head.addWidget(name)
        head.addStretch()
        hint_label = W.QLabel(hint)
        hint_label.setObjectName("muted")
        head.addWidget(hint_label)
        menu_button = W.QToolButton()
        menu_button.setText("⋯")
        menu_button.setAccessibleName("軌道選單")
        menu_button.setToolTip("重新命名／清除錄音／刪除此軌")
        menu_button.setVisible(track_index is not None)
        head.addWidget(menu_button)
        f.addLayout(head)
        row = W.QHBoxLayout()
        slider = W.QSlider(QtCore.Qt.Horizontal)
        slider.setRange(-600, 120)
        slider.setValue(round(value*10))
        field = spin(-60, 12, value, 1, " dB")
        field.setFixedWidth(85)
        slider.valueChanged.connect(lambda v, f=field: f.setValue(v/10))
        field.valueChanged.connect(lambda v, s=slider: s.setValue(round(v*10)))
        mute = W.QCheckBox("靜音")
        field.valueChanged.connect(self.change_mix)
        mute.toggled.connect(self.change_mix)
        row.addWidget(slider)
        row.addWidget(field)
        row.addWidget(mute)
        f.addLayout(row)
        frame.menu_button = menu_button
        if track_index is not None:
            frame.track_index = track_index
            frame.clicked.connect(lambda fr=frame: self.select_track(fr.track_index))
            menu_button.clicked.connect(lambda checked=False, fr=frame: self.show_track_menu(fr.track_index,
                                                                                               fr.menu_button))
        return {"frame": frame, "name": name, "hint": hint_label, "field": field, "mute": mute}

    def track_label(self, index):
        names = ("第一軌", "第二軌", "第三軌")
        return f"{names[index]} · {self.project.track(index).name}"

    def sync_tracks_ui(self):
        """Rebuild the extra track rows, tabs and lanes after tracks change."""
        p = self.project
        rec = p.is_record
        for row in self.extra_rows:
            self.track_controls.removeWidget(row["frame"])
            row["frame"].deleteLater()
        self.extra_rows = []
        for k, track in enumerate(p.tracks, start=1):
            hint = "已錄 " + clock(track.duration)[:5] if track.recording else "未錄"
            row = self.make_track_row(self.track_label(k), take_color(0, k), track.db, hint, k)
            self.loading = True
            row["mute"].setChecked(track.muted)
            self.loading = False
            self.track_controls.insertWidget(k, row["frame"], 1)
            self.extra_rows.append(row)
        while len(self.timeline.extra_waves) < len(p.tracks):
            self.timeline.extra_waves.append(np.array([]))
        del self.timeline.extra_waves[len(p.tracks):]
        self.track_frames[0].menu_button.setVisible(rec)
        if rec:
            self.track_names[0].setText(self.track_label(0))
        rows = 2 + len(p.tracks)
        minimum = Timeline.TOP + Timeline.BOTTOM + rows * 62 + (rows - 1) * Timeline.GAP
        for view in (self.timeline, self.edit_timeline):
            view.setMinimumHeight(max(170, minimum))
        self.track_tabs.blockSignals(True)
        while self.track_tabs.count():
            self.track_tabs.removeTab(0)
        for k in range(p.track_count):
            self.track_tabs.addTab(f"{k + 1} {p.track(k).name}")
            self.track_tabs.setTabTextColor(k, QtGui.QColor(theme.c(take_color(0, k))))
        self.track_tabs.setVisible(rec and p.track_count > 1)
        self.track_tabs.blockSignals(False)
        self.select_track(min(self.selected_track, p.track_count - 1))

    def select_track(self, index):
        if self.recording_active:
            return
        p = self.project
        index = max(0, min(index, p.track_count - 1)) if p.is_record else 0
        self.selected_track = index
        self.timeline.selected_track = index
        self.edit_timeline.selected_track = index
        self.track_tabs.blockSignals(True)
        if index < self.track_tabs.count():
            self.track_tabs.setCurrentIndex(index)
        self.track_tabs.blockSignals(False)
        frames = [self.track_frames[0]] + [r["frame"] for r in self.extra_rows]
        multi = p.is_record and p.track_count > 1
        for k, frame in enumerate(frames):
            color = take_color(0, k)
            theme.apply(frame, f"QFrame#card {{ border: 1px solid {color}; }}" if multi and k == index else "")
        if p.is_record:
            self.fx_title.setText(f"{self.track_label(index)} 效果")
            theme.apply(self.fx_title, f"color: {take_color(0, index)}; font-weight: 600;")
        self.preset_backup = None
        self.preset_undo.setEnabled(False)
        self.load_controls()
        self.refresh_record_panel()
        self.timeline.update()
        self.edit_timeline.update()
        if hasattr(self, "play_button"):
            self.update_record_buttons()

    def on_track_tab(self, index):
        if index >= 0:
            self.select_track(index)

    def current_track(self):
        return self.project.track(self.selected_track if self.project.is_record else 0)

    def refresh_record_panel(self):
        if not self.project.is_record or self.recording_active:
            return
        panel = self.record_panel
        track = self.current_track()
        multi = self.project.track_count > 1
        panel.set_target(self.selected_track, track.name, take_color(0, self.selected_track),
                         self.monitor_names(self.selected_track) if multi else None)
        if track.recording:
            panel.set_done(track.duration, track.recording, len(track.punches))
        else:
            panel.set_state("ready")

    def monitor_names(self, target):
        names = ["伴奏"] if self.project.backing and not self.project.backing_muted else []
        for k in range(self.project.track_count):
            track = self.project.track(k)
            if k != target and track.recording and not track.muted:
                names.append(f"{k + 1} {track.name}")
        return names

    def add_track(self):
        p = self.project
        if self.busy or self.recording_active or not p.is_record or not p.recording or p.track_count >= MAX_TRACKS:
            return
        used = {p.track(k).name for k in range(p.track_count)}
        suggestion = next((n for n in TRACK_NAMES if n not in used), "新軌")
        names = [suggestion] + [n for n in TRACK_NAMES if n != suggestion]
        name, ok = W.QInputDialog.getItem(self, "新增錄音軌", "新軌名稱（可直接輸入）：", names, 0, True)
        name = (name or "").strip()
        if not ok or not name:
            return
        effects = Effects()
        effects.limiter_enabled = p.effects.limiter_enabled
        p.tracks.append(Track(name=name[:20], effects=effects))
        self.selected_track = p.track_count - 1
        self.sync_tracks_ui()
        self.mark_dirty()
        self.refresh()
        self.statusBar().showMessage(f"已新增第 {p.track_count} 軌「{name}」；錄音時耳機會聽到伴奏與其他沒有靜音的軌")

    def show_track_menu(self, index, anchor):
        if self.busy or self.recording_active or not self.project.is_record:
            return
        self.select_track(index)
        menu = W.QMenu(self)
        menu.addAction("重新命名…", lambda: self.rename_track(index))
        if index > 0:
            clear = menu.addAction("清除錄音", lambda: self.clear_track(index))
            clear.setEnabled(bool(self.project.track(index).recording))
            menu.addAction("刪除此軌", lambda: self.delete_track(index))
        menu.exec(anchor.mapToGlobal(QtCore.QPoint(0, anchor.height()))) if QT6 else \
            menu.exec_(anchor.mapToGlobal(QtCore.QPoint(0, anchor.height())))

    def rename_track(self, index):
        track = self.project.track(index)
        name, ok = W.QInputDialog.getText(self, "重新命名", "軌道名稱：", text=track.name)
        name = (name or "").strip()
        if ok and name:
            track.name = name[:20]
            self.sync_tracks_ui()
            self.mark_dirty()

    def confirm(self, title, text):
        answer = W.QMessageBox.question(self, title, text, W.QMessageBox.Yes | W.QMessageBox.No, W.QMessageBox.No)
        return answer == W.QMessageBox.Yes

    def clear_track(self, index):
        track = self.project.track(index)
        if not track.recording or not self.confirm(
                "清除錄音", f"清除「{track.name}」的錄音？\n錄音檔會保留在錄音資料夾，不會刪除檔案。"):
            return
        track.recording, track.duration = "", 0.0
        track.punches, track.punch_undo = [], []
        self.timeline.extra_waves[index - 1] = np.array([])
        self.sync_tracks_ui()
        self.mark_dirty(audio=True)
        self.refresh()

    def delete_track(self, index):
        track = self.project.track(index)
        if track.recording and not self.confirm(
                "刪除此軌", f"刪除「{track.name}」這一軌？\n錄音檔會保留在錄音資料夾，不會刪除檔案。"):
            return
        del self.project.tracks[index - 1]
        del self.timeline.extra_waves[index - 1]
        self.selected_track = 0
        self.sync_tracks_ui()
        self.mark_dirty(audio=True)
        self.refresh()

    def open_pan_dialog(self):
        p = self.project
        if self.busy or self.recording_active or not p.is_record:
            return
        rows = [(f"{k + 1} {p.track(k).name}", take_color(0, k), p.track(k).pan) for k in range(p.track_count)]
        if p.backing:
            rows.append(("伴奏", "#e9b853", p.backing_pan))
        dialog = PanDialog(rows, pan_text, self)
        accepted = dialog.exec() if QT6 else dialog.exec_()
        if not accepted:
            return
        values = dialog.values()
        for k in range(p.track_count):
            p.track(k).pan = values[k]
        if p.backing:
            p.backing_pan = values[-1]
        self.mark_dirty(audio=True)
        self.statusBar().showMessage("聲道位置已更新")

    def load_controls(self):
        self.loading = True
        fx = self.current_track().effects
        self.eq_toggle.setChecked(fx.eq_enabled)
        self.highpass.setValue(fx.highpass)
        for band, fields in zip(fx.bands, self.bands):
            for field, value in zip(fields, (band.frequency, band.gain, band.q)):
                field.setValue(value)
        for key, widget in self.fx_fields.items():
            v = getattr(fx, key)
            if key.endswith("enabled"):
                widget.setChecked(v)
            else:
                widget.setValue(v*100 if key == "mix" else v)
        self.limiter.setChecked(self.project.effects.limiter_enabled)
        self.offset.setValue(self.project.offset*1000)
        for (field, mute), value, muted in zip(self.volume_fields,
                                             (self.project.video_db, self.project.backing_db),
                                             (self.project.video_muted, self.project.backing_muted)):
            field.setValue(value)
            mute.setChecked(muted)
        for row, track in zip(self.extra_rows, self.project.tracks):
            row["field"].setValue(track.db)
            row["mute"].setChecked(track.muted)
        self.preset.setCurrentIndex(0)
        self.loading = False
        self.eq_graph.effects = fx
        self.eq_graph.update()

    def change_effects(self, *args):
        if self.loading:
            return
        fx = self.current_track().effects
        fx.eq_enabled = self.eq_toggle.isChecked()
        fx.highpass = self.highpass.value()
        for band, fields in zip(fx.bands, self.bands):
            band.frequency, band.gain, band.q = [f.value() for f in fields]
        for key, widget in self.fx_fields.items():
            setattr(fx, key, widget.isChecked() if key.endswith("enabled") else
                    widget.value()/100 if key == "mix" else widget.value())
        # The limiter is on the master output: stored with track 1's effects.
        self.project.effects.limiter_enabled = self.limiter.isChecked()
        self.preset_chain = False
        self.loading = True
        self.preset.setCurrentIndex(0)
        self.loading = False
        self.eq_graph.update()
        self.mark_dirty(audio=True)

    def change_mix(self, *args):
        if self.loading:
            return
        offset = self.offset.value()/1000
        if abs(offset - self.project.offset) > 1e-9:
            self.alignment_reliable = None
        self.project.offset = offset
        self.project.video_db, self.project.backing_db = [f.value() for f, _ in self.volume_fields]
        self.project.video_muted, self.project.backing_muted = [m.isChecked() for _, m in self.volume_fields]
        for row, track in zip(self.extra_rows, self.project.tracks):
            track.db, track.muted = row["field"].value(), row["mute"].isChecked()
        self.timeline.update()
        self.mark_dirty(audio=True)

    def apply_preset(self, index):
        if self.loading or index == 0:
            return
        track = self.current_track()
        backup = copy.deepcopy(track.effects)
        fx = Effects()
        # Tone presets switch their effects on; only new projects start with
        # EQ/Comp/Revb bypassed. Loading a project restores its own flags.
        fx.eq_enabled = fx.compressor_enabled = fx.reverb_enabled = index != 1
        # Presets change the first-track tone only; keep the master limiter choice.
        fx.limiter_enabled = self.project.effects.limiter_enabled
        if index == 1:
            fx.eq_enabled = fx.compressor_enabled = fx.reverb_enabled = False
        elif index == 2:
            for b, gain in zip(fx.bands, (1, -2, 1.5, -1)):
                b.gain = gain
        elif index == 3:
            for b, gain in zip(fx.bands, (-1, -2, 2, 2)):
                b.gain = gain
            fx.mix = .12
        elif index == 4:
            fx.mix, fx.decay = .25, 2.3
            fx.bands[-1].gain = -2
        track.effects = fx
        if not self.preset_chain or self.preset_backup is None or self.preset_backup[0] is not self.project:
            # Keep the settings from before the first of consecutive preset
            # clicks, so trying several presets still returns to the user's own
            # values; a manual edit in between starts a new chain.
            self.preset_backup = (self.project, backup)
        self.preset_chain = True
        self.load_controls()
        self.loading = True
        self.preset.setCurrentIndex(index)
        self.loading = False
        self.preset_undo.setEnabled(True)
        self.mark_dirty(audio=True)

    def undo_preset(self):
        if self.busy or not self.preset_backup or self.preset_backup[0] is not self.project:
            return
        restored = copy.deepcopy(self.preset_backup[1])
        restored.limiter_enabled = self.project.effects.limiter_enabled
        self.current_track().effects = restored
        self.preset_backup = None
        self.preset_undo.setEnabled(False)
        self.load_controls()
        self.mark_dirty(audio=True)
        self.statusBar().showMessage("已還原套用快速音色之前的設定")

    def mark_dirty(self, audio=False):
        self.dirty = True
        if audio:
            was_playing = self.playing or self.pending_play
            self.pause()
            self.preview_dirty = True
            self.preview_label.setText("音效已變更 · 按播放更新")
            if was_playing and not self.recording_active:
                # Changed while listening: re-render, then continue from here.
                # Debounced so dragging a slider renders once, after it settles.
                self.resume_after_render = True
                self.resume_timer.start()
        self.setWindowTitle(f"{APP_NAME} {VERSION_LABEL} · 未儲存")

    def launch(self, function, callback):
        if self.busy:
            return
        self.pause()
        self.busy = True
        self.controls.setEnabled(False)
        self.busy_bar.show()
        self.cancel_button.show()
        self.refresh()
        self.job = Worker(function, self)
        self.job.result.connect(callback)
        self.job.failed.connect(self.show_error)
        self.job.progress.connect(self.statusBar().showMessage)
        self.job.finished.connect(self.job_finished)
        self.job.start()

    def job_finished(self):
        self.busy = False
        self.controls.setEnabled(True)
        self.busy_bar.hide()
        self.cancel_button.hide()
        self.job.deleteLater()
        self.job = None
        self.refresh()

    def cancel_job(self):
        if self.job:
            self.job.cancel.set()
            self.statusBar().showMessage("正在取消…")

    def show_error(self, text):
        text = str(text).strip() or "發生未預期的錯誤"
        self.statusBar().showMessage(text.splitlines()[0])
        if text != "作業已取消":
            box = W.QMessageBox(self)
            box.setWindowTitle(APP_NAME)
            box.setIcon(W.QMessageBox.Warning)
            box.setText(text.splitlines()[0])
            if "\n" in text:
                box.setDetailedText(text)
            box.exec() if QT6 else box.exec_()

    def playback_error(self, name, text):
        self.pause()
        if name == "影片":
            self.video_failed = True
            self.video_empty.setText(f"影片預覽無法播放\n\n{text}\n\n仍可嘗試匯出")
            self.video_stack.setCurrentWidget(self.video_empty)
        self.statusBar().showMessage(f"{name}預覽無法播放：{text}。請確認裝置與編碼；仍可嘗試匯出。")

    # ------------------------------------------------------------ modes
    def new_project(self):
        if self.busy or self.recording_active:
            return
        dialog = NewProjectDialog(self)
        accepted = dialog.exec() if QT6 else dialog.exec_()
        if not accepted or not dialog.choice:
            return
        if dialog.choice == "video":
            self.import_video()
        else:
            self.new_record_project()

    def new_record_project(self):
        if self.busy or self.recording_active:
            return
        path, _ = W.QFileDialog.getOpenFileName(self, "錄音模式：匯入伴奏", "", AUDIO_FILTER)
        if not path or not self.confirm_discard():
            return
        def task(cancel, progress):
            progress("正在讀取伴奏波形…")
            info = probe(path, cancel)
            if not info["audio"]:
                raise ValueError("伴奏檔案没有音訊")
            return info, waveform(path, cancel), backing_range(path, cancel)
        def done(result):
            info, wave, audible = result
            self.project = Project(mode="record", backing=path, duration=0.0, clips=[])
            self.selected_track = 0
            self.timeline.extra_waves = []
            self.backing_range = audible
            self.alignment_reliable = None
            self.preset_backup = None
            self.preset_undo.setEnabled(False)
            self.project_path = None
            self.undo_stack.clear()
            self.timeline.video_wave = np.array([])
            self.timeline.video_duration = None
            self.timeline.back_wave = wave
            self.timeline.back_duration = info["duration"]
            self.load_media(None)
            self.load_controls()
            self.apply_mode()
            self.record_panel.set_state("ready")
            self.record_offset_label.setText("錄音後會自動計算伴奏位移")
            self.mark_dirty()
            self.statusBar().showMessage("伴奏已匯入。確認麥克風音量後，按「開始錄音」")
            self.refresh()
        self.launch(task, done)

    def apply_mode(self):
        rec = self.project.is_record
        self.right_stack.setCurrentWidget(self.record_scroll if rec else self.video_section)
        if rec:
            self.mode_badge.setText("目前模式　● 錄音")
        elif self.project.video:
            self.mode_badge.setText("目前模式　▶ 匯入影片")
        else:
            self.mode_badge.setText("尚未建立專案")
        self.align_button.setVisible(not rec)
        self.align_label.setVisible(not rec)
        self.record_offset_label.setVisible(rec)
        self.track_names[0].setText(self.track_label(0) if rec else "第一軌 · 影片原音")
        self.fx_title.setText(f"{self.track_label(0)} 效果" if rec else "第一軌 · 影片原音 效果")
        theme.apply(self.fx_title, "color: #27c9c3; font-weight: 600;")
        self.pan_button.setVisible(rec)
        self.add_track_button.setVisible(rec)
        self.export_button.setText("匯出音訊（WAV / MP3）" if rec else "匯出影片 / 音訊")
        self.timeline.empty_text = ("匯入伴奏後開始錄音，波形會顯示在這裡" if rec else
                                    "匯入影片與伴奏後，波形會顯示在這裡")
        if not self.recording_active:
            self.timeline.override_duration = (self.timeline.back_duration or None) if rec and not self.project.recording else None
        if rec:
            self.ensure_session()
        elif self.session is not None and not self.recording_active:
            self.session.close_input()
        if not self.recording_active:
            self.sync_tracks_ui()
        self.timeline.update()

    def set_recording_ui(self, active):
        for widget in (self.h_split.widget(0), self.lower_widget):
            widget.setEnabled(not active)

    def update_record_buttons(self):
        if not hasattr(self, "record_panel"):
            return
        ready = (self.project.is_record and bool(self.project.backing) and not self.busy
                 and self.session is not None and self.session.input_open)
        if not self.record_panel.unavailable.text():
            self.record_panel.record_button.setEnabled(ready)
            self.record_panel.rerecord_button.setEnabled(ready)
            track = self.current_track()
            self.record_panel.punch_button.setEnabled(ready and bool(track.recording)
                                                      and not self.recording_active)
            self.record_panel.undo_punch_button.setEnabled(
                not self.busy and not self.recording_active and bool(track.punch_undo))
            self.record_panel.calibrate_button.setEnabled(
                not self.busy and not self.recording_active and self.session is not None and self.session.input_open)

    # ------------------------------------------------------------ audio devices
    def ensure_session(self):
        if not recorder.audio_available():
            self.record_panel.set_unavailable("此環境的 Qt 不支援錄音；請使用 Windows 版（PySide6／Qt 6）。")
            return False
        if self.session is None:
            self.session = recorder.AudioSession(self)
            self.session.level.connect(self.on_record_level)
            self.session.clipped.connect(self.record_panel.mark_clipped)
            self.session.progress.connect(self.on_record_progress)
            self.session.countdown.connect(self.on_record_countdown)
            self.session.take_finished.connect(self.finish_recording)
            self.session.calibration_finished.connect(self.on_calibration_result)
            self.session.failed.connect(self.on_record_failed)
            self.populate_devices()
        elif not self.session.input_open:
            self.open_selected_input()
        return True

    def populate_devices(self):
        panel = self.record_panel
        self.inputs, self.outputs = recorder.input_devices(), recorder.output_devices()
        for combo in (panel.input_combo, panel.channel_combo, panel.output_combo, panel.countdown_combo):
            combo.blockSignals(True)
        panel.input_combo.clear()
        panel.output_combo.clear()
        for combo, devices, key in ((panel.input_combo, self.inputs, "record/input"),
                                    (panel.output_combo, self.outputs, "record/output")):
            for device in devices:
                combo.addItem(device.description())
            saved = self.settings.value(key)
            keys = [recorder.device_key(d) for d in devices]
            if saved in keys:
                combo.setCurrentIndex(keys.index(saved))
        countdown = int(self.float_setting("record/countdown", 3))
        index = panel.countdown_combo.findData(countdown)
        panel.countdown_combo.setCurrentIndex(max(0, index))
        panel.volume_slider.setValue(round(self.float_setting("record/volume", -6.0) * 10))
        self.fill_channels()
        for combo in (panel.input_combo, panel.channel_combo, panel.output_combo, panel.countdown_combo):
            combo.blockSignals(False)
        panel.countdown_combo.currentIndexChanged.connect(
            lambda *_: self.settings.setValue("record/countdown", panel.countdown))
        if not self.inputs:
            panel.set_unavailable("找不到錄音裝置。請連接錄音介面後重新開啟程式。")
            return
        if not self.outputs:
            panel.set_unavailable("找不到播放裝置，無法在耳機播放伴奏。")
            return
        self.open_selected_input()

    def fill_channels(self):
        panel = self.record_panel
        device = self.selected_input()
        count = max(1, device.maximumChannelCount()) if device is not None else 1
        saved = int(self.float_setting("record/channel", 0))
        panel.channel_combo.clear()
        for i in range(min(count, 8)):
            panel.channel_combo.addItem(f"輸入 {i+1}（單聲道）", i)
        panel.channel_combo.setCurrentIndex(min(saved, panel.channel_combo.count()-1))

    def selected_input(self):
        i = self.record_panel.input_combo.currentIndex()
        return self.inputs[i] if 0 <= i < len(self.inputs) else None

    def selected_output(self):
        i = self.record_panel.output_combo.currentIndex()
        return self.outputs[i] if 0 <= i < len(self.outputs) else None

    def latency_key(self):
        a, b = self.selected_input(), self.selected_output()
        if a is None or b is None:
            return None
        return f"record/latency/{recorder.device_key(a)}-{recorder.device_key(b)}"

    def current_latency(self):
        key = self.latency_key()
        if not key or self.settings.value(key) is None:
            return None
        return self.float_setting(key, 0.0)

    def microphone_allowed(self):
        """macOS asks the user before an app may record. True when allowed."""
        if sys.platform != "darwin" or not hasattr(QtCore, "QMicrophonePermission"):
            return True
        app = W.QApplication.instance()
        permission = QtCore.QMicrophonePermission()
        status = app.checkPermission(permission)
        granted = QtCore.Qt.PermissionStatus.Granted
        if status == granted:
            return True
        if status == QtCore.Qt.PermissionStatus.Undetermined:
            self.record_panel.set_unavailable("正在等待麥克風權限…請在系統視窗按「允許」。")

            def answered(result):
                result = result.status() if hasattr(result, "status") else app.checkPermission(permission)
                if result == granted:
                    self.record_panel.set_unavailable("")
                    self.open_selected_input()
                else:
                    self.show_microphone_denied()
            try:
                app.requestPermission(permission, self, answered)
            except TypeError:
                app.requestPermission(permission, answered)
            return False
        self.show_microphone_denied()
        return False

    def show_microphone_denied(self):
        self.record_panel.set_unavailable(
            "沒有麥克風權限。請到「系統設定 → 隱私權與安全性 → 麥克風」開啟 Sax Cover Studio，"
            "然後重新開啟程式。")

    def open_selected_input(self):
        device = self.selected_input()
        if device is None or self.session is None:
            return
        if not self.microphone_allowed():
            return
        channel = int(self.record_panel.channel_combo.currentData() or 0)
        if self.session.open_input(device, channel):
            self.record_panel.format_label.setText(f"{self.session.rate/1000:g} kHz · 32-bit 浮點 · 單聲道")
        self.record_panel.set_latency(self.current_latency())
        self.update_record_buttons()

    def on_record_device_changed(self):
        if self.session is None or self.recording_active:
            return
        panel = self.record_panel
        input_key = recorder.device_key(self.selected_input()) if self.selected_input() is not None else None
        if input_key != self.settings.value("record/input"):
            panel.channel_combo.blockSignals(True)
            self.fill_channels()
            panel.channel_combo.blockSignals(False)
        if input_key:
            self.settings.setValue("record/input", input_key)
        if self.selected_output() is not None:
            self.settings.setValue("record/output", recorder.device_key(self.selected_output()))
        self.settings.setValue("record/channel", int(panel.channel_combo.currentData() or 0))
        self.open_selected_input()

    def on_record_volume(self, value_db):
        self.settings.setValue("record/volume", value_db)
        if self.punch is not None or getattr(self, "baked_monitor", False) and self.recording_active:
            return  # the backing level is baked into this take's headphone mix
        if self.session is not None and self.session.sink is not None:
            self.session.sink.setVolume(min(1.0, 10 ** (value_db / 20)))

    # ------------------------------------------------------------ recording
    def recordings_dir(self):
        paths = QtCore.QStandardPaths
        location = getattr(getattr(paths, "StandardLocation", paths), "DocumentsLocation")
        base = paths.writableLocation(location) or str(Path.home())
        return Path(base) / "Sax Cover Studio" / "錄音"

    def monitor_tracks(self, target):
        """[(path, backing_offset, gain, pan)] of the recorded, unmuted tracks other than `target`."""
        out = []
        for k in range(self.project.track_count):
            track = self.project.track(k)
            if k != target and track.recording and not track.muted:
                out.append((track.recording, track.backing_offset, 10 ** (track.db / 20), track.pan))
        return out

    @staticmethod
    def decode_monitor(tracks, cancel):
        return [(decode_mono(path, rate=48000, cancel=cancel), offset, gain, pan)
                for path, offset, gain, pan in tracks]

    def start_recording(self):
        if self.busy or self.recording_active or not self.project.is_record:
            return
        if not self.project.backing:
            self.show_error("請先匯入伴奏")
            return
        if self.session is None or not self.session.input_open:
            self.show_error("麥克風尚未開啟，請確認輸入裝置")
            return
        target = self.selected_track
        track = self.project.track(target)
        if target > 0 and not self.project.recording:
            self.show_error("請先錄好第一軌")
            return
        if track.recording:
            answer = W.QMessageBox.question(
                self, "重錄", f"重錄會取代「{track.name}」目前的整段錄音" +
                ("（中途重錄的紀錄也會清除）" if track.punches else "") +
                "。\n伴奏、EQ／壓縮／混響、音量與延遲校正都會保留。\n要開始重錄嗎？",
                W.QMessageBox.Yes | W.QMessageBox.No, W.QMessageBox.Yes)
            if answer != W.QMessageBox.Yes:
                return
        if self.current_latency() is None:
            answer = W.QMessageBox.question(
                self, "尚未校正延遲", "這組錄音介面與耳機還沒做延遲校正，錄完可能需要手動微調伴奏位移。\n要先做校正嗎？（約 10 秒）",
                W.QMessageBox.Yes | W.QMessageBox.No, W.QMessageBox.Yes)
            if answer == W.QMessageBox.Yes:
                self.open_calibration()
                return
        self.pause()
        backing = self.project.backing
        others = self.monitor_tracks(target)
        gain = min(1.0, 10 ** (self.record_panel.volume_db / 20))
        def task(cancel, progress):
            progress("正在準備伴奏…" if not others else "正在準備伴奏與其他軌…")
            samples = decode_stereo(backing, cancel=cancel)
            if not others:
                return samples, False
            # Other tracks are mixed in; the backing level is baked into the mix.
            return recorder.monitor_mix(samples, self.decode_monitor(others, cancel), backing_gain=gain), True
        def ready(result):
            samples, baked = result
            self.begin_take(samples, target, baked)
        self.launch(task, ready)

    def begin_take(self, samples, target=0, baked=False):
        stamp = QtCore.QDateTime.currentDateTime().toString("yyyyMMdd-HHmmss")
        suffix = "" if target == 0 else f"-第{target + 1}軌"
        path = self.recordings_dir() / f"錄音-{stamp}{suffix}.wav"
        countdown = self.record_panel.countdown
        volume = 1.0 if baked else min(1.0, 10 ** (self.record_panel.volume_db / 20))
        self.live_peaks = []
        self.take_track = target
        self.baked_monitor = baked
        self.record_panel.reset_clip()
        self.record_panel.clip_label.setText("錄音中…")
        if not self.session.start_take(str(path), self.selected_output(), samples, volume, countdown):
            return
        self.recording_active = True
        self.record_panel.set_state("countdown" if countdown else "recording")
        if target == 0:
            self.timeline.override_duration = countdown + len(samples) / 48000 + 2.5
            self.timeline.video_wave = np.array([])
            self.timeline.video_duration = 1e-6
            self.timeline.position = 0
        else:
            # Track 1's timeline stays; the new take grows on its own lane from
            # where the backing starts.
            p = self.project
            self.fresh = {"track": target, "length": len(samples) / 48000, "times": [], "peaks": [],
                          "heard": None}
            self.timeline.override_duration = max(p.duration, p.offset + len(samples) / 48000 + 2.5)
            self.timeline.punch_live = (target, p.offset, np.array([]), np.array([]), take_color(0, target))
        self.refresh()
        self.statusBar().showMessage(f"錄音中 · {self.track_label(target)} · 檔案：{path}")

    def stop_recording(self):
        if self.session is not None and self.recording_active:
            self.session.stop_take()

    def on_record_level(self, peak):
        self.record_panel.set_level(peak)
        live = self.punch if self.punch is not None else self.fresh
        if live is not None:
            heard = live["heard"]
            if heard is not None and heard >= live.get("start_main", -1e9):
                live["times"].append(heard)
                live["peaks"].append(peak)
            return
        if self.recording_active:
            self.live_peaks.append(peak)

    def update_live_lane(self, live):
        now = QtCore.QDateTime.currentMSecsSinceEpoch()
        if now - self.live_update > 120 and live["peaks"] and self.timeline.punch_live is not None:
            self.live_update = now
            peaks = np.array(live["peaks"], dtype=float)
            row, start, _t, _p, color = self.timeline.punch_live
            self.timeline.punch_live = (row, start, np.array(live["times"]),
                                        np.clip(peaks / max(.05, float(peaks.max())), 0, 1), color)

    def on_record_progress(self, seconds, left):
        if self.punch is not None:
            # `seconds` counts from the take start; playback starts ~immediately.
            punch = self.punch
            heard = punch["begin"] + seconds            # on the punched track's own timeline
            punch["heard"] = heard + punch["shift"]     # on track 1's timeline (for drawing)
            self.record_panel.set_punch_progress(punch["start"] - heard, punch["heard"], left)
            self.update_live_lane(punch)
            self.timeline.position = min(punch["heard"], self.timeline.total())
            self.timeline.update()
            return
        if self.fresh is not None:
            self.record_panel.set_progress(seconds, left)
            if left >= 0:
                # Backing time heard so far, placed on track 1's timeline.
                self.fresh["heard"] = self.project.offset + max(0.0, self.fresh["length"] - left)
                self.update_live_lane(self.fresh)
                self.timeline.position = min(self.fresh["heard"], self.timeline.total())
                self.timeline.update()
            return
        self.record_panel.set_progress(seconds, left)
        now = QtCore.QDateTime.currentMSecsSinceEpoch()
        if self.recording_active and now - self.live_update > 120 and self.live_peaks:
            self.live_update = now
            peaks = np.array(self.live_peaks, dtype=float)
            self.timeline.video_wave = np.clip(peaks / max(.05, float(peaks.max())), 0, 1)
            self.timeline.video_duration = max(seconds, 1e-6)
            self.timeline.position = seconds
            self.timeline.update()

    def on_record_countdown(self, seconds):
        self.record_panel.set_countdown(seconds)
        if seconds == 0:
            self.record_panel.set_state("recording")

    def end_live_display(self):
        self.timeline.punch_live = None
        self.timeline.override_duration = None
        self.record_panel.restore_hint()

    def finish_recording(self, result):
        if self.punch is not None:
            self.finish_punch(result)
            return
        if self.fresh is not None:
            self.finish_extra_take(result)
            return
        self.recording_active = False
        self.record_panel.restore_hint()
        latency = self.current_latency() or 0.0
        offset = recorder.recording_offset(result.start_offset, latency)
        path = result.path
        def task(cancel, progress):
            progress("正在分析錄音…")
            return probe(path, cancel), waveform(path, cancel)
        def done(analysis):
            info, wave = analysis
            p = self.project
            p.recording = path
            p.duration = info["duration"]
            p.clips = [Clip(0, p.duration)]
            p.offset = offset
            p.punches, p.punch_undo = [], []
            self.undo_stack.clear()
            self.alignment_reliable = None
            self.timeline.override_duration = None
            self.timeline.video_duration = None
            self.timeline.video_wave = wave
            self.load_media(None)
            self.load_controls()
            self.apply_mode()
            self.mark_dirty(audio=True)
            self.record_panel.set_done(p.duration, path)
            self.record_offset_label.setText(f"位移由錄音時間自動計算（已扣除 {latency:.1f} ms 延遲），可再手動微調")
            if result.peak >= .985:
                self.statusBar().showMessage("錄音完成，但有破音；建議調低錄音介面的輸入增益後重錄")
            elif p.tracks:
                self.statusBar().showMessage("第一軌錄音完成；其他軌依伴奏對齊")
            else:
                self.statusBar().showMessage("錄音完成並放入第一軌；按播放核對，或按「依伴奏自動裁剪」")
            self.refresh()
        self.record_panel.set_state("done" if self.project.recording else "ready")
        self.launch(task, done)

    def finish_extra_take(self, result):
        fresh, self.fresh = self.fresh, None
        self.recording_active = False
        self.end_live_display()
        target = fresh["track"]
        track = self.project.track(target)
        latency = self.current_latency() or 0.0
        offset = recorder.recording_offset(result.start_offset, latency)
        path = result.path
        def task(cancel, progress):
            progress("正在分析錄音…")
            return probe(path, cancel), waveform(path, cancel)
        def done(analysis):
            info, wave = analysis
            track.recording, track.duration, track.backing_offset = path, info["duration"], offset
            track.punches, track.punch_undo = [], []
            self.timeline.extra_waves[target - 1] = wave
            self.sync_tracks_ui()
            self.mark_dirty(audio=True)
            message = f"{self.track_label(target)} 錄音完成"
            self.statusBar().showMessage(message + ("，但有破音；建議調低輸入增益後重錄" if result.peak >= .985
                                                    else "；按播放聽合奏"))
            self.refresh()
        self.refresh_record_panel()
        self.launch(task, done)

    # ------------------------------------------------------------ punch-in
    def start_punch(self):
        """Re-record the selected track from the playhead to the end."""
        p = self.project
        target = self.selected_track if p.is_record else 0
        track = p.track(target)
        if self.busy or self.recording_active or not p.is_record or not track.recording:
            return
        if self.session is None or not self.session.input_open:
            self.show_error("麥克風尚未開啟，請確認輸入裝置")
            return
        shift = p.track_shift(target)
        start = max(0.0, min(self.position - shift, track.duration - .2))
        self.pause()
        backing, recording, offset = p.backing, track.recording, track.backing_offset
        others = self.monitor_tracks(target)
        gain = min(1.0, 10 ** (self.record_panel.volume_db / 20))
        def task(cancel, progress):
            progress("正在準備重錄（伴奏＋目前錄音）…")
            back = decode_stereo(backing, cancel=cancel)
            rec = decode_mono(recording, rate=48000, cancel=cancel)
            return recorder.punch_playback(back, rec, offset, start, backing_gain=gain,
                                           others=self.decode_monitor(others, cancel))
        def ready(result):
            mix, begin = result
            self.begin_punch(mix, begin, start, target)
        self.launch(task, ready)

    def begin_punch(self, mix, begin, start, target=0):
        p = self.project
        track = p.track(target)
        shift = p.track_shift(target)
        stamp = QtCore.QDateTime.currentDateTime().toString("yyyyMMdd-HHmmss")
        suffix = "" if target == 0 else f"-第{target + 1}軌"
        path = self.recordings_dir() / f"錄音-{stamp}{suffix}-重錄{len(track.punches) + 1}.wav"
        self.record_panel.reset_clip()
        self.record_panel.clip_label.setText("重錄中…")
        self.take_track = target
        self.punch = {"track": target, "start": start, "begin": begin, "shift": shift,
                      "start_main": start + shift, "heard": begin + shift, "times": [], "peaks": []}
        if not self.session.start_take(str(path), self.selected_output(), mix, 1.0, 0):
            self.punch = None
            return
        self.recording_active = True
        # Timeline spans the whole backing so the playhead and the new take can
        # run past the end of the old recording.
        self.timeline.override_duration = max(p.duration, begin + shift + len(mix) / 48000 + 2.5)
        self.timeline.punch_live = (target, start + shift, np.array([]), np.array([]),
                                    take_color(len(track.punches) + 1, target))
        self.record_panel.set_state("punch")
        self.record_panel.set_punch_progress(start - begin, begin + shift, -1)
        self.refresh()
        self.statusBar().showMessage(f"重錄中 · {self.track_label(target)} · 起點 {clock(start + shift)} · 檔案：{path}")

    def end_punch_display(self):
        self.end_live_display()

    def finish_punch(self, result):
        punch, self.punch = self.punch, None
        self.recording_active = False
        self.end_live_display()
        p = self.project
        target = punch["track"]
        track = p.track(target)
        latency = self.current_latency() or 0.0
        old_path = track.recording
        stamp = QtCore.QDateTime.currentDateTime().toString("yyyyMMdd-HHmmss")
        number = len(track.punches) + 1
        suffix = "" if target == 0 else f"-第{target + 1}軌"
        out = self.recordings_dir() / f"錄音-{stamp}{suffix}-合成{number}.wav"
        def task(cancel, progress):
            progress("正在接合重錄…")
            old = decode_mono(old_path, rate=48000, cancel=cancel)
            take = decode_mono(result.path, rate=48000, cancel=cancel)
            merged = recorder.splice_punch(old, take, punch["start"], punch["begin"],
                                           result.start_offset, latency)
            writer = recorder.WavWriter(out, 48000, 1)
            writer.write(merged)
            writer.close()
            return len(merged) / 48000, waveform(out, cancel)
        def done(analysis):
            seconds, wave = analysis
            track.punch_undo.append(PunchUndo(old_path, track.duration,
                                              copy.deepcopy(p.clips) if target == 0 else []))
            track.punches.append(Punch(punch["start"], number))
            track.recording = str(out)
            track.duration = seconds
            if target == 0:
                # Clips before the punch stay; the one holding it now runs to the new end.
                kept = [Clip(c.start, min(c.end, seconds)) for c in p.clips if c.start < punch["start"]]
                if kept:
                    kept[-1].end = seconds
                p.clips = kept or [Clip(0, seconds)]
                self.undo_stack.clear()
                self.timeline.video_wave = wave
                self.timeline.video_duration = None
                self.load_media(None)
                self.apply_mode()
            else:
                self.timeline.extra_waves[target - 1] = wave
                self.sync_tracks_ui()
            self.mark_dirty(audio=True)
            self.seek(max(0.0, punch["start_main"] - recorder.PREROLL))
            self.refresh_record_panel()
            self.statusBar().showMessage(f"{self.track_label(target)} 已從 {clock(punch['start_main'])} 重錄"
                                         f"（第 {number} 次）；不滿意可按「復原上一次重錄」")
            self.refresh()
        self.refresh_record_panel()
        self.launch(task, done)

    def undo_punch(self):
        p = self.project
        target = self.selected_track if p.is_record else 0
        track = p.track(target)
        if self.busy or self.recording_active or not track.punch_undo:
            return
        previous = track.punch_undo[-1]
        def task(cancel, progress):
            progress("正在復原…")
            return waveform(previous.recording, cancel)
        def done(wave):
            track.punch_undo.pop()
            removed = track.punches.pop()
            track.recording, track.duration = previous.recording, previous.duration
            if target == 0:
                p.clips = previous.clips or [Clip(0, previous.duration)]
                self.undo_stack.clear()
                self.timeline.video_wave = wave
                self.timeline.video_duration = None
                self.load_media(None)
                self.apply_mode()
            else:
                self.timeline.extra_waves[target - 1] = wave
                self.sync_tracks_ui()
            self.mark_dirty(audio=True)
            self.seek(max(0.0, removed.start + p.track_shift(target) - recorder.PREROLL))
            self.refresh_record_panel()
            self.statusBar().showMessage(f"已復原{self.track_label(target)}的第 {removed.number} 次重錄")
            self.refresh()
        self.launch(task, done)

    def on_record_failed(self, text):
        if self.calibration_dialog is not None:
            self.calibration_dialog.show_error(text)
            return
        if self.recording_active:
            self.recording_active = False
            fresh_or_punch = self.punch is not None or self.fresh is not None
            self.punch = None
            self.fresh = None
            self.timeline.punch_live = None
            self.record_panel.restore_hint()
            if fresh_or_punch:
                self.timeline.override_duration = None
            else:
                self.timeline.override_duration = None if self.project.recording else (self.timeline.back_duration or None)
                self.timeline.video_duration = None
                self.timeline.video_wave = (waveform_or_empty(self.project.recording))
            self.refresh_record_panel()
            if not self.project.recording:
                self.record_panel.set_state("ready")
            self.refresh()
        self.show_error(text)

    # ------------------------------------------------------------ calibration
    def open_calibration(self):
        if self.busy or self.recording_active or self.session is None or not self.session.input_open:
            return
        dialog = CalibrationDialog(self.current_latency(), self)
        dialog.measure_requested.connect(lambda: self.session.calibrate(self.selected_output()))
        self.calibration_dialog = dialog
        try:
            accepted = dialog.exec() if QT6 else dialog.exec_()
        finally:
            self.calibration_dialog = None
            if self.session.mode == "calibrate":
                self.session.cancel()
        if accepted and dialog.result_ms is not None and self.latency_key():
            self.settings.setValue(self.latency_key(), float(dialog.result_ms))
            self.record_panel.set_latency(dialog.result_ms)
            self.statusBar().showMessage(f"已套用延遲補償 {dialog.result_ms:.1f} ms")

    def on_calibration_result(self, median, spread, found):
        if self.calibration_dialog is not None:
            self.calibration_dialog.show_result(median, spread, found)

    def confirm_discard(self):
        if not self.dirty:
            return True
        answer = W.QMessageBox.question(self, "未儲存的專案", "目前專案尚未儲存，是否放棄變更？",
                                       W.QMessageBox.Yes | W.QMessageBox.No, W.QMessageBox.No)
        return answer == W.QMessageBox.Yes

    def import_video(self):
        if self.busy:
            return
        path, _ = W.QFileDialog.getOpenFileName(self, "匯入演奏影片", "", VIDEO_FILTER)
        if not path or not self.confirm_discard():
            return
        def task(cancel, progress):
            progress("正在讀取影片與原音波形…")
            info = probe(path, cancel)
            if not info["video"] or not info["audio"]:
                raise ValueError("請選擇包含畫面與原音的影片")
            still = Path(self.temp.name)/"import-still.jpg"
            thumbnail(path, still, cancel)
            return info, waveform(path, cancel), str(still)
        def done(result):
            info, wave, still = result
            self.project = Project(video=path, duration=info["duration"], clips=[Clip(0, info["duration"])])
            self.selected_track = 0
            self.timeline.extra_waves = []
            self.backing_range = None
            self.alignment_reliable = None
            self.preset_backup = None
            self.preset_undo.setEnabled(False)
            self.project_path = None
            self.undo_stack.clear()
            self.timeline.video_wave = wave
            self.timeline.back_wave = np.array([])
            self.timeline.back_duration = 0
            self.load_media(still)
            self.load_controls()
            self.apply_mode()
            self.mark_dirty(audio=True)
            self.align_label.setText("匯入伴奏後可比對前 90 秒")
            self.statusBar().showMessage("影片已匯入，接著可匯入伴奏")
            self.refresh()
        self.launch(task, done)

    def import_backing(self):
        if self.busy or self.recording_active or not (self.project.video or self.project.is_record):
            return
        path, _ = W.QFileDialog.getOpenFileName(self, "匯入同一版本伴奏", "", AUDIO_FILTER)
        if not path:
            return
        def task(cancel, progress):
            progress("正在讀取伴奏波形…")
            info = probe(path, cancel)
            if not info["audio"]:
                raise ValueError("伴奏檔案没有音訊")
            return info, waveform(path, cancel), backing_range(path, cancel)
        def done(result):
            info, wave, audible = result
            self.backing_range = audible
            self.alignment_reliable = None
            self.project.backing = path
            if not self.project.is_record:
                # A recording keeps its measured offset: the backing starts at
                # the same moment for any version of the same song.
                self.project.offset = 0
            self.timeline.back_wave = wave
            self.timeline.back_duration = info["duration"]
            self.load_controls()
            self.apply_mode()
            self.mark_dirty(audio=True)
            self.align_label.setText("尚未對齊 · 請按自動對齊前奏")
            self.statusBar().showMessage("伴奏已匯入")
            self.refresh()
        self.launch(task, done)

    def load_media(self, still=None):
        self.pause()
        self.video_failed = False
        self.video_stack.setCurrentWidget(self.video_widget)
        source(self.video_player, "" if self.project.is_record else self.project.video)
        if still:
            self.video_empty.setPixmap(QtGui.QPixmap(still).scaled(
                self.video_stack.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
            self.video_stack.setCurrentWidget(self.video_empty)
        source(self.audio_player, "")
        self.preview_path = ""
        self.preview_dirty = True
        self.position = 0
        self.mark_start.setMaximum(self.project.duration)
        self.mark_end.setMaximum(self.project.duration)
        self.mark_start.setValue(0)
        self.mark_end.setValue(self.project.duration)
        self.video_name.setText(Path(self.project.source).name if self.project.source else "")
        self.timeline.project = self.project
        self.timeline.selected = -1
        self.timeline.position = 0

    def align(self):
        if self.busy or not self.project.backing:
            return
        snapshot = copy.deepcopy(self.project)
        def task(cancel, progress):
            progress("正在比對前 90 秒的頻譜特徵…")
            result = align_files(snapshot.video, snapshot.backing, cancel=cancel)
            result.offset += audio_origin(probe(snapshot.video, cancel))
            return result
        def done(result):
            self.offset.setValue(result.offset*1000)
            self.alignment_reliable = result.reliable
            self.align_label.setText(f"可信度 {result.confidence:.0%} · {result.message}")
            hint = "；可按「依伴奏自動裁剪」保留演奏範圍" if self.backing_range else ""
            self.statusBar().showMessage("位移已套用；請播放前奏核對，長影片也請核對結尾" + hint)
        self.launch(task, done)

    def prepare_preview(self, autoplay=False):
        if self.busy or self.recording_active or not self.project.source:
            return
        if not self.preview_dirty and self.preview_path:
            if autoplay:
                self.start_play()
            return
        snapshot = copy.deepcopy(self.project)
        # Loading the new preview resets the player to 0; resume where we were.
        resume_at = self.position
        self.preview_revision += 1
        output = Path(self.temp.name) / f"preview-{self.preview_revision}.wav"
        def task(cancel, progress):
            render_mix(snapshot, output, cancel, progress)
            progress("正在建立輸出電平資訊…")
            # Peak envelope for a visual indicator, not a calibrated loudness meter.
            samples = decode_mono(output, rate=8000, cancel=cancel)
            n = 400
            padded = np.pad(samples, (0, (-len(samples)) % n))
            peaks = np.max(np.abs(padded.reshape(-1, n)), axis=1)
            return str(output), peaks
        def done(result):
            old = self.preview_path
            self.preview_path, self.preview_peaks = result
            source(self.audio_player, self.preview_path)
            self.seek(resume_at)
            if old:
                try:
                    Path(old).unlink(missing_ok=True)
                except PermissionError:
                    pass
            self.preview_dirty = False
            self.preview_label.setText("音效預覽已更新")
            self.statusBar().showMessage("預覽已就緒，音效與輸出使用相同處理流程")
            if autoplay or self.resume_after_render:
                # Media loading is asynchronous; wait for both media to be loaded.
                self.pending_play = True
                self.pending_since = QtCore.QDateTime.currentMSecsSinceEpoch()
                # The player may still report position 0 for the new file after
                # this; start_play seeks here again once the media is loaded.
                self.pending_position = resume_at
            self.resume_after_render = False
        self.pending_play = False
        self.launch(task, done)

    def resume_render(self):
        """Re-render after a change made while playing, then keep playing."""
        if not self.resume_after_render or not self.preview_dirty:
            self.resume_after_render = False
            return
        if self.busy:
            self.resume_timer.start()   # another job is running; try again shortly
            return
        self.prepare_preview(False)

    def toggle_play(self):
        if self.busy:
            return
        if self.resume_after_render:
            # Pressing play/pause while a resume is queued: the user takes over.
            self.resume_after_render = False
            self.resume_timer.stop()
            return
        if self.playing:
            self.pause()
        else:
            self.prepare_preview(True)

    def start_play(self):
        if not self.project.clips:
            self.show_error("沒有保留片段，請重設剪輯")
            return
        keep = next((c for c in self.project.clips if c.start <= self.position < c.end-.025), None)
        if keep is None:
            later = next((c for c in self.project.clips if c.start > self.position), self.project.clips[0])
            self.seek(later.start)
        self.audio_player.setPosition(round(self.position*1000))
        if not self.project.is_record:
            if not self.video_failed:
                self.video_stack.setCurrentWidget(self.video_widget)
            self.video_player.play()
        self.audio_player.play()
        self.playing = True
        self.play_button.setText("Ⅱ 暫停")
        self.edit_dialog.play_button.setText("Ⅱ 暫停")

    def pause(self):
        if hasattr(self, "video_player"):
            self.video_player.pause()
            self.audio_player.pause()
        self.playing = False
        self.pending_play = False
        if hasattr(self, "play_button"):
            self.play_button.setText("▶ 播放")
        if hasattr(self, "edit_dialog"):
            self.edit_dialog.play_button.setText("▶ 播放")

    def stop(self):
        self.resume_after_render = False
        self.resume_timer.stop()
        if self.busy:
            return
        self.pause()
        self.seek(self.project.clips[0].start if self.project.clips else 0)
        self.level.setValue(0)

    def seek(self, position):
        self.position = max(0, min(position, self.project.duration))
        if self.project.video and not self.project.is_record and not self.playing and not self.video_failed:
            # Show the real frame at the playhead instead of the import still.
            if state_stopped(self.video_player):
                self.video_player.play()
                self.video_player.pause()
            self.video_stack.setCurrentWidget(self.video_widget)
        self.jumping = True
        self.video_player.setPosition(round(self.position*1000))
        self.audio_player.setPosition(round(self.position*1000))
        self.jumping = False
        self.show_position()

    def on_position(self, milliseconds):
        if self.jumping:
            return
        self.position = milliseconds/1000
        if self.playing:
            keep = next((c for c in self.project.clips if c.start-.04 <= self.position < c.end-.02), None)
            if keep is None:
                later = next((c for c in self.project.clips if c.start > self.position+.01), None)
                if later:
                    self.seek(later.start)
                else:
                    self.pause()
                    self.seek(self.project.clips[-1].end if self.project.clips else 0)
                    return
        self.show_position()

    def show_position(self):
        for view in (self.timeline, self.edit_timeline):
            view.position = self.position
            view.update()
        self.time_label.setText(f"原片時間 {clock(self.position)}")
        if self.project.is_record and not self.recording_active:
            self.record_panel.set_punch_point(self.position)
        self.edit_dialog.time_label.setText(f"{clock(self.position)} / {clock(self.project.duration)}")
        if self.edit_dialog.isVisible() and self.project.duration > 0:
            # Keep the playhead in view when the waveform is zoomed in.
            bar = self.edit_dialog.timeline_scroll.horizontalScrollBar()
            x = self.edit_timeline.time_x(self.position)
            if not bar.value() <= x <= bar.value() + bar.pageStep():
                bar.setValue(int(x - bar.pageStep() * .2))

    def sync_players(self):
        if self.pending_play and not self.busy:
            media_status = QtMultimedia.QMediaPlayer.MediaStatus if QT6 else QtMultimedia.QMediaPlayer
            statuses = ((self.audio_player.mediaStatus(),) if self.project.is_record else
                        (self.video_player.mediaStatus(), self.audio_player.mediaStatus()))
            ready = (media_status.LoadedMedia, media_status.BufferedMedia, media_status.EndOfMedia)
            waited = QtCore.QDateTime.currentMSecsSinceEpoch() - self.pending_since
            if media_status.InvalidMedia in statuses:
                self.pending_play = False
                self.statusBar().showMessage("預覽媒體無法載入；請確認影片編碼，仍可嘗試匯出")
            elif all(s in ready for s in statuses):
                self.pending_play = False
                self.seek(self.pending_position)
                self.start_play()
            elif waited > 8000:
                # Some backends never report Loaded for a paused source; try anyway.
                self.pending_play = False
                self.statusBar().showMessage("媒體載入較慢，嘗試直接播放")
                self.seek(self.pending_position)
                self.start_play()
        if self.playing:
            # The rendered mix is the master clock: nudging the muted video is
            # invisible compared with audible jumps in the music.
            drift = 0 if self.project.is_record else self.audio_player.position()-self.video_player.position()
            now = QtCore.QDateTime.currentMSecsSinceEpoch()
            if abs(drift) > 150 and now - self.last_resync > 1000:
                self.last_resync = now
                self.jumping = True
                self.video_player.setPosition(self.audio_player.position())
                self.jumping = False
            if len(self.preview_peaks):
                idx = min(len(self.preview_peaks)-1, int(self.position/.05))
                peak = float(self.preview_peaks[idx])
                self.level.setValue(round(min(1, peak)*100))
                self.level.setToolTip(f"近似單聲道峰值 {20*np.log10(max(peak, 1e-8)):.1f} dBFS")

    def push_undo(self):
        self.pause()
        self.undo_stack.append(copy.deepcopy(self.project.clips))
        self.undo_stack = self.undo_stack[-100:]

    def auto_trim(self):
        if self.busy or not self.project.source or not self.project.backing:
            return
        if not self.backing_range:
            self.show_error("伴奏沒有偵測到有聲音的範圍，無法自動裁剪")
            return
        if self.alignment_reliable is False:
            answer = W.QMessageBox.question(
                self, "自動裁剪", "自動對齊的可信度偏低，伴奏位移可能不準。\n仍要依目前的位移裁剪嗎？（之後可按「復原剪輯」撤回）",
                W.QMessageBox.Yes | W.QMessageBox.No, W.QMessageBox.No)
            if answer != W.QMessageBox.Yes:
                return
        snapshot = copy.deepcopy(self.project.clips)
        try:
            start, end = self.project.trim_to_backing(*self.backing_range, self.pre_roll.value(), self.post_roll.value())
        except ValueError as exc:
            self.project.clips = snapshot
            self.show_error(str(exc))
            return
        self.pause()
        self.undo_stack.append(snapshot)
        self.mark_start.setValue(start)
        self.mark_end.setValue(end)
        self.mark_dirty()
        self.refresh()
        self.seek(start)
        self.statusBar().showMessage(f"已自動裁剪：保留 {clock(start)} → {clock(end)}（伴奏前 {self.pre_roll.value():g} 秒、後 {self.post_roll.value():g} 秒）")

    def trim(self):
        if not self.project.source or self.busy:
            return
        snapshot = copy.deepcopy(self.project.clips)
        try:
            self.project.trim(self.mark_start.value(), self.mark_end.value())
        except ValueError as exc:
            self.project.clips = snapshot
            self.show_error(str(exc))
            return
        self.pause()
        self.undo_stack.append(snapshot)
        self.mark_dirty()
        self.refresh()

    def split(self):
        if not self.project.source or self.busy:
            return
        snapshot = copy.deepcopy(self.project.clips)
        if self.project.split(self.position):
            self.pause()
            self.undo_stack.append(snapshot)
            self.mark_dirty()
            self.refresh()
        else:
            self.statusBar().showMessage("請將播放游標移到保留片段的中間再分割")

    def delete_clip(self):
        i = self.clip_list.currentRow()
        if self.busy or not 0 <= i < len(self.project.clips):
            return
        self.push_undo()
        del self.project.clips[i]
        self.mark_dirty()
        self.refresh()

    def undo(self):
        if self.undo_stack and not self.busy:
            self.pause()
            self.project.clips = self.undo_stack.pop()
            self.mark_dirty()
            self.refresh()

    def reset_edits(self):
        if not self.project.source or self.busy:
            return
        self.push_undo()
        self.project.clips = [Clip(0, self.project.duration)]
        self.mark_start.setValue(0)
        self.mark_end.setValue(self.project.duration)
        self.mark_dirty()
        self.refresh()

    def select_clip(self, index):
        for view in (self.timeline, self.edit_timeline):
            view.selected = index
            view.update()

    def refresh(self):
        has = bool(self.project.source)
        rec = self.project.is_record
        idle = not self.busy and not self.recording_active
        self.controls.setEnabled(not self.busy)
        self.new_button.setEnabled(idle)
        self.open_button.setEnabled(idle)
        self.save_button.setEnabled(idle and has)
        self.import_back_button.setEnabled((bool(self.project.video) or rec) and idle)
        self.align_button.setEnabled(not rec and has and bool(self.project.backing) and idle)
        self.autotrim_button.setEnabled(has and bool(self.project.backing) and bool(self.backing_range) and idle)
        self.export_button.setEnabled(has and bool(self.project.clips) and idle)
        self.play_button.setEnabled(has and bool(self.project.clips) and idle)
        self.stop_button.setEnabled(idle)
        self.preview_button.setEnabled(has and idle)
        self.limiter.setEnabled(idle)
        self.undo_button.setEnabled(bool(self.undo_stack) and not self.busy)
        selected = self.clip_list.currentRow()
        self.clip_list.blockSignals(True)
        self.clip_list.clear()
        for i, c in enumerate(self.project.clips):
            self.clip_list.addItem(f"{i+1:02}    {clock(c.start)} → {clock(c.end)}    ·    {c.end-c.start:.2f} s")
        self.clip_list.setCurrentRow(min(selected, len(self.project.clips)-1))
        self.clip_list.blockSignals(False)
        for view in (self.timeline, self.edit_timeline):
            view.selected = self.clip_list.currentRow()
            view.project = self.project
            view.update()
        self.edit_button.setEnabled(has and idle)
        full = self.project.track_count >= MAX_TRACKS
        self.add_track_button.setEnabled(rec and has and idle and not full)
        self.add_track_button.setToolTip(f"最多 {MAX_TRACKS} 軌" if full else
                                         "先錄好第一軌，再新增其他聲部（錄音時耳機會聽到伴奏與其他軌）"
                                         if not has else "新增一條錄音軌（最多 3 軌）")
        self.pan_button.setEnabled(rec and idle)
        self.track_tabs.setEnabled(idle)
        for frame in [self.track_frames[0]] + [r["frame"] for r in self.extra_rows]:
            frame.menu_button.setEnabled(idle)
        self.edit_dialog.autotrim_button.setEnabled(self.autotrim_button.isEnabled())
        self.duration_label.setText(f"輸出 {clock(self.project.output_duration)}")
        whole = [Clip(0, self.project.duration)]
        if not has:
            self.edits_summary.setText("尚未錄音" if rec else "尚未匯入影片")
        elif self.project.clips == whole:
            self.edits_summary.setText(f"未剪輯 · {clock(self.project.duration)}")
        else:
            self.edits_summary.setText(f"已剪輯 · {len(self.project.clips)} 段 · 輸出 {clock(self.project.output_duration)}")
        if has:
            label = Path(self.project.source).name
        elif rec and self.project.backing:
            label = f"伴奏：{Path(self.project.backing).name}"
        else:
            label = "按「新專案」開始" if not self.project.backing else ""
        if has and self.project.backing:
            label += f"　·　伴奏：{Path(self.project.backing).name}"
        self.project_label.setText(label)
        self.set_recording_ui(self.recording_active)
        self.update_record_buttons()

    def save_project(self):
        if self.busy or self.recording_active or not self.project.source:
            if self.project.is_record and not self.project.source:
                self.statusBar().showMessage("請先錄音再儲存專案")
            return
        path = self.project_path
        if not path:
            path, _ = W.QFileDialog.getSaveFileName(self, "儲存專案", "演奏混音.saxproj", f"{APP_NAME} 專案 (*.saxproj)")
        if not path:
            return
        if not str(path).lower().endswith(".saxproj"):
            path += ".saxproj"
        try:
            self.project.save(path)
            self.project_path = path
            self.dirty = False
            self.setWindowTitle(f"{APP_NAME} {VERSION_LABEL} · {Path(path).name}")
            self.statusBar().showMessage("專案已儲存（原始影音檔請保留於原位置）")
        except Exception as exc:
            self.show_error(str(exc))

    def open_project(self):
        if self.busy or self.recording_active:
            return
        path, _ = W.QFileDialog.getOpenFileName(self, "開啟專案", "", f"{APP_NAME} 專案 (*.saxproj)")
        if not path or not self.confirm_discard():
            return
        def task(cancel, progress):
            progress("正在讀取專案與波形…")
            p = Project.load(path)
            if not p.source:
                raise ValueError("專案沒有錄音" if p.is_record else "專案沒有影片")
            for name, title in (("video", "影片"), ("recording", "錄音"), ("backing", "伴奏")):
                value = getattr(p, name)
                if value and (name != "video" or not p.is_record) and not Path(value).is_file():
                    raise ValueError(f"找不到{title}：{value}\n請將原始檔移回原位置，或在 .saxproj 中更新路徑。")
            vinfo = probe(p.source, cancel)
            if not vinfo["audio"] or (not p.is_record and not vinfo["video"]):
                raise ValueError("專案錄音沒有聲音" if p.is_record else "專案影片缺少畫面或音訊")
            if abs(vinfo["duration"]-p.duration) > .5:
                raise ValueError("錄音長度與專案不同，檔案可能已被修改" if p.is_record else "影片長度與專案不同，原始檔可能已被修改")
            vwave = waveform(p.source, cancel)
            still = None
            if not p.is_record:
                still = Path(self.temp.name)/"project-still.jpg"
                thumbnail(p.video, still, cancel)
            extra = []
            for track in p.tracks:
                if track.recording and not Path(track.recording).is_file():
                    raise ValueError(f"找不到「{track.name}」的錄音：{track.recording}\n"
                                     "請將錄音檔移回原位置，或在 .saxproj 中更新路徑。")
                extra.append(waveform(track.recording, cancel) if track.recording else np.array([]))
            bwave, bd, audible = np.array([]), 0, None
            if p.backing:
                bd = probe(p.backing, cancel)["duration"]
                bwave = waveform(p.backing, cancel)
                audible = backing_range(p.backing, cancel)
            return p, vwave, bwave, bd, (str(still) if still else None), audible, extra
        def done(result):
            (self.project, self.timeline.video_wave, self.timeline.back_wave,
             self.timeline.back_duration, still, self.backing_range, self.timeline.extra_waves) = result
            self.selected_track = 0
            self.alignment_reliable = None
            self.preset_backup = None
            self.preset_undo.setEnabled(False)
            self.project_path = path
            self.undo_stack.clear()
            self.timeline.video_duration = None
            self.load_media(still)
            self.load_controls()
            self.apply_mode()
            if self.project.is_record:
                self.record_panel.set_done(self.project.duration, self.project.recording,
                                           len(self.project.punches))
                self.record_offset_label.setText("已讀取儲存的位移 · 請播放核對")
            self.dirty = False
            self.preview_label.setText("按播放建立音效預覽")
            self.align_label.setText("已讀取儲存的位移 · 請播放核對")
            self.setWindowTitle(f"{APP_NAME} {VERSION_LABEL} · {Path(path).name}")
            self.statusBar().showMessage("專案已開啟")
            self.refresh()
        self.launch(task, done)

    def export_dialog(self):
        if self.busy or self.recording_active or not self.project.source or not self.project.clips:
            return
        rec = self.project.is_record
        base = Path(self.project.backing if rec and self.project.backing else self.project.source)
        name = base.stem + ("_錄音混音" if rec else "_混音")
        start = str((Path(self.project.source).parent if not rec else base.parent) / name)
        filters = ("WAV 音訊 (*.wav);;MP3 音訊 (*.mp3)" if rec else
                   "MP4 影片 (*.mp4);;WAV 音訊 (*.wav);;MP3 音訊 (*.mp3)")
        destination, selected_filter = W.QFileDialog.getSaveFileName(self, "匯出混音成品", start, filters)
        if not destination:
            return
        if not Path(destination).suffix:
            destination += (".mp3" if selected_filter.startswith("MP3") else ".wav" if rec or selected_filter.startswith("WAV")
                            else ".mp4")
        snapshot = copy.deepcopy(self.project)
        self.launch(lambda cancel, progress: export(snapshot, destination, cancel, progress),
                    lambda output: self.statusBar().showMessage(f"匯出完成：{output}"))

    def closeEvent(self, event):
        if self.recording_active:
            self.statusBar().showMessage("請先停止錄音再關閉")
            event.ignore()
            return
        if self.busy:
            self.statusBar().showMessage("請先取消作業，等待完成後再關閉")
            event.ignore()
            return
        if not self.confirm_discard():
            event.ignore()
            return
        self.pause()
        if self.session is not None:
            self.session.cancel()
            self.session.close_input()
        source(self.audio_player, "")
        source(self.video_player, "")
        try:
            self.temp.cleanup()
        except PermissionError:
            pass
        event.accept()


def main():
    # Kept for compatibility; the launcher shows the splash before heavy imports.
    from .launcher import main as launch
    launch()


if __name__ == "__main__":
    main()
