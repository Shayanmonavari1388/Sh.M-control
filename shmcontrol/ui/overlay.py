"""
Desktop metrics overlay – corner-docked, always-on-top.
Not injected into exclusive fullscreen games.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QFont, QGuiApplication, QMouseEvent
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from shmcontrol.system.metrics import MetricsCollector
from shmcontrol.system.fps_reader import get_fps

# corner: top-left | top-right | bottom-left | bottom-right
DEFAULT_CORNER = "top-right"
MARGIN = 16


class MetricsOverlay(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Sh.M Overlay")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setStyleSheet(
            """
            QWidget#overlayRoot {
                background-color: rgba(12, 16, 24, 200);
                border-radius: 14px;
                border: 1px solid rgba(56, 189, 248, 0.25);
            }
            QLabel {
                color: #e8edf7;
                background: transparent;
                font-weight: 700;
                font-size: 12px;
            }
            """
        )
        self.setObjectName("overlayRoot")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(2)
        self.label = QLabel("—")
        self.label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self.label)

        self._collector = MetricsCollector()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._enabled = False
        self._corner = DEFAULT_CORNER
        self._drag_offset: QPoint | None = None

        self.resize(210, 130)
        self._place_corner()

    def set_corner(self, corner: str) -> None:
        if corner in ("top-left", "top-right", "bottom-left", "bottom-right"):
            self._corner = corner
            self._place_corner()

    def _place_corner(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        w, h = self.width(), self.height()
        if self._corner == "top-left":
            x, y = geo.left() + MARGIN, geo.top() + MARGIN
        elif self._corner == "top-right":
            x, y = geo.right() - w - MARGIN, geo.top() + MARGIN
        elif self._corner == "bottom-left":
            x, y = geo.left() + MARGIN, geo.bottom() - h - MARGIN
        else:
            x, y = geo.right() - w - MARGIN, geo.bottom() - h - MARGIN
        self.move(x, y)

    def set_overlay_enabled(self, on: bool) -> None:
        self._enabled = on
        if on:
            self._place_corner()
            self.show()
            self.raise_()
            self._timer.start(1000)
            self._tick()
        else:
            self._timer.stop()
            self.hide()

    def _tick(self) -> None:
        try:
            m = self._collector.collect()
            gpu = "N/A"
            if m.gpus:
                g = m.gpus[0]
                parts = []
                if g.temperature_c is not None:
                    parts.append(f"{g.temperature_c:.0f}°C")
                if g.gpu_util_percent is not None:
                    parts.append(f"{g.gpu_util_percent}%")
                gpu = " ".join(parts) if parts else "GPU"
            fps = get_fps()
            fps_s = f"{fps:.0f}" if fps is not None else "N/A"
            self.label.setText(
                f"FPS  {fps_s}\n"
                f"CPU  {m.cpu_percent:.0f}%\n"
                f"RAM  {m.ram_percent:.0f}%\n"
                f"GPU  {gpu}\n"
                f"NET  ↓{m.net_download_mb_s:.2f} ↑{m.net_upload_mb_s:.2f}"
            )
            self.adjustSize()
            # keep docked unless user dragged
            if self._drag_offset is None:
                self._place_corner()
        except Exception as e:
            self.label.setText(str(e)[:80])

    # optional drag
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        # after drag, stay where user left it (don't snap until re-enable)
        self._drag_offset = None
        super().mouseReleaseEvent(event)


_overlay: MetricsOverlay | None = None


def get_overlay() -> MetricsOverlay:
    global _overlay
    if _overlay is None:
        _overlay = MetricsOverlay()
    return _overlay
