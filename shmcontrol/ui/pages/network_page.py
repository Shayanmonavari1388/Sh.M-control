"""Network tools + live apps with real icons."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QFileInfo, QSize
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QBrush, QPixmap
from PySide6.QtWidgets import (
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QVBoxLayout, QWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QFileIconProvider, QAbstractItemView,
)

from shmcontrol.network.tools import (
    ping, dns_lookup, get_public_ip, get_local_ip, get_default_gateway,
    flush_dns, list_network_adapters,
)
from shmcontrol.network.apps_monitor import network_apps_monitor
from shmcontrol.ui.i18n import t, get_language


_file_icons = QFileIconProvider()
_icon_cache: dict[str, QIcon] = {}


def _letter_icon(name: str, size: int = 20) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QBrush(QColor(56, 189, 248)))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(0, 0, size, size, 5, 5)
    letter = (name or "?")[0].upper()
    p.setPen(QPen(QColor(255, 255, 255)))
    f = p.font()
    f.setBold(True)
    f.setPixelSize(int(size * 0.55))
    p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, letter)
    p.end()
    return QIcon(pm)


def _app_icon(name: str, path: str = "") -> QIcon:
    key = path or name
    if key in _icon_cache:
        return _icon_cache[key]
    icon = None
    if path:
        try:
            from pathlib import Path
            if Path(path).is_file():
                icon = _file_icons.icon(QFileInfo(path))
                if icon is None or icon.isNull():
                    icon = QIcon(path)
        except Exception:
            icon = None
    if icon is None or icon.isNull():
        icon = _letter_icon(name, 22)
    _icon_cache[key] = icon
    return icon


def _fmt_rate(bps: float | None) -> str:
    if bps is None:
        return "—"
    if bps < 1024:
        return f"{bps:.0f} B/s"
    if bps < 1024 ** 2:
        return f"{bps / 1024:.1f} KB/s"
    return f"{bps / (1024 ** 2):.2f} MB/s"


def _fmt_bytes(b: int | None) -> str:
    if b is None:
        return "—"
    if b < 1024:
        return f"{b} B"
    if b < 1024 ** 2:
        return f"{b / 1024:.1f} KB"
    if b < 1024 ** 3:
        return f"{b / (1024 ** 2):.1f} MB"
    return f"{b / (1024 ** 3):.2f} GB"


class NetworkPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_apps)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        self._title = QLabel()
        self._title.setObjectName("pageHeader")
        root.addWidget(self._title)
        self._sub = QLabel()
        self._sub.setObjectName("pageSubtitle")
        self._sub.setWordWrap(True)
        root.addWidget(self._sub)

        # ---- Live apps ----
        apps_card = QFrame()
        apps_card.setObjectName("card")
        al = QVBoxLayout(apps_card)
        al.setContentsMargins(16, 14, 16, 14)
        al.setSpacing(10)

        row = QHBoxLayout()
        self._apps_title = QLabel()
        self._apps_title.setStyleSheet(
            "font-size: 13px; font-weight: 800; color: #7dd3fc; letter-spacing: 0.8px; "
            "background: transparent; border: none;"
        )
        row.addWidget(self._apps_title)
        row.addStretch()
        self._bytes_note = QLabel()
        self._bytes_note.setStyleSheet(
            "color: #fbbf24; font-size: 11px; font-weight: 600; background: transparent; border: none;"
        )
        row.addWidget(self._bytes_note)
        self._btn_refresh = QPushButton()
        self._btn_refresh.setObjectName("primary")
        self._btn_refresh.setFixedHeight(32)
        self._btn_refresh.clicked.connect(self._refresh_apps)
        row.addWidget(self._btn_refresh)
        al.addLayout(row)

        self.apps_table = QTableWidget(0, 8)
        self.apps_table.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.apps_table.setIconSize(QSize(20, 20))
        self.apps_table.setShowGrid(False)
        self.apps_table.verticalHeader().setVisible(False)
        self.apps_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.apps_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.apps_table.setAlternatingRowColors(True)
        hdr = self.apps_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in range(1, 8):
            hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self.apps_table.setMinimumHeight(260)
        al.addWidget(self.apps_table)
        root.addWidget(apps_card, stretch=2)

        # ---- Classic tools ----
        tools_card = QFrame()
        tools_card.setObjectName("card")
        tl = QVBoxLayout(tools_card)
        tl.setContentsMargins(16, 14, 16, 14)
        tl.setSpacing(10)
        self._tools_title = QLabel()
        self._tools_title.setStyleSheet(
            "font-size: 13px; font-weight: 800; color: #7dd3fc; letter-spacing: 0.8px; "
            "background: transparent; border: none;"
        )
        tl.addWidget(self._tools_title)

        form = QFormLayout()
        self.host_input = QLineEdit("1.1.1.1")
        self._host_lbl = QLabel("Host / IP")
        form.addRow(self._host_lbl, self.host_input)
        tl.addLayout(form)

        btns = QHBoxLayout()
        self._tool_btns: list[tuple[QPushButton, str, object]] = []
        for key, slot in [
            ("Ping", self._do_ping),
            ("DNS Lookup", self._do_dns),
            ("Public IP", self._do_public),
            ("Local IP", self._do_local),
            ("Gateway", self._do_gateway),
            ("Flush DNS", self._do_flush),
            ("Adapters", self._do_adapters),
        ]:
            b = QPushButton(key)
            b.clicked.connect(slot)
            btns.addWidget(b)
            self._tool_btns.append((b, key, slot))
        tl.addLayout(btns)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumHeight(140)
        tl.addWidget(self.output)
        root.addWidget(tools_card, stretch=1)

        self.retranslate()

    def retranslate(self) -> None:
        fa = get_language() == "fa"
        self._title.setText(t("network") if t("network") != "network" else ("شبکه" if fa else "Network"))
        self._sub.setText(
            "نرم‌افزارهای دارای اتصال شبکه · آیکون واقعی · ابزارهای شبکه"
            if fa else
            "Apps with network connections · real icons · network tools"
        )
        self._apps_title.setText("نرم‌افزارهای شبکه (زنده)" if fa else "LIVE NETWORK APPS")
        self._btn_refresh.setText(t("refresh"))
        self._tools_title.setText("ابزار شبکه" if fa else "NETWORK TOOLS")
        self._host_lbl.setText("Host / IP")
        headers = (
            ["نرم‌افزار", "PID", "اتصالات", "دانلود", "آپلود", "↓ نرخ", "↑ نرخ", "مقصد"]
            if fa else
            ["Application", "PID", "Conns", "Download", "Upload", "↓ Rate", "↑ Rate", "Remote"]
        )
        self.apps_table.setHorizontalHeaderLabels(headers)

    def on_show(self) -> None:
        self.retranslate()
        self._refresh_apps()
        if not self._timer.isActive():
            self._timer.start(2500)

    def hideEvent(self, event) -> None:
        self._timer.stop()
        super().hideEvent(event)

    def _refresh_apps(self) -> None:
        fa = get_language() == "fa"
        apps = network_apps_monitor.snapshot()
        self.apps_table.setRowCount(len(apps))
        any_bytes = False
        for i, a in enumerate(apps):
            name_item = QTableWidgetItem(f"  {a.name}")
            name_item.setIcon(_app_icon(a.name, a.path))
            self.apps_table.setItem(i, 0, name_item)
            self.apps_table.setItem(i, 1, QTableWidgetItem(str(a.pid)))
            self.apps_table.setItem(i, 2, QTableWidgetItem(str(a.connections)))

            if a.bytes_supported and a.download_bytes is not None:
                any_bytes = True
                self.apps_table.setItem(i, 3, QTableWidgetItem(_fmt_bytes(a.download_bytes)))
                self.apps_table.setItem(i, 4, QTableWidgetItem(_fmt_bytes(a.upload_bytes)))
                self.apps_table.setItem(i, 5, QTableWidgetItem(_fmt_rate(a.download_rate)))
                self.apps_table.setItem(i, 6, QTableWidgetItem(_fmt_rate(a.upload_rate)))
            else:
                for col in (3, 4, 5, 6):
                    it = QTableWidgetItem("—")
                    it.setForeground(QColor("#64748b"))
                    self.apps_table.setItem(i, col, it)

            remote = ", ".join(a.remote_sample) if a.remote_sample else "—"
            self.apps_table.setItem(i, 7, QTableWidgetItem(remote))
            self.apps_table.setRowHeight(i, 32)

        if any_bytes:
            self._bytes_note.setText(
                "آمار TCP واقعی (EStats) · نرخ از نمونه دوم به بعد"
                if fa else
                "Real TCP EStats · rates from 2nd sample"
            )
            self._bytes_note.setStyleSheet(
                "color: #34d399; font-size: 11px; font-weight: 600; background: transparent; border: none;"
            )
        else:
            self._bytes_note.setText(
                "برای آمار بایت، برنامه را Run as Administrator اجرا کنید"
                if fa else
                "Run as Administrator for per-app byte stats"
            )

    def _log(self, text: str) -> None:
        self.output.append(text)

    def _do_ping(self) -> None:
        host = self.host_input.text().strip()
        self._log(f"Pinging {host} ...")
        r = ping(host)
        if r.success:
            self._log(f"OK – Latency: {r.latency_ms:.1f} ms  Loss: {r.packet_loss}%")
        else:
            self._log(f"Failed: {r.error}")

    def _do_dns(self) -> None:
        host = self.host_input.text().strip()
        r = dns_lookup(host)
        if r.success:
            self._log(f"{host} → {', '.join(r.addresses)}")
        else:
            self._log(f"DNS failed: {r.error}")

    def _do_public(self) -> None:
        self._log(f"Public IP: {get_public_ip() or 'N/A'}")

    def _do_local(self) -> None:
        self._log(f"Local IP: {get_local_ip() or 'N/A'}")

    def _do_gateway(self) -> None:
        self._log(f"Gateway: {get_default_gateway() or 'N/A'}")

    def _do_flush(self) -> None:
        ok, msg = flush_dns()
        self._log(msg if ok else f"Flush failed: {msg}")

    def _do_adapters(self) -> None:
        adapters = list_network_adapters()
        if not adapters:
            self._log("No adapters found")
            return
        for a in adapters:
            self._log(str(a))
