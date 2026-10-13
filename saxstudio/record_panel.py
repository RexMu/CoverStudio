"""Widgets for record mode: input meter, recording panel and dialogs."""
from __future__ import annotations

import math

from .qt import QtCore, QtGui, QtWidgets as W, Signal


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
        if peak >= .985:
            self.clipped = True
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
            if i >= 27:
                color = "#ff5a4f"
            elif i >= 22:
                color = "#e9b853"
            else:
                color = "#2ac5bf"
            on = i < lit or i == hold
            p.setBrush(QtGui.QColor(color if on else "#22344a"))
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        layout = W.QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)
        head = W.QHBoxLayout()
        title = W.QLabel("● 錄音")
        title.setStyleSheet("font-size: 15px; font-weight: 700; color: #ff8a7a;")
        head.addWidget(title)
        head.addStretch()
        self.format_label = W.QLabel("48 kHz · 32-bit 浮點 · 單聲道")
        self.format_label.setObjectName("muted")
        head.addWidget(self.format_label)
        layout.addLayout(head)

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
        layout.addLayout(grid)
        self.input_combo.currentIndexChanged.connect(lambda *_: self.device_changed.emit())
        self.channel_combo.currentIndexChanged.connect(lambda *_: self.device_changed.emit())
        self.output_combo.currentIndexChanged.connect(lambda *_: self.device_changed.emit())

        meter_head = W.QHBoxLayout()
        label = W.QLabel("輸入音量")
        label.setObjectName("muted")
        meter_head.addWidget(label)
        meter_head.addStretch()
        self.level_text = W.QLabel("—")
        meter_head.addWidget(self.level_text)
        layout.addLayout(meter_head)
        self.meter = LevelMeter()
        layout.addWidget(self.meter)
        scale = W.QHBoxLayout()
        for i, text in enumerate(("-60", "-24", "-12", "-6", "0 dB")):
            if i:
                scale.addStretch()
            mark = W.QLabel(text)
            mark.setStyleSheet("color: #6f8396; font-size: 10px;")
            scale.addWidget(mark)
        layout.addLayout(scale)
        self.clip_label = W.QLabel("試吹一下，讓音量落在黃色區域之前")
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
        layout.addLayout(volume_row)
        self.volume_slider.valueChanged.connect(self._volume)

        latency = W.QFrame()
        latency.setObjectName("latencyBox")
        latency.setStyleSheet("QFrame#latencyBox { background: #132232; border: 1px solid #2c4156; border-radius: 6px; }")
        row = W.QHBoxLayout(latency)
        row.setContentsMargins(10, 6, 10, 6)
        label = W.QLabel("延遲補償")
        label.setObjectName("muted")
        row.addWidget(label)
        self.latency_value = W.QLabel("尚未校正")
        self.latency_value.setStyleSheet("font-weight: 600;")
        row.addWidget(self.latency_value)
        row.addStretch()
        self.calibrate_button = W.QPushButton("校正")
        self.calibrate_button.clicked.connect(self.calibrate_requested.emit)
        row.addWidget(self.calibrate_button)
        layout.addWidget(latency)

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
        self.rec_state.setStyleSheet("color: #ff8a7a; font-weight: 700;")
        status.addWidget(self.rec_state)
        self.rec_time = W.QLabel("00:00.0")
        self.rec_time.setStyleSheet("font-size: 18px; font-weight: 600;")
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
        self.done_label.setStyleSheet("color: #32d4ce; font-weight: 700;")
        self.done_label.setWordWrap(True)
        box.addWidget(self.done_label)
        buttons = W.QHBoxLayout()
        play = W.QPushButton("▶  播放混音")
        play.setObjectName("primary")
        play.clicked.connect(self.play_requested.emit)
        buttons.addWidget(play)
        self.rerecord_button = W.QPushButton("重錄（取代這次錄音）")
        self.rerecord_button.setToolTip("伴奏、EQ／壓縮／混響、音量與延遲校正都保留，只換掉錄音")
        self.rerecord_button.clicked.connect(self.record_requested.emit)
        buttons.addWidget(self.rerecord_button)
        box.addLayout(buttons)
        self.file_label = W.QLabel("")
        self.file_label.setObjectName("muted")
        self.file_label.setWordWrap(True)
        self.file_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        box.addWidget(self.file_label)
        self.states.addWidget(done)
        layout.addWidget(self.states)
        self.unavailable = W.QLabel("")
        self.unavailable.setWordWrap(True)
        self.unavailable.setStyleSheet("color: #ffb5ac;")
        self.unavailable.hide()
        layout.addWidget(self.unavailable)
        layout.addStretch()
        self.settings_widgets = [self.input_combo, self.channel_combo, self.output_combo,
                                 self.countdown_combo, self.calibrate_button]

    # ---- state
    def _volume(self, value):
        self.volume_text.setText(f"{value/10:.1f} dB")
        self.volume_changed.emit(value / 10)

    @property
    def volume_db(self):
        return self.volume_slider.value() / 10

    @property
    def countdown(self):
        return int(self.countdown_combo.currentData() or 0)

    def set_level(self, peak):
        self.meter.set_level(peak)
        self.level_text.setText(f"{db(peak):.1f} dB")
        if self.meter.clipped:
            self.clip_label.setText("⚠ 破音了！請調低錄音介面的輸入增益")
            self.clip_label.setStyleSheet("color: #ff8a7a; font-weight: 600;")

    def reset_clip(self):
        self.meter.reset_clip()
        self.clip_label.setText("音量良好，未破音")
        self.clip_label.setStyleSheet("color: #32d4ce;")

    def set_latency(self, ms):
        if ms is None:
            self.latency_value.setText("尚未校正")
            self.latency_value.setStyleSheet("font-weight: 600; color: #e9b853;")
            self.calibrate_button.setText("校正")
        else:
            self.latency_value.setText(f"{ms:.1f} ms · 已校正")
            self.latency_value.setStyleSheet("font-weight: 600; color: #32d4ce;")
            self.calibrate_button.setText("重新校正")

    def set_state(self, state):
        index = {"ready": 0, "recording": 1, "countdown": 1, "done": 2}[state]
        self.states.setCurrentIndex(index)
        busy = state in ("recording", "countdown")
        for widget in self.settings_widgets:
            widget.setEnabled(not busy)
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

    def set_done(self, seconds, path):
        minutes, rest = divmod(seconds, 60)
        self.done_label.setText(f"✓ 錄音完成 · {int(minutes):02}:{rest:04.1f} 已放入第一軌")
        self.file_label.setText(f"檔案：{path}")
        self.set_state("done")

    def set_unavailable(self, message):
        message = message or ""
        self.unavailable.setText(message)
        self.unavailable.setVisible(bool(message))
        self.record_button.setEnabled(not message)
        self.rerecord_button.setEnabled(not message)
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
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
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
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
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
        self.result.setStyleSheet("font-size: 16px; font-weight: 600; color: #32d4ce;")
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
        self.result.setStyleSheet("font-size: 16px; font-weight: 600; color: #e9b853;")
        self.measure_requested.emit()

    def show_result(self, median, spread, found):
        self.result_ms = median
        self.result.setText(f"量到的延遲：{median:.1f} ms　（{found} 聲偵測到 · 誤差 ±{spread:.1f} ms）")
        self.result.setStyleSheet("font-size: 16px; font-weight: 600; color: #32d4ce;")
        self.measure_button.setText("重新測量")
        self.measure_button.setEnabled(True)
        self.apply_button.setText(f"套用 {median:.1f} ms")
        self.apply_button.setEnabled(True)

    def show_error(self, text):
        self.result.setText(text)
        self.result.setStyleSheet("font-size: 14px; font-weight: 600; color: #ff8a7a;")
        self.measure_button.setText("重新測量")
        self.measure_button.setEnabled(True)

    def _manual(self):
        value, ok = W.QInputDialog.getDouble(self, "手動輸入延遲", "延遲（ms）：",
                                            self.result_ms or 0.0, 0.0, 1000.0, 1)
        if ok:
            self.show_result(value, 0.0, 0)
            self.result.setText(f"手動設定：{value:.1f} ms")
