"""Monitoring hub: live metrics + traffic + playtime."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QFileInfo
from PySide6.QtGui import QIcon, QColor, QPixmap, QPainter
from PySide6.QtWidgets import (
    QFileIconProvider,
    QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
)

from shmcontrol.system.metrics import MetricsCollector
from shmcontrol.network.apps_monitor import network_apps_monitor
from shmcontrol.gaming.playtime import playtime_tracker
from shmcontrol.ui.i18n import get_language

_icon_cache: dict[str, QIcon] = {}
_provider = None

def _get_provider():
    global _provider
    if _provider is None:
        _provider = QFileIconProvider()
    return _provider

def _letter_icon(name: str) -> QIcon:
    letter = (name[:1] or "?").upper()
    colors = ["#0ea5e9", "#6366f1", "#22c55e", "#f59e0b", "#ec4899", "#14b8a6"]
    color = colors[sum(ord(c) for c in name) % len(colors)]
    pm = QPixmap(28, 28)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(1, 1, 26, 26, 7, 7)
    p.setPen(QColor("#fff"))
    f = p.font()
    f.setBold(True)
    f.setPointSize(11)
    p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, letter)
    p.end()
    return QIcon(pm)

def _app_icon(name: str, path: str = "") -> QIcon:
    key = path or name
    if key in _icon_cache:
        return _icon_cache[key]
    icon = QIcon()
    if path:
        try:
            from pathlib import Path as P
            if P(path).is_file():
                icon = _get_provider().icon(QFileInfo(path))
        except Exception:
            pass
    if icon.isNull():
        icon = _letter_icon(name)
    _icon_cache[key] = icon
    return icon



def _fmt_b(b: int | None) -> str:
    if b is None:
        return "—"
    if b < 1024 ** 2:
        return f"{b/1024:.0f} KB"
    if b < 1024 ** 3:
        return f"{b/(1024**2):.1f} MB"
    return f"{b/(1024**3):.2f} GB"


def _fmt_rate(x: float | None) -> str:
    if x is None:
        return "—"
    return f"{x/1024/1024:.2f} MB/s" if x > 50_000 else f"{x/1024:.1f} KB/s"


class MonitoringPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self._collector = MetricsCollector()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(12)

        self.title = QLabel()
        self.title.setObjectName("pageHeader")
        root.addWidget(self.title)

        # live strip
        strip = QHBoxLayout()
        self.m_cpu = self._metric_box("CPU")
        self.m_gpu = self._metric_box("GPU")
        self.m_ram = self._metric_box("RAM")
        self.m_net = self._metric_box("NET")
        for w in (self.m_cpu, self.m_gpu, self.m_ram, self.m_net):
            strip.addWidget(w)
        root.addLayout(strip)

        # traffic table
        self.tr_title = QLabel()
        self.tr_title.setObjectName("sectionTitle")
        root.addWidget(self.tr_title)
        self.table = QTableWidget(0, 5)
        self.table.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        root.addWidget(self.table, stretch=1)

        # playtime
        self.pt_title = QLabel()
        self.pt_title.setObjectName("sectionTitle")
        root.addWidget(self.pt_title)
        self.pt_label = QLabel("—")
        self.pt_label.setStyleSheet("color: #94a3b8;")
        root.addWidget(self.pt_label)

        self.retranslate()

    def _metric_box(self, name: str) -> QFrame:
        f = QFrame()
        f.setObjectName("card")
        l = QVBoxLayout(f)
        l.setContentsMargins(14, 12, 14, 12)
        title = QLabel(name)
        title.setObjectName("cardTitle")
        val = QLabel("—")
        val.setObjectName("cardValueInfo")
        val.setObjectName("cardValue")
        sub = QLabel("")
        sub.setObjectName("cardSub")
        bar = QProgressBar()
        bar.setTextVisible(False)
        bar.setFixedHeight(5)
        l.addWidget(title)
        l.addWidget(val)
        l.addWidget(sub)
        l.addWidget(bar)
        f._val = val
        f._sub = sub
        f._bar = bar
        return f

    def retranslate(self) -> None:
        fa = get_language() == "fa"
        self.title.setText("مانیتورینگ" if fa else "Monitoring")
        self.tr_title.setText("ترافیک برنامه‌ها" if fa else "APP TRAFFIC")
        self.pt_title.setText("زمان بازی (امروز)" if fa else "PLAYTIME (TODAY)")
        self.table.setHorizontalHeaderLabels(
            ["برنامه", "اتصالات", "دانلود", "آپلود", "نرخ ↓"] if fa
            else ["App", "Conns", "Down", "Up", "↓ Rate"]
        )

    def on_show(self) -> None:
        self.retranslate()
        self._refresh()
        if not self._timer.isActive():
            self._timer.start(2000)

    def hideEvent(self, e) -> None:
        self._timer.stop()
        super().hideEvent(e)

    def _refresh(self) -> None:
        try:
            playtime_tracker.tick()
        except Exception:
            pass
        m = self._collector.collect()
        self.m_cpu._val.setText(f"{m.cpu_percent:.0f}%")
        if m.cpu_temp_c is not None:
            self.m_cpu._sub.setText(f"{m.cpu_temp_c:.0f}°C")
        self.m_cpu._bar.setValue(int(m.cpu_percent))
        self.m_ram._val.setText(f"{m.ram_used_gb:.1f}/{m.ram_total_gb:.0f}")
        self.m_ram._sub.setText(f"{m.ram_percent:.0f}%")
        self.m_ram._bar.setValue(int(m.ram_percent))
        if m.gpus:
            g = m.gpus[0]
            self.m_gpu._val.setText(
                f"{g.temperature_c:.0f}°C" if g.temperature_c is not None else "—"
            )
            if g.gpu_util_percent is not None:
                self.m_gpu._sub.setText(f"{g.gpu_util_percent}%")
                self.m_gpu._bar.setValue(int(g.gpu_util_percent))
        self.m_net._val.setText(f"↓{m.net_download_mb_s:.2f}")
        self.m_net._sub.setText(f"↑{m.net_upload_mb_s:.2f} MB/s")

        apps = network_apps_monitor.snapshot()[:40]
        self.table.setRowCount(len(apps))
        for i, a in enumerate(apps):
            name_item = QTableWidgetItem(f"  {a.name}")
            name_item.setIcon(_app_icon(a.name, getattr(a, "path", "") or ""))
            self.table.setItem(i, 0, name_item)
            self.table.setItem(i, 1, QTableWidgetItem(str(a.connections)))
            self.table.setItem(i, 2, QTableWidgetItem(_fmt_b(a.download_bytes)))
            self.table.setItem(i, 3, QTableWidgetItem(_fmt_b(a.upload_bytes)))
            self.table.setItem(i, 4, QTableWidgetItem(_fmt_rate(a.download_rate)))
            self.table.setRowHeight(i, 30)

        s = playtime_tracker.summary(1)
        h, rem = divmod(s["total_sec"], 3600)
        mi = rem // 60
        games = ", ".join(f"{g['name']} ({g['seconds']//60}m)" for g in s["games"][:5]) or "—"
        fa = get_language() == "fa"
        self.pt_label.setText(
            (f"مجموع امروز: {h}س {mi}د — {games}" if fa else f"Today: {h}h {mi}m — {games}")
        )
