"""
ZUGZWANG - Update Notification Dialog
macOS-style UI for version alerts and download progress.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QLabel, QProgressBar
from qfluentwidgets import InfoBar
from ..core.config import APP_BUILD, APP_VERSION
from .components import ZugzwangDialog

class UpdateDialog(ZugzwangDialog):
    """
    Premium Apple-style update notification screen using the new popup system.
    """
    
    update_started = Signal(str) # download_url

    def __init__(self, new_version: str, download_url: str, parent=None):
        self.new_version = new_version
        self.download_url = download_url
        
        title = "Software Update"
        desc = f"A new version of ZUGZWANG is ready to install.\nYou are currently using v{APP_VERSION} (build {APP_BUILD})."
        
        super().__init__(
            title=title,
            message=desc,
            parent=parent,
            confirm_text="Update Now",
            cancel_text="Later",
            single_button=False,
            destructive=False
        )
        
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint | Qt.WindowSystemMenuHint)
        
        # Adjust dimensions to accommodate the progress bar and extra label
        self.setFixedSize(340, 210)
        self.container.setFixedSize(340, 210)
        
        layout = self.container.layout()
        
        # Subtitle for version info (inserted just after the title at index 1)
        self.subtitle_label = QLabel(f"Version {self.new_version} is available")
        self.subtitle_label.setStyleSheet("color: #8E8E93; font-family: 'SF Pro Text', 'PT Root UI', sans-serif; font-size: 12px; font-weight: 500; background: transparent; border: none;")
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        layout.insertWidget(1, self.subtitle_label)
        
        # Add Progress Bar & Status (Hidden initially)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar { background: rgba(255, 255, 255, 0.1); border: none; border-radius: 3px; }
            QProgressBar::chunk { background: #0A84FF; border-radius: 3px; }
        """)
        
        self.status_label = QLabel("")
        self.status_label.setVisible(False)
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #8E8E93; font-family: 'SF Pro Text', 'PT Root UI', sans-serif; font-size: 11px; background: transparent; border: none;")
        
        # Insert them before the buttons layout (which is now at index 4 because we inserted the subtitle)
        # title(0), subtitle(1), message(2), [progress_bar(3)], [status_label(4)], btn_layout(5)
        layout.insertWidget(3, self.progress_bar)
        layout.insertWidget(4, self.status_label)
        
        # Re-wire OK button to start update instead of closing immediately
        self.ok_btn.clicked.disconnect()
        self.ok_btn.clicked.connect(self._start_update)

    def _start_update(self):
        self.ok_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
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
        self.ok_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)
        InfoBar.error("Update Failed", msg, duration=5000, parent=self)
