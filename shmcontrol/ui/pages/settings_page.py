"""Settings – language applies real FA/EN translations."""

from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QLabel, QPushButton,
    QVBoxLayout, QWidget, QMessageBox, QSpinBox, QGroupBox, QHBoxLayout,
)
from shmcontrol.config.settings import settings_manager
from shmcontrol import __app_name__, __version__
from shmcontrol.ui.i18n import t, set_language


class SettingsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(14)

        self.title = QLabel()
        self.title.setObjectName("pageHeader")
        lay.addWidget(self.title)

        form = QFormLayout()
        self.lang_label = QLabel()
        self.lang = QComboBox()
        # Display names for languages
        self.lang.addItem("فارسی", "fa")
        self.lang.addItem("English", "en")
        cur = settings_manager.settings.language or "fa"
        idx = self.lang.findData(cur)
        if idx >= 0:
            self.lang.setCurrentIndex(idx)
        form.addRow(self.lang_label, self.lang)

        self.start_win = QCheckBox()
        self.start_win.setChecked(settings_manager.settings.start_with_windows)
        form.addRow(self.start_win)

        self.tray = QCheckBox()
        self.tray.setChecked(settings_manager.settings.minimize_to_tray)
        form.addRow(self.tray)

        self.close_tray = QCheckBox()
        self.close_tray.setChecked(getattr(settings_manager.settings, "close_to_tray", True))
        form.addRow(self.close_tray)

        self.interval_label = QLabel()
        self.interval = QSpinBox()
        self.interval.setRange(1000, 10000)
        self.interval.setSingleStep(500)
        self.interval.setValue(settings_manager.settings.monitoring_interval_ms)
        form.addRow(self.interval_label, self.interval)
        lay.addLayout(form)

        self.save_btn = QPushButton()
        self.save_btn.setObjectName("primary")
        self.save_btn.clicked.connect(self._save)
        lay.addWidget(self.save_btn)

        self.upd_box = QGroupBox()
        ul = QVBoxLayout(self.upd_box)
        self.ver_label = QLabel()
        self.latest_label = QLabel()
        ul.addWidget(self.ver_label)
        ul.addWidget(self.latest_label)
        row = QHBoxLayout()
        self.check_btn = QPushButton()
        self.check_btn.clicked.connect(self._check_updates)
        row.addWidget(self.check_btn)
        row.addStretch()
        ul.addLayout(row)
        self.update_note = QLabel()
        self.update_note.setWordWrap(True)
        self.update_note.setStyleSheet("color: #64748b;")
        ul.addWidget(self.update_note)
        lay.addWidget(self.upd_box)

        self.foot = QLabel()
        lay.addWidget(self.foot)
        lay.addStretch()
        self.retranslate()

    def on_show(self) -> None:
        self.retranslate()

    def retranslate(self) -> None:
        self.title.setText(t("settings_title"))
        self.lang_label.setText(t("language"))
        self.start_win.setText(t("start_windows"))
        self.tray.setText(t("minimize_tray"))
        self.close_tray.setText(t("close_to_tray"))
        self.interval_label.setText(t("monitor_interval"))
        self.save_btn.setText(t("save_settings"))
        self.upd_box.setTitle(t("updates"))
        self.ver_label.setText(f"{t('current_version')} {__version__}")
        self.check_btn.setText(t("check_updates"))
        self.update_note.setText(t("update_note"))
        self.foot.setText(f"{__app_name__} v{__version__}")
        if not self.latest_label.text() or "—" in self.latest_label.text() or "Latest" in self.latest_label.text() or "نسخه" in self.latest_label.text():
            pass

    def _save(self) -> None:
        s = settings_manager.settings
        lang = self.lang.currentData() or "fa"
        s.language = lang
        s.start_with_windows = self.start_win.isChecked()
        s.minimize_to_tray = self.tray.isChecked()
        s.close_to_tray = self.close_tray.isChecked()
        s.monitoring_interval_ms = self.interval.value()
        settings_manager.save()
        set_language(lang)
        self.retranslate()
        QMessageBox.information(self, t("settings_title"), t("lang_restart"))

    def _check_updates(self) -> None:
        from shmcontrol.updater import check_for_update, open_releases_page, REPO_URL
        now = datetime.now(timezone.utc).isoformat()
        settings_manager.settings.last_update_check = now
        settings_manager.save()
        info = check_for_update()
        if info.error:
            self.latest_label.setText(f"Error: {info.error}")
            QMessageBox.warning(self, t("updates"), info.error)
            return
        if info.available:
            self.latest_label.setText(
                f"{t('current_version')} {info.current}\n"
                f"Latest: {info.latest}\n"
                f"Update available"
            )
            msg = (
                f"نسخه جدید: {info.latest}\n"
                f"نسخه فعلی: {info.current}\n\n"
                f"صفحه انتشار باز شود؟"
            )
            reply = QMessageBox.question(
                self, t("updates"), msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                open_releases_page()
        else:
            self.latest_label.setText(
                f"{t('current_version')} {info.current}\n"
                f"Latest: {info.latest}\nUp to date"
            )
            QMessageBox.information(
                self, t("updates"),
                f"Up to date (v{info.current})\n{REPO_URL}",
            )
