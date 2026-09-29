"""Telegram: numeric User ID + session alert preferences."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget, QFrame,
    QCheckBox, QGroupBox,
)

from shmcontrol.config.settings import settings_manager
from shmcontrol.api.cloud import bind_telegram, register_device
from shmcontrol.ui.i18n import get_language


class TelegramPage(QWidget):
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

        box = QFrame()
        box.setObjectName("card")
        bl = QVBoxLayout(box)
        bl.setContentsMargins(18, 16, 18, 16)
        bl.setSpacing(12)

        self.uid_lbl = QLabel()
        bl.addWidget(self.uid_lbl)
        self.uid_edit = QLineEdit()
        self.uid_edit.setPlaceholderText("123456789")
        self.uid_edit.setMinimumHeight(44)
        bl.addWidget(self.uid_edit)

        # Session alerts
        self.alert_box = QGroupBox()
        al = QVBoxLayout(self.alert_box)
        self.chk_unlock = QCheckBox()
        self.chk_lock = QCheckBox()
        self.chk_startup = QCheckBox()
        self.chk_resume = QCheckBox()
        for w in (self.chk_unlock, self.chk_lock, self.chk_startup, self.chk_resume):
            al.addWidget(w)
        bl.addWidget(self.alert_box)

        self.btn = QPushButton()
        self.btn.setObjectName("primary")
        self.btn.setMinimumHeight(44)
        self.btn.clicked.connect(self._save)
        bl.addWidget(self.btn)

        self.hint = QLabel()
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("color: #94a3b8;")
        bl.addWidget(self.hint)

        lay.addWidget(box)
        self.status = QLabel()
        self.status.setStyleSheet("color: #64748b;")
        lay.addWidget(self.status)
        lay.addStretch()
        self.retranslate()
        self._load()

    def retranslate(self) -> None:
        fa = get_language() == "fa"
        self.title.setText("تلگرام" if fa else "Telegram")
        self.sub.setText(
            "فقط User ID عددی + انتخاب اعلان‌های قفل/روشن شدن"
            if fa else
            "Numeric User ID + choose lock/unlock/startup alerts"
        )
        self.uid_lbl.setText("User ID عددی" if fa else "Numeric User ID")
        self.alert_box.setTitle("اعلان‌های تلگرام" if fa else "Telegram alerts")
        self.chk_unlock.setText(
            "وقتی قفل سیستم باز شد خبر بده"
            if fa else
            "Notify when workstation is unlocked"
        )
        self.chk_lock.setText(
            "وقتی سیستم قفل شد خبر بده"
            if fa else
            "Notify when workstation is locked"
        )
        self.chk_startup.setText(
            "وقتی برنامه/سیستم آنلاین شد خبر بده"
            if fa else
            "Notify when app starts (PC online)"
        )
        self.chk_resume.setText(
            "وقتی از Sleep برگشت خبر بده"
            if fa else
            "Notify on resume from sleep"
        )
        self.btn.setText("ذخیره" if fa else "Save")
        self.hint.setText(
            "در ربات /id بزنید → عدد را اینجا ذخیره کنید.\n"
            "برنامه باید باز باشد تا اعلان قفل/باز شدن ارسال شود."
            if fa else
            "In the bot send /id → save the number here.\n"
            "Keep the app running to send lock/unlock alerts."
        )

    def on_show(self) -> None:
        self.retranslate()
        self._load()

    def _load(self) -> None:
        s = settings_manager.settings
        if s.telegram_user_id:
            self.uid_edit.setText(str(s.telegram_user_id))
        else:
            self.uid_edit.clear()
        self.chk_unlock.setChecked(bool(getattr(s, "notify_on_unlock", True)))
        self.chk_lock.setChecked(bool(getattr(s, "notify_on_lock", False)))
        self.chk_startup.setChecked(bool(getattr(s, "notify_on_startup", True)))
        self.chk_resume.setChecked(bool(getattr(s, "notify_on_resume", True)))
        self.status.setText(f"Device: {s.device_id or '—'}")

    def _save(self) -> None:
        fa = get_language() == "fa"
        raw = self.uid_edit.text().strip()
        if not raw.isdigit():
            QMessageBox.warning(self, "Telegram", "فقط عدد" if fa else "Numbers only")
            return
        uid = int(raw)
        s = settings_manager.settings
        s.telegram_user_id = uid
        s.cloud_sync_enabled = True
        s.notify_on_unlock = self.chk_unlock.isChecked()
        s.notify_on_lock = self.chk_lock.isChecked()
        s.notify_on_startup = self.chk_startup.isChecked()
        s.notify_on_resume = self.chk_resume.isChecked()
        if not getattr(s, "device_name", None):
            s.device_name = "PC"
        settings_manager.save()

        register_device(name=s.device_name or "PC")
        res = bind_telegram(uid, name=s.device_name or "PC")
        try:
            from shmcontrol.api.poller import cloud_poller
            cloud_poller.start()
        except Exception:
            pass
        try:
            from shmcontrol.system.session_monitor import session_monitor
            session_monitor.start()
        except Exception:
            pass

        if res.get("ok"):
            QMessageBox.information(
                self, "OK",
                f"ذخیره شد: {uid}" if fa else f"Saved: {uid}",
            )
        else:
            QMessageBox.warning(
                self, "Telegram",
                f"ID ذخیره شد ({uid})\n{res.get('error')}"
                if fa else
                f"ID saved ({uid})\n{res.get('error')}",
            )
        self._load()
