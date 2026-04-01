"""
ZUGZWANG - Keyboard Shortcut Help Dialog
Displays all global shortcuts in a premium macOS-style modal.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QPushButton, QVBoxLayout, QWidget, QScrollArea
)


_SHORTCUTS = {
    "Navigation": [
        ("Ctrl+1", "Dashboard"),
        ("Ctrl+2", "Search"),
        ("Ctrl+3", "Statistics"),
        ("Ctrl+4", "Monitor"),
        ("Ctrl+5", "Send Messages"),
        ("Ctrl+6", "Settings"),
        ("Ctrl+,", "Settings (quick)"),
    ],
    "Actions": [
        ("Ctrl+N", "New Search (clear form)"),
        ("Ctrl+E", "Export results"),
        ("Ctrl+R", "Re-run last search"),
        ("Esc", "Stop active job"),
    ],
    "Search": [
        ("Ctrl+F", "Focus search bar"),
        ("?", "Show this help dialog"),
    ],
}


class ShortcutHelpDialog(QDialog):
    """Premium macOS-style keyboard shortcuts help modal."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(480)
        self._drag_pos = None

        container = QFrame(self)
        container.setObjectName("ShortcutContainer")
        container.setStyleSheet("""
            QFrame#ShortcutContainer {
                background: #1C1C1E;
                border: 1px solid #3A3A3C;
                border-radius: 16px;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 28, 28, 24)
        layout.setSpacing(0)

        # Title
        title = QLabel("Keyboard Shortcuts")
        title.setStyleSheet(
            "color: #FFFFFF; font-family: 'PT Root UI', sans-serif; "
            "font-size: 22px; font-weight: 700; background: transparent; border: none;"
        )
        layout.addWidget(title)
        layout.addSpacing(20)

        # Sections
        for idx, (section, items) in enumerate(_SHORTCUTS.items()):
            if idx > 0:
                div = QFrame()
                div.setFixedHeight(1)
                div.setStyleSheet("background: #3A3A3C; border: none;")
                layout.addWidget(div)
                layout.addSpacing(14)

            sec_lbl = QLabel(section.upper())
            sec_lbl.setStyleSheet(
                "color: #636366; font-family: 'PT Root UI', sans-serif; "
                "font-size: 10px; font-weight: 600; letter-spacing: 1.5px; "
                "background: transparent; border: none;"
            )
            layout.addWidget(sec_lbl)
            layout.addSpacing(8)

            grid = QGridLayout()
            grid.setSpacing(8)
            grid.setColumnStretch(2, 1)
            for row_i, (key, desc) in enumerate(items):
                key_pill = QLabel(key)
                key_pill.setFixedHeight(24)
                key_pill.setStyleSheet("""
                    QLabel {
                        background: #2C2C2E; border-radius: 6px;
                        color: #0A84FF; font-family: 'SF Mono', 'Menlo', monospace;
                        font-size: 12px; font-weight: 600;
                        padding: 0 8px;
                    }
                """)
                key_pill.setAlignment(Qt.AlignCenter)
                desc_lbl = QLabel(desc)
                desc_lbl.setStyleSheet(
                    "color: #AEAEB2; font-family: 'PT Root UI', sans-serif; "
                    "font-size: 13px; background: transparent; border: none;"
                )
                grid.addWidget(key_pill, row_i, 0, Qt.AlignLeft)
                grid.addWidget(desc_lbl, row_i, 1, Qt.AlignLeft)
            layout.addLayout(grid)
            layout.addSpacing(14)

        # Close button
        close_btn = QPushButton("CLOSE")
        close_btn.setFixedHeight(36)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: #2C2C2E; border: 1px solid #3A3A3C;
                border-radius: 8px; color: #AEAEB2;
                font-family: 'PT Root UI', sans-serif;
                font-size: 13px; font-weight: 600;
            }
            QPushButton:hover { background: #3A3A3C; color: #FFFFFF; }
        """)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self.adjustSize()

        if parent:
            center = parent.geometry().center()
            self.move(center.x() - self.width() // 2, center.y() - self.height() // 2)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.accept()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()
