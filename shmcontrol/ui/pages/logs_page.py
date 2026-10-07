"""Logs viewer."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget, QHeaderView, QLineEdit
)
from shmcontrol.database.models import db


class LogsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Logs")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        lay.addWidget(title)

        row = QHBoxLayout()
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter feature / command...")
        row.addWidget(self.filter_edit)
        btn = QPushButton("Refresh")
        btn.clicked.connect(self._load)
        row.addWidget(btn)
        clear = QPushButton("Clear Old")
        clear.clicked.connect(self._clear)
        row.addWidget(clear)
        lay.addLayout(row)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Time", "Level", "Feature", "Command", "Result / Error"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.table)

    def on_show(self) -> None:
        self._load()

    def _load(self) -> None:
        q = self.filter_edit.text().strip()
        if q:
            rows = db.execute(
                "SELECT timestamp, level, feature, command, result, error FROM logs "
                "WHERE feature LIKE ? OR command LIKE ? ORDER BY id DESC LIMIT 200",
                (f"%{q}%", f"%{q}%"),
            )
        else:
            rows = db.execute(
                "SELECT timestamp, level, feature, command, result, error FROM logs ORDER BY id DESC LIMIT 200"
            )
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem((r["timestamp"] or "")[:19]))
            self.table.setItem(i, 1, QTableWidgetItem(r["level"] or ""))
            self.table.setItem(i, 2, QTableWidgetItem(r["feature"] or ""))
            self.table.setItem(i, 3, QTableWidgetItem(r["command"] or ""))
            msg = r["result"] or r["error"] or ""
            self.table.setItem(i, 4, QTableWidgetItem(msg[:120]))

    def _clear(self) -> None:
        with db.connection() as conn:
            conn.execute("DELETE FROM logs WHERE id NOT IN (SELECT id FROM logs ORDER BY id DESC LIMIT 500)")
        self._load()
