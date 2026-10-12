from __future__ import annotations

import copy
import sys
import tempfile
from pathlib import Path

import numpy as np

from . import __version__
from .branding import APP_NAME, StartupSplash, application_icon, set_windows_identity
from .effect_panels import CollapsibleEffect
from .alignment import align_files
from .engine import audio_origin, export, render_mix
from .media import check_ffmpeg, decode_mono, probe, thumbnail, waveform
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


def dark_palette():
    palette = QtGui.QPalette()
    roles = QtGui.QPalette.ColorRole if QT6 else QtGui.QPalette
    for role, color in [("Window", "#101923"), ("WindowText", "#e5edf7"), ("Base", "#101d2b"),
                        ("AlternateBase", "#182635"), ("Text", "#e5edf7"), ("Button", "#24384c"),
                        ("ButtonText", "#e5edf7"), ("Highlight", "#28646a"), ("HighlightedText", "#ffffff"),
                        ("ToolTipBase", "#253d51"), ("ToolTipText", "#eff7ff")]:
        palette.setColor(getattr(roles, role), QtGui.QColor(color))
    return palette


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
        self.pending_since = 0.0
        self.last_resync = 0.0
        self.settings = QtCore.QSettings("SaxStudio", "SaxStudio")
        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.setWindowIcon(application_icon())
        self.resize(1440, 980)
        self.setMinimumSize(1120, 800)
        self.setStyleSheet(STYLE)
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
        layout.addLayout(toolbar)
        self.controls = W.QWidget()
        controls_layout = W.QVBoxLayout(self.controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(10)
        upper = W.QHBoxLayout()
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
        self.preset = W.QComboBox()
        self.preset.addItems(["自訂", "自然乾聲", "溫暖薩克斯風", "明亮獨奏", "柔和空間"])
        self.preset.currentIndexChanged.connect(self.apply_preset)
        fx_header.addWidget(self.preset)
        fx_layout.addLayout(fx_header)
        eq_box = W.QGroupBox("參數 EQ")
        eq_layout = W.QVBoxLayout(eq_box)
        eq_top = W.QHBoxLayout()
        self.eq_toggle = W.QCheckBox("啟用 EQ")
        eq_top.addWidget(self.eq_toggle)
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
        fx_layout.addWidget(eq_box)
        effects_row = W.QHBoxLayout()
        effects_row.setAlignment(QtCore.Qt.AlignTop)
        self.fx_fields = {}
        self.effect_sections = {}
        for name, enabled_name, params in [
            ("Comp 壓縮", "compressor_enabled", [
                ("threshold", "門檻", -60, 0, -18, " dB"),
                ("ratio", "比例", 1, 20, 3, " : 1"),
                ("attack", "啟動", .1, 200, 15, " ms"),
                ("release", "釋放", 10, 2000, 120, " ms"),
                ("makeup", "補償", 0, 24, 0, " dB")]),
            ("Revb 混響", "reverb_enabled", [
                ("mix", "乾濕 Mix", 0, 100, 18, " %"),
                ("decay", "衰減 RT60", .2, 5, 1.6, " s"),
                ("predelay", "預延遲", 0, 150, 20, " ms")])]:
            group = CollapsibleEffect(name)
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
        scroll = W.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(fx_area)
        upper.addWidget(scroll, 6)
        right = W.QVBoxLayout()
        self.video_stack = W.QStackedWidget()
        self.video_empty = W.QLabel("影片預覽\n\n匯入演奏影片後，可在此核對聲畫")
        self.video_empty.setAlignment(QtCore.Qt.AlignCenter)
        self.video_empty.setObjectName("muted")
        self.video_empty.setStyleSheet("background: #0b121c; color: #8498ae; border: 1px solid #304359; border-radius: 8px;")
        self.video_widget = QtMultimediaWidgets.QVideoWidget()
        self.video_widget.setMinimumSize(340, 190)
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
        upper.addLayout(right, 5)
        controls_layout.addLayout(upper, 1)
        align_row = W.QHBoxLayout()
        self.align_button = button("自動對齊前奏", self.align)
        align_row.addWidget(self.align_button)
        self.align_label = W.QLabel("匯入伴奏後可比對前 90 秒")
        self.align_label.setObjectName("muted")
        align_row.addWidget(self.align_label, 1)
        align_row.addWidget(W.QLabel("伴奏位移（＋延後／－提前）"))
        self.offset = spin(-86400000, 86400000, 0, 1, " ms")
        self.offset.setSingleStep(1)
        self.offset.setMinimumWidth(145)
        self.offset.valueChanged.connect(self.change_mix)
        align_row.addWidget(self.offset)
        controls_layout.addLayout(align_row)
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
        controls_layout.addLayout(tracks)
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
        self.loading = True
        self.preset.setCurrentIndex(0)
        self.loading = False
        self.eq_graph.update()
        self.mark_dirty(audio=True)

    def change_mix(self, *args):
        if self.loading:
            return
        self.project.offset = self.offset.value()/1000
        self.project.video_db, self.project.backing_db = [f.value() for f, _ in self.volume_fields]
        self.project.video_muted, self.project.backing_muted = [m.isChecked() for _, m in self.volume_fields]
        self.timeline.update()
        self.mark_dirty(audio=True)

    def apply_preset(self, index):
        if self.loading or index == 0:
            return
        fx = Effects()
        # Keep the original tone presets' processing choices; only new projects
        # start with Comp/Revb bypassed. Loading a project restores its own flags.
        fx.compressor_enabled = fx.reverb_enabled = index != 1
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
        self.load_controls()
        self.loading = True
        self.preset.setCurrentIndex(index)
        self.loading = False
        self.mark_dirty(audio=True)

    def mark_dirty(self, audio=False):
        self.dirty = True
        if audio:
            self.pause()
            self.preview_dirty = True
            self.preview_label.setText("音效已變更 · 按播放更新")
        self.setWindowTitle(f"{APP_NAME} {__version__} · 未儲存")

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
            return info, waveform(path, cancel)
        def done(result):
            info, wave = result
            self.project.backing, self.project.offset = path, 0
            self.timeline.back_wave = wave
            self.timeline.back_duration = info["duration"]
            self.load_controls()
            self.mark_dirty(audio=True)
            self.align_label.setText("尚未對齊 · 請按自動對齊前奏")
            self.statusBar().showMessage("伴奏已匯入")
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
            self.align_label.setText(f"可信度 {result.confidence:.0%} · {result.message}")
            self.statusBar().showMessage("位移已套用；請播放前奏核對，長影片也請核對結尾")
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
            self.setWindowTitle(f"{APP_NAME} {__version__} · {Path(path).name}")
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
            bwave, bd = np.array([]), 0
            if p.backing:
                bd = probe(p.backing, cancel)["duration"]
                bwave = waveform(p.backing, cancel)
            return p, vwave, bwave, bd, str(still)
        def done(result):
            self.project, self.timeline.video_wave, self.timeline.back_wave, self.timeline.back_duration, still = result
            self.project_path = path
            self.undo_stack.clear()
            self.load_media(still)
            self.load_controls()
            self.dirty = False
            self.preview_label.setText("按播放建立音效預覽")
            self.align_label.setText("已讀取儲存的位移 · 請播放核對")
            self.setWindowTitle(f"{APP_NAME} {__version__} · {Path(path).name}")
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
    import time
    set_windows_identity()
    app = W.QApplication(sys.argv)
    # Fusion draws spin-box arrows consistently; the Windows 11 style lays them
    # out side by side and its hit areas do not match the custom stylesheet.
    app.setStyle("Fusion")
    app.setPalette(dark_palette())
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("SaxStudio")
    app.setWindowIcon(application_icon())
    splash = StartupSplash(app.windowIcon())
    started = time.monotonic()
    splash.show()
    app.processEvents()
    window = MainWindow()
    window.show()
    def verify_tools():
        try:
            problems = check_ffmpeg()
        except Exception as exc:
            problems = [f"FFmpeg 無法執行：{exc}"]
        if problems:
            window.show_error("FFmpeg 不符合需求，部分功能會失敗\n" + "\n".join(problems) +
                              "\n\n請將 FFmpeg 7.1 以上的完整版 ffmpeg.exe／ffprobe.exe 放進 tools 資料夾。")
    def finish_startup():
        splash.finish(window)
        QtCore.QTimer.singleShot(150, verify_tools)
    QtCore.QTimer.singleShot(max(0, round(900-(time.monotonic()-started)*1000)), finish_startup)
    sys.exit(app.exec() if QT6 else app.exec_())


if __name__ == "__main__":
    main()
