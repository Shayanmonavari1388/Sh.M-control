"""
Sh.M Control – custom painted icons (no external asset dependency).
Clean geometric icons for nav + metric cards.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QBrush, QLinearGradient, QPainterPath
from PySide6.QtWidgets import QApplication


def _px(size: int = 64) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    return pm


def _painter(pm: QPixmap) -> QPainter:
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    return p


def icon_app(size: int = 256) -> QIcon:
    """Main application icon – shield + pulse."""
    pm = _px(size)
    p = _painter(pm)
    s = float(size)

    # Soft glow circle
    from PySide6.QtGui import QRadialGradient
    rg = QRadialGradient(s * 0.5, s * 0.45, s * 0.55)
    rg.setColorAt(0.0, QColor(14, 165, 233, 90))
    rg.setColorAt(1.0, QColor(0, 0, 0, 0))
    p.setBrush(QBrush(rg))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QRectF(s * 0.05, s * 0.05, s * 0.9, s * 0.9))

    # Shield path
    path = QPainterPath()
    path.moveTo(s * 0.50, s * 0.12)
    path.lineTo(s * 0.82, s * 0.28)
    path.lineTo(s * 0.82, s * 0.55)
    path.quadTo(s * 0.82, s * 0.78, s * 0.50, s * 0.90)
    path.quadTo(s * 0.18, s * 0.78, s * 0.18, s * 0.55)
    path.lineTo(s * 0.18, s * 0.28)
    path.closeSubpath()

    grad = QLinearGradient(0, s * 0.1, 0, s * 0.9)
    grad.setColorAt(0.0, QColor(56, 189, 248))
    grad.setColorAt(0.5, QColor(99, 102, 241))
    grad.setColorAt(1.0, QColor(14, 165, 233))
    p.setBrush(QBrush(grad))
    p.setPen(QPen(QColor(125, 211, 252, 180), max(1, size // 48)))
    p.drawPath(path)

    # Inner pulse / network node
    p.setBrush(QColor(15, 23, 42, 220))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QRectF(s * 0.36, s * 0.40, s * 0.28, s * 0.28))

    p.setPen(QPen(QColor(125, 211, 252), max(2, size // 32)))
    p.drawEllipse(QRectF(s * 0.42, s * 0.46, s * 0.16, s * 0.16))
    p.drawLine(QPointF(s * 0.50, s * 0.46), QPointF(s * 0.50, s * 0.38))
    p.drawLine(QPointF(s * 0.42, s * 0.54), QPointF(s * 0.34, s * 0.54))
    p.drawLine(QPointF(s * 0.58, s * 0.54), QPointF(s * 0.66, s * 0.54))

    p.end()
    return QIcon(pm)


def _stroke_icon(draw_fn, size: int = 64, color: QColor | None = None) -> QIcon:
    pm = _px(size)
    p = _painter(pm)
    col = color or QColor(125, 211, 252)
    pen = QPen(col, max(2.0, size * 0.07))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    draw_fn(p, float(size), col)
    p.end()
    return QIcon(pm)


def icon_cpu(size: int = 64) -> QIcon:
    def draw(p, s, c):
        m = s * 0.22
        p.drawRoundedRect(QRectF(m, m, s - 2 * m, s - 2 * m), s * 0.08, s * 0.08)
        # pins
        for i in range(3):
            x = s * (0.32 + i * 0.18)
            p.drawLine(QPointF(x, m), QPointF(x, m - s * 0.08))
            p.drawLine(QPointF(x, s - m), QPointF(x, s - m + s * 0.08))
            y = s * (0.32 + i * 0.18)
            p.drawLine(QPointF(m, y), QPointF(m - s * 0.08, y))
            p.drawLine(QPointF(s - m, y), QPointF(s - m + s * 0.08, y))
        p.drawRect(QRectF(s * 0.38, s * 0.38, s * 0.24, s * 0.24))
    return _stroke_icon(draw, size)


def icon_ram(size: int = 64) -> QIcon:
    def draw(p, s, c):
        p.drawRoundedRect(QRectF(s * 0.15, s * 0.30, s * 0.70, s * 0.40), 4, 4)
        for i in range(4):
            x = s * (0.22 + i * 0.15)
            p.drawLine(QPointF(x, s * 0.30), QPointF(x, s * 0.22))
        p.setBrush(QBrush(c))
        p.drawRect(QRectF(s * 0.25, s * 0.40, s * 0.12, s * 0.18))
        p.drawRect(QRectF(s * 0.45, s * 0.40, s * 0.12, s * 0.18))
        p.drawRect(QRectF(s * 0.65, s * 0.40, s * 0.08, s * 0.18))
    return _stroke_icon(draw, size)


def icon_gpu(size: int = 64) -> QIcon:
    def draw(p, s, c):
        p.drawRoundedRect(QRectF(s * 0.12, s * 0.28, s * 0.76, s * 0.44), 6, 6)
        p.drawEllipse(QRectF(s * 0.22, s * 0.36, s * 0.28, s * 0.28))
        p.drawEllipse(QRectF(s * 0.30, s * 0.44, s * 0.12, s * 0.12))
        p.drawLine(QPointF(s * 0.58, s * 0.40), QPointF(s * 0.78, s * 0.40))
        p.drawLine(QPointF(s * 0.58, s * 0.50), QPointF(s * 0.74, s * 0.50))
        p.drawLine(QPointF(s * 0.58, s * 0.60), QPointF(s * 0.70, s * 0.60))
    return _stroke_icon(draw, size)


def icon_temp(size: int = 64) -> QIcon:
    def draw(p, s, c):
        p.drawRoundedRect(QRectF(s * 0.42, s * 0.12, s * 0.16, s * 0.52), 8, 8)
        p.setBrush(QBrush(c))
        p.drawEllipse(QRectF(s * 0.34, s * 0.55, s * 0.32, s * 0.32))
        p.drawLine(QPointF(s * 0.50, s * 0.22), QPointF(s * 0.50, s * 0.55))
    return _stroke_icon(draw, size)


def icon_fan(size: int = 64) -> QIcon:
    def draw(p, s, c):
        p.drawEllipse(QRectF(s * 0.18, s * 0.18, s * 0.64, s * 0.64))
        p.drawEllipse(QRectF(s * 0.42, s * 0.42, s * 0.16, s * 0.16))
        for ang in (0, 120, 240):
            from math import cos, sin, radians
            a = radians(ang - 90)
            p.drawLine(
                QPointF(s * 0.5 + cos(a) * s * 0.08, s * 0.5 + sin(a) * s * 0.08),
                QPointF(s * 0.5 + cos(a) * s * 0.28, s * 0.5 + sin(a) * s * 0.28),
            )
    return _stroke_icon(draw, size)


def icon_disk(size: int = 64) -> QIcon:
    def draw(p, s, c):
        p.drawRoundedRect(QRectF(s * 0.18, s * 0.22, s * 0.64, s * 0.56), 6, 6)
        p.drawLine(QPointF(s * 0.18, s * 0.38), QPointF(s * 0.82, s * 0.38))
        p.setBrush(QBrush(c))
        p.drawEllipse(QRectF(s * 0.62, s * 0.50, s * 0.10, s * 0.10))
    return _stroke_icon(draw, size)


def icon_download(size: int = 64) -> QIcon:
    def draw(p, s, c):
        p.drawLine(QPointF(s * 0.50, s * 0.18), QPointF(s * 0.50, s * 0.62))
        path = QPainterPath()
        path.moveTo(s * 0.32, s * 0.48)
        path.lineTo(s * 0.50, s * 0.68)
        path.lineTo(s * 0.68, s * 0.48)
        p.drawPath(path)
        p.drawLine(QPointF(s * 0.24, s * 0.78), QPointF(s * 0.76, s * 0.78))
    return _stroke_icon(draw, size)


def icon_upload(size: int = 64) -> QIcon:
    def draw(p, s, c):
        p.drawLine(QPointF(s * 0.50, s * 0.78), QPointF(s * 0.50, s * 0.34))
        path = QPainterPath()
        path.moveTo(s * 0.32, s * 0.48)
        path.lineTo(s * 0.50, s * 0.28)
        path.lineTo(s * 0.68, s * 0.48)
        p.drawPath(path)
        p.drawLine(QPointF(s * 0.24, s * 0.18), QPointF(s * 0.76, s * 0.18))
    return _stroke_icon(draw, size)


def icon_network(size: int = 64) -> QIcon:
    def draw(p, s, c):
        p.drawEllipse(QRectF(s * 0.38, s * 0.38, s * 0.24, s * 0.24))
        p.drawEllipse(QRectF(s * 0.22, s * 0.22, s * 0.56, s * 0.56))
        p.drawEllipse(QRectF(s * 0.12, s * 0.12, s * 0.76, s * 0.76))
    return _stroke_icon(draw, size)


def icon_timer(size: int = 64) -> QIcon:
    def draw(p, s, c):
        p.drawEllipse(QRectF(s * 0.16, s * 0.16, s * 0.68, s * 0.68))
        p.drawLine(QPointF(s * 0.50, s * 0.50), QPointF(s * 0.50, s * 0.28))
        p.drawLine(QPointF(s * 0.50, s * 0.50), QPointF(s * 0.68, s * 0.50))
        p.drawLine(QPointF(s * 0.38, s * 0.12), QPointF(s * 0.62, s * 0.12))
    return _stroke_icon(draw, size)


def icon_game(size: int = 64) -> QIcon:
    def draw(p, s, c):
        p.drawRoundedRect(QRectF(s * 0.14, s * 0.32, s * 0.72, s * 0.36), 10, 10)
        p.drawLine(QPointF(s * 0.30, s * 0.42), QPointF(s * 0.30, s * 0.58))
        p.drawLine(QPointF(s * 0.22, s * 0.50), QPointF(s * 0.38, s * 0.50))
        p.setBrush(QBrush(c))
        p.drawEllipse(QRectF(s * 0.58, s * 0.42, s * 0.08, s * 0.08))
        p.drawEllipse(QRectF(s * 0.70, s * 0.52, s * 0.08, s * 0.08))
    return _stroke_icon(draw, size)


def icon_settings(size: int = 64) -> QIcon:
    def draw(p, s, c):
        p.drawEllipse(QRectF(s * 0.34, s * 0.34, s * 0.32, s * 0.32))
        p.drawEllipse(QRectF(s * 0.18, s * 0.18, s * 0.64, s * 0.64))
        for i in range(8):
            from math import cos, sin, radians
            a = radians(i * 45)
            p.drawLine(
                QPointF(s * 0.5 + cos(a) * s * 0.34, s * 0.5 + sin(a) * s * 0.34),
                QPointF(s * 0.5 + cos(a) * s * 0.44, s * 0.5 + sin(a) * s * 0.44),
            )
    return _stroke_icon(draw, size)


def icon_shield(size: int = 64) -> QIcon:
    def draw(p, s, c):
        path = QPainterPath()
        path.moveTo(s * 0.50, s * 0.12)
        path.lineTo(s * 0.80, s * 0.28)
        path.lineTo(s * 0.80, s * 0.52)
        path.quadTo(s * 0.80, s * 0.78, s * 0.50, s * 0.90)
        path.quadTo(s * 0.20, s * 0.78, s * 0.20, s * 0.52)
        path.lineTo(s * 0.20, s * 0.28)
        path.closeSubpath()
        p.drawPath(path)
    return _stroke_icon(draw, size)


NAV_ICONS = {
    "dashboard": icon_app,
    "system": icon_cpu,
    "gaming": icon_game,
    "connectivity": icon_network,
    "cooling": icon_fan,
    "network": icon_network,
    "dns": icon_shield,
    "usage": icon_download,
    "timer": icon_timer,
    "telegram": icon_network,
    "alerts": icon_temp,
    "logs": icon_disk,
    "settings": icon_settings,
}

METRIC_ICONS = {
    "cpu": icon_cpu,
    "ram": icon_ram,
    "gpu_util": icon_gpu,
    "gpu_mem": icon_gpu,
    "cpu_temp": icon_temp,
    "gpu_temp": icon_temp,
    "gpu_fan": icon_fan,
    "disk": icon_disk,
    "net_down": icon_download,
    "net_up": icon_upload,
    "local_ip": icon_network,
    "public_ip": icon_network,
    "uptime": icon_timer,
    "gpu_name": icon_gpu,
    "timer": icon_timer,
    "game_mode": icon_game,
}


def save_app_icon_png(path: str, size: int = 256) -> str:
    """Export app icon PNG for packaging."""
    ic = icon_app(size)
    pm = ic.pixmap(size, size)
    pm.save(path, "PNG")
    return path
