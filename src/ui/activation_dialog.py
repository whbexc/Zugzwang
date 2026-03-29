"""
ZUGZWANG - Activation Dialog
Modern DRM screen to handle product key activation.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, 
    QLineEdit, QFrame, QGraphicsDropShadowEffect
)
from qfluentwidgets import (
    PushButton, PrimaryPushButton, TransparentPushButton, 
    FluentIcon, StrongBodyLabel, CaptionLabel, IconWidget,
    LineEdit, InfoBar, InfoBarPosition
)
from .theme import Theme
from ..core.security import LicenseManager

class ActivationDialog(QDialog):
    """
    Premium Activation screen.
    Shows the unique Machine ID and collects a license key.
    """
    
    activated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self._build_ui()
        
    def _build_ui(self):
        self.setFixedSize(440, 520)
        
        # Outer Shadow Container
        self.container = QFrame(self)
        self.container.setGeometry(10, 10, 420, 500)
        self.container.setObjectName("MainContainer")
        self.container.setStyleSheet(f"""
            QFrame#MainContainer {{
                background: #1C1C1E;
                border: 1px solid {Theme.BORDER_LIGHT};
                border-radius: 20px;
            }}
        """)
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setXOffset(0)
        shadow.setYOffset(10)
        shadow.setColor(Qt.black)
        self.container.setGraphicsEffect(shadow)
        
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(16)
        
        # Header
        header = QVBoxLayout()
        header.setAlignment(Qt.AlignCenter)
        header.setSpacing(8)
        
        icon = IconWidget(FluentIcon.FINGERPRINT)
        icon.setFixedSize(56, 56)
        icon.setStyleSheet(f"color: {Theme.ACCENT_BLUE};")
        header.addWidget(icon, 0, Qt.AlignCenter)
        
        title = StrongBodyLabel("Enter License Key")
        title.setStyleSheet("font-size: 22px; color: #FFFFFF;")
        header.addWidget(title, 0, Qt.AlignCenter)
        
        subtitle = CaptionLabel("Activation required to use ZUGZWANG")
        subtitle.setStyleSheet("color: #8E8E93;")
        header.addWidget(subtitle, 0, Qt.AlignCenter)
        
        layout.addLayout(header)
        layout.addSpacing(10)
        
        # Machine ID Section
        mid_layout = QVBoxLayout()
        mid_layout.setSpacing(4)
        mid_lbl = CaptionLabel("YOUR MACHINE ID")
        mid_lbl.setStyleSheet("color: #636366; font-weight: 800; font-size: 10px; letter-spacing: 0.5px;")
        mid_layout.addWidget(mid_lbl)
        
        self.mid_field = QLineEdit(LicenseManager.get_machine_id())
        self.mid_field.setReadOnly(True)
        self.mid_field.setFixedHeight(36)
        self.mid_field.setStyleSheet(f"""
            QLineEdit {{
                background: #2C2C2E;
                border: 1px solid rgba(255,255,255,0.05);
                border-radius: 8px;
                color: {Theme.ACCENT_BLUE};
                font-family: 'Consolas', 'Courier New', monospace;
                font-weight: 700;
                padding: 0 12px;
                font-size: 14px;
            }}
        """)
        mid_layout.addWidget(self.mid_field)
        
        copy_btn = TransparentPushButton("Copy Machine ID")
        copy_btn.setFixedHeight(24)
        copy_btn.setStyleSheet("color: #8E8E93; font-size: 10px;")
        copy_btn.clicked.connect(self._copy_id)
        mid_layout.addWidget(copy_btn, 0, Qt.AlignRight)
        
        layout.addLayout(mid_layout)
        
        # Contact Support Section
        contact_layout = QHBoxLayout()
        contact_layout.setSpacing(12)
        contact_layout.setAlignment(Qt.AlignCenter)
        
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl

        def open_url(url):
            QDesktopServices.openUrl(QUrl(url))

        tg_btn = TransparentPushButton("Contact via Telegram")
        tg_btn.setIcon(FluentIcon.SEND)
        tg_btn.clicked.connect(lambda: open_url("https://t.me/+OsHHWTSv_bVkZTM0"))
        tg_btn.setStyleSheet("color: #0A84FF; font-size: 11px;")
        
        wa_btn = TransparentPushButton("Contact via WhatsApp")
        wa_btn.setIcon(FluentIcon.CHAT)
        wa_btn.clicked.connect(lambda: open_url("https://wa.me/212663007212"))
        wa_btn.setStyleSheet("color: #30D158; font-size: 11px;")

        contact_layout.addWidget(tg_btn)
        contact_layout.addWidget(wa_btn)
        layout.addLayout(contact_layout)
        
        layout.addSpacing(10)

        # License Key Field
        key_layout = QVBoxLayout()
        key_layout.setSpacing(8)
        key_lbl = CaptionLabel("ENTER PRODUCT KEY")
        key_lbl.setStyleSheet("color: #636366; font-weight: 800; font-size: 10px; letter-spacing: 0.5px;")
        key_layout.addWidget(key_lbl)
        
        self.key_input = LineEdit()
        self.key_input.setPlaceholderText("ZUG-XXXX-XXXX-XXXX")
        self.key_input.setFixedHeight(44)
        self.key_input.setStyleSheet("""
            LineEdit {
                background: #1C1C1E;
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 10px;
                color: #FFFFFF;
                font-family: 'Consolas', monospace;
                font-size: 17px;
                padding: 0 16px;
            }
            LineEdit:focus { border-color: #0A84FF; }
        """)
        key_layout.addWidget(self.key_input)
        layout.addLayout(key_layout)
        
        layout.addStretch()
        
        # Actions
        btn_v = QVBoxLayout()
        btn_v.setSpacing(10)
        
        is_already_active = LicenseManager.is_active()
        
        self.activate_btn = PrimaryPushButton("Activate Now")
        self.activate_btn.setFixedHeight(44)
        self.activate_btn.setStyleSheet(f"""
            PrimaryPushButton {{
                background: {Theme.ACCENT_BLUE};
                color: #FFFFFF;
                font-weight: 800;
                font-size: 14px;
                border-radius: 10px;
            }}
            PrimaryPushButton:hover {{ background: #409CFF; }}
        """)
        self.activate_btn.clicked.connect(self._activate)
        btn_v.addWidget(self.activate_btn)
        
        exit_text = "Close Application" if not is_already_active else "Cancel"
        self.exit_btn = PushButton(exit_text)
        self.exit_btn.setFixedHeight(44)
        self.exit_btn.setStyleSheet("""
            PushButton {
                background: transparent;
                border: 1px solid #3A3A3C;
                color: #8E8E93;
                font-weight: 600;
                font-size: 13px;
                border-radius: 10px;
            }
            PushButton:hover { background: #2C2C2E; color: #FFFFFF; }
        """)
        self.exit_btn.clicked.connect(self._on_exit_clicked)
        btn_v.addWidget(self.exit_btn)
        
        layout.addLayout(btn_v)
        
    def _on_exit_clicked(self):
        if LicenseManager.is_active():
            self.reject()
        else:
            import sys
            sys.exit(0)
        
    def _copy_id(self):
        from PySide6.QtGui import QClipboard, QGuiApplication
        QGuiApplication.clipboard().setText(self.mid_field.text())
        InfoBar.success("Copied", "Machine ID copied to clipboard.", duration=2000, parent=self)
        
    def _activate(self):
        key = self.key_input.text().strip()
        if not key:
            InfoBar.error("Required", "Please enter your license key.", duration=3000, parent=self)
            return
            
        if LicenseManager.activate(key):
            self.activated.emit()
            self.accept()
        else:
            InfoBar.error("Invalid Key", "Product key does not match this machine.", duration=4000, parent=self)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
        super().keyPressEvent(event)
mode:AGENT_MODE_EXECUTION
