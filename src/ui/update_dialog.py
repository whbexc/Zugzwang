"""
ZUGZWANG - Update Notification Dialog
macOS-style UI for version alerts and download progress.
"""

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, 
    QFrame, QPushButton, QProgressBar
)
from qfluentwidgets import (
    FluentIcon, IconWidget, InfoBar
)
from .theme import Theme
from ..core.config import APP_VERSION

class UpdateDialog(QDialog):
    """
    Premium update notification screen.
    """
    
    update_started = Signal(str) # download_url

    def __init__(self, new_version: str, download_url: str, parent=None):
        super().__init__(parent)
        self.new_version = new_version
        self.download_url = download_url
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._drag_pos = None
        
        self._build_ui()
        
    def _build_ui(self):
        self.setFixedSize(440, 320)
        
        self.container = QFrame(self)
        self.container.setGeometry(0, 0, 440, 320)
        self.container.setObjectName("MainContainer")
        self.container.setStyleSheet("""
            QFrame#MainContainer {
                background: #1C1C1E;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 20px;
            }
        """)
        
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)
        
        # Header
        header = QHBoxLayout()
        header.setSpacing(16)
        
        icon = IconWidget(FluentIcon.UPDATE)  # Or CLOUD_DOWNLOAD
        icon.setFixedSize(48, 48)
        icon.setStyleSheet("color: #0A84FF;")
        header.addWidget(icon)
        
        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        
        title = QLabel("Software Update")
        title.setStyleSheet("""
            color: white; 
            font-family: "-apple-system", "PT Root UI", sans-serif; 
            font-size: 20px; 
            font-weight: 700;
        """)
        title_layout.addWidget(title)
        
        ver_label = QLabel(f"Version {self.new_version} is available")
        ver_label.setStyleSheet("""
            color: #8E8E93; 
            font-family: "-apple-system", "PT Root UI", sans-serif; 
            font-size: 13px;
        """)
        title_layout.addWidget(ver_label)
        header.addLayout(title_layout)
        header.addStretch()
        
        layout.addLayout(header)
        
        # Description
        desc = QLabel(
            f"A new version of ZUGZWANG is ready to install. "
            f"You are currently using v{APP_VERSION}."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("""
            color: #D1D1D6; 
            font-family: "-apple-system", "PT Root UI", sans-serif; 
            font-size: 14px; 
            line-height: 1.4;
        """)
        layout.addWidget(desc)
        
        layout.addStretch()
        
        # Progress Bar (Hidden initially)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background: #2C2C2E;
                border: none;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background: #0A84FF;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("")
        self.status_label.setVisible(False)
        self.status_label.setStyleSheet("color: #8E8E93; font-size: 11px;")
        layout.addWidget(self.status_label)
        
        # Action Buttons
        self.btn_layout = QHBoxLayout()
        self.btn_layout.setSpacing(12)
        
        self.later_btn = QPushButton("Later")
        self.later_btn.setFixedSize(120, 40)
        self.later_btn.setCursor(Qt.PointingHandCursor)
        self.later_btn.setStyleSheet("""
            QPushButton {
                background: #2C2C2E;
                border: 1px solid #3A3A3C;
                border-radius: 10px;
                color: white;
                font-family: "-apple-system", sans-serif;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover { background: #3A3A3C; }
        """)
        self.later_btn.clicked.connect(self.reject)
        
        self.update_btn = QPushButton("Update Now")
        self.update_btn.setFixedSize(140, 40)
        self.update_btn.setCursor(Qt.PointingHandCursor)
        self.update_btn.setStyleSheet("""
            QPushButton {
                background: #0A84FF;
                color: white;
                border: none;
                border-radius: 10px;
                font-family: "-apple-system", sans-serif;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover { background: #409CFF; }
        """)
        self.update_btn.clicked.connect(self._start_update)
        
        self.btn_layout.addStretch()
        self.btn_layout.addWidget(self.later_btn)
        self.btn_layout.addWidget(self.update_btn)
        
        layout.addLayout(self.btn_layout)

    def _start_update(self):
        self.update_btn.setEnabled(False)
        self.later_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setVisible(True)
        self.status_label.setText("Starting download...")
        self.update_started.emit(self.download_url)

    def set_progress(self, val: int):
        self.progress_bar.setValue(val)
        self.status_label.setText(f"Downloading update... {val}%")

    def set_error(self, msg: str):
        self.status_label.setText(f"Error: {msg}")
        self.status_label.setStyleSheet("color: #FF453A; font-size: 11px;")
        self.update_btn.setEnabled(True)
        self.later_btn.setEnabled(True)
        InfoBar.error("Update Failed", msg, duration=5000, parent=self)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()
