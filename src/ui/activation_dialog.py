"""
ZUGZWANG - Activation Dialog (macOS Redesign)
"Apple Style" - Premium, minimal, highly-polished.
"""

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, 
    QLineEdit, QFrame, QGraphicsDropShadowEffect, QPushButton
)
from qfluentwidgets import (
    FluentIcon, IconWidget, LineEdit, InfoBar
)
from .theme import Theme
from ..core.security import LicenseManager

class ActivationDialog(QDialog):
    """
    macOS-style Activation screen.
    """
    
    activated = Signal()
    open_send_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self._build_ui()
        
    def _build_ui(self):
        # Spec: Width 480px, bg #1C1C1E, border-radius 16px
        self.setFixedSize(480, 640)
        
        self.container = QFrame(self)
        self.container.setGeometry(0, 0, 480, 640)
        self.container.setObjectName("MainContainer")
        self.container.setStyleSheet("""
            QFrame#MainContainer {
                background: #1C1C1E;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 16px;
            }
        """)
        
        # Spec: padding 32px 28px
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(28, 32, 28, 32)
        layout.setSpacing(16)
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━
        # SECTION 1 — HEADER
        # ━━━━━━━━━━━━━━━━━━━━━━━━━
        header = QVBoxLayout()
        header.setAlignment(Qt.AlignCenter)
        header.setSpacing(0)
        
        # Icon: SF Symbols "touchid" style
        icon = IconWidget(FluentIcon.FINGERPRINT)
        icon.setFixedSize(48, 48)
        icon.setStyleSheet("color: #0A84FF;")
        header.addWidget(icon, 0, Qt.AlignCenter)
        header.addSpacing(12)
        
        # Title "Enter License Key"
        title = QLabel("Enter License Key")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            color: white; 
            font-family: "-apple-system", "PT Root UI", sans-serif; 
            font-size: 22px; 
            font-weight: 600;
        """)
        header.addWidget(title)
        header.addSpacing(6)
        
        # Subtitle
        subtitle = QLabel("Activation required to use ZUGZWANG")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("""
            color: #8E8E93; 
            font-family: "-apple-system", "PT Root UI", sans-serif; 
            font-size: 13px;
        """)
        header.addWidget(subtitle)
        header.addSpacing(24)
        
        layout.addLayout(header)
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━
        # SECTION 2 — MACHINE ID
        # ━━━━━━━━━━━━━━━━━━━━━━━━━
        mid_layout = QVBoxLayout()
        mid_layout.setSpacing(6)
        
        mid_lbl = QLabel("YOUR MACHINE ID")
        mid_lbl.setStyleSheet("""
            color: #8E8E93; 
            font-family: "-apple-system", "PT Root UI", sans-serif; 
            font-size: 10px; 
            font-weight: 600; 
            letter-spacing: 1.4px;
        """)
        mid_layout.addWidget(mid_lbl)
        
        # Field Container: bg #2C2C2E, border #3A3A3C, radius 10px, height 44px
        mid_container = QFrame()
        mid_container.setFixedHeight(44)
        mid_container.setStyleSheet("""
            QFrame {
                background: #2C2C2E;
                border: 1px solid #3A3A3C;
                border-radius: 10px;
            }
        """)
        
        mid_box_layout = QHBoxLayout(mid_container)
        mid_box_layout.setContentsMargins(14, 0, 14, 0)
        mid_box_layout.setSpacing(0)
        
        self.mid_field = QLineEdit(LicenseManager.get_machine_id())
        self.mid_field.setReadOnly(True)
        self.mid_field.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                color: #0A84FF;
                font-family: "PT Root UI", "Menlo", monospace;
                font-size: 14px;
                letter-spacing: 0.5px;
            }
        """)
        
        copy_btn = QPushButton("Copy")
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.setIcon(FluentIcon.COPY.icon(color=QColor("#636366")))
        copy_btn.setIconSize(QSize(16, 16))
        copy_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #636366;
                font-family: "-apple-system", "PT Root UI", sans-serif;
                font-size: 13px;
            }
            QPushButton:hover {
                color: #AEAEB2;
            }
        """)
        copy_btn.clicked.connect(self._copy_id)
        
        mid_box_layout.addWidget(self.mid_field, 1)
        mid_box_layout.addWidget(copy_btn)
        
        mid_layout.addWidget(mid_container)
        layout.addLayout(mid_layout)
        layout.addSpacing(16)
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━
        # SECTION 3 — CONTACT BUTTONS
        # ━━━━━━━━━━━━━━━━━━━━━━━━━
        contact_layout = QHBoxLayout()
        contact_layout.setSpacing(10)
        
        contact_btn_style = """
            QPushButton {
                background: #2C2C2E;
                border: 1px solid #3A3A3C;
                border-radius: 10px;
                height: 40px;
                color: white;
                font-family: "-apple-system", "PT Root UI", sans-serif;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #3A3A3C;
            }
        """
        
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        def open_url(url): QDesktopServices.openUrl(QUrl(url))

        tg_btn = QPushButton("Telegram")
        tg_btn.setIcon(FluentIcon.SEND.icon(color=QColor("#0A84FF")))
        tg_btn.setIconSize(QSize(18, 18))
        tg_btn.setCursor(Qt.PointingHandCursor)
        tg_btn.setStyleSheet(contact_btn_style)
        tg_btn.clicked.connect(lambda: open_url("https://t.me/+OsHHWTSv_bVkZTM0"))
        
        wa_btn = QPushButton("WhatsApp")
        wa_btn.setIcon(FluentIcon.CHAT.icon(color=QColor("#30D158")))
        wa_btn.setIconSize(QSize(18, 18))
        wa_btn.setCursor(Qt.PointingHandCursor)
        wa_btn.setStyleSheet(contact_btn_style)
        wa_btn.clicked.connect(lambda: open_url("https://wa.me/212663007212"))

        contact_layout.addWidget(tg_btn)
        contact_layout.addWidget(wa_btn)
        layout.addLayout(contact_layout)
        layout.addSpacing(16)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━
        # SECTION 4 — PRODUCT KEY INPUT
        # ━━━━━━━━━━━━━━━━━━━━━━━━━
        key_layout = QVBoxLayout()
        key_layout.setSpacing(6)
        
        key_lbl = QLabel("ENTER PRODUCT KEY")
        key_lbl.setStyleSheet("""
            color: #8E8E93; 
            font-family: "-apple-system", "PT Root UI", sans-serif; 
            font-size: 10px; 
            font-weight: 600; 
            letter-spacing: 1.4px;
        """)
        key_layout.addWidget(key_lbl)
        
        self.key_input = LineEdit()
        self.key_input.setPlaceholderText("ZUG-XXXX-XXXX-XXXX")
        self.key_input.setFixedHeight(44)
        self.key_input.setStyleSheet("""
            LineEdit {
                background: #2C2C2E;
                border: 1px solid #3A3A3C;
                border-radius: 10px;
                color: #AEAEB2;
                font-family: "PT Root UI", "Menlo", monospace;
                font-size: 14px;
                padding: 0 14px;
                letter-spacing: 1px;
            }
            LineEdit:focus { 
                border: 1px solid #0A84FF;
                background: #2C2C2E;
            }
        """)
        key_layout.addWidget(self.key_input)
        layout.addLayout(key_layout)
        layout.addSpacing(16)
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━
        # SECTION 5 — ACTION BUTTONS
        # ━━━━━━━━━━━━━━━━━━━━━━━━━
        actions = QVBoxLayout()
        actions.setSpacing(8)
        
        self.activate_btn = QPushButton("Activate Now")
        self.activate_btn.setFixedHeight(44)
        self.activate_btn.setCursor(Qt.PointingHandCursor)
        self.activate_btn.setStyleSheet("""
            QPushButton {
                background: #0A84FF;
                color: white;
                border: none;
                border-radius: 10px;
                font-family: "-apple-system", "PT Root UI", sans-serif;
                font-size: 15px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #409CFF;
            }
        """)
        self.activate_btn.clicked.connect(self._activate)
        actions.addWidget(self.activate_btn)
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━
        # FREE ACCESS BANNER
        # ━━━━━━━━━━━━━━━━━━━━━━━━━
        banner = QFrame()
        banner.setObjectName("FreeBanner")
        banner.setStyleSheet("""
            QFrame#FreeBanner {
                background-color: #1C3A1C;
                border: 1px solid #30D158;
                border-radius: 10px;
            }
            QLabel {
                background: transparent;
                border: none;
                padding: 0;
                margin: 0;
            }
        """)
        banner_layout = QHBoxLayout(banner)
        banner_layout.setContentsMargins(16, 12, 16, 12)
        banner_layout.setSpacing(12)
        
        check_icon = IconWidget(FluentIcon.COMPLETED)
        check_icon.setFixedSize(20, 20)
        # Use a more minimal stroke-like icon if available, or just stick to green
        check_icon.setStyleSheet("color: #30D158; background: transparent; border: none;")
        banner_layout.addWidget(check_icon, 0, Qt.AlignVCenter)
        
        text_container = QWidget()
        text_container.setObjectName("BannerText")
        text_container.setStyleSheet("QWidget#BannerText { background: transparent; border: none; }")
        text_vbox = QVBoxLayout(text_container)
        text_vbox.setContentsMargins(0, 0, 0, 0)
        text_vbox.setSpacing(3)
        
        b_title = QLabel("Free Access Available")
        b_title.setStyleSheet("color: #30D158; font-family: 'PT Root UI', sans-serif; font-size: 13px; font-weight: 600; background: transparent; border: none;")
        
        b_sub = QLabel("Send tab is currently free — no license needed")
        b_sub.setStyleSheet("color: #8E8E93; font-family: 'PT Root UI', sans-serif; font-size: 11px; font-weight: 400; background: transparent; border: none;")
        
        text_vbox.addWidget(b_title)
        text_vbox.addWidget(b_sub)
        banner_layout.addWidget(text_container, 1)
        
        nav_btn = QPushButton("Open Send →")
        nav_btn.setCursor(Qt.PointingHandCursor)
        nav_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #30D158;
                font-family: 'PT Root UI', sans-serif;
                font-size: 13px;
                font-weight: 600;
                padding: 0;
            }
            QPushButton:hover {
                color: rgba(48, 209, 88, 0.7);
            }
        """)
        nav_btn.clicked.connect(self._on_open_send)
        banner_layout.addWidget(nav_btn)
        
        actions.addSpacing(8)
        actions.addWidget(banner)
        
        # Close Button
        self.close_btn = QPushButton("Close Application")
        self.close_btn.setFixedHeight(36)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #636366;
                font-family: "-apple-system", "PT Root UI", sans-serif;
                font-size: 13px;
            }
            QPushButton:hover {
                color: #AEAEB2;
            }
        """)
        self.close_btn.clicked.connect(self._on_exit_clicked)
        actions.addWidget(self.close_btn)
        
        layout.addLayout(actions)
        layout.addStretch()

    def _on_open_send(self):
        self.open_send_requested.emit()
        self.accept()

    def _on_exit_clicked(self):
        if LicenseManager.is_active():
            self.reject()
        else:
            import sys
            sys.exit(0)
        
    def _copy_id(self):
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
