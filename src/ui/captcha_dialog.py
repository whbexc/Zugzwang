"""
ZUGZWANG - CAPTCHA HITL Bridge
Remote Interaction Dialog for Headless Sessions.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QScrollArea, QFrame, QLineEdit, QPushButton
)
from PySide6.QtCore import Qt, Signal, QPoint, QSize
from PySide6.QtGui import QPixmap, QImage, QMouseEvent
from qfluentwidgets import (
    PrimaryPushButton, PushButton, SubtitleLabel, 
    CaptionLabel, FluentIcon, ToolButton, StrongBodyLabel
)
from .theme import Theme
from ..core.events import event_bus

class CaptchaDialog(QDialog):
    """
    Interaction bridge for headless CAPTCHAs.
    Displays a screenshot and captures user interactions.
    """
    
    def __init__(self, job_id: str, parent=None):
        print(f"[DEBUG] Initializing CaptchaDialog for job {job_id}")
        super().__init__(parent)
        self.job_id = job_id
        self._image_data = None
        self._original_size = QSize(0, 0)
        
        self.setWindowFlags(Qt.Window | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle("Security Check")
        self.resize(1000, 800)
        self.setStyleSheet(f"background-color: {Theme.BG_ZINC}; color: {Theme.TEXT_PRIMARY};")
        
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)
        
        # Header
        header = QVBoxLayout()
        title = SubtitleLabel("Bot Detection Triggered")
        title.setStyleSheet(f"color: {Theme.ACCENT_BLUE}; font-weight: 700;")
        desc = CaptionLabel("A security check was encountered in the headless session. Solve it below to continue.")
        header.addWidget(title)
        header.addWidget(desc)
        layout.addLayout(header)
        
        # Remote View
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setStyleSheet("background-color: #000; border-radius: 8px;")
        
        self._view = QLabel()
        self._view.setAlignment(Qt.AlignCenter)
        self._view.setCursor(Qt.CrossCursor)
        self._view.mousePressEvent = self._on_image_clicked
        
        self._scroll.setWidget(self._view)
        layout.addWidget(self._scroll, 1)
        
        # Interaction Row
        footer = QHBoxLayout()
        
        self._input = QLineEdit()
        self._input.setPlaceholderText("Type text here if required...")
        self._input.setFixedHeight(40)
        self._input.setStyleSheet(Theme.line_edit())
        self._input.returnPressed.connect(self._send_text)
        
        self._btn_send = ToolButton(FluentIcon.SEND, self)
        self._btn_send.clicked.connect(self._send_text)
        
        self._btn_refresh = PushButton("Refresh View")
        self._btn_refresh.clicked.connect(self._request_refresh)
        
        self._btn_done = PrimaryPushButton("I've Solved It")
        self._btn_done.clicked.connect(self.accept)
        
        footer.addWidget(self._input, 1)
        footer.addWidget(self._btn_send)
        footer.addSpacing(20)
        footer.addWidget(self._btn_refresh)
        footer.addWidget(self._btn_done)
        
        layout.addLayout(footer)

    def update_screenshot(self, image_bytes: bytes):
        """Updates the remote preview with new frame data."""
        self._image_data = image_bytes
        img = QImage.fromData(image_bytes)
        if img.isNull(): return
        
        self._original_size = img.size()
        pix = QPixmap.fromImage(img)
        
        # Scale to fit while maintaining aspect ratio
        max_w = self._scroll.width() - 40
        max_h = 1200 # Allow vertical scrolling
        scaled = pix.scaled(max_w, max_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._view.setPixmap(scaled)

    def _on_image_clicked(self, event: QMouseEvent):
        if not self._view.pixmap() or self._original_size.isEmpty():
            return
            
        # Calculate coordinate mapping
        pix_rect = self._view.pixmap().rect()
        pix_rect.moveCenter(self._view.rect().center())
        
        if not pix_rect.contains(event.pos()):
            return
            
        # Relative to pixmap
        rel_x = event.pos().x() - pix_rect.x()
        rel_y = event.pos().y() - pix_rect.y()
        
        # Map back to original browser coordinates
        mapped_x = int(rel_x * self._original_size.width() / pix_rect.width())
        mapped_y = int(rel_y * self._original_size.height() / pix_rect.height())
        
        event_bus.emit(
            event_bus.CAPTCHA_INTERACTION,
            job_id=self.job_id,
            type="click",
            x=mapped_x,
            y=mapped_y
        )

    def _send_text(self):
        text = self._input.text().strip()
        if not text: return
        
        event_bus.emit(
            event_bus.CAPTCHA_INTERACTION,
            job_id=self.job_id,
            type="type",
            text=text
        )
        self._input.clear()

    def _request_refresh(self):
        event_bus.emit(
            event_bus.CAPTCHA_INTERACTION,
            job_id=self.job_id,
            type="refresh"
        )
