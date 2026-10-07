"""System Timer / Scheduler — works fully offline."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QSpinBox, QVBoxLayout, QWidget, QFormLayout, QFrame,
)

from shmcontrol.system.timer import system_timer
from shmcontrol.ui.i18n import get_language


class TimerPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(12)

        self.title = QLabel()
        self.title.setObjectName("pageHeader")
        lay.addWidget(self.title)

        card = QFrame()
        card.setObjectName("card")
        cl = QVBoxLayout(card)
        self.status = QLabel()
        self.status.setStyleSheet("font-size: 16px; color: #58a6ff;")
        cl.addWidget(self.status)
        self.countdown = QLabel("")
        self.countdown.setStyleSheet("font-size: 32px; font-weight: 800; color: #e2e8f0;")
        cl.addWidget(self.countdown)
        lay.addWidget(card)

        form = QFormLayout()
        self.action = QComboBox()
        self.action.addItem("خاموش کردن", "shutdown")
        self.action.addItem("ری‌استارت", "restart")
        self.action.addItem("خواب (Sleep)", "sleep")
        self.action.addItem("قفل صفحه", "lock")
        self.action.addItem("هایبرنیت", "hibernate")
        form.addRow("عملیات:", self.action)

        self.hours = QSpinBox()
        self.hours.setRange(0, 168)
        self.hours.setValue(0)
        self.mins = QSpinBox()
        self.mins.setRange(0, 59)
        self.mins.setValue(5)
        row = QHBoxLayout()
        row.addWidget(self.hours)
        row.addWidget(QLabel("ساعت"))
        row.addWidget(self.mins)
        row.addWidget(QLabel("دقیقه"))
        form.addRow("زمان:", row)
        lay.addLayout(form)

        btns = QHBoxLayout()
        self.schedule_btn = QPushButton()
        self.schedule_btn.setObjectName("primary")
        self.schedule_btn.clicked.connect(self._schedule)
        btns.addWidget(self.schedule_btn)
        self.cancel_btn = QPushButton()
        self.cancel_btn.clicked.connect(self._cancel)
        btns.addWidget(self.cancel_btn)
        btns.addStretch()
        lay.addLayout(btns)

        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.setStyleSheet("color: #8b949e;")
        lay.addWidget(self.note)
        lay.addStretch()

        self._ui_timer = QTimer(self)
        self._ui_timer.timeout.connect(self._refresh)
        self._ui_timer.start(1000)
        self.retranslate()
        self._refresh()

        # Ensure watcher is running (offline-safe)
        try:
            system_timer.start_watcher()
        except Exception:
            pass

    def retranslate(self) -> None:
        fa = get_language() == "fa"
        self.title.setText("تایمر سیستم" if fa else "System Timer")
        self.schedule_btn.setText("زمان‌بندی" if fa else "Schedule")
        self.cancel_btn.setText("لغو تایمر" if fa else "Cancel Timer")
        self.note.setText(
            "فقط یک تایمر فعال مجاز است. بعد از ری‌استارت برنامه، تایمرهای منقضی‌شده اجرا نمی‌شوند."
            if fa else
            "Only one active timer. Expired timers after restart never auto-run."
        )

    def on_show(self) -> None:
        self.retranslate()
        self._refresh()
        try:
            system_timer.start_watcher()
        except Exception:
            pass

    def _refresh(self) -> None:
        fa = get_language() == "fa"
        try:
            a = system_timer.get_active()
            if not a:
                self.status.setText("هیچ تایمر فعالی نیست" if fa else "No scheduled action")
                self.countdown.setText("Idle")
                return
            rem = system_timer.remaining_seconds()
            if rem is None:
                rem = 0
            h, rem2 = divmod(int(rem), 3600)
            m, s = divmod(rem2, 60)
            self.status.setText(
                f"فعال: {a.action}" if fa else f"Active: {a.action}"
            )
            self.countdown.setText(f"{h:02d}:{m:02d}:{s:02d}")
        except Exception as e:
            self.status.setText(f"Error: {e}")
            self.countdown.setText("—")

    def _schedule(self) -> None:
        fa = get_language() == "fa"
        action = self.action.currentData() or self.action.currentText()
        action = str(action).lower().strip()
        delta = timedelta(hours=self.hours.value(), minutes=self.mins.value())
        if delta.total_seconds() < 60:
            QMessageBox.warning(
                self, "Timer",
                "حداقل ۱ دقیقه" if fa else "Minimum duration is 1 minute",
            )
            return
        if action in ("shutdown", "restart", "hibernate"):
            reply = QMessageBox.question(
                self,
                "Confirm",
                (f"{action} تا {self.hours.value()}س {self.mins.value()}د تنظیم شود؟"
                 if fa else
                 f"Schedule {action} in {self.hours.value()}h {self.mins.value()}m?"),
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        target = datetime.now(timezone.utc) + delta
        try:
            ok, msg, sid = system_timer.schedule(
                action, target, source="ui", require_confirm=False
            )
            if not ok and "already exists" in (msg or "").lower():
                r = QMessageBox.question(
                    self, "Timer",
                    (msg + "\n\nجایگزین شود؟") if fa else (msg + "\n\nReplace existing?"),
                )
                if r == QMessageBox.StandardButton.Yes:
                    ok, msg, sid = system_timer.replace(action, target, source="ui")
            QMessageBox.information(self, "Timer", msg)
        except Exception as e:
            QMessageBox.warning(self, "Timer", str(e))
        self._refresh()

    def _cancel(self) -> None:
        try:
            ok, msg = system_timer.cancel()
            QMessageBox.information(self, "Timer", msg)
        except Exception as e:
            QMessageBox.warning(self, "Timer", str(e))
        self._refresh()
