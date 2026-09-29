"""Sh.M Control – Main Window (no VPN page, custom icons, full exit)."""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton,
    QScrollArea, QStackedWidget, QSystemTrayIcon, QMenu, QVBoxLayout, QWidget,
    QMessageBox,
)

from shmcontrol import __version__, __app_name__
from shmcontrol.config.settings import settings_manager
from shmcontrol.ui.theme import DARK_GAMING_QSS
from shmcontrol.ui.icons import NAV_ICONS, icon_app
from shmcontrol.ui.i18n import t, set_language, on_language_change
from shmcontrol.ui.pages.dashboard import DashboardPage
from shmcontrol.ui.pages.system_page import SystemPage
from shmcontrol.ui.pages.network_page import NetworkPage
from shmcontrol.ui.pages.dns_page import DnsPage
from shmcontrol.ui.pages.gaming_page import GamingPage
from shmcontrol.ui.pages.connectivity_page import ConnectivityPage
from shmcontrol.ui.pages.usage_page import UsagePage
from shmcontrol.ui.pages.telegram_page import TelegramPage
from shmcontrol.ui.pages.alerts_page import AlertsPage
from shmcontrol.ui.pages.logs_page import LogsPage
from shmcontrol.ui.pages.settings_page import SettingsPage
from shmcontrol.ui.pages.about_page import AboutPage
from shmcontrol.ui.pages.timer_page import TimerPage
from shmcontrol.ui.pages.cooling_page import CoolingPage
from shmcontrol.ui.pages.monitoring_page import MonitoringPage
from shmcontrol.ui.pages.ping_guard_page import PingGuardPage
from shmcontrol.ui.pages.overlay_page import OverlayPage

logger = logging.getLogger("shmcontrol.ui")

# (section_key, [(page_key, label_key, icon_key), ...])
NAV_GROUPS = [
    ("nav_overview", [
        ("dashboard", "dashboard", "dashboard"),
        ("monitoring", "monitoring", "dashboard"),
        ("system", "system", "system"),
    ]),
    ("nav_gaming_sec", [
        ("gaming", "gaming", "gaming"),
        ("connectivity", "connectivity", "connectivity"),
        ("ping_guard", "ping_guard", "network"),
        ("overlay", "overlay", "settings"),
        ("cooling", "cooling", "cooling"),
    ]),
    ("nav_network_sec", [
        ("network", "network", "network"),
        ("dns", "dns", "dns"),
        ("usage", "usage", "usage"),
    ]),
    ("nav_tools", [
        ("timer", "timer", "timer"),
        ("telegram", "telegram", "telegram"),
        ("alerts", "alerts", "alerts"),
        ("logs", "logs", "logs"),
        ("settings", "settings", "settings"),
        ("about", "about", "settings"),
    ]),
]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{__app_name__} v{__version__}")
        self.resize(1380, 880)
        self.setMinimumSize(1120, 720)
        self.setStyleSheet(DARK_GAMING_QSS)

        app_icon = icon_app(256)
        self.setWindowIcon(app_icon)
        QApplication.instance().setWindowIcon(app_icon)

        self._pages: dict[str, QWidget] = {}
        self._nav_buttons: dict[str, QPushButton] = {}
        self._section_labels: list = []
        self._footer_label = None
        self._tray: Optional[QSystemTrayIcon] = None
        self._force_quit = False

        self._build_ui()
        self._setup_tray()
        self._apply_language()
        self.navigate("dashboard")

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("contentHost")
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        side_outer = QVBoxLayout(sidebar)
        side_outer.setContentsMargins(0, 0, 0, 0)
        side_outer.setSpacing(0)

        brand = QFrame()
        brand.setObjectName("sidebarBrand")
        brand_lay = QHBoxLayout(brand)
        brand_lay.setContentsMargins(14, 14, 14, 10)
        logo = QLabel()
        logo.setPixmap(icon_app(40).pixmap(40, 40))
        brand_text = QVBoxLayout()
        title = QLabel(__app_name__)
        title.setObjectName("appTitle")
        title.setStyleSheet("padding: 0;")
        ver = QLabel(f"v{__version__}")
        ver.setObjectName("appVersion")
        ver.setStyleSheet("padding: 0;")
        brand_text.addWidget(title)
        brand_text.addWidget(ver)
        brand_lay.addWidget(logo)
        brand_lay.addLayout(brand_text)
        side_outer.addWidget(brand)

        nav_scroll = QScrollArea()
        nav_scroll.setWidgetResizable(True)
        nav_scroll.setFrameShape(QFrame.Shape.NoFrame)
        nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        nav_host = QWidget()
        side_layout = QVBoxLayout(nav_host)
        side_layout.setContentsMargins(0, 8, 0, 12)
        side_layout.setSpacing(2)

        for section_key, items in NAV_GROUPS:
            sec = QLabel(t(section_key))
            sec.setObjectName("navSection")
            side_layout.addWidget(sec)
            self._section_labels.append((sec, section_key))
            for key, label_key, icon_key in items:
                btn = QPushButton(f"  {t(label_key)}")
                fn = NAV_ICONS.get(icon_key)
                if fn:
                    try:
                        btn.setIcon(fn(32))
                    except Exception:
                        pass
                from PySide6.QtCore import QSize
                btn.setIconSize(QSize(18, 18))
                btn.setCheckable(True)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(lambda checked=False, k=key: self.navigate(k))
                side_layout.addWidget(btn)
                self._nav_buttons[key] = btn

        side_layout.addStretch()
        nav_scroll.setWidget(nav_host)
        side_outer.addWidget(nav_scroll, stretch=1)

        foot = QLabel(f"  ●  {t('local_agent')}")
        self._footer_label = foot
        foot.setObjectName("appVersion")
        side_outer.addWidget(foot)
        self.stack = QStackedWidget()
        self.stack.setObjectName("contentHost")
        root.addWidget(self.stack, stretch=1)
        root.addWidget(sidebar)

        self._pages["dashboard"] = DashboardPage()
        self._pages["monitoring"] = MonitoringPage()
        self._pages["ping_guard"] = PingGuardPage()
        self._pages["overlay"] = OverlayPage()
        self._pages["gaming"] = GamingPage()
        self._pages["connectivity"] = ConnectivityPage()
        self._pages["network"] = NetworkPage()
        self._pages["usage"] = UsagePage()
        self._pages["dns"] = DnsPage()
        self._pages["system"] = SystemPage()
        self._pages["timer"] = TimerPage()
        self._pages["cooling"] = CoolingPage()
        self._pages["telegram"] = TelegramPage()
        self._pages["alerts"] = AlertsPage()
        self._pages["logs"] = LogsPage()
        self._pages["settings"] = SettingsPage()
        self._pages["about"] = AboutPage()

        for key, widget in self._pages.items():
            self.stack.addWidget(widget)

    def navigate(self, key: str) -> None:
        if key not in self._pages:
            return
        for k, btn in self._nav_buttons.items():
            btn.setChecked(k == key)
        self.stack.setCurrentWidget(self._pages[key])
        page = self._pages[key]
        if hasattr(page, "on_show"):
            page.on_show()

    def _setup_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(icon_app(64))
        self._tray.setToolTip(__app_name__)
        menu = QMenu()
        show_act = QAction(t("open_dashboard"), self)
        show_act.triggered.connect(lambda: self._tray_navigate("dashboard"))
        menu.addAction(show_act)
        menu.addSeparator()
        exit_act = QAction(t("exit_completely"), self)
        exit_act.triggered.connect(self.quit_completely)
        menu.addAction(exit_act)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def quit_completely(self) -> None:
        """Full process exit – not minimize to tray."""
        self._force_quit = True
        dash = self._pages.get("dashboard")
        if dash and hasattr(dash, "_worker") and dash._worker:
            try:
                dash._worker.stop()
                dash._worker.wait(2000)
            except Exception:
                pass
        QApplication.instance().quit()

    def _tray_navigate(self, key: str) -> None:
        self.showNormal()
        self.activateWindow()
        self.navigate(key)

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.showNormal()
            self.activateWindow()

    def _apply_language(self) -> None:
        lang = getattr(settings_manager.settings, "language", "fa") or "fa"
        set_language(lang)
        # Keep LTR for data/tables; Persian is applied via translated strings
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        for page in self._pages.values():
            page.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self._retranslate()
        on_language_change(lambda _lang: self._retranslate())

    def _retranslate(self) -> None:
        """Refresh nav + known page titles when language changes."""
        for sec, key in getattr(self, "_section_labels", []):
            sec.setText(t(key))
        # Map page_key -> label_key same as NAV
        label_map = {}
        for _sk, items in NAV_GROUPS:
            for page_key, label_key, _ik in items:
                label_map[page_key] = label_key
        for key, btn in self._nav_buttons.items():
            btn.setText(f"  {t(label_map.get(key, key))}")
        if self._footer_label:
            self._footer_label.setText(f"  ●  {t('local_agent')}")
        # Ask pages to retranslate if they support it
        for page in self._pages.values():
            if hasattr(page, "retranslate"):
                try:
                    page.retranslate()
                except Exception:
                    pass

    def closeEvent(self, event) -> None:
        if self._force_quit:
            event.accept()
            return
        s = settings_manager.settings
        close_to_tray = getattr(s, "close_to_tray", True)
        if close_to_tray and self._tray:
            event.ignore()
            self.hide()
            self._tray.showMessage(
                __app_name__,
                t("tray_minimized"),
                QSystemTrayIcon.MessageIcon.Information,
                2500,
            )
            return
        # Ask
        reply = QMessageBox.question(
            self,
            t("exit_title"),
            t("exit_msg"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._force_quit = True
            event.accept()
        elif reply == QMessageBox.StandardButton.No and self._tray:
            event.ignore()
            self.hide()
        else:
            event.ignore()


# Power resume: only after long inactivity (not every focus/click)
def _install_resume_watcher(window) -> None:
    """Notify resume only if app was inactive ~90s+ (sleep/hibernate-like)."""
    try:
        import time
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt

        app = QApplication.instance()
        if app is None:
            return
        state = {"inactive_since": None, "last_notify": 0.0}

        def on_state(app_state):
            try:
                now = time.monotonic()
                if app_state in (
                    Qt.ApplicationState.ApplicationInactive,
                    Qt.ApplicationState.ApplicationSuspended,
                    Qt.ApplicationState.ApplicationHidden,
                ):
                    if state["inactive_since"] is None:
                        state["inactive_since"] = now
                    return
                if app_state != Qt.ApplicationState.ApplicationActive:
                    return
                # Became active
                since = state["inactive_since"]
                state["inactive_since"] = None
                if since is None:
                    return
                idle = now - since
                # Real sleep usually >> 90s; ignore alt-tab / short blur
                if idle < 90:
                    return
                if now - state["last_notify"] < 120:
                    return
                from shmcontrol.config.settings import settings_manager
                if not getattr(settings_manager.settings, "notify_on_resume", True):
                    return
                from shmcontrol.notifications.notify import notify_telegram_real, notify_windows
                name = getattr(settings_manager.settings, "device_name", None) or "PC"
                fa = (settings_manager.settings.language or "fa") == "fa"
                mins = int(idle // 60)
                msg = (
                    f"🟡 سیستم از Sleep برگشت (حدود {mins} دقیقه)\nDevice: {name}"
                    if fa else
                    f"🟡 PC resumed from sleep (~{mins} min)\nDevice: {name}"
                )
                notify_windows("Sh.M Control", msg, key="session_resume", cooldown=120)
                notify_telegram_real(msg, key="session_resume", cooldown=120)
                state["last_notify"] = now
            except Exception:
                pass

        app.applicationStateChanged.connect(on_state)
    except Exception:
        pass
