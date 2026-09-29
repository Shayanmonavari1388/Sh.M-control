"""Fan + RGB page — hardware-aware, no fake values."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget, QGroupBox, QFormLayout
)

from shmcontrol.system.fan_control import fan_controller
from shmcontrol.system.rgb_control import rgb_controller


class CoolingPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Cooling / Fan & RGB")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        lay.addWidget(title)

        # Fan
        fan_box = QGroupBox("Fan Control")
        fl = QVBoxLayout(fan_box)
        self.fan_status = QLabel("")
        self.fan_status.setWordWrap(True)
        fl.addWidget(self.fan_status)
        self.fan_list = QLabel("")
        self.fan_list.setWordWrap(True)
        fl.addWidget(self.fan_list)
        lay.addWidget(fan_box)

        # RGB
        rgb_box = QGroupBox("RGB Control")
        rl = QVBoxLayout(rgb_box)
        self.rgb_status = QLabel("")
        self.rgb_status.setWordWrap(True)
        rl.addWidget(self.rgb_status)
        lay.addWidget(rgb_box)

        btn = QPushButton("Refresh Hardware Detection")
        btn.clicked.connect(self._refresh)
        lay.addWidget(btn)

        note = QLabel(
            "Fan/RGB write control requires vendor SDK or OpenRGB. "
            "This page never shows fabricated RPM or colors."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #8b949e;")
        lay.addWidget(note)
        lay.addStretch()

    def on_show(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        fs = fan_controller.status()
        self.fan_status.setText(
            f"Supported: {fs.supported} | Backend: {fs.backend}\n{fs.message}"
        )
        if fs.fans:
            lines = []
            for f in fs.fans:
                parts = [f.name]
                if f.rpm is not None:
                    parts.append(f"{f.rpm} RPM")
                if f.percent is not None:
                    parts.append(f"{f.percent}%")
                lines.append(" — ".join(parts))
            self.fan_list.setText("\n".join(lines))
        else:
            self.fan_list.setText("No fan sensors reported.")

        rs = rgb_controller.status()
        self.rgb_status.setText(
            f"Supported: {rs.supported} | Backend: {rs.backend}\n{rs.message}"
        )
