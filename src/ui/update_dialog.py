"""
ZUGZWANG - Update Notification Dialog
macOS-style UI for version alerts and download progress.
"""

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, 
    QFrame, QPushButton, QProgressBar, QSizePolicy
)
from qfluentwidgets import InfoBar
from ..core.config import APP_BUILD, APP_VERSION

class UpdateDialog(QDialog):
    """
    Premium Apple-style update notification screen.
    """
    
    update_started = Signal(str) # download_url

    def __init__(self, new_version: str, download_url: str, parent=None):
        super().__init__(parent)
        self.new_version = new_version
        self.download_url = download_url
        
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowSystemMenuHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(340, 210)
        
        self._build_ui()
        
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        bg = QWidget()
        bg.setStyleSheet("QWidget { background: rgba(40, 40, 40, 0.95); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 14px; }")
        bg_layout = QVBoxLayout(bg)
        bg_layout.setContentsMargins(24, 24, 24, 24)
        bg_layout.setSpacing(8)

        # Title
        title_lbl = QLabel("Software Update")
        title_lbl.setStyleSheet("color: #FFFFFF; font-family: 'SF Pro Text', 'PT Root UI', sans-serif; font-size: 16px; font-weight: 600; background: transparent; border: none;")
        title_lbl.setAlignment(Qt.AlignCenter)
        bg_layout.addWidget(title_lbl)
        
        # Subtitle
        ver_label = QLabel(f"Version {self.new_version} is available")
        ver_label.setStyleSheet("color: #8E8E93; font-family: 'SF Pro Text', 'PT Root UI', sans-serif; font-size: 12px; font-weight: 500; background: transparent; border: none;")
        ver_label.setAlignment(Qt.AlignCenter)
        bg_layout.addWidget(ver_label)
        
        bg_layout.addSpacing(4)

        # Description
        desc_text = f"A new version of ZUGZWANG is ready to install.\nYou are currently using v{APP_VERSION} (build {APP_BUILD})."
        desc_lbl = QLabel(desc_text)
        desc_lbl.setWordWrap(True)
        desc_lbl.setAlignment(Qt.AlignCenter)
        desc_lbl.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-family: 'SF Pro Text', 'PT Root UI', sans-serif; font-size: 13px; font-weight: 400; background: transparent; border: none; line-height: 1.4;")
        bg_layout.addWidget(desc_lbl, 1)

        # Progress Bar & Status (Hidden initially)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar { background: rgba(255, 255, 255, 0.1); border: none; border-radius: 3px; }
            QProgressBar::chunk { background: #0A84FF; border-radius: 3px; }
        """)
        bg_layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("")
        self.status_label.setVisible(False)
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #8E8E93; font-family: 'SF Pro Text', 'PT Root UI', sans-serif; font-size: 11px; background: transparent; border: none;")
        bg_layout.addWidget(self.status_label)

        # Action Buttons
        self.btn_layout = QHBoxLayout()
        self.btn_layout.setContentsMargins(0, 10, 0, 0)
        self.btn_layout.setSpacing(12)

        self.later_btn = QPushButton("Later")
        self.later_btn.setCursor(Qt.PointingHandCursor)
        self.later_btn.setFixedHeight(32)
        self.later_btn.setStyleSheet("QPushButton { background: rgba(255, 255, 255, 0.1); color: white; border: none; border-radius: 6px; font-family: 'SF Pro Text', 'PT Root UI', sans-serif; font-size: 13px; font-weight: 500; } QPushButton:hover { background: rgba(255, 255, 255, 0.15); }")
        self.later_btn.clicked.connect(self.reject)
        
        self.update_btn = QPushButton("Update Now")
        self.update_btn.setCursor(Qt.PointingHandCursor)
        self.update_btn.setFixedHeight(32)
        self.update_btn.setStyleSheet("QPushButton { background: #0A84FF; color: white; border: none; border-radius: 6px; font-family: 'SF Pro Text', 'PT Root UI', sans-serif; font-size: 13px; font-weight: 600; } QPushButton:hover { background: rgba(10, 132, 255, 0.8); }")
        self.update_btn.clicked.connect(self._start_update)

        self.btn_layout.addWidget(self.later_btn)
        self.btn_layout.addWidget(self.update_btn)
        
        bg_layout.addLayout(self.btn_layout)
        layout.addWidget(bg)

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
        self.status_label.setStyleSheet("color: #FF453A; font-family: 'SF Pro Text', 'PT Root UI', sans-serif; font-size: 11px; background: transparent; border: none;")
        self.update_btn.setEnabled(True)
        self.later_btn.setEnabled(True)
        InfoBar.error("Update Failed", msg, duration=5000, parent=self)
