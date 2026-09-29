"""Premium metric cards + subtle animated background."""

from __future__ import annotations

import math
from PySide6.QtCore import Qt, QTimer, QPointF
from PySide6.QtGui import QPainter, QColor, QLinearGradient, QRadialGradient, QPen, QBrush
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar, QSizePolicy, QVBoxLayout, QWidget,
)


class AnimatedBackground(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._t = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(50)

    def _tick(self) -> None:
        self._t += 0.01
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        base = QLinearGradient(0, 0, w, h)
        base.setColorAt(0.0, QColor(11, 14, 20))
        base.setColorAt(1.0, QColor(13, 16, 24))
        p.fillRect(self.rect(), base)

        x1 = w * (0.18 + 0.06 * math.sin(self._t * 0.6))
        y1 = h * (0.22 + 0.08 * math.cos(self._t * 0.45))
        r1 = min(w, h) * 0.32
        g1 = QRadialGradient(x1, y1, r1)
        g1.setColorAt(0.0, QColor(14, 165, 233, 28))
        g1.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(g1))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(x1, y1), r1, r1)

        x2 = w * (0.78 + 0.05 * math.cos(self._t * 0.5))
        y2 = h * (0.68 + 0.06 * math.sin(self._t * 0.4))
        r2 = min(w, h) * 0.26
        g2 = QRadialGradient(x2, y2, r2)
        g2.setColorAt(0.0, QColor(99, 102, 241, 22))
        g2.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(g2))
        p.drawEllipse(QPointF(x2, y2), r2, r2)
        p.end()


class MetricCard(QFrame):
    """Clean metric: title row + big value + sub + thin bar."""

    def __init__(self, title: str, icon=None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("metricCard")
        self.setMinimumHeight(118)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(6)

        top = QHBoxLayout()
        top.setSpacing(8)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("cardTitle")
        top.addWidget(self.title_label)
        top.addStretch()
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(22, 22)
        if icon is not None:
            self.icon_label.setPixmap(icon.pixmap(20, 20))
        top.addWidget(self.icon_label)
        lay.addLayout(top)

        row = QHBoxLayout()
        self.value_label = QLabel("—")
        self.value_label.setObjectName("cardValue")
        row.addWidget(self.value_label)
        row.addStretch()
        self.side_label = QLabel("")
        self.side_label.setStyleSheet(
            "color: #8b95a8; font-size: 13px; font-weight: 600; background: transparent; border: none;"
        )
        row.addWidget(self.side_label)
        lay.addLayout(row)

        self.sub_label = QLabel("")
        self.sub_label.setObjectName("cardSub")
        lay.addWidget(self.sub_label)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(5)
        self.bar.hide()
        lay.addWidget(self.bar)

    def set_value(self, text: str, level: str = "info") -> None:
        self.value_label.setText(text)
        obj = {
            "ok": "cardValueOk",
            "warn": "cardValueWarn",
            "crit": "cardValueCrit",
            "info": "cardValueInfo",
        }.get(level, "cardValue")
        self.value_label.setObjectName(obj)
        self.value_label.style().unpolish(self.value_label)
        self.value_label.style().polish(self.value_label)

    def set_side(self, text: str) -> None:
        self.side_label.setText(text)

    def set_sub(self, text: str) -> None:
        self.sub_label.setText(text)

    def set_bar(self, value: int | None, level: str = "ok") -> None:
        if value is None:
            self.bar.hide()
            return
        self.bar.show()
        self.bar.setValue(max(0, min(100, int(value))))
        name = {"ok": "barOk", "warn": "barWarn", "crit": "barCrit"}.get(level, "barOk")
        self.bar.setObjectName(name)
        self.bar.style().unpolish(self.bar)
        self.bar.style().polish(self.bar)
