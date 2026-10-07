"""
App Internet Usage – clean premium layout (LTR, no clutter).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QFileInfo, QSize
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QPixmap, QIcon
from PySide6.QtWidgets import QFileIconProvider
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QVBoxLayout, QWidget, QComboBox, QSpinBox, QMessageBox, QFormLayout,
    QGroupBox, QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QSizePolicy, QGridLayout,
)

from shmcontrol.usage.collector import usage_collector
from shmcontrol.usage.limits import usage_limit_manager
from shmcontrol.ui.i18n import t, get_language


def _fmt(b: int) -> str:
    b = max(0, int(b or 0))
    if b < 1024:
        return f"{b} B"
    if b < 1024 ** 2:
        return f"{b / 1024:.1f} KB"
    if b < 1024 ** 3:
        return f"{b / (1024 ** 2):.1f} MB"
    return f"{b / (1024 ** 3):.2f} GB"


def _icon(name: str, size: int = 36) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    key = (name or "?").lower()
    colors = {
        "chrome": QColor(66, 133, 244), "xray": QColor(99, 102, 241),
        "sing-box": QColor(99, 102, 241), "nvidia": QColor(118, 185, 0),
        "system": QColor(71, 85, 105), "__system__": QColor(71, 85, 105),
        "svchost": QColor(100, 116, 139), "explorer": QColor(14, 165, 233),
    }
    color = QColor(56, 189, 248)
    for k, c in colors.items():
        if k in key:
            color = c
            break
    p.setBrush(QBrush(color))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(0, 0, size, size, 10, 10)
    letter = (name or "?").replace(".exe", "").replace("__", "")
    letter = (letter[0] if letter else "?").upper()
    p.setPen(QPen(QColor(255, 255, 255)))
    f = p.font()
    f.setBold(True)
    f.setPixelSize(int(size * 0.42))
    p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, letter)
    p.end()
    return QIcon(pm)


_file_icons = QFileIconProvider()
_icon_cache: dict[str, QIcon] = {}


def _real_app_icon(name: str, path: str = "", size: int = 22) -> QIcon:
    """Prefer real Windows EXE icon; fall back to letter tile."""
    key = path or name
    if key in _icon_cache:
        return _icon_cache[key]
    icon = None
    if path:
        try:
            from pathlib import Path as _P
            if _P(path).is_file():
                icon = _file_icons.icon(QFileInfo(path))
                if icon is None or icon.isNull():
                    # QIcon from file path also works for .exe on Windows
                    icon = QIcon(path)
        except Exception:
            icon = None
    if icon is None or icon.isNull():
        icon = _icon(name, max(size, 32))
    _icon_cache[key] = icon
    return icon


class StatBox(QFrame):
    def __init__(self, label: str, value: str, color: str) -> None:
        super().__init__()
        self.setStyleSheet(
            "QFrame { background: rgba(15,23,42,0.65); border: 1px solid #1e293b; border-radius: 14px; }"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(4)
        self.lab = QLabel(label)
        self.lab.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 600; background: transparent; border: none;")
        self.val = QLabel(value)
        self.val.setStyleSheet(
            f"color: {color}; font-size: 22px; font-weight: 800; background: transparent; border: none;"
        )
        lay.addWidget(self.lab)
        lay.addWidget(self.val)

    def set_value(self, text: str) -> None:
        self.val.setText(text)

    def set_label(self, text: str) -> None:
        self.lab.setText(text)


class UsagePage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(18)

        # ---- Header ----
        head = QHBoxLayout()
        head.setSpacing(12)
        left = QVBoxLayout()
        left.setSpacing(2)
        self._title = QLabel()
        self._title.setObjectName("pageHeader")
        self._sub = QLabel()
        self._sub.setObjectName("pageSubtitle")
        left.addWidget(self._title)
        left.addWidget(self._sub)
        head.addLayout(left, stretch=1)

        self.period = QComboBox()
        self.period.setFixedWidth(150)
        self.period.setFixedHeight(36)
        self._btn = QPushButton()
        self._btn.setObjectName("primary")
        self._btn.setFixedHeight(36)
        self._btn.clicked.connect(self._load)
        head.addWidget(self.period, alignment=Qt.AlignmentFlag.AlignTop)
        head.addWidget(self._btn, alignment=Qt.AlignmentFlag.AlignTop)
        root.addLayout(head)

        # ---- System traffic (main focus) ----
        self.sys_card = QFrame()
        self.sys_card.setObjectName("card")
        sys_lay = QVBoxLayout(self.sys_card)
        sys_lay.setContentsMargins(20, 16, 20, 16)
        sys_lay.setSpacing(14)

        top_row = QHBoxLayout()
        ic = QLabel()
        ic.setFixedSize(40, 40)
        ic.setPixmap(_icon("__SYSTEM__", 40).pixmap(40, 40))
        self._sys_title = QLabel()
        self._sys_title.setStyleSheet(
            "font-size: 15px; font-weight: 700; color: #f1f5f9; background: transparent; border: none;"
        )
        top_row.addWidget(ic)
        top_row.addWidget(self._sys_title)
        top_row.addStretch()
        self._note_pill = QLabel()
        self._note_pill.setStyleSheet(
            "background: rgba(251,191,36,0.12); color: #fbbf24; border: 1px solid rgba(251,191,36,0.35);"
            "border-radius: 10px; padding: 4px 10px; font-size: 11px; font-weight: 600;"
        )
        top_row.addWidget(self._note_pill)
        sys_lay.addLayout(top_row)

        stats = QHBoxLayout()
        stats.setSpacing(12)
        self.box_down = StatBox("Download", "—", "#38bdf8")
        self.box_up = StatBox("Upload", "—", "#a78bfa")
        self.box_total = StatBox("Total", "—", "#34d399")
        stats.addWidget(self.box_down)
        stats.addWidget(self.box_up)
        stats.addWidget(self.box_total)
        sys_lay.addLayout(stats)
        root.addWidget(self.sys_card)

        # ---- Two columns: processes + VPN ----
        cols = QHBoxLayout()
        cols.setSpacing(14)

        # Left: processes table
        proc_card = QFrame()
        proc_card.setObjectName("card")
        pl = QVBoxLayout(proc_card)
        pl.setContentsMargins(16, 14, 16, 14)
        pl.setSpacing(10)
        self._proc_title = QLabel()
        self._proc_title.setStyleSheet(
            "font-size: 12px; font-weight: 800; color: #7dd3fc; letter-spacing: 1px; background: transparent; border: none;"
        )
        pl.addWidget(self._proc_title)
        self._proc_hint = QLabel()
        self._proc_hint.setWordWrap(True)
        self._proc_hint.setStyleSheet("color: #64748b; font-size: 11px; background: transparent; border: none;")
        pl.addWidget(self._proc_hint)

        self.proc_table = QTableWidget(0, 2)
        self.proc_table.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.proc_table.setShowGrid(False)
        self.proc_table.verticalHeader().setVisible(False)
        self.proc_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.proc_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.proc_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.proc_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.proc_table.setAlternatingRowColors(True)
        self.proc_table.setMinimumHeight(200)
        pl.addWidget(self.proc_table)
        cols.addWidget(proc_card, stretch=3)

        # Right: VPN + limits stacked
        right = QVBoxLayout()
        right.setSpacing(14)

        vpn_card = QFrame()
        vpn_card.setObjectName("card")
        vl = QVBoxLayout(vpn_card)
        vl.setContentsMargins(16, 14, 16, 14)
        vl.setSpacing(8)
        self._vpn_title = QLabel()
        self._vpn_title.setStyleSheet(
            "font-size: 12px; font-weight: 800; color: #7dd3fc; letter-spacing: 1px; background: transparent; border: none;"
        )
        vl.addWidget(self._vpn_title)
        self.vpn_status = QLabel()
        self.vpn_status.setWordWrap(True)
        self.vpn_status.setStyleSheet("color: #e2e8f0; font-size: 13px; background: transparent; border: none;")
        vl.addWidget(self.vpn_status)
        self.vpn_procs = QLabel()
        self.vpn_procs.setWordWrap(True)
        self.vpn_procs.setStyleSheet("color: #94a3b8; font-size: 12px; background: transparent; border: none;")
        vl.addWidget(self.vpn_procs)
        right.addWidget(vpn_card)

        lim_card = QFrame()
        lim_card.setObjectName("card")
        ll = QVBoxLayout(lim_card)
        ll.setContentsMargins(16, 14, 16, 14)
        ll.setSpacing(10)
        self._lim_title = QLabel()
        self._lim_title.setStyleSheet(
            "font-size: 12px; font-weight: 800; color: #7dd3fc; letter-spacing: 1px; background: transparent; border: none;"
        )
        ll.addWidget(self._lim_title)

        form = QFormLayout()
        form.setSpacing(8)
        self.lim_scope = QComboBox()
        self.lim_scope.addItems(["system", "application", "vpn", "adapter"])
        self.lim_target = QLineEdit()
        self.lim_target.setPlaceholderText("chrome.exe")
        self.lim_mb = QSpinBox()
        self.lim_mb.setRange(1, 1_000_000)
        self.lim_mb.setValue(5000)
        self.lim_action = QComboBox()
        self.lim_action.addItems(["notify", "notify_disconnect"])
        self._lbl_scope = QLabel("Scope")
        self._lbl_target = QLabel("Target")
        self._lbl_mb = QLabel("MB")
        self._lbl_act = QLabel("Action")
        form.addRow(self._lbl_scope, self.lim_scope)
        form.addRow(self._lbl_target, self.lim_target)
        form.addRow(self._lbl_mb, self.lim_mb)
        form.addRow(self._lbl_act, self.lim_action)
        ll.addLayout(form)

        brow = QHBoxLayout()
        self._btn_add = QPushButton()
        self._btn_add.setObjectName("primary")
        self._btn_add.clicked.connect(self._add_limit)
        self._btn_chk = QPushButton()
        self._btn_chk.clicked.connect(self._check_limits)
        self._btn_del = QPushButton()
        self._btn_del.clicked.connect(self._del_limit)
        brow.addWidget(self._btn_add)
        brow.addWidget(self._btn_chk)
        brow.addWidget(self._btn_del)
        ll.addLayout(brow)

        self.lim_table = QTableWidget(0, 3)
        self.lim_table.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.lim_table.verticalHeader().setVisible(False)
        self.lim_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.lim_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.lim_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.lim_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.lim_table.setMaximumHeight(120)
        ll.addWidget(self.lim_table)
        right.addWidget(lim_card)
        right.addStretch()

        cols.addLayout(right, stretch=2)
        root.addLayout(cols, stretch=1)

        self.retranslate()

    def retranslate(self) -> None:
        fa = get_language() == "fa"
        self._title.setText(t("usage_title"))
        self._sub.setText(t("usage_sub"))
        self._btn.setText(t("refresh"))
        self._sys_title.setText(t("system_all"))
        self._note_pill.setText(
            "ویندوز: فقط مجموع سیستم دقیق است" if fa else "Windows: system total only"
        )
        self.box_down.set_label(t("download"))
        self.box_up.set_label(t("upload"))
        self.box_total.set_label("Total" if not fa else "جمع")
        self._proc_title.setText(t("active_procs"))
        self._proc_hint.setText(
            "برنامه‌هایی که الان اتصال شبکه دارند — رتبه‌بندی مصرف نیستند."
            if fa else
            "Apps with open connections now — not a usage ranking."
        )
        self.proc_table.setHorizontalHeaderLabels(
            ["Process", "Status"] if not fa else ["پروسه", "وضعیت"]
        )
        self._vpn_title.setText(t("vpn_tunnel"))
        self._lim_title.setText(t("usage_limits"))
        self._lbl_scope.setText(t("scope"))
        self._lbl_target.setText(t("target"))
        self._lbl_mb.setText(t("limit_mb"))
        self._lbl_act.setText(t("action"))
        self._btn_add.setText(t("add_limit"))
        self._btn_chk.setText(t("check_limits"))
        self._btn_del.setText(t("delete_limit"))
        self.lim_table.setHorizontalHeaderLabels(
            [t("scope"), t("target"), t("limit_mb")]
        )
        cur = self.period.currentIndex()
        self.period.blockSignals(True)
        self.period.clear()
        self.period.addItems([t("period_today"), t("period_7"), t("period_30")])
        self.period.setCurrentIndex(max(0, min(cur, 2)))
        self.period.blockSignals(False)

    def on_show(self) -> None:
        self.retranslate()
        self._load()
        self._load_limits()
        self._load_vpn()

    def _load(self) -> None:
        days = {0: 1, 1: 7, 2: 30}.get(self.period.currentIndex(), 1)
        rows = usage_collector.get_period_totals(days=days)
        sys = next((r for r in rows if r["process_name"] == "__SYSTEM__"), None)
        if not sys and rows:
            # aggregate if needed
            dl = sum(r["download_bytes"] for r in rows)
            ul = sum(r["upload_bytes"] for r in rows)
            sys = {"download_bytes": dl, "upload_bytes": ul, "total_bytes": dl + ul}
        if sys:
            self.box_down.set_value(_fmt(sys["download_bytes"]))
            self.box_up.set_value(_fmt(sys["upload_bytes"]))
            self.box_total.set_value(_fmt(sys["total_bytes"]))
        else:
            self.box_down.set_value("0 B")
            self.box_up.set_value("0 B")
            self.box_total.set_value("0 B")

        fa = get_language() == "fa"
        details = usage_collector.get_active_network_process_details()
        self.proc_table.setRowCount(len(details))
        status = "Online" if not fa else "آنلاین"
        self.proc_table.setIconSize(QSize(20, 20))
        for i, d in enumerate(details):
            name = d.get("name") or "?"
            path = d.get("path") or ""
            item = QTableWidgetItem(f"  {name}")
            item.setIcon(_real_app_icon(name, path, 20))
            self.proc_table.setItem(i, 0, item)
            st = QTableWidgetItem(status)
            st.setForeground(QColor("#34d399"))
            self.proc_table.setItem(i, 1, st)
            self.proc_table.setRowHeight(i, 34)

    def _load_vpn(self) -> None:
        fa = get_language() == "fa"
        try:
            from shmcontrol.vpn.monitor import vpn_monitor
            st = vpn_monitor.detect()
            if st.connected:
                parts = []
                if st.adapters:
                    parts.append(
                        ("آداپتر: " if fa else "Adapter: ") + ", ".join(st.adapters)
                    )
                if st.processes:
                    parts.append(
                        ("پروسه: " if fa else "Process: ") + ", ".join(st.processes)
                    )
                method = st.detection_method or ""
                head = "VPN فعال" if fa else "VPN active"
                if st.provider_hint and st.provider_hint != "Unknown":
                    head += f" · {st.provider_hint}"
                self.vpn_status.setText(head + (f" ({method})" if method else ""))
                self.vpn_procs.setText(" | ".join(parts) if parts else "—")
            else:
                self.vpn_status.setText(t("no_vpn"))
                self.vpn_procs.setText(t("no_vpn_proc"))
        except Exception as e:
            self.vpn_status.setText(str(e))
            self.vpn_procs.setText("")

    def _load_limits(self) -> None:
        limits = usage_limit_manager.list_limits()
        self.lim_table.setRowCount(len(limits))
        for i, lim in enumerate(limits):
            self.lim_table.setItem(i, 0, QTableWidgetItem(lim.scope))
            self.lim_table.setItem(i, 1, QTableWidgetItem(lim.target))
            self.lim_table.setItem(i, 2, QTableWidgetItem(str(lim.limit_bytes // (1024 * 1024))))

    def _add_limit(self) -> None:
        scope = self.lim_scope.currentText()
        target = self.lim_target.text().strip() or scope
        usage_limit_manager.set_limit(scope, target, self.lim_mb.value(), self.lim_action.currentText())
        self._load_limits()
        QMessageBox.information(self, t("usage_limits"), t("limit_saved"))

    def _del_limit(self) -> None:
        row = self.lim_table.currentRow()
        if row < 0:
            # fallback: any selected index
            idxs = self.lim_table.selectionModel().selectedIndexes()
            if idxs:
                row = idxs[0].row()
        if row < 0 or self.lim_table.rowCount() == 0:
            QMessageBox.information(
                self, t("usage_limits"),
                "یک ردیف را از جدول انتخاب کنید" if get_language() == "fa" else "Select a row in the table first",
            )
            return
        scope_item = self.lim_table.item(row, 0)
        target_item = self.lim_table.item(row, 1)
        if not scope_item or not target_item:
            return
        scope = scope_item.text().strip()
        target = target_item.text().strip()
        usage_limit_manager.remove_limit(scope, target)
        self._load_limits()
        QMessageBox.information(
            self, t("usage_limits"),
            "سقف حذف شد" if get_language() == "fa" else "Limit removed",
        )

    def _check_limits(self) -> None:
        breaches = usage_limit_manager.check_and_alert()
        if not breaches:
            QMessageBox.information(self, t("usage_limits"), t("no_limit_exceeded"))
            return
        for b in breaches:
            QMessageBox.warning(
                self, t("usage_limits"),
                f"{b.get('scope')}/{b.get('target')}: "
                f"{b['used_bytes']/(1024**3):.2f} / {b['limit_bytes']/(1024**3):.2f} GB",
            )
