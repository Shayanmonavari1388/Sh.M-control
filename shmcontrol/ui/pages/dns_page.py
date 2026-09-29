"""DNS Manager page — real list + Windows Apply/Restore with verification."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget, QHeaderView, QMessageBox, QLineEdit
)

from shmcontrol.dns.manager import dns_manager


class DnsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._servers: list[dict] = []
        self._test_cache: dict[str, dict] = {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)

        title = QLabel("DNS Manager")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        lay.addWidget(title)

        note = QLabel(
            "Status/Latency from real DNS queries (UDP/53). "
            "Apply/Restore require Administrator on Windows. "
            "A working DNS does not guarantee lower game ping."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #8b949e;")
        lay.addWidget(note)

        toolbar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search DNS...")
        self.search.textChanged.connect(self._reload)
        toolbar.addWidget(self.search)

        self.adapter_combo = QComboBox()
        self.adapter_combo.currentIndexChanged.connect(self._on_adapter_changed)
        toolbar.addWidget(QLabel("Adapter:"))
        toolbar.addWidget(self.adapter_combo)

        btn_read = QPushButton("Read Current")
        btn_read.clicked.connect(self._read_current)
        toolbar.addWidget(btn_read)

        btn_refresh = QPushButton("Refresh List")
        btn_refresh.clicked.connect(self._seed_and_load)
        toolbar.addWidget(btn_refresh)

        btn_test = QPushButton("Test Selected")
        btn_test.clicked.connect(self._test_selected)
        toolbar.addWidget(btn_test)

        btn_apply = QPushButton("Apply DNS")
        btn_apply.setObjectName("primary")
        btn_apply.clicked.connect(self._apply)
        toolbar.addWidget(btn_apply)

        btn_restore = QPushButton("Restore Previous DNS")
        btn_restore.clicked.connect(self._restore)
        toolbar.addWidget(btn_restore)
        toolbar.addStretch()
        lay.addLayout(toolbar)

        self.current_dns_label = QLabel("Current DNS: —")
        self.current_dns_label.setStyleSheet("color: #58a6ff;")
        lay.addWidget(self.current_dns_label)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "Name", "Primary", "Secondary", "IPv6", "Status", "Query ms"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        lay.addWidget(self.table)

        self.status = QLabel("")
        lay.addWidget(self.status)

    def on_show(self) -> None:
        self._load_adapters()
        self._seed_and_load()
        self._read_current()

    def _load_adapters(self) -> None:
        self.adapter_combo.blockSignals(True)
        self.adapter_combo.clear()
        adapters = dns_manager.list_dns_adapters()
        # Default: first non-virtual up adapter
        default_idx = 0
        for i, a in enumerate(adapters):
            label = a["name"]
            if a.get("is_virtual"):
                label += " [VPN/Virtual]"
            if not a.get("is_up"):
                label += " [down]"
            self.adapter_combo.addItem(label, a)
            if default_idx == 0 and a.get("is_up") and not a.get("is_virtual"):
                default_idx = i
        if adapters:
            self.adapter_combo.setCurrentIndex(default_idx)
        self.adapter_combo.blockSignals(False)

    def _selected_adapter_info(self) -> dict | None:
        data = self.adapter_combo.currentData()
        return data if isinstance(data, dict) else None

    def _selected_adapter_name(self) -> str:
        info = self._selected_adapter_info()
        return (info or {}).get("name") or ""

    def _on_adapter_changed(self) -> None:
        self._read_current()

    def _read_current(self) -> None:
        name = self._selected_adapter_name()
        if not name:
            self.current_dns_label.setText("Current DNS: —")
            return
        r = dns_manager.read_adapter_dns(name)
        if r.get("error") and not r.get("ok"):
            self.current_dns_label.setText(f"Current DNS: (read failed) {r.get('error')}")
            return
        mode = r.get("mode") or "unknown"
        servers = r.get("servers") or []
        if mode == "dhcp" and not servers:
            self.current_dns_label.setText(f"Current DNS [{name}]: Automatic / DHCP")
        elif servers:
            self.current_dns_label.setText(
                f"Current DNS [{name}]: {', '.join(servers)} ({mode})"
            )
        else:
            self.current_dns_label.setText(f"Current DNS [{name}]: {mode}")

    def _seed_and_load(self) -> None:
        n = dns_manager.seed_from_json()
        if n:
            self.status.setText(f"Loaded {n} DNS servers from database file")
        self._reload()

    def _reload(self) -> None:
        q = (self.search.text() or "").strip().lower()
        all_srv = dns_manager.list_servers(category=None)
        if q:
            all_srv = [
                s for s in all_srv
                if q in (s.get("name") or "").lower()
                or q in (s.get("primary_ip") or "")
                or q in (s.get("secondary_ip") or "")
            ]
        self._servers = all_srv
        self.table.setRowCount(len(self._servers))
        for i, s in enumerate(self._servers):
            primary = s.get("primary_ip") or ""
            cached = self._test_cache.get(primary, {})
            status = cached.get("status", "—")
            qms = cached.get("resolution_ms")
            qms_s = f"{qms}" if qms is not None else "—"
            self.table.setItem(i, 0, QTableWidgetItem(s.get("name", "")))
            self.table.setItem(i, 1, QTableWidgetItem(primary))
            self.table.setItem(i, 2, QTableWidgetItem(s.get("secondary_ip") or "—"))
            self.table.setItem(i, 3, QTableWidgetItem(s.get("ipv6") or "—"))
            self.table.setItem(i, 4, QTableWidgetItem(str(status).upper() if status != "—" else "—"))
            self.table.setItem(i, 5, QTableWidgetItem(qms_s))

    def _selected_server(self) -> dict | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        idx = rows[0].row()
        if 0 <= idx < len(self._servers):
            return self._servers[idx]
        return None

    def _test_selected(self) -> None:
        s = self._selected_server()
        if not s:
            QMessageBox.warning(self, "DNS", "Select a DNS first")
            return
        primary = s.get("primary_ip") or ""
        self.status.setText(f"Testing {s.get('name')} ({primary}) …")
        r = dns_manager.test_dns(primary, samples=3)
        self._test_cache[primary] = r
        sec = s.get("secondary_ip")
        sec_msg = ""
        if sec:
            r2 = dns_manager.test_dns(sec, samples=1)
            sec_msg = f" | Secondary {sec}: {r2['status']}"
            if r2.get("resolution_ms") is not None:
                sec_msg += f" {r2['resolution_ms']} ms"
        self.status.setText(
            f"{s.get('name')}: {r['status'].upper()} | "
            f"avg {r.get('resolution_avg_ms')} ms "
            f"(min {r.get('resolution_min_ms')} / max {r.get('resolution_max_ms')})"
            f"{sec_msg}"
            + (f" | {r.get('error')}" if r.get("error") else "")
        )
        self._reload()

    def _apply(self) -> None:
        s = self._selected_server()
        info = self._selected_adapter_info()
        if not s or not info:
            QMessageBox.warning(self, "DNS", "Select DNS and Adapter")
            return
        adapter = info["name"]
        primary = s.get("primary_ip")
        secondary = s.get("secondary_ip")

        if info.get("is_virtual"):
            warn = QMessageBox.warning(
                self,
                "VPN / Virtual Adapter",
                f"'{adapter}' looks like a VPN or virtual adapter.\n\n"
                "Changing DNS on VPN adapters can break tunnels.\n"
                "Continue anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if warn != QMessageBox.StandardButton.Yes:
                return
            allow_virtual = True
        else:
            allow_virtual = False

        reply = QMessageBox.question(
            self,
            "Apply DNS",
            f"Are you sure you want to apply this DNS?\n\n"
            f"Adapter: {adapter}\n"
            f"DNS: {s.get('name')}\n"
            f"Primary: {primary}\n"
            f"Secondary: {secondary or '—'}\n\n"
            f"Requires Administrator on Windows.\n"
            f"Previous DNS will be backed up for Restore.",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        ok, msg, details = dns_manager.apply_dns_windows(
            adapter, primary, secondary, allow_virtual=allow_virtual, verify=True
        )
        self._read_current()
        if ok:
            QMessageBox.information(self, "DNS", msg)
        else:
            QMessageBox.critical(self, "DNS Apply Failed", msg)

    def _restore(self) -> None:
        adapter = self._selected_adapter_name()
        if not adapter:
            return
        reply = QMessageBox.question(
            self,
            "Restore DNS",
            f"Restore previous DNS on '{adapter}'?\n"
            f"(Static backup if available, otherwise Automatic/DHCP)",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        ok, msg, _ = dns_manager.restore_previous_dns(adapter, verify=True)
        self._read_current()
        if ok:
            QMessageBox.information(self, "DNS", msg)
        else:
            QMessageBox.critical(self, "DNS Restore Failed", msg)
