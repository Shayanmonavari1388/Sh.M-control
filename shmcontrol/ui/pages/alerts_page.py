"""Alerts configuration page."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QFormLayout, QHBoxLayout, QLabel, QDoubleSpinBox,
    QPushButton, QVBoxLayout, QWidget, QMessageBox, QGroupBox
)
from shmcontrol.config.settings import settings_manager


class AlertsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Alerts & Temperature Thresholds")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        lay.addWidget(title)

        # Temperature thresholds
        temp_box = QGroupBox("Temperature Thresholds (°C)")
        form = QFormLayout(temp_box)
        t = settings_manager.settings.temperature
        self.cpu_warn = QDoubleSpinBox()
        self.cpu_warn.setRange(50, 110)
        self.cpu_warn.setValue(t.cpu_warning)
        self.cpu_crit = QDoubleSpinBox()
        self.cpu_crit.setRange(60, 120)
        self.cpu_crit.setValue(t.cpu_critical)
        self.gpu_warn = QDoubleSpinBox()
        self.gpu_warn.setRange(50, 110)
        self.gpu_warn.setValue(t.gpu_warning)
        self.gpu_crit = QDoubleSpinBox()
        self.gpu_crit.setRange(60, 120)
        self.gpu_crit.setValue(t.gpu_critical)
        form.addRow("CPU Warning:", self.cpu_warn)
        form.addRow("CPU Critical:", self.cpu_crit)
        form.addRow("GPU Warning:", self.gpu_warn)
        form.addRow("GPU Critical:", self.gpu_crit)
        lay.addWidget(temp_box)

        note = QLabel(
            "وقتی Threshold رد شود: Windows Notification + (اختیاری) Telegram.\n"
            "از Spam جلوگیری می‌شود (cooldown)."
        )
        note.setStyleSheet("color: #8b949e;")
        lay.addWidget(note)

        save = QPushButton("Save Thresholds")
        save.setObjectName("primary")
        save.clicked.connect(self._save)
        lay.addWidget(save)
        lay.addStretch()

    def _save(self) -> None:
        s = settings_manager.settings
        s.temperature.cpu_warning = self.cpu_warn.value()
        s.temperature.cpu_critical = self.cpu_crit.value()
        s.temperature.gpu_warning = self.gpu_warn.value()
        s.temperature.gpu_critical = self.gpu_crit.value()
        settings_manager.save()
        QMessageBox.information(self, "Alerts", "Thresholds saved")
