"""
ZUGZWANG - Toast Manager
Non-blocking macOS-style notification toasts, bottom-right corner.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QPropertyAnimation, QEasingCurve, QTimer, Qt, QRect, Signal
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget

# ── Toast type config ────────────────────────────────────────────────────────
_TYPE_COLORS = {
    "success": "#30D158",
    "info":    "#0A84FF",
    "warning": "#FF9F0A",
    "error":   "#FF453A",
}


class ToastWidget(QFrame):
    """Single toast card with left accent border and auto-dismiss."""
    dismissed = Signal()

    def __init__(self, title: str, subtitle: str, toast_type: str, duration: int, parent: QWidget):
        super().__init__(parent)
        self._duration = duration
        accent = _TYPE_COLORS.get(toast_type, "#0A84FF")

        self.setFixedWidth(300)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"""
            QFrame {{
                background: #2C2C2E;
                border: none;
                border-left: 3px solid {accent};
                border-radius: 10px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(3)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            "color: #FFFFFF; font-family: 'PT Root UI', sans-serif; "
            "font-size: 13px; font-weight: 600; background: transparent; border: none;"
        )
        title_lbl.setWordWrap(True)
        layout.addWidget(title_lbl)

        if subtitle:
            sub_lbl = QLabel(subtitle)
            sub_lbl.setStyleSheet(
                "color: #8E8E93; font-family: 'PT Root UI', sans-serif; "
                "font-size: 11px; background: transparent; border: none;"
            )
            sub_lbl.setWordWrap(True)
            layout.addWidget(sub_lbl)

        self.adjustSize()

        # Auto-dismiss
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(duration)
        self._timer.timeout.connect(self.dismissed.emit)
        self._timer.start()

    def mousePressEvent(self, event):
        self._timer.stop()
        self.dismissed.emit()
        super().mousePressEvent(event)


class ToastManager(QObject):
    """Manages a vertical stack of up to 4 toasts anchored to the bottom-right of parent window."""

    MAX_TOASTS = 4
    GAP = 8
    MARGIN = 20

    def __init__(self, parent_window: QWidget):
        super().__init__(parent_window)
        self._window = parent_window
        self._toasts: list[ToastWidget] = []

    # ── Public API ────────────────────────────────────────────────────────────

    def show(self, title: str, subtitle: str = "", toast_type: str = "info", duration: int = 4000) -> None:
        # Enforce max 4 toasts
        while len(self._toasts) >= self.MAX_TOASTS:
            self._remove_toast(self._toasts[0])

        toast = ToastWidget(title, subtitle, toast_type, duration, self._window)
        toast.dismissed.connect(lambda t=toast: self._remove_toast(t))
        toast.show()
        self._toasts.append(toast)
        self._reposition_all()
        self._slide_in(toast)

    # ── Private ───────────────────────────────────────────────────────────────

    def _remove_toast(self, toast: ToastWidget) -> None:
        if toast not in self._toasts:
            toast.deleteLater()
            return
        self._slide_out(toast)

    def _reposition_all(self) -> None:
        """Place toasts stacked from the bottom-right corner up."""
        win = self._window
        if not win:
            return
        x = win.width() - 300 - self.MARGIN
        y_bottom = win.height() - self.MARGIN
        for toast in reversed(self._toasts):
            h = max(toast.sizeHint().height(), 56)
            y = y_bottom - h
            toast.setGeometry(QRect(x, y, 300, h))
            y_bottom = y - self.GAP

    def _slide_in(self, toast: ToastWidget) -> None:
        win = self._window
        if not win:
            return
        target = toast.geometry()
        start = QRect(win.width(), target.y(), target.width(), target.height())
        toast.setGeometry(start)
        anim = QPropertyAnimation(toast, b"geometry", toast)
        anim.setDuration(250)
        anim.setStartValue(start)
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()

    def _slide_out(self, toast: ToastWidget) -> None:
        win = self._window
        if not win:
            return
        target_x = win.width() + 20
        current = toast.geometry()
        end = QRect(target_x, current.y(), current.width(), current.height())
        anim = QPropertyAnimation(toast, b"geometry", toast)
        anim.setDuration(200)
        anim.setStartValue(current)
        anim.setEndValue(end)
        anim.setEasingCurve(QEasingCurve.InCubic)
        if toast in self._toasts:
            self._toasts.remove(toast)
        anim.finished.connect(toast.deleteLater)
        anim.finished.connect(self._reposition_all)
        anim.start()
