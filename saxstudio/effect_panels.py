"""Presentation-only controls for the existing effect settings."""
from .qt import QtCore, QtGui, QtWidgets, Signal
from . import theme


class ToggleSwitch(QtWidgets.QCheckBox):
    def __init__(self, label, parent=None):
        super().__init__(parent)
        self.setFixedSize(38, 24)
        self.setAccessibleName(label)
        self.setToolTip(label)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.toggled.connect(lambda checked: self.update())

    def hitButton(self, position):
        return self.rect().contains(position)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        if not self.isEnabled():
            painter.setOpacity(.45)
        checked = self.isChecked()
        painter.setPen(QtGui.QPen(QtGui.QColor(theme.c("#2ac5bf" if checked else "#5b6c7f")), 1))
        painter.setBrush(QtGui.QColor(theme.c("#2ac5bf" if checked else "#3a4b5e")))
        painter.drawRoundedRect(QtCore.QRectF(1, 3, 36, 18), 9, 9)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(theme.c("#0d393c" if checked else "#d9e4ec")))
        painter.drawEllipse(QtCore.QRectF(21 if checked else 4, 5, 14, 14))
        if self.hasFocus():
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.setPen(QtGui.QPen(QtGui.QColor(theme.c("#78eee4")), 1))
            painter.drawRoundedRect(QtCore.QRectF(.5, .5, 37, 23), 10, 10)


class InfoButton(QtWidgets.QToolButton):
    """Small circled "i" that opens a click-away help card."""

    def __init__(self, title, html, parent=None):
        super().__init__(parent)
        self.title, self.html = title, html
        self.popup = None
        self.setObjectName("info")
        self.setText("i")
        self.setFixedSize(20, 20)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setToolTip(f"{title} 參數說明")
        self.setAccessibleName(f"{title} 參數說明")
        self.clicked.connect(self.show_popup)

    def show_popup(self):
        popup = QtWidgets.QFrame(self.window(), QtCore.Qt.Popup)
        popup.setObjectName("infoPopup")
        popup.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        layout = QtWidgets.QVBoxLayout(popup)
        layout.setContentsMargins(14, 12, 14, 12)
        text = QtWidgets.QLabel(theme.css(f"<b style='font-size:14px'>{self.title}</b>{self.html}"))
        text.setObjectName("infoText")
        text.setWordWrap(True)
        text.setTextFormat(QtCore.Qt.RichText)
        text.setFixedWidth(380)
        layout.addWidget(text)
        popup.adjustSize()
        position = self.mapToGlobal(QtCore.QPoint(0, self.height() + 4))
        screen = QtWidgets.QApplication.screenAt(position) or QtWidgets.QApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            position.setX(max(area.left(), min(position.x(), area.right() - popup.width())))
            if position.y() + popup.height() > area.bottom():
                position.setY(self.mapToGlobal(QtCore.QPoint(0, 0)).y() - popup.height() - 4)
        popup.move(position)
        popup.show()
        self.popup = popup


class PresetBar(QtWidgets.QWidget):
    """Quick tone buttons with the small QComboBox-like API the window uses.

    Index 0 means "自訂" (no preset button lit); 1..n map to the buttons.
    """
    currentIndexChanged = Signal(int)

    def __init__(self, presets, parent=None):
        super().__init__(parent)
        self._index = 0
        self.buttons = []
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        for i, (name, tip) in enumerate(presets, 1):
            b = QtWidgets.QPushButton(name)
            b.setObjectName("preset")
            b.setCheckable(True)
            b.setToolTip(tip)
            b.setCursor(QtCore.Qt.PointingHandCursor)
            b.clicked.connect(lambda checked=False, i=i: self.setCurrentIndex(i))
            row.addWidget(b)
            self.buttons.append(b)
        self.custom = QtWidgets.QLabel("自訂")
        self.custom.setObjectName("presetCustom")
        self.custom.setToolTip("手動調整任何參數後，會變成自訂設定")
        row.addWidget(self.custom)
        row.addStretch()
        self._sync()

    def count(self):
        return len(self.buttons) + 1

    def currentIndex(self):
        return self._index

    def setCurrentIndex(self, index):
        index = max(0, min(int(index), len(self.buttons)))
        changed = index != self._index
        self._index = index
        self._sync()
        if changed:
            self.currentIndexChanged.emit(index)

    def _sync(self):
        for i, b in enumerate(self.buttons, 1):
            b.setChecked(i == self._index)
        self.custom.setEnabled(self._index == 0)


class CollapsibleEffect(QtWidgets.QFrame):
    def __init__(self, name, parent=None, info=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Maximum)
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        header = QtWidgets.QWidget()
        header.setObjectName("effectHead")
        row = QtWidgets.QHBoxLayout(header)
        row.setContentsMargins(12, 11, 12, 11)
        row.setSpacing(10)
        self.toggle = ToggleSwitch(f"啟用 {name}")
        row.addWidget(self.toggle)
        labels = QtWidgets.QVBoxLayout()
        labels.setSpacing(2)
        self.title = QtWidgets.QLabel(name)
        theme.apply(self.title, "font-size: 14px; font-weight: 600;")
        self.status = QtWidgets.QLabel("未啟用")
        title_row = QtWidgets.QHBoxLayout()
        title_row.setSpacing(6)
        title_row.addWidget(self.title)
        self.info = InfoButton(name, info) if info else None
        if self.info:
            title_row.addWidget(self.info)
        title_row.addStretch()
        labels.addLayout(title_row)
        labels.addWidget(self.status)
        row.addLayout(labels)
        row.addStretch()
        self.arrow = QtWidgets.QToolButton()
        self.arrow.setObjectName("effectArrow")
        self.arrow.setFixedSize(28, 28)
        self.arrow.setCheckable(True)
        self.arrow.setArrowType(QtCore.Qt.DownArrow)
        self.arrow.setAccessibleName(f"展開或收合 {name} 參數")
        self.arrow.setToolTip("只展開／收合參數，不改變效果開關")
        self.arrow.toggled.connect(self.set_expanded)
        row.addWidget(self.arrow)
        outer.addWidget(header)
        self.body = QtWidgets.QWidget()
        self.body.setObjectName("effectBody")
        self.grid = QtWidgets.QGridLayout(self.body)
        self.grid.setContentsMargins(12, 10, 12, 13)
        outer.addWidget(self.body)
        self.body.hide()
        self.toggle.toggled.connect(self.update_enabled)
        self.update_enabled(False)

    def update_enabled(self, enabled):
        self.body.setEnabled(enabled)
        self.status.setText("已啟用" if enabled else "未啟用")
        theme.apply(self.status, "font-size: 11px; color: " + ("#32d4ce" if enabled else "#91a4b9") + ";")

    def set_expanded(self, expanded):
        self.body.setVisible(expanded)
        self.arrow.setArrowType(QtCore.Qt.UpArrow if expanded else QtCore.Qt.DownArrow)
        if self.arrow.isChecked() != expanded:
            self.arrow.blockSignals(True)
            self.arrow.setChecked(expanded)
            self.arrow.blockSignals(False)
