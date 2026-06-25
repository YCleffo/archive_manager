from __future__ import annotations
from typing import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap


class IconFactory:
    def __init__(self, color: str = "#425466") -> None:
        self.color = color
        self._cache: dict[tuple[str, int, str], QIcon] = {}

    def icon(self, name: str, size: int = 20, color: str | None = None) -> QIcon:
        icon_color = color or self.color
        key = (name, size, icon_color)
        if key not in self._cache:
            self._cache[key] = self._build_icon(name, size, icon_color)
        return self._cache[key]

    def _build_icon(self, name: str, size: int, color: str) -> QIcon:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor(color), max(1.6, size / 12))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        scale = size / 20

        def p(x: float, y: float) -> QPointF:
            return QPointF(x * scale, y * scale)

        def r(x: float, y: float, w: float, h: float) -> QRectF:
            return QRectF(x * scale, y * scale, w * scale, h * scale)

        if name == "back":
            painter.drawLine(p(12.5, 5), p(7, 10))
            painter.drawLine(p(7, 10), p(12.5, 15))
            painter.drawLine(p(7.5, 10), p(16, 10))
        elif name == "forward":
            painter.drawLine(p(7.5, 5), p(13, 10))
            painter.drawLine(p(13, 10), p(7.5, 15))
            painter.drawLine(p(4, 10), p(12.5, 10))
        elif name == "up":
            painter.drawLine(p(10, 4.5), p(5, 10))
            painter.drawLine(p(10, 4.5), p(15, 10))
            painter.drawLine(p(10, 5), p(10, 16))
        elif name == "home":
            painter.drawPolyline([p(4, 10), p(10, 4.5), p(16, 10)])
            painter.drawRoundedRect(r(6, 9, 8, 7), 1.5 * scale, 1.5 * scale)
        elif name == "refresh":
            painter.drawArc(r(4, 4, 12, 12), 35 * 16, 280 * 16)
            painter.drawLine(p(14.5, 4.7), p(16.2, 8.2))
            painter.drawLine(p(14.5, 4.7), p(11.2, 5.8))
        elif name == "undo":
            painter.drawLine(p(8, 6), p(4.5, 9.5))
            painter.drawLine(p(8, 13), p(4.5, 9.5))
            painter.drawPath(self._arc_path(p))
        elif name == "folder":
            self._draw_folder(painter, r, p, plus=False)
        elif name == "new-folder":
            self._draw_folder(painter, r, p, plus=True)
        elif name == "file":
            painter.drawRoundedRect(r(5, 3.5, 10, 13), 1.5 * scale, 1.5 * scale)
            painter.drawLine(p(11.5, 3.8), p(15, 7.3))
            painter.drawLine(p(11.7, 3.8), p(11.7, 7.2))
            painter.drawLine(p(11.7, 7.2), p(15, 7.2))
        elif name == "rename":
            painter.drawRoundedRect(r(4, 4, 10, 12), 1.4 * scale, 1.4 * scale)
            painter.drawLine(p(7, 8), p(11, 8))
            painter.drawLine(p(7, 11), p(10, 11))
            painter.drawLine(p(11.5, 14.5), p(16.5, 9.5))
            painter.drawLine(p(15.2, 8.2), p(16.8, 9.8))
        elif name == "delete":
            painter.drawLine(p(6, 7), p(14, 7))
            painter.drawLine(p(8, 7), p(8.6, 16))
            painter.drawLine(p(12, 7), p(11.4, 16))
            painter.drawRoundedRect(r(7, 7, 6, 9), 1.2 * scale, 1.2 * scale)
            painter.drawLine(p(8.5, 5), p(11.5, 5))
        elif name == "copy":
            painter.drawRoundedRect(r(7, 5, 8, 10), 1.4 * scale, 1.4 * scale)
            painter.drawRoundedRect(r(4.5, 8, 8, 8), 1.4 * scale, 1.4 * scale)
        elif name == "move":
            painter.drawLine(p(4, 10), p(15, 10))
            painter.drawLine(p(11, 6), p(15, 10))
            painter.drawLine(p(11, 14), p(15, 10))
            painter.drawLine(p(6, 6), p(6, 14))
        elif name == "zip":
            painter.drawRoundedRect(r(5, 3.5, 10, 13), 1.5 * scale, 1.5 * scale)
            painter.drawLine(p(10, 4.5), p(10, 15))
            for y in (6, 8.5, 11, 13.5):
                painter.drawPoint(p(11.7, y))
        elif name == "extract":
            painter.drawLine(p(10, 4), p(10, 12))
            painter.drawLine(p(6.5, 9), p(10, 12.5))
            painter.drawLine(p(13.5, 9), p(10, 12.5))
            painter.drawRoundedRect(r(5, 13.5, 10, 2.5), 1.1 * scale, 1.1 * scale)
        elif name == "size":
            painter.drawRoundedRect(r(4.5, 4.5, 11, 11), 1.4 * scale, 1.4 * scale)
            painter.drawLine(p(7, 13), p(13, 7))
            painter.drawLine(p(9.7, 7), p(13, 7))
            painter.drawLine(p(13, 10.3), p(13, 7))
            painter.drawLine(p(7, 13), p(7, 9.7))
            painter.drawLine(p(7, 13), p(10.3, 13))
        elif name == "search":
            painter.drawEllipse(r(4.5, 4.5, 8, 8))
            painter.drawLine(p(11.3, 11.3), p(16, 16))
        elif name == "stop":
            painter.drawLine(p(6, 6), p(14, 14))
            painter.drawLine(p(14, 6), p(6, 14))
        elif name == "reset":
            eraser = QPainterPath()
            eraser.moveTo(p(4.2, 13.4))
            eraser.lineTo(p(11.3, 6.3))
            eraser.lineTo(p(15.8, 10.8))
            eraser.lineTo(p(9.1, 17.2))
            eraser.lineTo(p(6.0, 17.2))
            eraser.lineTo(p(4.2, 15.4))
            eraser.closeSubpath()
            painter.drawPath(eraser)
            painter.drawLine(p(8.3, 9.3), p(12.8, 13.8))
            painter.drawLine(p(10.8, 17.2), p(16.2, 17.2))
        elif name == "more":
            painter.setBrush(QColor(color))
            for x in (6.2, 10, 13.8):
                painter.drawEllipse(p(x, 10), 1.1 * scale, 1.1 * scale)
        elif name == "open":
            painter.drawRoundedRect(r(4.5, 5, 9, 10), 1.5 * scale, 1.5 * scale)
            painter.drawLine(p(10, 10), p(16, 5))
            painter.drawLine(p(12.5, 5), p(16, 5))
            painter.drawLine(p(16, 5), p(16, 8.5))
        elif name == "preview":
            path = QPainterPath()
            path.moveTo(p(3.5, 10))
            path.cubicTo(p(6, 6), p(14, 6), p(16.5, 10))
            path.cubicTo(p(14, 14), p(6, 14), p(3.5, 10))
            painter.drawPath(path)
            painter.drawEllipse(r(8, 8, 4, 4))
        elif name == "close":
            painter.drawLine(p(6, 6), p(14, 14))
            painter.drawLine(p(14, 6), p(6, 14))
        else:
            painter.drawEllipse(r(5, 5, 10, 10))

        painter.end()
        return QIcon(pixmap)

    def _arc_path(self, p: Callable[[float, float], QPointF]) -> QPainterPath:
        path = QPainterPath()
        path.moveTo(p(5, 9.5))
        path.cubicTo(p(8, 5.5), p(15.8, 6.5), p(15.8, 12))
        path.cubicTo(p(15.8, 15), p(13.4, 16.4), p(10.4, 16.4))
        return path

    def _draw_folder(
        self,
        painter: QPainter,
        r: Callable[[float, float, float, float], QRectF],
        p: Callable[[float, float], QPointF],
        plus: bool,
    ) -> None:
        path = QPainterPath()
        path.moveTo(p(3.5, 7.5))
        path.lineTo(p(7.5, 7.5))
        path.lineTo(p(8.8, 5.5))
        path.lineTo(p(16.5, 5.5))
        path.lineTo(p(16.5, 15))
        path.lineTo(p(3.5, 15))
        path.closeSubpath()
        painter.drawPath(path)
        if plus:
            painter.drawLine(p(10, 8.3), p(10, 12.4))
            painter.drawLine(p(8, 10.35), p(12, 10.35))
