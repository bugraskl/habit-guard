"""The screen curtain: a see-through layer over every monitor until the hand comes down.

It never takes input or focus: clicks and keystrokes go straight through to the
windows underneath, so the curtain can never lock you out. Two looks:

* **dim**: the screen darkens, more with each alarm level, with the message in
  the middle;
* **flash**: a red frame around each screen pulses, and the message sits at the
  top.
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen, QScreen
from PySide6.QtWidgets import QWidget

#: Darkness (0-255) of the dim curtain for alarm levels 1 to 3.
DIM_ALPHA = {1: 110, 2: 165, 3: 215}
FADE_MS = 160
FRAME_PX = 18


class CurtainWindow(QWidget):
    """One monitor's curtain."""

    def __init__(self, screen: QScreen):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setScreen(screen)
        self.setGeometry(screen.geometry())
        self._style = "dim"
        self._level = 1
        self._message = ""
        self._pulse = 1.0
        self._fade = QVariantAnimation(self)
        self._fade.setDuration(FADE_MS)
        self._fade.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._fade.valueChanged.connect(lambda v: self.setWindowOpacity(float(v)))
        self._fade.finished.connect(self._after_fade)
        self._pulser = QVariantAnimation(self)
        self._pulser.setStartValue(0.25)
        self._pulser.setEndValue(1.0)
        self._pulser.setDuration(450)
        self._pulser.setLoopCount(-1)
        self._pulser.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._pulser.valueChanged.connect(self._on_pulse)
        self._closing = False

    def present(self, style: str, level: int, message: str) -> None:
        self._style, self._level, self._message = style, level, message
        self._closing = False
        if style == "flash":
            self._pulser.start()
        else:
            self._pulser.stop()
            self._pulse = 1.0
        self.update()
        if not self.isVisible():
            self.setWindowOpacity(0.0)
            self.show()
        self._animate(self.windowOpacity(), 1.0)

    def dismiss(self) -> None:
        if not self.isVisible() or self._closing:
            return
        self._closing = True
        self._animate(self.windowOpacity(), 0.0)

    def _animate(self, start: float, end: float) -> None:
        self._fade.stop()
        self._fade.setStartValue(start)
        self._fade.setEndValue(end)
        self._fade.start()

    def _after_fade(self) -> None:
        if self._closing:
            self._pulser.stop()
            self.hide()
            self._closing = False

    def _on_pulse(self, value: object) -> None:
        self._pulse = float(value)  # type: ignore[arg-type]
        self.update()

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        font = QFont(self.font())
        if self._style == "flash":
            alpha = int(60 + 195 * self._pulse)
            pen = QPen(QColor(235, 40, 40, alpha))
            pen.setWidth(FRAME_PX * (1 + (self._level - 1) // 2))
            painter.setPen(pen)
            painter.drawRect(
                rect.adjusted(FRAME_PX // 2, FRAME_PX // 2, -FRAME_PX // 2, -FRAME_PX // 2)
            )
            font.setPointSize(max(18, rect.height() // 28))
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QColor(255, 255, 255, 235))
            top = QRectF(0, rect.height() * 0.06, rect.width(), rect.height() * 0.12)
            painter.fillRect(
                QRectF(rect.width() * 0.25, top.top(), rect.width() * 0.5, top.height()),
                QColor(200, 30, 30, 200),
            )
            painter.drawText(top, int(Qt.AlignmentFlag.AlignCenter), self._message)
        else:
            painter.fillRect(rect, QColor(0, 0, 0, DIM_ALPHA.get(self._level, 215)))
            font.setPointSize(max(28, rect.height() // 14))
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QColor(255, 255, 255, 245))
            painter.drawText(QRectF(rect), int(Qt.AlignmentFlag.AlignCenter), self._message)


class Curtain:
    """All curtain windows, one per screen."""

    def __init__(self) -> None:
        self._windows: list[CurtainWindow] = []

    def show(self, style: str, level: int, message: str) -> None:
        screens = QGuiApplication.screens()
        if len(self._windows) != len(screens) or any(
            w.screen() is not s for w, s in zip(self._windows, screens, strict=False)
        ):
            self.close()
            self._windows = [CurtainWindow(s) for s in screens]
        for window in self._windows:
            window.present(style, level, message)

    def hide(self) -> None:
        for window in self._windows:
            window.dismiss()

    def close(self) -> None:
        for window in self._windows:
            window.hide()
            window.deleteLater()
        self._windows = []
