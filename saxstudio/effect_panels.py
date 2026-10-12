"""Presentation-only controls for the existing effect settings."""
from .qt import QtCore, QtGui, QtWidgets


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
        painter.setPen(QtGui.QPen(QtGui.QColor("#2ac5bf" if checked else "#5b6c7f"), 1))
        painter.setBrush(QtGui.QColor("#2ac5bf" if checked else "#3a4b5e"))
        painter.drawRoundedRect(QtCore.QRectF(1, 3, 36, 18), 9, 9)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor("#0d393c" if checked else "#d9e4ec"))
        painter.drawEllipse(QtCore.QRectF(21 if checked else 4, 5, 14, 14))
        if self.hasFocus():
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.setPen(QtGui.QPen(QtGui.QColor("#78eee4"), 1))
            painter.drawRoundedRect(QtCore.QRectF(.5, .5, 37, 23), 10, 10)


class CollapsibleEffect(QtWidgets.QFrame):
    def __init__(self, name, parent=None):
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
        self.title.setStyleSheet("font-size: 14px; font-weight: 600;")
        self.status = QtWidgets.QLabel("未啟用")
        labels.addWidget(self.title)
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
        self.status.setStyleSheet("font-size: 11px; color: " + ("#32d4ce" if enabled else "#91a4b9") + ";")

    def set_expanded(self, expanded):
        self.body.setVisible(expanded)
        self.arrow.setArrowType(QtCore.Qt.UpArrow if expanded else QtCore.Qt.DownArrow)
        if self.arrow.isChecked() != expanded:
            self.arrow.blockSignals(True)
            self.arrow.setChecked(expanded)
            self.arrow.blockSignals(False)
