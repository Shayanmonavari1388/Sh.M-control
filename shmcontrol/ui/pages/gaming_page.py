"""Game Mode + Windows optimizations — manual ON/OFF works offline."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
    QMessageBox, QScrollArea, QGridLayout,
)

from shmcontrol.gaming.game_mode import game_mode_manager
from shmcontrol.gaming import optimizations as opt
from shmcontrol.config.settings import settings_manager
from shmcontrol.ui.i18n import get_language


class GamingPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)

        self.title = QLabel()
        self.title.setObjectName("pageHeader")
        outer.addWidget(self.title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        host = QWidget()
        lay = QVBoxLayout(host)
        lay.setSpacing(12)

        top = QFrame()
        top.setObjectName("card")
        tl = QHBoxLayout(top)
        self.chk_master = QCheckBox()
        self.chk_master.setChecked(
            bool(getattr(settings_manager.settings, "game_mode_enabled", False))
            or game_mode_manager.is_active
        )
        self.chk_master.toggled.connect(self._toggle_master)
        self.status = QLabel()
        tl.addWidget(self.chk_master)
        tl.addStretch()
        tl.addWidget(self.status)
        lay.addWidget(top)

        self.grid_host = QFrame()
        self.grid_host.setObjectName("card")
        gl = QGridLayout(self.grid_host)
        gl.setSpacing(10)
        self.toggles: dict[str, QCheckBox] = {}
        items = [
            ("priority", "اولویت پردازنده برای بازی", "Game process priority"),
            ("power", "پاور پلن High Performance", "High Performance power plan"),
            ("win_gm", "Windows Game Mode", "Windows Game Mode registry"),
            ("hags", "HAGS (نیاز Admin + ری‌استارت)", "HAGS (Admin + reboot)"),
            ("temp_clean", "پاکسازی TEMP", "Clean user TEMP"),
            ("trim_ws", "Trim Working Set", "Trim working set"),
        ]
        for i, (key, fa, en) in enumerate(items):
            cb = QCheckBox(fa)
            cb.setProperty("en", en)
            cb.setProperty("fa", fa)
            cb.setChecked(key in ("priority", "power", "win_gm"))
            self.toggles[key] = cb
            gl.addWidget(cb, i // 2, i % 2)
        lay.addWidget(self.grid_host)

        row = QHBoxLayout()
        self.btn_apply = QPushButton()
        self.btn_apply.setObjectName("primary")
        self.btn_apply.clicked.connect(self._apply)
        self.btn_scan = QPushButton()
        self.btn_scan.clicked.connect(self._scan)
        row.addWidget(self.btn_apply)
        row.addWidget(self.btn_scan)
        row.addStretch()
        lay.addLayout(row)

        self.hint = QLabel()
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("color: #94a3b8;")
        lay.addWidget(self.hint)
        lay.addStretch()

        scroll.setWidget(host)
        outer.addWidget(scroll)
        self.retranslate()
        self._refresh_status()

    def retranslate(self) -> None:
        fa = get_language() == "fa"
        self.title.setText("حالت بازی" if fa else "Game Mode")
        self.chk_master.setText("حالت گیمینگ روشن" if fa else "Game Mode ON")
        self.btn_apply.setText("اعمال بهینه‌سازی‌ها" if fa else "Apply optimizations")
        self.btn_scan.setText("اسکن بازی فعال" if fa else "Scan active game")
        self.hint.setText(
            "با روشن کردن تیک بالا، Game Mode فوراً فعال می‌شود (حتی بدون بازی).\n"
            "اگر بازی از لیست شناخته‌شده باز باشد، اولویت پردازنده هم بالا می‌رود."
            if fa else
            "Turn the switch ON to activate Game Mode immediately (even without a game).\n"
            "If a known game is running, process priority is also boosted."
        )
        for cb in self.toggles.values():
            cb.setText(cb.property("fa") if fa else cb.property("en"))

    def on_show(self) -> None:
        self.retranslate()
        self._refresh_status()

    def _refresh_status(self) -> None:
        fa = get_language() == "fa"
        st = game_mode_manager.state
        if st.active:
            self.status.setText(
                (f"فعال: {st.game_name}" if fa else f"Active: {st.game_name}")
            )
            self.status.setStyleSheet("color: #22c55e; font-weight: 700;")
            self.chk_master.blockSignals(True)
            self.chk_master.setChecked(True)
            self.chk_master.blockSignals(False)
        else:
            self.status.setText("خاموش" if fa else "Off")
            self.status.setStyleSheet("color: #94a3b8;")

    def _toggle_master(self, on: bool) -> None:
        settings_manager.settings.game_mode_enabled = on
        settings_manager.save()
        fa = get_language() == "fa"
        if on:
            ok, msg = game_mode_manager.force_activate("Manual")
            # Apply selected optimizations
            self._apply_selected(silent=True)
            QMessageBox.information(self, "Game Mode", msg if ok else f"FAIL: {msg}")
        else:
            ok, msg = game_mode_manager.force_deactivate()
            try:
                opt.set_balanced_power()
            except Exception:
                pass
            QMessageBox.information(self, "Game Mode", msg)
        self._refresh_status()

    def _apply_selected(self, silent: bool = False) -> None:
        lines = []
        if self.toggles["power"].isChecked():
            ok, m = opt.set_high_performance_power()
            lines.append(f"Power: {m}")
        if self.toggles["win_gm"].isChecked():
            ok, m = opt.enable_windows_game_mode(True)
            lines.append(f"Win GM: {m}")
        if self.toggles["hags"].isChecked():
            ok, m = opt.enable_hags(True)
            lines.append(f"HAGS: {m}")
        if self.toggles["temp_clean"].isChecked():
            ok, m = opt.clean_temp_files() if hasattr(opt, "clean_temp") else (False, "N/A")
            lines.append(f"TEMP: {m}")
        if self.toggles["trim_ws"].isChecked():
            ok, m = opt.empty_working_sets()
            lines.append(f"Trim: {m}")
        if self.toggles["priority"].isChecked() and game_mode_manager.state.pid:
            ok, m = opt.set_process_priority(game_mode_manager.state.pid, "high")
            lines.append(f"Priority: {m}")
        if not silent:
            QMessageBox.information(self, "Apply", "\n".join(lines) or "Nothing selected")

    def _apply(self) -> None:
        if not game_mode_manager.is_active:
            game_mode_manager.force_activate("Manual")
            settings_manager.settings.game_mode_enabled = True
            settings_manager.save()
            self.chk_master.blockSignals(True)
            self.chk_master.setChecked(True)
            self.chk_master.blockSignals(False)
        self._apply_selected(silent=False)
        self._refresh_status()

    def _scan(self) -> None:
        game_mode_manager.enabled = True
        game_mode_manager.scan_and_apply()
        self._refresh_status()
        fa = get_language() == "fa"
        if game_mode_manager.is_active and not game_mode_manager.state.manual:
            QMessageBox.information(
                self, "Scan",
                f"بازی پیدا شد: {game_mode_manager.state.game_name}" if fa
                else f"Game found: {game_mode_manager.state.game_name}",
            )
        else:
            QMessageBox.information(
                self, "Scan",
                "بازی شناخته‌شده‌ای در حال اجرا نیست." if fa
                else "No known game process running.",
            )
