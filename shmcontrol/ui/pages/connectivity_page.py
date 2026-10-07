"""Game Connectivity Tester page."""

from __future__ import annotations

import asyncio
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QVBoxLayout, QWidget, QMessageBox
)

from shmcontrol.connectivity.tester import connectivity_tester, EndpointSpec
from shmcontrol.database.models import db


class TestWorker(QThread):
    finished = Signal(object)

    def __init__(self, name: str, kind: str) -> None:
        super().__init__()
        self.name = name
        self.kind = kind

    def run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            report = loop.run_until_complete(
                connectivity_tester.run_test(self.name, self.kind)
            )
            self.finished.emit(report)
        finally:
            loop.close()


class ConnectivityPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Game & Launcher Connectivity Tester")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        lay.addWidget(title)

        note = QLabel(
            "نتایج بر اساس تست واقعی هستند. هیچ تضمینی برای ورود به Match داده نمی‌شود. "
            "اگر تستی ممکن نباشد «Not Testable» نمایش داده می‌شود."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #8b949e;")
        lay.addWidget(note)

        row = QHBoxLayout()
        self.target_type = QComboBox()
        self.target_type.addItems(["game", "launcher"])
        self.target_combo = QComboBox()
        row.addWidget(QLabel("Type:"))
        row.addWidget(self.target_type)
        row.addWidget(QLabel("Target:"))
        row.addWidget(self.target_combo)
        btn = QPushButton("Test Connection")
        btn.setObjectName("primary")
        btn.clicked.connect(self._run)
        row.addWidget(btn)
        row.addStretch()
        lay.addLayout(row)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        lay.addWidget(self.output)

        self.target_type.currentTextChanged.connect(self._load_targets)
        self._load_targets()

    def _load_targets(self) -> None:
        self.target_combo.clear()
        kind = self.target_type.currentText()
        if kind == "game":
            rows = db.execute("SELECT name FROM games WHERE enabled=1 ORDER BY name")
        else:
            rows = db.execute("SELECT name FROM launchers WHERE enabled=1 ORDER BY name")
        for r in rows:
            self.target_combo.addItem(r["name"])
        if self.target_combo.count() == 0:
            self.target_combo.addItem("(no profiles – add in Gaming page)")

    def _run(self) -> None:
        name = self.target_combo.currentText()
        kind = self.target_type.currentText()
        if not name or name.startswith("("):
            QMessageBox.information(self, "Connectivity", "No target selected / no endpoints in DB yet.")
            return
        self.output.append(f"\n▶ Testing {name} ({kind}) ...")
        self.worker = TestWorker(name, kind)
        self.worker.finished.connect(self._on_done)
        self.worker.start()

    def _on_done(self, report) -> None:
        d = report.to_dict()
        self.output.append(f"\n{'='*50}")
        self.output.append(f"{d['target_name'].upper()} CONNECTION CHECK")
        self.output.append(f"Endpoints Tested: {d['total']}")
        self.output.append(f"Successful: {d['successful']}   Failed: {d['failed']}   Not Testable: {d['not_testable']}")
        if d["avg_latency_ms"] is not None:
            self.output.append(f"Average Latency: {d['avg_latency_ms']} ms")
        self.output.append(f"Status: {d['status']}")
        self.output.append("-" * 40)
        for r in d["results"]:
            icon = "⛔" if r["not_testable"] else ("✅" if r["success"] else "❌")
            lat = f"{r['latency_ms']:.0f}ms" if r["latency_ms"] is not None else ""
            err = r["error"] or r["details"] or ""
            self.output.append(f"{icon} [{r['service'] or r['protocol']}] {r['hostname']} {lat} {err}")
        self.output.append("=" * 50)
