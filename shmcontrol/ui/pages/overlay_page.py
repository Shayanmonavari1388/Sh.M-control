"""Overlay settings – desktop HUD (not fullscreen injection)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget, QMessageBox,
    QCheckBox, QComboBox,
)

from shmcontrol.ui.overlay import get_overlay
from shmcontrol.ui.i18n import get_language


class OverlayPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(14)

        self.title = QLabel()
        self.title.setObjectName("pageHeader")
        lay.addWidget(self.title)
        self.sub = QLabel()
        self.sub.setObjectName("pageSubtitle")
        self.sub.setWordWrap(True)
        lay.addWidget(self.sub)

        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.setStyleSheet(
            "QLabel { background: #121722; border: 1px solid #1e2636; border-radius: 14px; padding: 14px; color: #cbd5e1; }"
        )
        lay.addWidget(self.note)

        row = QHBoxLayout()
        self.chk = QCheckBox()
        self.corner = QComboBox()
        self.corner.addItem("بالا راست / Top-Right", "top-right")
        self.corner.addItem("بالا چپ / Top-Left", "top-left")
        self.corner.addItem("پایین راست / Bottom-Right", "bottom-right")
        self.corner.addItem("پایین چپ / Bottom-Left", "bottom-left")
        self.btn = QPushButton()
        self.btn.setObjectName("primary")
        self.btn.clicked.connect(self._apply)
        row.addWidget(self.chk)
        row.addWidget(self.corner)
        row.addWidget(self.btn)
        row.addStretch()
        lay.addLayout(row)
        lay.addStretch()
        self.retranslate()

    def retranslate(self) -> None:
        fa = get_language() == "fa"
        self.title.setText("اورلی" if fa else "Overlay")
        self.sub.setText(
            "نمایش متریک در گوشه صفحه (همیشه رو) — با ماوس قابل جابه‌جایی"
            if fa else
            "Metrics in screen corner (always on top) — drag to move"
        )
        self.note.setText(
            "اورلی داخل Fullscreen انحصاری تزریق نمی‌شود. "
            "برای دیدن روی بازی از Borderless استفاده کنید. "
            "برای بهترین نتیجه برنامه را با Administrator اجرا کنید."
            if fa else
            "Not injected into exclusive fullscreen. Use Borderless over games. "
            "Run as Administrator for best results."
        )
        self.chk.setText("فعال" if fa else "Enabled")
        self.btn.setText("اعمال" if fa else "Apply")

    def on_show(self) -> None:
        self.retranslate()

    def _apply(self) -> None:
        ov = get_overlay()
        corner = self.corner.currentData()
        ov.set_corner(str(corner))
        ov.set_overlay_enabled(self.chk.isChecked())
        fa = get_language() == "fa"
        QMessageBox.information(
            self, "Overlay",
            ("اورلی اعمال شد" if fa else "Overlay applied")
            + f"\n{corner}",
        )
