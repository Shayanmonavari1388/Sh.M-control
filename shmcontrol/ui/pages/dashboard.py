"""Dashboard – animated bg, custom icons, clean cards."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal, Qt, QTimer
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea,
    QVBoxLayout, QWidget,
)

from shmcontrol.system.metrics import MetricsCollector, SystemMetrics
from shmcontrol.ui.icons import METRIC_ICONS
from shmcontrol.ui.widgets import AnimatedBackground, MetricCard
from shmcontrol.ui.i18n import t


class MetricsWorker(QThread):
    updated = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._collector = MetricsCollector()
        self._running = True

    def run(self) -> None:
        self._collector.collect()
        while self._running:
            try:
                self.updated.emit(self._collector.collect())
            except Exception:
                pass
            self.msleep(2000)

    def stop(self) -> None:
        self._running = False


def _level_pct(p):
    if p is None:
        return "info"
    if p >= 90:
        return "crit"
    if p >= 75:
        return "warn"
    return "ok"


def _level_temp(t, warn=75, crit=90):
    if t is None:
        return "info"
    if t >= crit:
        return "crit"
    if t >= warn:
        return "warn"
    return "ok"


class DashboardPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._worker = None
        self._build()
        self._start_worker()

    def _build(self) -> None:
        self._bg = AnimatedBackground(self)
        self._bg.lower()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(16)

        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        self._header_title = QLabel(t("dash_title"))
        self._header_title.setObjectName("pageHeader")
        self._header_sub = QLabel(t("dash_sub"))
        self._header_sub.setObjectName("pageSubtitle")
        titles.addWidget(self._header_title)
        titles.addWidget(self._header_sub)
        head.addLayout(titles)
        head.addStretch()
        self.chip_gpu = QLabel("GPU · —")
        self.chip_gpu.setObjectName("statusChip")
        self.chip_net = QLabel("Network · —")
        self.chip_net.setObjectName("statusChip")
        head.addWidget(self.chip_gpu)
        head.addWidget(self.chip_net)
        outer.addLayout(head)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName("contentHost")
        root = QVBoxLayout(content)
        root.setContentsMargins(0, 4, 6, 12)
        root.setSpacing(14)

        def section(text):
            lab = QLabel(text)
            lab.setObjectName("sectionTitle")
            return lab

        def icon_for(key):
            fn = METRIC_ICONS.get(key)
            return fn(64) if fn else None

        root.addWidget(section("PERFORMANCE"))
        perf = QGridLayout()
        perf.setSpacing(14)
        self.cards = {}
        for i, (key, title) in enumerate([
            ("cpu", "CPU Usage"), ("ram", "RAM Usage"),
            ("gpu_util", "GPU Usage"), ("gpu_mem", "GPU Memory"),
            ("cpu_temp", "CPU Temp"), ("gpu_temp", "GPU Temp"),
            ("gpu_fan", "GPU Fan"), ("disk", "Disk Usage"),
        ]):
            c = MetricCard(title, icon_for(key))
            self.cards[key] = c
            perf.addWidget(c, i // 4, i % 4)
        root.addLayout(perf)

        root.addWidget(section("NETWORK"))
        net = QGridLayout()
        net.setSpacing(14)
        for i, (key, title) in enumerate([
            ("net_down", "Download"), ("net_up", "Upload"),
            ("local_ip", "Local IP"), ("public_ip", "Public IP"),
        ]):
            c = MetricCard(title, icon_for(key))
            self.cards[key] = c
            net.addWidget(c, 0, i)
        root.addLayout(net)

        root.addWidget(section("SYSTEM"))
        sysg = QGridLayout()
        sysg.setSpacing(14)
        for i, (key, title) in enumerate([
            ("gpu_name", "Graphics"), ("uptime", "Uptime"),
            ("timer", "System Timer"), ("game_mode", "Game Mode"),
        ]):
            c = MetricCard(title, icon_for(key))
            self.cards[key] = c
            sysg.addWidget(c, 0, i)
        root.addLayout(sysg)
        root.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

        QTimer.singleShot(400, self._fetch_public_ip)
        QTimer.singleShot(800, self._refresh_extras)
        self._net_timer = QTimer(self)
        self._net_timer.timeout.connect(self._poll_network_status)
        self._net_timer.start(2500)
        QTimer.singleShot(600, self._poll_network_status)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._bg.setGeometry(self.rect())

    def _start_worker(self) -> None:
        self._worker = MetricsWorker()
        self._worker.updated.connect(self._on_metrics)
        self._worker.start()

    def _fetch_public_ip(self) -> None:
        from shmcontrol.network.tools import get_public_ip
        try:
            ip = get_public_ip(timeout=2.0)
        except Exception:
            ip = None
        self.cards["public_ip"].set_value(ip or "N/A", "info")
        self._update_net_chip(online=bool(ip))

    def _is_online(self) -> bool:
        """Fast local connectivity probe (does not require public IP services)."""
        import socket
        for host, port in (("1.1.1.1", 53), ("8.8.8.8", 53), ("1.1.1.1", 443)):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.8)
                s.connect((host, port))
                s.close()
                return True
            except Exception:
                try:
                    s.close()
                except Exception:
                    pass
                continue
        # Fallback: any non-loopback IPv4 assigned
        try:
            import psutil
            for _name, addrs in psutil.net_if_addrs().items():
                for a in addrs:
                    if getattr(a, "family", None) == socket.AF_INET:
                        ip = a.address or ""
                        if ip and not ip.startswith("127.") and not ip.startswith("169.254."):
                            # Has interface, try UDP connect for route
                            try:
                                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                                s.settimeout(0.5)
                                s.connect(("8.8.8.8", 80))
                                s.close()
                                return True
                            except Exception:
                                pass
        except Exception:
            pass
        return False

    def _update_net_chip(self, online: bool | None = None) -> None:
        if online is None:
            try:
                online = self._is_online()
            except Exception:
                online = False
        if online:
            self.chip_net.setText("Network · Online")
            self.chip_net.setObjectName("statusChipOk")
        else:
            self.chip_net.setText("Network · Offline")
            self.chip_net.setObjectName("statusChipErr")
        try:
            self.chip_net.style().unpolish(self.chip_net)
            self.chip_net.style().polish(self.chip_net)
        except Exception:
            pass

    def _poll_network_status(self) -> None:
        """Update Online/Offline chip every few seconds."""
        try:
            online = self._is_online()
            self._update_net_chip(online=online)
            # Refresh public IP occasionally when online and card is N/A
            if online:
                cur = ""
                try:
                    cur = self.cards["public_ip"]._value.text() if hasattr(self.cards["public_ip"], "_value") else ""
                except Exception:
                    cur = ""
                if not cur or cur in ("N/A", "—", "-"):
                    QTimer.singleShot(0, self._fetch_public_ip)
            else:
                try:
                    self.cards["public_ip"].set_value("N/A", "info")
                except Exception:
                    pass
        except Exception:
            self._update_net_chip(online=False)

    def _refresh_extras(self) -> None:
        try:
            from shmcontrol.system.timer import system_timer
            a = system_timer.get_active()
            if a:
                rem = system_timer.remaining_seconds() or 0
                h, rem = divmod(rem, 3600)
                m, s = divmod(rem, 60)
                self.cards["timer"].set_value(f"{h:02d}:{m:02d}:{s:02d}", "warn")
                self.cards["timer"].set_sub(a.action.upper())
            else:
                self.cards["timer"].set_value("Idle", "ok")
                self.cards["timer"].set_sub("No scheduled action")
        except Exception:
            self.cards["timer"].set_value("—", "info")
        try:
            from shmcontrol.gaming.game_mode import game_mode_manager
            on = bool(getattr(game_mode_manager, "is_active", False))
            st = game_mode_manager.state
            if on:
                label = st.game_name or "ON"
                self.cards["game_mode"].set_value("ON", "ok")
                self.cards["game_mode"].set_sub(str(label)[:28])
            elif getattr(game_mode_manager, "enabled", False):
                self.cards["game_mode"].set_value("Ready", "info")
                self.cards["game_mode"].set_sub("Waiting for game")
            else:
                self.cards["game_mode"].set_value("Off", "info")
                self.cards["game_mode"].set_sub("Not engaged")
        except Exception:
            self.cards["game_mode"].set_value("Off", "info")

    def _on_metrics(self, m: SystemMetrics) -> None:
        lv = _level_pct(m.cpu_percent)
        self.cards["cpu"].set_value(f"{m.cpu_percent:.0f}%", lv)
        self.cards["cpu"].set_side("")
        self.cards["cpu"].set_bar(int(m.cpu_percent), lv)
        lv = _level_pct(m.ram_percent)
        self.cards["ram"].set_value(f"{m.ram_percent:.0f}%", lv)
        self.cards["ram"].set_sub(f"{m.ram_used_gb:.1f} / {m.ram_total_gb:.1f} GB")
        self.cards["ram"].set_bar(int(m.ram_percent), lv)
        lv = _level_pct(m.disk_percent)
        self.cards["disk"].set_value(f"{m.disk_percent:.0f}%", lv)
        self.cards["disk"].set_bar(int(m.disk_percent), lv)
        self.cards["net_down"].set_value(f"{m.net_download_mb_s:.2f}", "info")
        self.cards["net_down"].set_sub("MB/s")
        self.cards["net_up"].set_value(f"{m.net_upload_mb_s:.2f}", "info")
        self.cards["net_up"].set_sub("MB/s")
        self.cards["local_ip"].set_value(m.local_ip or "N/A", "info")
        # Net chip is polled separately every 2.5s for accuracy
        if m.public_ip:
            self.cards["public_ip"].set_value(m.public_ip, "info")
        hours = int(m.uptime_seconds // 3600)
        mins = int((m.uptime_seconds % 3600) // 60)
        self.cards["uptime"].set_value(f"{hours}h {mins}m", "info")
        if m.cpu_temp_c is not None:
            lv = _level_temp(m.cpu_temp_c)
            self.cards["cpu_temp"].set_value(f"{m.cpu_temp_c:.0f}°C", lv)
            self.cards["cpu_temp"].set_side(f"{m.cpu_percent:.0f}%")
            self.cards["cpu_temp"].set_bar(int(min(100, m.cpu_temp_c)), lv)
        else:
            self.cards["cpu_temp"].set_value("N/A", "info")
            self.cards["cpu_temp"].set_sub("Sensor not available")
            self.cards["cpu_temp"].set_bar(None)
        if m.gpus:
            g = m.gpus[0]
            self.chip_gpu.setText(f"GPU · {(g.name or 'NVIDIA')[:22]}")
            self.chip_gpu.setObjectName("statusChipOk")
            self.chip_gpu.style().unpolish(self.chip_gpu)
            self.chip_gpu.style().polish(self.chip_gpu)
            self.cards["gpu_name"].set_value((g.name or "—")[:28], "info")
            if g.gpu_util_percent is not None:
                lv = _level_pct(float(g.gpu_util_percent))
                self.cards["gpu_util"].set_value(f"{g.gpu_util_percent}%", lv)
                self.cards["gpu_util"].set_bar(int(g.gpu_util_percent), lv)
            if g.mem_used_mb is not None and g.mem_total_mb:
                used, total = g.mem_used_mb / 1024, g.mem_total_mb / 1024
                pct = (g.mem_used_mb / g.mem_total_mb) * 100
                lv = _level_pct(pct)
                self.cards["gpu_mem"].set_value(f"{used:.1f}/{total:.0f}", lv)
                self.cards["gpu_mem"].set_sub("GB")
                self.cards["gpu_mem"].set_bar(int(pct), lv)
            if g.temperature_c is not None:
                lv = _level_temp(g.temperature_c)
                self.cards["gpu_temp"].set_value(f"{g.temperature_c:.0f}°C", lv)
                if g.gpu_util_percent is not None:
                    self.cards["gpu_temp"].set_side(f"{g.gpu_util_percent}%")
                self.cards["gpu_temp"].set_bar(int(min(100, g.temperature_c)), lv)
            if g.fans:
                fan_strs = [f"F{f.index}:{f.speed_percent}%" for f in g.fans if f.speed_percent is not None]
                if fan_strs:
                    avg = g.fan_speed_avg_percent
                    self.cards["gpu_fan"].set_value("  ".join(fan_strs), "info")
                    if avg is not None:
                        self.cards["gpu_fan"].set_sub(f"Avg {avg:.0f}%")
                        self.cards["gpu_fan"].set_bar(int(avg), _level_pct(avg))
                else:
                    self.cards["gpu_fan"].set_value("N/A", "info")
                    self.cards["gpu_fan"].set_sub("Not available")
            else:
                self.cards["gpu_fan"].set_value("N/A", "info")
                self.cards["gpu_fan"].set_sub("Not available")
        else:
            self.chip_gpu.setText("GPU · Not detected")
            self.cards["gpu_util"].set_value("N/A", "info")
            self.cards["gpu_fan"].set_value("N/A", "info")
        self._refresh_extras()

    def retranslate(self) -> None:
        if hasattr(self, "_header_title"):
            self._header_title.setText(t("dash_title"))
            self._header_sub.setText(t("dash_sub"))
        # Card titles
        mapping = {
            "cpu": "cpu_usage", "ram": "ram_usage", "gpu_util": "gpu_usage",
            "gpu_mem": "gpu_memory", "cpu_temp": "cpu_temp", "gpu_temp": "gpu_temp",
            "gpu_fan": "gpu_fan", "disk": "disk_usage", "net_down": "download",
            "net_up": "upload", "local_ip": "local_ip", "public_ip": "public_ip",
            "gpu_name": "graphics", "uptime": "uptime", "timer": "system_timer",
            "game_mode": "game_mode",
        }
        for key, tk in mapping.items():
            card = self.cards.get(key)
            if card and hasattr(card, "title_label"):
                card.title_label.setText(t(tk).upper())

    def on_show(self) -> None:
        self.retranslate()
        self._refresh_extras()

    def closeEvent(self, event) -> None:
        if self._worker:
            self._worker.stop()
            self._worker.wait(3000)
        super().closeEvent(event)
