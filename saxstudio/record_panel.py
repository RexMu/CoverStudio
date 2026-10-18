"""Widgets for record mode: input meter, recording panel and dialogs."""
from __future__ import annotations

import math

from .qt import QtCore, QtGui, QtWidgets as W, Signal
from . import theme


def db(value):
    return 20 * math.log10(max(value, 1e-6))


class LevelMeter(W.QWidget):
    """Segmented peak meter, -60 to 0 dBFS, with peak hold and clip latch."""
    SEGMENTS = 30

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(16)
        self.setMaximumHeight(18)
        self.value = 0.0
        self.hold = 0.0
        self.hold_time = 0.0
        self.clipped = False
        self.decay = QtCore.QElapsedTimer()
        self.decay.start()
        self.setAccessibleName("輸入音量表")

    def set_level(self, peak):
        now = self.decay.elapsed() / 1000
        # Smooth fall so the meter is readable at ~60 updates per second.
        self.value = max(peak, self.value * .85)
        if peak >= self.hold or now - self.hold_time > 1.5:
            self.hold, self.hold_time = peak, now
        self.update()

    def reset_clip(self):
        self.clipped = False
        self.update()

    @staticmethod
    def position(value):
        return max(0.0, min(1.0, (db(value) + 60) / 60))

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        n = self.SEGMENTS
        gap = 2
        width = (self.width() - gap * (n - 1)) / n
        lit = round(self.position(self.value) * n)
        hold = min(n - 1, round(self.position(self.hold) * n) - 1)
        for i in range(n):
            # 2 dB per segment: yellow from -12 dB, red from -4 dB.
            if i >= 28:
                color = "#ff5a4f"
            elif i >= 24:
                color = "#e9b853"
            else:
                color = "#2ac5bf"
            on = i < lit or i == hold
            p.setBrush(QtGui.QColor(theme.c(color if on else "#22344a")))
            p.setPen(QtCore.Qt.NoPen)
            p.drawRoundedRect(QtCore.QRectF(i * (width + gap), 0, width, self.height()), 2, 2)


def _labelled(text, widget):
    box = W.QVBoxLayout()
    box.setSpacing(4)
    label = W.QLabel(text)
    label.setObjectName("muted")
    label.setBuddy(widget)
    box.addWidget(label)
    box.addWidget(widget)
    return box


class RecordPanel(W.QFrame):
    """Right-hand panel in record mode (replaces the video preview)."""
    device_changed = Signal()
    record_requested = Signal()
    stop_requested = Signal()
    calibrate_requested = Signal()
    play_requested = Signal()
    volume_changed = Signal(float)
    punch_requested = Signal()
    undo_punch_requested = Signal()
    settings_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        layout = W.QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)
        head = W.QHBoxLayout()
        title = W.QLabel("● 錄音")
        theme.apply(title, "font-size: 15px; font-weight: 700; color: #ff8a7a;")
        head.addWidget(title)
        head.addStretch()
        self.format_label = W.QLabel("48 kHz · 32-bit 浮點 · 單聲道")
        self.format_label.setObjectName("muted")
        head.addWidget(self.format_label)
        layout.addLayout(head)

        # ---- settings fold: devices, countdown, headphone volume, latency
        self.fold = W.QFrame()
        self.fold.setObjectName("settingsFold")
        theme.apply(self.fold, "QFrame#settingsFold { background: #132232; border: 1px solid #2c4156; border-radius: 6px; }")
        fold_box = W.QVBoxLayout(self.fold)
        fold_box.setContentsMargins(10, 6, 10, 8)
        fold_box.setSpacing(4)
        fold_head = W.QHBoxLayout()
        self.fold_button = W.QToolButton()
        self.fold_button.setObjectName("foldButton")
        self.fold_button.setText("⚙ 錄音設定")
        self.fold_button.setCheckable(True)
        self.fold_button.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.fold_button.setArrowType(QtCore.Qt.RightArrow)
        self.fold_button.setAccessibleName("展開或收合錄音設定")
        theme.apply(self.fold_button, "QToolButton { border: none; font-weight: 600; padding: 2px 0; }")
        self.fold_button.toggled.connect(self.set_settings_expanded)
        fold_head.addWidget(self.fold_button)
        fold_head.addStretch()
        self.fold_hint = W.QLabel("展開")
        self.fold_hint.setObjectName("muted")
        fold_head.addWidget(self.fold_hint)
        fold_box.addLayout(fold_head)
        self.summary = W.QLabel("")
        self.summary.setObjectName("muted")
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(QtCore.Qt.RichText)
        fold_box.addWidget(self.summary)
        self.fold_body = W.QWidget()
        body = W.QVBoxLayout(self.fold_body)
        body.setContentsMargins(0, 4, 0, 0)
        body.setSpacing(8)
        fold_box.addWidget(self.fold_body)
        layout.addWidget(self.fold)

        grid = W.QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        self.input_combo = W.QComboBox()
        self.channel_combo = W.QComboBox()
        self.output_combo = W.QComboBox()
        self.countdown_combo = W.QComboBox()
        for text, value in (("3 秒", 3), ("5 秒", 5), ("關閉", 0)):
            self.countdown_combo.addItem(text, value)
        for i, (text, combo) in enumerate((("輸入裝置", self.input_combo), ("輸入聲道", self.channel_combo),
                                           ("耳機輸出", self.output_combo), ("開始前倒數", self.countdown_combo))):
            grid.addLayout(_labelled(text, combo), i // 2, i % 2)
        body.addLayout(grid)
        self.input_combo.currentIndexChanged.connect(lambda *_: self.device_changed.emit())
        self.channel_combo.currentIndexChanged.connect(lambda *_: self.device_changed.emit())
        self.output_combo.currentIndexChanged.connect(lambda *_: self.device_changed.emit())

        meter_head = W.QHBoxLayout()
        label = W.QLabel("輸入音量")
        label.setObjectName("muted")
        meter_head.addWidget(label)
        meter_head.addStretch()
        self.level_text = W.QLabel("—")
        self.recent_peak, self.recent_time = 0.0, 0.0
        meter_head.addWidget(self.level_text)
        layout.addLayout(meter_head)
        self.meter = LevelMeter()
        layout.addWidget(self.meter)
        scale = W.QHBoxLayout()
        for i, text in enumerate(("-60", "-24", "-12", "-4", "0 dB")):
            if i:
                scale.addStretch()
            mark = W.QLabel(text)
            theme.apply(mark, "color: #6f8396; font-size: 10px;")
            scale.addWidget(mark)
        layout.addLayout(scale)
        self.clip_label = W.QLabel("試吹最大聲的段落，峰值落在黃色區（-12～-6 dB）最理想")
        self.clip_label.setObjectName("muted")
        layout.addWidget(self.clip_label)

        volume_row = W.QHBoxLayout()
        label = W.QLabel("耳機裡的伴奏音量")
        label.setObjectName("muted")
        volume_row.addWidget(label)
        self.volume_slider = W.QSlider(QtCore.Qt.Horizontal)
        self.volume_slider.setRange(-300, 0)
        self.volume_slider.setValue(-60)
        self.volume_slider.setAccessibleName("耳機裡的伴奏音量")
        volume_row.addWidget(self.volume_slider, 1)
        self.volume_text = W.QLabel("-6.0 dB")
        volume_row.addWidget(self.volume_text)
        body.addLayout(volume_row)
        self.volume_slider.valueChanged.connect(self._volume)

        latency = W.QFrame()
        latency.setObjectName("latencyBox")
        theme.apply(latency, "QFrame#latencyBox { background: #132232; border: 1px solid #2c4156; border-radius: 6px; }")
        row = W.QHBoxLayout(latency)
        row.setContentsMargins(10, 6, 10, 6)
        label = W.QLabel("延遲補償")
        label.setObjectName("muted")
        row.addWidget(label)
        self.latency_value = W.QLabel("尚未校正")
        theme.apply(self.latency_value, "font-weight: 600;")
        row.addWidget(self.latency_value)
        row.addStretch()
        self.calibrate_button = W.QPushButton("校正")
        self.calibrate_button.clicked.connect(self.calibrate_requested.emit)
        row.addWidget(self.calibrate_button)
        body.addWidget(latency)
        for combo in (self.input_combo, self.channel_combo, self.output_combo, self.countdown_combo):
            combo.currentIndexChanged.connect(lambda *_: self.update_summary())
        self.latency_ms = None
        self.fold_body.hide()

        self.states = W.QStackedWidget()
        ready = W.QWidget()
        box = W.QVBoxLayout(ready)
        box.setContentsMargins(0, 0, 0, 0)
        self.record_button = W.QPushButton("●  開始錄音")
        self.record_button.setObjectName("record")
        self.record_button.clicked.connect(self.record_requested.emit)
        box.addWidget(self.record_button)
        self.ready_hint = W.QLabel("按下後倒數，伴奏從頭播放；跟著伴奏吹完後按停止，伴奏播完也會自動停止。")
        self.ready_hint.setObjectName("muted")
        self.ready_hint.setWordWrap(True)
        box.addWidget(self.ready_hint)
        self.states.addWidget(ready)

        active = W.QWidget()
        box = W.QVBoxLayout(active)
        box.setContentsMargins(0, 0, 0, 0)
        status = W.QHBoxLayout()
        self.rec_state = W.QLabel("● 錄音中")
        theme.apply(self.rec_state, "color: #ff8a7a; font-weight: 700;")
        status.addWidget(self.rec_state)
        self.rec_time = W.QLabel("00:00.0")
        theme.apply(self.rec_time, "font-size: 18px; font-weight: 600;")
        status.addWidget(self.rec_time)
        status.addStretch()
        self.rec_left = W.QLabel("")
        self.rec_left.setObjectName("muted")
        status.addWidget(self.rec_left)
        box.addLayout(status)
        self.stop_button = W.QPushButton("■  停止錄音")
        self.stop_button.setObjectName("stopRecord")
        self.stop_button.clicked.connect(self.stop_requested.emit)
        box.addWidget(self.stop_button)
        hint = W.QLabel("錄音同時寫入硬碟，程式意外關閉也不會遺失已錄的部分。")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        box.addWidget(hint)
        self.states.addWidget(active)

        done = W.QWidget()
        box = W.QVBoxLayout(done)
        box.setContentsMargins(0, 0, 0, 0)
        self.done_label = W.QLabel("")
        theme.apply(self.done_label, "color: #32d4ce; font-weight: 700;")
        self.done_label.setWordWrap(True)
        box.addWidget(self.done_label)
        buttons = W.QHBoxLayout()
        play = W.QPushButton("▶  播放混音")
        play.setObjectName("primary")
        play.clicked.connect(self.play_requested.emit)
        buttons.addWidget(play)
        self.rerecord_button = W.QPushButton("重錄（取代整段）")
        self.rerecord_button.setToolTip("伴奏、EQ／壓縮／混響、音量與延遲校正都保留，只換掉錄音")
        self.rerecord_button.clicked.connect(self.record_requested.emit)
        buttons.addWidget(self.rerecord_button)
        box.addLayout(buttons)
        self.punch_button = W.QPushButton("●  從 00:00.0 重錄到結尾")
        self.punch_button.setObjectName("punch")
        theme.apply(self.punch_button, "QPushButton#punch { background: #3a2a12; border: 1px solid #e9b853; "
                                       "color: #ffd88a; font-weight: 600; padding: 8px; border-radius: 6px; }"
                                       "QPushButton#punch:disabled { color: #7f6a45; border-color: #5a4a2a; }")
        self.punch_button.setToolTip("起點＝播放頭位置（點下方時間軸移動）。起點前 3 秒先播伴奏與目前錄音，"
                                     "到起點開始錄；按停止或伴奏播完結束，起點之後換成新錄音。")
        self.punch_button.clicked.connect(self.punch_requested.emit)
        box.addWidget(self.punch_button)
        undo_row = W.QHBoxLayout()
        self.undo_punch_button = W.QPushButton("↶  復原上一次重錄")
        self.undo_punch_button.clicked.connect(self.undo_punch_requested.emit)
        undo_row.addWidget(self.undo_punch_button, 1)
        self.undo_hint = W.QLabel("")
        self.undo_hint.setObjectName("muted")
        undo_row.addWidget(self.undo_hint)
        box.addLayout(undo_row)
        self.punch_hint = W.QLabel("點下方時間軸設定重錄起點；起點前 3 秒會先播伴奏與目前錄音讓你銜接。")
        self.punch_hint.setObjectName("muted")
        self.punch_hint.setWordWrap(True)
        box.addWidget(self.punch_hint)
        self.file_label = W.QLabel("")
        self.file_label.setObjectName("muted")
        self.file_label.setWordWrap(True)
        self.file_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        box.addWidget(self.file_label)
        self.states.addWidget(done)
        layout.addWidget(self.states)
        self.unavailable = W.QLabel("")
        self.unavailable.setWordWrap(True)
        theme.apply(self.unavailable, "color: #ffb5ac;")
        self.unavailable.hide()
        layout.addWidget(self.unavailable)
        layout.addStretch()
        self.settings_widgets = [self.input_combo, self.channel_combo, self.output_combo,
                                 self.countdown_combo, self.calibrate_button]
        self.update_summary()

    # ---- state
    def _volume(self, value):
        self.volume_text.setText(f"{value/10:.1f} dB")
        if hasattr(self, "summary"):
            self.update_summary()
        self.volume_changed.emit(value / 10)

    @property
    def volume_db(self):
        return self.volume_slider.value() / 10

    @property
    def countdown(self):
        return int(self.countdown_combo.currentData() or 0)

    def set_level(self, peak):
        self.meter.set_level(peak)
        now = self.meter.decay.elapsed() / 1000
        # Highest peak of the last 3 seconds, to compare with the interface's LEDs.
        if peak >= self.recent_peak or now - self.recent_time > 3:
            self.recent_peak, self.recent_time = peak, now
        self.level_text.setText(f"{db(peak):.1f} dB · 3 秒峰值 {db(self.recent_peak):.1f} dB")

    def mark_clipped(self):
        """Sustained full-scale input (see recorder.is_clipping)."""
        self.meter.clipped = True
        self.meter.update()
        self.clip_label.setText("⚠ 破音了！請調低錄音介面的輸入增益；"
                                "若介面燈號未亮，請檢查 Windows 錄音裝置音量是否為 100 並關閉音訊增強")
        theme.apply(self.clip_label, "color: #ff8a7a; font-weight: 600;")

    def reset_clip(self):
        self.meter.reset_clip()
        self.clip_label.setText("音量良好，未破音")
        theme.apply(self.clip_label, "color: #32d4ce;")

    def set_latency(self, ms):
        self.latency_ms = ms
        self.update_summary()
        if ms is None:
            self.latency_value.setText("尚未校正")
            theme.apply(self.latency_value, "font-weight: 600; color: #e9b853;")
            self.calibrate_button.setText("校正")
        else:
            self.latency_value.setText(f"{ms:.1f} ms · 已校正")
            theme.apply(self.latency_value, "font-weight: 600; color: #32d4ce;")
            self.calibrate_button.setText("重新校正")

    def set_state(self, state):
        index = {"ready": 0, "recording": 1, "countdown": 1, "punch": 1, "done": 2}[state]
        self.states.setCurrentIndex(index)
        busy = state in ("recording", "countdown", "punch")
        for widget in self.settings_widgets:
            widget.setEnabled(not busy)
        if busy:
            self.fold_body.hide()   # keep the record controls in view
        else:
            self.fold_body.setVisible(self.fold_button.isChecked())
        self.fold_button.setEnabled(not busy)
        if state == "punch":
            self.rec_state.setText("◔ 預備中")
            theme.apply(self.rec_state, "color: #e9b853; font-weight: 700;")
            self.rec_left.setText("秒後開始錄音")
        else:
            theme.apply(self.rec_state, "color: #ff8a7a; font-weight: 700;")
        if state == "countdown":
            self.rec_state.setText("倒數")
            self.rec_left.setText("伴奏即將開始")

    def set_countdown(self, seconds):
        if seconds > 0:
            self.rec_state.setText("倒數")
            self.rec_time.setText(f"{seconds}")
        else:
            self.rec_state.setText("● 錄音中")

    def set_progress(self, seconds, left):
        if left < 0:
            return  # still counting in; keep the countdown number on screen
        minutes, rest = divmod(seconds, 60)
        self.rec_time.setText(f"{int(minutes):02}:{rest:04.1f}")
        if left >= 0:
            m, s = divmod(left, 60)
            self.rec_left.setText(f"伴奏剩 {int(m):02}:{s:04.1f}")

    def set_done(self, seconds, path, punches=0):
        minutes, rest = divmod(seconds, 60)
        extra = f" · 重錄 {punches} 次" if punches else ""
        self.done_label.setText(f"✓ 已錄 {int(minutes):02}:{rest:04.1f}{extra}")
        self.file_label.setText(f"檔案：{path}")
        self.undo_punch_button.setVisible(bool(punches))
        self.undo_hint.setVisible(bool(punches))
        self.undo_hint.setText(f"可連續復原 {punches} 次")
        self.set_state("done")

    def set_punch_point(self, seconds):
        minutes, rest = divmod(max(0.0, seconds), 60)
        self.punch_button.setText(f"●  從 {int(minutes):02}:{rest:04.1f} 重錄到結尾")

    def set_punch_progress(self, preroll_left, timeline_seconds, backing_left):
        """During a punch-in: count down the preroll, then show the timeline time."""
        if preroll_left > 0:
            self.rec_state.setText("◔ 預備中")
            theme.apply(self.rec_state, "color: #e9b853; font-weight: 700;")
            self.rec_time.setText(f"{preroll_left:.1f}")
            self.rec_left.setText("秒後開始錄音")
            return
        self.rec_state.setText("● 重錄中")
        theme.apply(self.rec_state, "color: #ff8a7a; font-weight: 700;")
        minutes, rest = divmod(timeline_seconds, 60)
        self.rec_time.setText(f"{int(minutes):02}:{rest:04.1f}")
        if backing_left >= 0:
            m, s = divmod(backing_left, 60)
            self.rec_left.setText(f"伴奏剩 {int(m):02}:{s:04.1f}")

    # ---- settings fold
    def set_settings_expanded(self, expanded):
        if self.fold_button.isChecked() != expanded:
            self.fold_button.blockSignals(True)
            self.fold_button.setChecked(expanded)
            self.fold_button.blockSignals(False)
        self.fold_button.setArrowType(QtCore.Qt.DownArrow if expanded else QtCore.Qt.RightArrow)
        self.fold_hint.setText("收合" if expanded else "展開")
        self.fold_body.setVisible(expanded)
        self.summary.setVisible(not expanded)
        self.settings_toggled.emit(expanded)

    def update_summary(self):
        def name(combo):
            return combo.currentText() or "—"
        parts = [f"輸入：{name(self.input_combo)} · {name(self.channel_combo)}",
                 f"耳機：{name(self.output_combo)}"]
        if self.latency_ms is None:
            parts.append(f"<span style='color:{theme.c('#e9b853')}'>⚠ 延遲尚未校正</span>")
        else:
            parts.append(f"延遲 {self.latency_ms:.1f} ms")
        parts.append(f"伴奏 {self.volume_slider.value()/10:.1f} dB")
        parts.append(f"倒數 {self.countdown_combo.currentText() or '—'}")
        self.summary.setText("　｜　".join(parts))

    def set_unavailable(self, message):
        message = message or ""
        self.unavailable.setText(message)
        self.unavailable.setVisible(bool(message))
        self.record_button.setEnabled(not message)
        self.rerecord_button.setEnabled(not message)
        self.punch_button.setEnabled(not message)
        self.calibrate_button.setEnabled(not message)


class NewProjectDialog(W.QDialog):
    """Pick the track-1 source; the mode is fixed for the project's lifetime."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("開始新專案")
        self.choice = None
        layout = W.QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(16)
        title = W.QLabel("開始新專案")
        theme.apply(title, "font-size: 20px; font-weight: 700;")
        layout.addWidget(title)
        hint = W.QLabel("選擇第一軌的來源。模式建立後不會改變，要換模式請開新專案。")
        hint.setObjectName("muted")
        layout.addWidget(hint)
        cards = W.QHBoxLayout()
        cards.setSpacing(14)
        self.cards = {}
        for key, heading, text, formats in (
                ("video", "匯入影片", "使用已經錄好的演奏影片。第一軌是影片原音，\n匯入伴奏後自動對齊前奏。", "可匯出：MP4、WAV、MP3"),
                ("record", "錄音", "戴耳機邊聽伴奏邊錄。先匯入伴奏，\n再選擇麥克風開始錄音；位移自動計算。", "可匯出：WAV、MP3")):
            card = W.QPushButton(f"{heading}\n\n{text}\n\n{formats}")
            card.setObjectName("modeCard")
            card.setCheckable(True)
            card.setMinimumSize(280, 190)
            card.clicked.connect(lambda checked=False, key=key: self.pick(key))
            card.setAccessibleName(heading)
            cards.addWidget(card)
            self.cards[key] = card
        layout.addLayout(cards)
        buttons = W.QHBoxLayout()
        buttons.addStretch()
        cancel = W.QPushButton("取消")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        self.next_button = W.QPushButton("下一步")
        self.next_button.setObjectName("primary")
        self.next_button.setEnabled(False)
        self.next_button.clicked.connect(self.accept)
        buttons.addWidget(self.next_button)
        layout.addLayout(buttons)

    def pick(self, key):
        self.choice = key
        for k, card in self.cards.items():
            card.setChecked(k == key)
        self.next_button.setEnabled(True)
        self.next_button.setText("下一步：選擇影片" if key == "video" else "下一步：匯入伴奏")


class CalibrationDialog(W.QDialog):
    """Measure output+input latency with clicks played into the microphone."""
    measure_requested = Signal()

    def __init__(self, current_ms=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("錄音延遲校正")
        self.result_ms = None
        self.setMinimumWidth(560)
        layout = W.QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(12)
        title = W.QLabel("錄音延遲校正")
        theme.apply(title, "font-size: 20px; font-weight: 700;")
        layout.addWidget(title)
        intro = W.QLabel("聲音送到耳機、再從麥克風收回來會有一點延遲。換了錄音介面或耳機時做一次，"
                         "程式會記住結果，之後每次錄音自動補償。")
        intro.setObjectName("muted")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        for n, heading, text in (
                ("1", "拿下耳機，放在麥克風前面", "使用跟錄音時同一個輸出（錄音介面的耳機孔），量到的延遲才一樣；房間保持安靜。"),
                ("2", "按「開始測量」", "程式會播放 8 聲節拍，同時用麥克風收音，約 5 秒。"),
                ("3", "確認結果後套用", "8 聲的結果很接近就代表準確；錄完仍可用伴奏位移手動微調。")):
            step = W.QLabel(f"<b>{n}.　{heading}</b><br><span style='color:#91a4b9'>{text}</span>")
            step.setWordWrap(True)
            step.setTextFormat(QtCore.Qt.RichText)
            layout.addWidget(step)
        self.result = W.QLabel("尚未測量" if current_ms is None else f"目前設定：{current_ms:.1f} ms")
        theme.apply(self.result, "font-size: 16px; font-weight: 600; color: #32d4ce;")
        self.result.setWordWrap(True)
        layout.addWidget(self.result)
        buttons = W.QHBoxLayout()
        self.measure_button = W.QPushButton("開始測量")
        self.measure_button.clicked.connect(self._measure)
        buttons.addWidget(self.measure_button)
        manual = W.QPushButton("手動輸入")
        manual.clicked.connect(self._manual)
        buttons.addWidget(manual)
        buttons.addStretch()
        cancel = W.QPushButton("取消")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        self.apply_button = W.QPushButton("套用")
        self.apply_button.setObjectName("primary")
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self.accept)
        buttons.addWidget(self.apply_button)
        layout.addLayout(buttons)

    def _measure(self):
        self.measure_button.setEnabled(False)
        self.apply_button.setEnabled(False)
        self.result.setText("測量中…請保持安靜")
        theme.apply(self.result, "font-size: 16px; font-weight: 600; color: #e9b853;")
        self.measure_requested.emit()

    def show_result(self, median, spread, found):
        self.result_ms = median
        self.result.setText(f"量到的延遲：{median:.1f} ms　（{found} 聲偵測到 · 誤差 ±{spread:.1f} ms）")
        theme.apply(self.result, "font-size: 16px; font-weight: 600; color: #32d4ce;")
        self.measure_button.setText("重新測量")
        self.measure_button.setEnabled(True)
        self.apply_button.setText(f"套用 {median:.1f} ms")
        self.apply_button.setEnabled(True)

    def show_error(self, text):
        self.result.setText(text)
        theme.apply(self.result, "font-size: 14px; font-weight: 600; color: #ff8a7a;")
        self.measure_button.setText("重新測量")
        self.measure_button.setEnabled(True)

    def _manual(self):
        value, ok = W.QInputDialog.getDouble(self, "手動輸入延遲", "延遲（ms）：",
                                            self.result_ms or 0.0, 0.0, 1000.0, 1)
        if ok:
            self.show_result(value, 0.0, 0)
            self.result.setText(f"手動設定：{value:.1f} ms")
