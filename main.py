"""
ZUGZWANG - Application Entry Point

Improvements over v1:
- Global Exception Handler (shows GUI error instead of silent crash in .exe)
- High DPI fractional scaling fixes
- Applies global application icon (assets/icon.ico)
- Normalizes base widget style to 'Fusion' for consistent cross-platform theming
"""

from __future__ import annotations
import sys
import os
import traceback
from pathlib import Path


def _global_exception_handler(exc_type, exc_value, exc_traceback):
    """
    Catch any unhandled exception and show it in a premium macOS-style dialog.
    Ensures that even startup crashes look like 'ZUGZWANG'.
    """
    if issubclass(exc_type, KeyboardInterrupt) or issubclass(exc_type, SystemExit):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QTextEdit
    from PySide6.QtCore import Qt
    
    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    print(f"CRITICAL UNHANDLED ERROR:\n{error_msg}", file=sys.stderr)

    class ZugzwangErrorDialog(QDialog):
        def __init__(self, title: str, message: str, details: str):
            super().__init__()
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
            self.setAttribute(Qt.WA_TranslucentBackground)
            self.setFixedSize(520, 320)
            self._drag_pos = None
            
            # Container
            self.container = QFrame(self)
            self.container.setObjectName("DialogContainer")
            self.container.setFixedSize(520, 320)
            self.container.setStyleSheet("""
                QFrame#DialogContainer {
                    background-color: #1E1E1E;
                    border: 1px solid #323232;
                    border-radius: 20px;
                }
            """)
            
            layout = QVBoxLayout(self.container)
            layout.setContentsMargins(40, 42, 40, 32)
            layout.setSpacing(14)
            
            # Header
            self.title_label = QLabel(title.upper())
            self.title_label.setAlignment(Qt.AlignCenter)
            self.title_label.setStyleSheet("color: #FFFFFF; font-family: 'SF Pro Display', 'Segoe UI'; font-size: 24px; font-weight: 800; background: transparent;")
            layout.addWidget(self.title_label)
            
            # Message
            self.message_label = QLabel(message)
            self.message_label.setAlignment(Qt.AlignCenter)
            self.message_label.setWordWrap(True)
            self.message_label.setStyleSheet("color: #D1D1D6; font-family: 'SF Pro Text', 'Segoe UI'; font-size: 15px; font-weight: 400; background: transparent;")
            layout.addWidget(self.message_label)

            # Details (Optional, collapsed by default)
            self.details_area = QTextEdit()
            self.details_area.setPlainText(details)
            self.details_area.setReadOnly(True)
            self.details_area.setVisible(False)
            self.details_area.setStyleSheet("""
                QTextEdit {
                    background: #111111;
                    color: #FF453A;
                    border: 1px solid #323232;
                    border-radius: 8px;
                    font-family: 'SF Mono', 'Menlo', monospace;
                    font-size: 11px;
                }
            """)
            layout.addWidget(self.details_area)
            
            layout.addStretch()
            
            # Buttons
            btn_row = QHBoxLayout()
            btn_row.setSpacing(12)
            
            self.ok_btn = QPushButton("OK")
            self.ok_btn.setFixedSize(140, 44)
            self.ok_btn.setCursor(Qt.PointingHandCursor)
            self.ok_btn.setStyleSheet("""
                QPushButton {
                    background: #FF453A;
                    border: none;
                    border-radius: 12px;
                    color: #FFFFFF;
                    font-family: 'SF Pro Text';
                    font-size: 15px;
                    font-weight: 700;
                }
                QPushButton:hover { background: #FF5C52; }
            """)
            self.ok_btn.clicked.connect(self.accept)
            
            self.details_btn = QPushButton("Show Details")
            self.details_btn.setFixedSize(140, 44)
            self.details_btn.setCursor(Qt.PointingHandCursor)
            self.details_btn.setStyleSheet("""
                QPushButton {
                    background: #2C2C2E;
                    border: 1px solid #3A3A3C;
                    border-radius: 12px;
                    color: #FFFFFF;
                    font-family: 'SF Pro Text';
                    font-size: 15px;
                    font-weight: 500;
                }
                QPushButton:hover { background: #3A3A3C; }
            """)
            self.details_btn.clicked.connect(self._toggle_details)
            
            btn_row.addStretch()
            btn_row.addWidget(self.ok_btn)
            btn_row.addWidget(self.details_btn)
            btn_row.addStretch()
            layout.addLayout(btn_row)

        def _toggle_details(self):
            visible = not self.details_area.isVisible()
            self.details_area.setVisible(visible)
            if visible:
                self.setFixedSize(520, 520)
                self.container.setFixedSize(520, 520)
                self.details_btn.setText("Hide Details")
            else:
                self.setFixedSize(520, 320)
                self.container.setFixedSize(520, 320)
                self.details_btn.setText("Show Details")

        def mousePressEvent(self, event):
            if event.button() == Qt.LeftButton:
                self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
                event.accept()

        def mouseMoveEvent(self, event):
            if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
                self.move(event.globalPos() - self._drag_pos)
                event.accept()

    dialog = ZugzwangErrorDialog("Fatal Error", str(exc_value), error_msg)
    dialog.exec()


def main():
    # Install global crash reporter
    sys.excepthook = _global_exception_handler

    # High DPI scaling environment variables must be set before QApplication
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
    
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont, QIcon

    # Allow fractional scaling (125%, 150%) to be passed through without rounding to integers
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)
    
    # Normalizes underlying geometries across OS (crucial for custom stylesheets)
    app.setStyle("Fusion")
    
    app.setApplicationName("ZUGZWANG")
    app.setApplicationVersion("1.0.1")
    app.setOrganizationName("ZUGZWANG")

    # Load and register PT Root UI font family
    from PySide6.QtGui import QFontDatabase
    
    # Handle PyInstaller bundle path resolution
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base_dir = Path(sys._MEIPASS)
    else:
        base_dir = Path(__file__).parent
        
    _fonts_dir = base_dir / "src" / "ui" / "assets" / "fonts"
    for _ttf in _fonts_dir.glob("pt-root-ui*.ttf"):
        QFontDatabase.addApplicationFont(str(_ttf))

    # Default font globally — PT Root UI Regular 10pt
    font = QFont("PT Root UI", 10)
    font.setWeight(QFont.Weight.Normal)
    app.setFont(font)

    # Set icon globally (used for taskbar, window title, and all dialogs)
    icon_path = base_dir / "assets" / "icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    from src.ui.main_window import MainWindow
    from src.core.config import config_manager
    from src.ui.security_overlay import SecurityOverlay
    from src.core.security import LicenseManager
    from src.ui.activation_dialog import ActivationDialog

    # 1. License Check (Smooth Onboarding)
    # The app opens freely so users can see their data. Activation is checked at search time.

    # 2. Check for Security PIN-lock (Local Access Pack)
    s = config_manager.settings
    if s.security_enabled and s.security_pin:
        overlay = SecurityOverlay(s.security_pin)
        if not overlay.exec():
            sys.exit(0)

    window = MainWindow()
    window.showMaximized()

    # If the app exits event loop cleanly, exit process cleanly
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
