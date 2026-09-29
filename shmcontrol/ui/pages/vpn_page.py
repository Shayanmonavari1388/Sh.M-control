"""VPN Detection & Traffic – monitoring only, no VPN service."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget, QPushButton

from shmcontrol.vpn.monitor import vpn_monitor


class VpnPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)

        title = QLabel("VPN Monitoring")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        lay.addWidget(title)

        self.status = QLabel("Checking...")
        self.status.setStyleSheet("font-size: 16px;")
        lay.addWidget(self.status)

        self.details = QLabel("")
        self.details.setWordWrap(True)
        lay.addWidget(self.details)

        self.traffic = QLabel("")
        lay.addWidget(self.traffic)

        self.attr = QLabel("")
        self.attr.setStyleSheet("color: #d29922;")
        self.attr.setWordWrap(True)
        lay.addWidget(self.attr)

        btn = QPushButton("Refresh Detection")
        btn.clicked.connect(self._detect)
        lay.addWidget(btn)

        note = QLabel(
            "Sh.M Control only detects and monitors VPN adapters. "
            "It does not provide, sell, or generate VPN configs."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #8b949e;")
        lay.addWidget(note)
        lay.addStretch()

    def on_show(self) -> None:
        self._detect()

    def _detect(self) -> None:
        s = vpn_monitor.detect()
        if s.connected:
            self.status.setText("🟢 VPN / Virtual Adapter Connected")
            self.details.setText(
                "Adapters:\n" + "\n".join(f"• {n}" for n in s.adapters)
                + f"\n\nProvider hint: {s.provider_hint}"
            )
            self.traffic.setText(
                f"Adapter traffic (from OS counters):\n"
                f"Download: {s.download_bytes / (1024**2):.1f} MB\n"
                f"Upload: {s.upload_bytes / (1024**2):.1f} MB\n"
                f"Total: {(s.download_bytes + s.upload_bytes) / (1024**2):.1f} MB"
            )
            self.attr.setText(
                "VPN traffic detected.\n"
                "Per-app VPN attribution unavailable on this platform "
                "(Windows does not expose process→tunnel mapping without drivers)."
            )
        else:
            self.status.setText("⚪ No active VPN adapter detected")
            self.details.setText("Provider: Unknown / Not detected")
            self.traffic.setText("")
            self.attr.setText("")
