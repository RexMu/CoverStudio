from __future__ import annotations

import copy
import sys
import tempfile
from pathlib import Path

import numpy as np

from . import AUTHOR, VERSION_LABEL, __version__
from .branding import APP_NAME, application_icon, asset_path, dark_palette
from .effect_panels import CollapsibleEffect, PresetBar
from .help_text import COMP_HELP, EQ_HELP, PRESETS, REVB_HELP
from .alignment import align_files
from .engine import audio_origin, export, render_mix
from .media import active_range, decode_mono, probe, thumbnail, waveform
from .model import Clip, Effects, Project
from .qt import QT6, QtCore, QtGui, QtMultimedia, QtWidgets as W, QtMultimediaWidgets, player, source, state_stopped
from .widgets import EQGraph, Timeline, Worker

VIDEO_FILTER = "影片 (*.mp4 *.mov *.mkv *.avi *.webm);;所有檔案 (*)"
AUDIO_FILTER = "伴奏 (*.mp3 *.wav *.flac *.m4a *.aac *.ogg);;所有檔案 (*)"

STYLE = """
QMainWindow, QWidget { background: #101923; color: #e5edf7; font-family: 'Segoe UI', 'Microsoft JhengHei UI', 'Noto Sans CJK TC'; font-size: 13px; }
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
    return sheet


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


def clock(seconds):
    ms = round(max(0, seconds)*1000)
    return f"{ms//60000:02}:{ms//1000%60:02}.{ms%1000:03}"


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
        self.video_failed = False
        self.backing_range = None
        self.alignment_reliable = None
        self.pending_since = 0.0
        self.last_resync = 0.0
        self.settings = QtCore.QSettings("SaxStudio", "SaxStudio")
        self.setWindowTitle(f"{APP_NAME} {VERSION_LABEL}")
        self.setWindowIcon(application_icon())
        self.resize(1440, 980)
        self.setMinimumSize(1120, 800)
        self.setStyleSheet(style_sheet())
        self.build_ui()
        self.video_player = player(self, self.video_widget, muted=True)
        self.audio_player = player(self)
        self.video_player.positionChanged.connect(self.on_position)
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
        version.setStyleSheet("color: #32d4ce; font-size: 12px; font-weight: 600; padding-left: 8px;")
        header.addWidget(version)
        header.addStretch()
        self.export_button = button("匯出影片 / 音訊", self.export_dialog, True)
        header.addWidget(self.export_button)
        layout.addLayout(header)
        toolbar = W.QHBoxLayout()
        self.import_video_button = button("匯入影片", self.import_video)
        self.import_back_button = button("匯入伴奏", self.import_backing)
        for b in [self.import_video_button, self.import_back_button,
                  button("開啟專案", self.open_project), button("儲存專案", self.save_project)]:
            toolbar.addWidget(b)
        self.project_label = W.QLabel("尚未匯入影片")
        self.project_label.setObjectName("muted")
        toolbar.addWidget(self.project_label, 1)
        reset_layout = button("重設版面", self.reset_layout)
        reset_layout.setToolTip("把效果區、影片區與音訊條恢復為預設大小")
        toolbar.addWidget(reset_layout)
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
        fx_title = W.QLabel("第一軌 · 影片原音 效果")
        fx_title.setStyleSheet("color: #27c9c3; font-weight: 600;")
        fx_title.setToolTip("EQ、壓縮、混響只處理影片原音；匯入的伴奏不會套用這些效果")
        fx_header.addWidget(fx_title)
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
        self.video_empty.setStyleSheet("background: #0b121c; color: #8498ae; border: 1px solid #304359; border-radius: 8px;")
        self.video_widget = QtMultimediaWidgets.QVideoWidget()
        self.video_widget.setMinimumSize(240, 135)
        self.video_stack.setMinimumSize(240, 135)
        self.video_stack.addWidget(self.video_empty)
        self.video_stack.addWidget(self.video_widget)
        right.addWidget(self.video_stack, 1)
        self.video_name = W.QLabel("影片預覽 · 尚未匯入")
        self.video_name.setObjectName("muted")
        self.video_name.setWordWrap(True)
        right.addWidget(self.video_name)
        edits = W.QFrame()
        edits.setObjectName("card")
        edits_outer = W.QVBoxLayout(edits)
        edits_outer.setContentsMargins(10, 4, 10, 6)
        edits_head = W.QHBoxLayout()
        self.edits_toggle = W.QToolButton()
        self.edits_toggle.setObjectName("section")
        self.edits_toggle.setCheckable(True)
        self.edits_toggle.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
        self.edits_toggle.setToolTip("展開或收合時間剪輯工具（影片與伴奏同步剪輯）")
        self.edits_toggle.toggled.connect(self.set_edits_expanded)
        edits_head.addWidget(self.edits_toggle)
        edits_head.addStretch()
        self.edits_summary = W.QLabel("未剪輯")
        self.edits_summary.setObjectName("muted")
        edits_head.addWidget(self.edits_summary)
        edits_outer.addLayout(edits_head)
        self.edits_body = W.QWidget()
        edits_layout = W.QVBoxLayout(self.edits_body)
        edits_layout.setContentsMargins(0, 0, 0, 0)
        edits_outer.addWidget(self.edits_body)
        marks = W.QHBoxLayout()
        self.mark_start = spin(0, 86400, 0, 3, " s")
        self.mark_end = spin(0, 86400, 0, 3, " s")
        marks.addWidget(button("起點 ←", lambda: self.mark_start.setValue(self.position)))
        marks.addWidget(self.mark_start)
        marks.addWidget(button("終點 ←", lambda: self.mark_end.setValue(self.position)))
        marks.addWidget(self.mark_end)
        edits_layout.addLayout(marks)
        edit_buttons = W.QHBoxLayout()
        for b in [button("保留起訖範圍", self.trim), button("分割", self.split), button("刪除片段", self.delete_clip)]:
            edit_buttons.addWidget(b)
        edits_layout.addLayout(edit_buttons)
        auto_row = W.QHBoxLayout()
        auto_row.addWidget(W.QLabel("自動裁剪保留：伴奏前"))
        self.pre_roll = spin(0, 30, self.float_setting("edit/pre_roll", 3.0), 1, " s")
        auto_row.addWidget(self.pre_roll)
        auto_row.addWidget(W.QLabel("伴奏後"))
        self.post_roll = spin(0, 30, self.float_setting("edit/post_roll", 2.0), 1, " s")
        auto_row.addWidget(self.post_roll)
        auto_row.addStretch()
        self.pre_roll.valueChanged.connect(lambda v: self.settings.setValue("edit/pre_roll", v))
        self.post_roll.valueChanged.connect(lambda v: self.settings.setValue("edit/post_roll", v))
        edits_layout.addLayout(auto_row)
        self.clip_list = W.QListWidget()
        self.clip_list.setMaximumHeight(95)
        self.clip_list.currentRowChanged.connect(self.select_clip)
        edits_layout.addWidget(self.clip_list)
        undo_row = W.QHBoxLayout()
        self.undo_button = button("復原剪輯", self.undo)
        undo_row.addWidget(self.undo_button)
        undo_row.addWidget(button("重設剪輯", self.reset_edits))
        self.duration_label = W.QLabel("輸出長度 00:00.000")
        undo_row.addWidget(self.duration_label)
        edits_layout.addLayout(undo_row)
        right.addWidget(edits)
        self.h_split.addWidget(right_widget)
        self.h_split.setStretchFactor(0, 3)
        self.h_split.setStretchFactor(1, 2)
        lower_widget = W.QWidget()
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
        self.align_button = button("自動對齊前奏", self.align)
        align_row.addWidget(self.align_button)
        self.autotrim_button = button("依伴奏自動裁剪", self.auto_trim)
        self.autotrim_button.setToolTip("以伴奏實際有聲音的範圍為準，保留伴奏開始前與結束後的設定秒數，其餘剪掉（可復原）")
        align_row.addWidget(self.autotrim_button)
        self.align_label = W.QLabel("匯入伴奏後可比對前 90 秒")
        self.align_label.setObjectName("muted")
        align_row.addWidget(self.align_label, 1)
        align_row.addWidget(W.QLabel("伴奏位移（＋延後／－提前）"))
        self.offset = spin(-86400000, 86400000, 0, 1, " ms")
        self.offset.setSingleStep(1)
        self.offset.setMinimumWidth(145)
        self.offset.valueChanged.connect(self.change_mix)
        align_row.addWidget(self.offset)
        lower.addLayout(align_row)
        tracks = W.QHBoxLayout()
        track_controls = W.QVBoxLayout()
        track_controls.setContentsMargins(0, 28, 0, 6)
        self.volume_fields = []
        for label, color, value, hint in [
                ("第一軌 · 影片原音", "#27c9c3", 0, "套用上方 EQ／壓縮／混響"),
                ("第二軌 · 伴奏", "#e9b853", -6, "只調整音量與位移，不套用音效")]:
            frame = W.QFrame()
            frame.setObjectName("card")
            f = W.QVBoxLayout(frame)
            name = W.QLabel(label)
            name.setStyleSheet(f"color: {color}; font-weight: 600;")
            head = W.QHBoxLayout()
            head.addWidget(name)
            head.addStretch()
            hint_label = W.QLabel(hint)
            hint_label.setObjectName("muted")
            head.addWidget(hint_label)
            f.addLayout(head)
            row = W.QHBoxLayout()
            slider = W.QSlider(QtCore.Qt.Horizontal)
            slider.setRange(-600, 120)
            slider.setValue(value*10)
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
            track_controls.addWidget(frame)
            self.volume_fields.append((field, mute))
        track_widget = W.QWidget()
        track_widget.setLayout(track_controls)
        track_widget.setFixedWidth(310)
        tracks.addWidget(track_widget)
        self.timeline = Timeline()
        self.timeline.seek.connect(self.seek)
        self.timeline.select.connect(self.clip_list.setCurrentRow)
        tracks.addWidget(self.timeline, 1)
        lower.addLayout(tracks, 1)
        layout.addWidget(self.controls, 1)
        transport = W.QHBoxLayout()
        self.play_button = button("▶ 播放", self.toggle_play, True)
        transport.addWidget(self.play_button)
        transport.addWidget(button("■ 停止", self.stop))
        transport.addWidget(button("更新音效預覽", lambda: self.prepare_preview(False)))
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
        expanded = self.settings.value("ui/edits_expanded", False)
        expanded = expanded if isinstance(expanded, bool) else str(expanded).lower() == "true"
        self.edits_toggle.setChecked(expanded)
        self.set_edits_expanded(expanded)
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

    def set_edits_expanded(self, expanded, remember=True):
        self.edits_body.setVisible(expanded)
        self.edits_toggle.setText(("▾" if expanded else "▸") + "  ✂ 時間剪輯")
        if self.edits_toggle.isChecked() != expanded:
            self.edits_toggle.blockSignals(True)
            self.edits_toggle.setChecked(expanded)
            self.edits_toggle.blockSignals(False)
        if remember:
            self.settings.setValue("ui/edits_expanded", expanded)

    def setup_shortcuts(self):
        shortcut_type = QtGui.QShortcut if QT6 else W.QShortcut
        for key, fn in [("Ctrl+S", self.save_project), ("Ctrl+O", self.open_project),
                        ("Ctrl+Z", self.undo), ("Ctrl+B", self.split)]:
            s = shortcut_type(QtGui.QKeySequence(key), self)
            s.activated.connect(fn)

    def load_controls(self):
        self.loading = True
        fx = self.project.effects
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
        self.limiter.setChecked(fx.limiter_enabled)
        self.offset.setValue(self.project.offset*1000)
        for (field, mute), value, muted in zip(self.volume_fields,
                                             (self.project.video_db, self.project.backing_db),
                                             (self.project.video_muted, self.project.backing_muted)):
            field.setValue(value)
            mute.setChecked(muted)
        self.preset.setCurrentIndex(0)
        self.loading = False
        self.eq_graph.effects = fx
        self.eq_graph.update()

    def change_effects(self, *args):
        if self.loading:
            return
        fx = self.project.effects
        fx.eq_enabled = self.eq_toggle.isChecked()
        fx.highpass = self.highpass.value()
        for band, fields in zip(fx.bands, self.bands):
            band.frequency, band.gain, band.q = [f.value() for f in fields]
        for key, widget in self.fx_fields.items():
            setattr(fx, key, widget.isChecked() if key.endswith("enabled") else
                    widget.value()/100 if key == "mix" else widget.value())
        fx.limiter_enabled = self.limiter.isChecked()
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
        self.timeline.update()
        self.mark_dirty(audio=True)

    def apply_preset(self, index):
        if self.loading or index == 0:
            return
        backup = copy.deepcopy(self.project.effects)
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
        self.project.effects = fx
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
        self.project.effects = copy.deepcopy(self.preset_backup[1])
        self.preset_backup = None
        self.preset_undo.setEnabled(False)
        self.load_controls()
        self.mark_dirty(audio=True)
        self.statusBar().showMessage("已還原套用快速音色之前的設定")

    def mark_dirty(self, audio=False):
        self.dirty = True
        if audio:
            self.pause()
            self.preview_dirty = True
            self.preview_label.setText("音效已變更 · 按播放更新")
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
            self.mark_dirty(audio=True)
            self.align_label.setText("匯入伴奏後可比對前 90 秒")
            self.statusBar().showMessage("影片已匯入，接著可匯入伴奏")
            self.refresh()
        self.launch(task, done)

    def import_backing(self):
        if self.busy or not self.project.video:
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
            self.project.backing, self.project.offset = path, 0
            self.timeline.back_wave = wave
            self.timeline.back_duration = info["duration"]
            self.load_controls()
            self.mark_dirty(audio=True)
            self.align_label.setText("尚未對齊 · 請按自動對齊前奏")
            self.statusBar().showMessage("伴奏已匯入")
            self.refresh()
        self.launch(task, done)

    def load_media(self, still=None):
        self.pause()
        self.video_failed = False
        self.video_stack.setCurrentWidget(self.video_widget)
        source(self.video_player, self.project.video)
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
        self.video_name.setText(Path(self.project.video).name)
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
        if self.busy or not self.project.video:
            return
        if not self.preview_dirty and self.preview_path:
            if autoplay:
                self.start_play()
            return
        snapshot = copy.deepcopy(self.project)
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
            if old:
                try:
                    Path(old).unlink(missing_ok=True)
                except PermissionError:
                    pass
            self.preview_dirty = False
            self.preview_label.setText("音效預覽已更新")
            self.statusBar().showMessage("預覽已就緒，音效與輸出使用相同處理流程")
            if autoplay:
                # Media loading is asynchronous; wait for both media to be loaded.
                self.pending_play = True
                self.pending_since = QtCore.QDateTime.currentMSecsSinceEpoch()
        self.pending_play = False
        self.launch(task, done)

    def toggle_play(self):
        if self.busy:
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
        if not self.video_failed:
            self.video_stack.setCurrentWidget(self.video_widget)
        self.video_player.play()
        self.audio_player.play()
        self.playing = True
        self.play_button.setText("Ⅱ 暫停")

    def pause(self):
        if hasattr(self, "video_player"):
            self.video_player.pause()
            self.audio_player.pause()
        self.playing = False
        self.pending_play = False
        if hasattr(self, "play_button"):
            self.play_button.setText("▶ 播放")

    def stop(self):
        if self.busy:
            return
        self.pause()
        self.seek(self.project.clips[0].start if self.project.clips else 0)
        self.level.setValue(0)

    def seek(self, position):
        self.position = max(0, min(position, self.project.duration))
        if self.project.video and not self.playing and not self.video_failed:
            # Show the real frame at the playhead instead of the import still.
            if state_stopped(self.video_player):
                self.video_player.play()
                self.video_player.pause()
            self.video_stack.setCurrentWidget(self.video_widget)
        self.jumping = True
        self.video_player.setPosition(round(self.position*1000))
        self.audio_player.setPosition(round(self.position*1000))
        self.jumping = False
        self.timeline.position = self.position
        self.timeline.update()
        self.time_label.setText(f"原片時間 {clock(self.position)}")

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
        self.timeline.position = self.position
        self.timeline.update()
        self.time_label.setText(f"原片時間 {clock(self.position)}")

    def sync_players(self):
        if self.pending_play and not self.busy:
            media_status = QtMultimedia.QMediaPlayer.MediaStatus if QT6 else QtMultimedia.QMediaPlayer
            statuses = (self.video_player.mediaStatus(), self.audio_player.mediaStatus())
            ready = (media_status.LoadedMedia, media_status.BufferedMedia, media_status.EndOfMedia)
            waited = QtCore.QDateTime.currentMSecsSinceEpoch() - self.pending_since
            if media_status.InvalidMedia in statuses:
                self.pending_play = False
                self.statusBar().showMessage("預覽媒體無法載入；請確認影片編碼，仍可嘗試匯出")
            elif all(s in ready for s in statuses):
                self.pending_play = False
                self.start_play()
            elif waited > 8000:
                # Some backends never report Loaded for a paused source; try anyway.
                self.pending_play = False
                self.statusBar().showMessage("媒體載入較慢，嘗試直接播放")
                self.start_play()
        if self.playing:
            # The rendered mix is the master clock: nudging the muted video is
            # invisible compared with audible jumps in the music.
            drift = self.audio_player.position()-self.video_player.position()
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
        if self.busy or not self.project.video or not self.project.backing:
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
        self.set_edits_expanded(True, remember=False)
        self.mark_dirty()
        self.refresh()
        self.seek(start)
        self.statusBar().showMessage(f"已自動裁剪：保留 {clock(start)} → {clock(end)}（伴奏前 {self.pre_roll.value():g} 秒、後 {self.post_roll.value():g} 秒）")

    def trim(self):
        if not self.project.video or self.busy:
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
        if not self.project.video or self.busy:
            return
        snapshot = copy.deepcopy(self.project.clips)
        if self.project.split(self.position):
            self.set_edits_expanded(True, remember=False)
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
            self.set_edits_expanded(True, remember=False)
            self.pause()
            self.project.clips = self.undo_stack.pop()
            self.mark_dirty()
            self.refresh()

    def reset_edits(self):
        if not self.project.video or self.busy:
            return
        self.push_undo()
        self.project.clips = [Clip(0, self.project.duration)]
        self.mark_start.setValue(0)
        self.mark_end.setValue(self.project.duration)
        self.mark_dirty()
        self.refresh()

    def select_clip(self, index):
        self.timeline.selected = index
        self.timeline.update()

    def refresh(self):
        has = bool(self.project.video)
        self.controls.setEnabled(not self.busy)
        self.import_video_button.setEnabled(not self.busy)
        self.import_back_button.setEnabled(has and not self.busy)
        self.align_button.setEnabled(bool(self.project.backing) and not self.busy)
        self.autotrim_button.setEnabled(bool(self.project.backing) and bool(self.backing_range) and not self.busy)
        self.export_button.setEnabled(has and bool(self.project.clips) and not self.busy)
        self.play_button.setEnabled(has and bool(self.project.clips) and not self.busy)
        self.limiter.setEnabled(not self.busy)
        self.undo_button.setEnabled(bool(self.undo_stack) and not self.busy)
        selected = self.clip_list.currentRow()
        self.clip_list.blockSignals(True)
        self.clip_list.clear()
        for i, c in enumerate(self.project.clips):
            self.clip_list.addItem(f"{i+1:02}    {clock(c.start)} → {clock(c.end)}    ·    {c.end-c.start:.2f} s")
        self.clip_list.setCurrentRow(min(selected, len(self.project.clips)-1))
        self.clip_list.blockSignals(False)
        self.timeline.selected = self.clip_list.currentRow()
        self.timeline.project = self.project
        self.timeline.update()
        self.duration_label.setText(f"輸出 {clock(self.project.output_duration)}")
        whole = [Clip(0, self.project.duration)]
        if not has:
            self.edits_summary.setText("尚未匯入影片")
        elif self.project.clips == whole:
            self.edits_summary.setText(f"未剪輯 · {clock(self.project.duration)}")
        else:
            self.edits_summary.setText(f"已剪輯 · {len(self.project.clips)} 段 · 輸出 {clock(self.project.output_duration)}")
        self.project_label.setText(Path(self.project.video).name if has else "尚未匯入影片")

    def save_project(self):
        if self.busy or not self.project.video:
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
        if self.busy:
            return
        path, _ = W.QFileDialog.getOpenFileName(self, "開啟專案", "", f"{APP_NAME} 專案 (*.saxproj)")
        if not path or not self.confirm_discard():
            return
        def task(cancel, progress):
            progress("正在讀取專案與波形…")
            p = Project.load(path)
            if not p.video:
                raise ValueError("專案沒有影片")
            for name, title in (("video", "影片"), ("backing", "伴奏")):
                value = getattr(p, name)
                if value and not Path(value).is_file():
                    raise ValueError(f"找不到{title}：{value}\n請將原始檔移回原位置，或在 .saxproj 中更新路徑。")
            vinfo = probe(p.video, cancel)
            if not vinfo["video"] or not vinfo["audio"]:
                raise ValueError("專案影片缺少畫面或音訊")
            if abs(vinfo["duration"]-p.duration) > .5:
                raise ValueError("影片長度與專案不同，原始檔可能已被修改")
            vwave = waveform(p.video, cancel)
            still = Path(self.temp.name)/"project-still.jpg"
            thumbnail(p.video, still, cancel)
            bwave, bd, audible = np.array([]), 0, None
            if p.backing:
                bd = probe(p.backing, cancel)["duration"]
                bwave = waveform(p.backing, cancel)
                audible = backing_range(p.backing, cancel)
            return p, vwave, bwave, bd, str(still), audible
        def done(result):
            (self.project, self.timeline.video_wave, self.timeline.back_wave,
             self.timeline.back_duration, still, self.backing_range) = result
            self.alignment_reliable = None
            self.preset_backup = None
            self.preset_undo.setEnabled(False)
            self.project_path = path
            self.undo_stack.clear()
            self.load_media(still)
            self.load_controls()
            self.dirty = False
            self.preview_label.setText("按播放建立音效預覽")
            self.align_label.setText("已讀取儲存的位移 · 請播放核對")
            self.setWindowTitle(f"{APP_NAME} {VERSION_LABEL} · {Path(path).name}")
            self.statusBar().showMessage("專案已開啟")
            self.refresh()
        self.launch(task, done)

    def export_dialog(self):
        if self.busy or not self.project.video or not self.project.clips:
            return
        destination, selected_filter = W.QFileDialog.getSaveFileName(
            self, "匯出混音成品", str(Path(self.project.video).with_name(Path(self.project.video).stem + "_混音")),
            "MP4 影片 (*.mp4);;WAV 音訊 (*.wav);;MP3 音訊 (*.mp3)")
        if not destination:
            return
        if not Path(destination).suffix:
            destination += ".wav" if selected_filter.startswith("WAV") else ".mp3" if selected_filter.startswith("MP3") else ".mp4"
        snapshot = copy.deepcopy(self.project)
        self.launch(lambda cancel, progress: export(snapshot, destination, cancel, progress),
                    lambda output: self.statusBar().showMessage(f"匯出完成：{output}"))

    def closeEvent(self, event):
        if self.busy:
            self.statusBar().showMessage("請先取消作業，等待完成後再關閉")
            event.ignore()
            return
        if not self.confirm_discard():
            event.ignore()
            return
        self.pause()
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
