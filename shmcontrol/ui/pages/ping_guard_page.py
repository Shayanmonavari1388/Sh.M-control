"""
Ping stability / background upload awareness.
True per-app upload hard-cap needs WFP driver — we provide monitoring + warnings.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
    QCheckBox, QDoubleSpinBox, QMessageBox,
)

from shmcontrol.network.apps_monitor import network_apps_monitor
from shmcontrol.network.tools import ping
from shmcontrol.ui.i18n import get_language


class PingGuardPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._sample)
        self._protect = False
        self._limit_mb = 3.0

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        self.title = QLabel()
        self.title.setObjectName("pageHeader")
        root.addWidget(self.title)
        self.sub = QLabel()
        self.sub.setObjectName("pageSubtitle")
        self.sub.setWordWrap(True)
        root.addWidget(self.sub)

        card = QFrame()
        card.setObjectName("card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(18, 16, 18, 16)
        row = QHBoxLayout()
        self.chk = QCheckBox()
        self.chk.toggled.connect(self._toggle)
        row.addWidget(self.chk)
        row.addStretch()
        cl.addLayout(row)

        lim = QHBoxLayout()
        self.lim_lbl = QLabel()
        self.spin = QDoubleSpinBox()
        self.spin.setRange(0.5, 50)
        self.spin.setValue(3.0)
        self.spin.setSuffix(" MB/s")
        lim.addWidget(self.lim_lbl)
        lim.addWidget(self.spin)
        lim.addStretch()
        cl.addLayout(lim)

        self.stats = QLabel("—")
        self.stats.setStyleSheet("color: #94a3b8; font-size: 13px;")
        cl.addWidget(self.stats)
        root.addWidget(card)

        self.who = QLabel()
        self.who.setWordWrap(True)
        self.who.setStyleSheet("color: #cbd5e1;")
        root.addWidget(self.who)

        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.setStyleSheet("color: #64748b; font-size: 12px;")
        root.addWidget(self.note)
        root.addStretch()
        self.retranslate()

    def retranslate(self) -> None:
        fa = get_language() == "fa"
        self.title.setText("پایداری پینگ" if fa else "Ping Guard")
        self.sub.setText(
            "هشدار آپلود سنگین هنگام بازی — قفل سخت نیاز به درایور WFP دارد"
            if fa else
            "Heavy upload warning while gaming — hard lock needs WFP driver"
        )
        self.chk.setText("محافظت فعال" if fa else "Protection enabled")
        self.lim_lbl.setText("سقف هشدار آپلود هر برنامه" if fa else "Per-app upload warn threshold")
        self.note.setText(
            "Sh.M Control برنامه‌هایی که از سقف عبور کنند را نشان می‌دهد. "
            "قطع اجباری ترافیک هر پروسه بدون درایور فیلتر شبکه ممکن نیست و انجام نمی‌شود."
            if fa else
            "Apps exceeding the threshold are listed. Forced per-process throttle "
            "requires a network filter driver and is not silently applied."
        )

    def on_show(self) -> None:
        self.retranslate()
        if not self._timer.isActive():
            self._timer.start(3000)
        self._sample()

    def hideEvent(self, e) -> None:
        self._timer.stop()
        super().hideEvent(e)

    def _toggle(self, on: bool) -> None:
        self._protect = on

    def _sample(self) -> None:
        fa = get_language() == "fa"
        self._limit_mb = self.spin.value()
        # baseline ping
        r = ping("1.1.1.1", count=1)
        ping_s = f"{r.latency_ms:.0f} ms" if r.success else "—"
        self.stats.setText(
            (f"پینگ فعلی: {ping_s}" if fa else f"Current ping: {ping_s}")
        )
        if not self._protect:
            self.who.setText("—" if not fa else "محافظت خاموش است")
            return
        limit_bps = self._limit_mb * 1024 * 1024
        apps = network_apps_monitor.snapshot()
        heavy = []
        for a in apps:
            rate = a.upload_rate or 0
            if rate >= limit_bps:
                heavy.append(f"{a.name} ↑{_fmt_mb(rate)}")
        if heavy:
            self.who.setText(
                ("آپلود سنگین:\n" if fa else "Heavy upload:\n") + "\n".join(heavy[:12])
            )
        else:
            self.who.setText(
                "الان هیچ برنامه بالای سقف نیست" if fa else "No app above threshold"
            )


def _fmt_mb(bps: float) -> str:
    return f"{bps/1024/1024:.2f} MB/s"
