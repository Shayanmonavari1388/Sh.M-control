"""System page – control + confirmation."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget, QFrame,
)

from shmcontrol.system.control import SystemAction, execute_system_action
from shmcontrol.ui.i18n import get_language
from shmcontrol.core.admin import is_admin


class SystemPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(14)

        self.title = QLabel()
        self.title.setObjectName("pageHeader")
        lay.addWidget(self.title)
        self.info = QLabel()
        self.info.setObjectName("pageSubtitle")
        self.info.setWordWrap(True)
        lay.addWidget(self.info)

        self.admin_lbl = QLabel()
        lay.addWidget(self.admin_lbl)

        row = QHBoxLayout()
        self.buttons = []
        specs = [
            ("Shutdown", SystemAction.SHUTDOWN, True),
            ("Restart", SystemAction.RESTART, True),
            ("Sleep", SystemAction.SLEEP, False),
            ("Hibernate", SystemAction.HIBERNATE, False),
            ("Lock", SystemAction.LOCK, False),
            ("Cancel Shutdown", SystemAction.CANCEL_SHUTDOWN, False),
        ]
        for text, action, danger in specs:
            btn = QPushButton(text)
            if danger:
                btn.setObjectName("danger")
            btn.clicked.connect(lambda checked=False, a=action, t=text: self._confirm(a, t))
            row.addWidget(btn)
            self.buttons.append((btn, text, action))
        lay.addLayout(row)

        note = QLabel()
        note.setWordWrap(True)
        note.setStyleSheet("color: #64748b; font-size: 12px;")
        self.note = note
        lay.addWidget(note)
        lay.addStretch()
        self.retranslate()

    def retranslate(self) -> None:
        fa = get_language() == "fa"
        self.title.setText("کنترل سیستم" if fa else "System Control")
        self.info.setText(
            "عملیات حساس نیاز به تأیید دارند."
            if fa else
            "Sensitive actions require confirmation."
        )
        self.admin_lbl.setText(
            ("وضعیت Admin: بله" if is_admin() else "وضعیت Admin: خیر — برخی کارها محدود می‌شود")
            if fa else
            ("Admin: Yes" if is_admin() else "Admin: No — some actions may be limited")
        )
        self.admin_lbl.setStyleSheet(
            "color: #34d399; font-weight: 700;" if is_admin() else "color: #fbbf24; font-weight: 700;"
        )
        self.note.setText(
            "Sleep از Hibernate جدا است. Cancel فقط shutdown/restart زمان‌بندی‌شده را لغو می‌کند."
            if fa else
            "Sleep is separate from Hibernate. Cancel only aborts a scheduled shutdown/restart."
        )

    def on_show(self) -> None:
        self.retranslate()

    def _confirm(self, action: SystemAction, label: str) -> None:
        fa = get_language() == "fa"
        destructive = action in (
            SystemAction.SHUTDOWN, SystemAction.RESTART,
            SystemAction.SLEEP, SystemAction.HIBERNATE,
        )
        if destructive:
            reply = QMessageBox.question(
                self,
                "Confirmation" if not fa else "تأیید",
                (f"آیا از «{label}» مطمئن هستید؟" if fa else f"Are you sure you want to {label}?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        delay = 5 if action in (SystemAction.SHUTDOWN, SystemAction.RESTART) else 0
        ok, msg = execute_system_action(action, delay_seconds=delay)
        if ok:
            QMessageBox.information(self, "Result" if not fa else "نتیجه", msg)
        else:
            QMessageBox.warning(self, "Failed" if not fa else "خطا", msg)
