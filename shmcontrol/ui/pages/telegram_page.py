"""Telegram remote control — requires Sh.M account login."""

from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget, QFrame,
    QCheckBox, QGroupBox, QHBoxLayout, QStackedWidget,
)

from shmcontrol.config.settings import settings_manager
from shmcontrol.api.cloud import bind_telegram, register_device
from shmcontrol.security.auth import auth_manager
from shmcontrol.ui.i18n import get_language


class TelegramPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
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

        self.stack = QStackedWidget()
        root.addWidget(self.stack)

        # --- Login / Register ---
        auth_page = QFrame()
        auth_page.setObjectName("card")
        al = QVBoxLayout(auth_page)
        al.setContentsMargins(18, 16, 18, 16)
        al.setSpacing(10)

        self.auth_info = QLabel()
        self.auth_info.setWordWrap(True)
        self.auth_info.setStyleSheet("color: #94a3b8;")
        al.addWidget(self.auth_info)

        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("email@example.com")
        self.email_edit.setMinimumHeight(42)
        al.addWidget(self.email_edit)

        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass_edit.setPlaceholderText("Password")
        self.pass_edit.setMinimumHeight(42)
        al.addWidget(self.pass_edit)

        row = QHBoxLayout()
        self.btn_login = QPushButton()
        self.btn_login.setObjectName("primary")
        self.btn_login.setMinimumHeight(42)
        self.btn_login.clicked.connect(self._login)
        self.btn_register = QPushButton()
        self.btn_register.setMinimumHeight(42)
        self.btn_register.clicked.connect(self._register)
        row.addWidget(self.btn_login)
        row.addWidget(self.btn_register)
        al.addLayout(row)
        self.stack.addWidget(auth_page)

        # --- Telegram bind (after login) ---
        tg_page = QFrame()
        tg_page.setObjectName("card")
        bl = QVBoxLayout(tg_page)
        bl.setContentsMargins(18, 16, 18, 16)
        bl.setSpacing(12)

        self.logged_as = QLabel()
        self.logged_as.setStyleSheet("color: #22c55e; font-weight: 600;")
        bl.addWidget(self.logged_as)

        self.uid_lbl = QLabel()
        bl.addWidget(self.uid_lbl)
        self.uid_edit = QLineEdit()
        self.uid_edit.setPlaceholderText("123456789")
        self.uid_edit.setMinimumHeight(44)
        bl.addWidget(self.uid_edit)

        self.alert_box = QGroupBox()
        ag = QVBoxLayout(self.alert_box)
        self.chk_unlock = QCheckBox()
        self.chk_lock = QCheckBox()
        self.chk_startup = QCheckBox()
        self.chk_resume = QCheckBox()
        for w in (self.chk_unlock, self.chk_lock, self.chk_startup, self.chk_resume):
            ag.addWidget(w)
        bl.addWidget(self.alert_box)

        self.btn_save = QPushButton()
        self.btn_save.setObjectName("primary")
        self.btn_save.setMinimumHeight(44)
        self.btn_save.clicked.connect(self._save)
        bl.addWidget(self.btn_save)

        self.btn_bot = QPushButton()
        self.btn_bot.setMinimumHeight(40)
        self.btn_bot.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://t.me/ShMmControlbot")))
        bl.addWidget(self.btn_bot)


        self.btn_logout = QPushButton()
        self.btn_logout.setMinimumHeight(40)
        self.btn_logout.clicked.connect(self._logout)
        bl.addWidget(self.btn_logout)

        self.hint = QLabel()
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("color: #94a3b8;")
        bl.addWidget(self.hint)

        self.stack.addWidget(tg_page)

        self.status = QLabel()
        self.status.setStyleSheet("color: #64748b;")
        root.addWidget(self.status)
        root.addStretch()

        self.retranslate()
        self._refresh_gate()

    def retranslate(self) -> None:
        fa = get_language() == "fa"
        self.title.setText("تلگرام / حساب Sh.M" if fa else "Telegram / Sh.M Account")
        self.sub.setText(
            "برای امنیت، ابتدا وارد حساب Sh.M شوید؛ بعد User ID تلگرام را ذخیره کنید."
            if fa else
            "For security, sign in to your Sh.M account first, then save your Telegram User ID."
        )
        self.auth_info.setText(
            "ورود با حساب Sh.M. برای ثبت‌نام جدید دکمه «ثبت‌نام در سایت» را بزنید (login.shayanmonavari.ir)."
            if fa else
            "Sign in with your Sh.M account. Use Register on website for new accounts (login.shayanmonavari.ir)."
        )
        self.btn_login.setText("ورود" if fa else "Sign in")
        self.btn_register.setText("ثبت‌نام در سایت" if fa else "Register on website")
        self.uid_lbl.setText("User ID عددی تلگرام" if fa else "Telegram numeric User ID")
        self.alert_box.setTitle("اعلان‌های نشست" if fa else "Session alerts")
        self.chk_unlock.setText("اعلان باز شدن قفل" if fa else "Notify on unlock")
        self.chk_lock.setText("اعلان قفل شدن" if fa else "Notify on lock")
        self.chk_startup.setText("اعلان روشن شدن برنامه" if fa else "Notify on app start")
        self.chk_resume.setText("اعلان بازگشت از خواب" if fa else "Notify on resume")
        self.btn_save.setText("ذخیره و اتصال" if fa else "Save & link")
        self.btn_logout.setText("خروج از حساب" if fa else "Sign out")
        self.btn_bot.setText("باز کردن ربات @ShMmControlbot" if fa else "Open bot @ShMmControlbot")
        self.hint.setText(
            "ربات: @ShMmControlbot — در ربات /id بزنید و عدد را اینجا وارد کنید. بدون ورود حساب Sh.M کنترل ریموت فعال نمی‌شود."
            if fa else
            "Bot: @ShMmControlbot — send /id in the bot and paste the number here. Login to Sh.M account required."
        )

    def on_show(self) -> None:
        self.retranslate()
        self._refresh_gate()

    def _refresh_gate(self) -> None:
        if auth_manager.is_logged_in:
            self.stack.setCurrentIndex(1)
            fa = get_language() == "fa"
            self.logged_as.setText(
                (f"وارد شده: {auth_manager.email}" if fa else f"Signed in: {auth_manager.email}")
            )
            self._load_tg()
        else:
            self.stack.setCurrentIndex(0)
            self.status.setText("")

    def _login(self) -> None:
        ok, msg = auth_manager.login(self.email_edit.text().strip(), self.pass_edit.text())
        if ok:
            QMessageBox.information(self, "Sh.M", "OK")
            self.pass_edit.clear()
            self._refresh_gate()
        else:
            QMessageBox.warning(self, "Sh.M", msg)

    def _register(self) -> None:
        # Registration is on the website (email verification via Resend)
        QDesktopServices.openUrl(QUrl("https://login.shayanmonavari.ir/#/register"))
        fa = get_language() == "fa"
        QMessageBox.information(
            self,
            "Sh.M",
            "برای ثبت‌نام به سایت منتقل شدید.\nبعد از ساخت حساب، اینجا فقط ورود کنید."
            if fa else
            "Opened the website for registration.\nAfter creating an account, sign in here.",
        )

    def _logout(self) -> None:
        auth_manager.logout()
        self._refresh_gate()
        QMessageBox.information(self, "Sh.M", "Signed out")

    def _load_tg(self) -> None:
        s = settings_manager.settings
        if s.telegram_user_id:
            self.uid_edit.setText(str(s.telegram_user_id))
        self.chk_unlock.setChecked(bool(s.notify_on_unlock))
        self.chk_lock.setChecked(bool(s.notify_on_lock))
        self.chk_startup.setChecked(bool(s.notify_on_startup))
        self.chk_resume.setChecked(bool(s.notify_on_resume))

    def _save(self) -> None:
        if not auth_manager.is_logged_in:
            QMessageBox.warning(self, "Sh.M", "Login required")
            return
        raw = self.uid_edit.text().strip()
        if not raw.isdigit():
            QMessageBox.warning(self, "Telegram", "Invalid User ID")
            return
        uid = int(raw)
        s = settings_manager.settings
        s.telegram_user_id = uid
        s.notify_on_unlock = self.chk_unlock.isChecked()
        s.notify_on_lock = self.chk_lock.isChecked()
        s.notify_on_startup = self.chk_startup.isChecked()
        s.notify_on_resume = self.chk_resume.isChecked()
        s.cloud_sync_enabled = True
        settings_manager.save()
        try:
            register_device(name=s.device_name or "PC")
        except Exception:
            pass
        res = bind_telegram(uid, name=s.device_name or "PC")
        if res.get("ok"):
            self.status.setText("Linked")
            QMessageBox.information(self, "Telegram", "Linked successfully")
        else:
            self.status.setText(str(res.get("error") or res))
            QMessageBox.warning(self, "Telegram", str(res.get("error") or res))
