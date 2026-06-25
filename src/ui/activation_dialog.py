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

    def __init__(self, parent=None, startup_prompt: bool = False):
        super().__init__(parent)
        self._startup_prompt = startup_prompt
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self._build_ui()
        
    def _build_ui(self):
        # We don't set a fixed height here, we let the layout automatically hug the content.
        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        
        self.container = QFrame(self)
        self.container.setObjectName("MainContainer")
        self.container.setStyleSheet("""
            QFrame#MainContainer {
                background: #242426;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 14px;
            }
        """)
        self.container.setFixedWidth(460)
        dialog_layout.addWidget(self.container)
        
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(28, 28, 28, 24)
        layout.setSpacing(0)
        layout.setSizeConstraint(QVBoxLayout.SetFixedSize)
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━
        # 1. HEADER (macOS Sheet Style)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(14)
        
        icon_chip = QFrame()
        icon_chip.setFixedSize(36, 36)
        icon_chip.setStyleSheet("background: rgba(255, 255, 255, 0.05); border-radius: 8px;")
        chip_layout = QVBoxLayout(icon_chip)
        chip_layout.setContentsMargins(0, 0, 0, 0)
        icon = IconWidget(FluentIcon.VPN)
        icon.setFixedSize(18, 18)
        icon.setStyleSheet("color: #E5E5EA; background: transparent;")
        chip_layout.addWidget(icon, 0, Qt.AlignCenter)
        
        header_layout.addWidget(icon_chip, 0, Qt.AlignTop)
        
        header_text_layout = QVBoxLayout()
        header_text_layout.setSpacing(2)
        title = QLabel("Activate ZUGZWANG Pro")
        title.setStyleSheet("""
            color: #FFFFFF; 
            background: transparent;
            font-family: "-apple-system", "SF Pro Text", sans-serif; 
            font-size: 15px; 
            font-weight: 600;
        """)
        header_text_layout.addWidget(title)
        
        subtitle = QLabel("Unlock pro features and remove trial limits")
        subtitle.setStyleSheet("""
            color: rgba(255, 255, 255, 0.45); 
            background: transparent;
            font-family: "-apple-system", "SF Pro Text", sans-serif; 
            font-size: 12.5px;
        """)
        header_text_layout.addWidget(subtitle)
        
        header_layout.addLayout(header_text_layout)
        header_layout.addStretch(1)
        
        layout.addLayout(header_layout)
        layout.addSpacing(24)
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━
        # 2. PERSUASION / BENEFITS
        # ━━━━━━━━━━━━━━━━━━━━━━━━━
        benefits_layout = QVBoxLayout()
        benefits_layout.setSpacing(10)
        
        def _make_prop(text: str):
            row = QHBoxLayout()
            row.setSpacing(10)
            chk = IconWidget(FluentIcon.ACCEPT)
            chk.setFixedSize(12, 12)
            chk.setStyleSheet("color: rgba(255, 255, 255, 0.4); background: transparent;")
            lbl = QLabel(text)
            lbl.setStyleSheet("color: #D1D1D6; background: transparent; font-family: '-apple-system', 'SF Pro Text', sans-serif; font-size: 13px; font-weight: 400;")
            row.addWidget(chk, 0, Qt.AlignVCenter)
            row.addWidget(lbl, 1, Qt.AlignVCenter)
            return row
            
        benefits_layout.addLayout(_make_prop("Unlimited automated PDF generation"))
        benefits_layout.addLayout(_make_prop("Dynamic personalization of your Anschreiben"))
        benefits_layout.addLayout(_make_prop("Unlimited mass email broadcasts"))
        benefits_layout.addLayout(_make_prop("Deep website scanning for hidden contacts"))
        benefits_layout.addLayout(_make_prop("Unlimited Google Maps lead extraction"))
        benefits_layout.addLayout(_make_prop("Priority customer support & updates"))
        benefits_layout.addLayout(_make_prop("Removal of all free trial restrictions"))
        layout.addLayout(benefits_layout)
        
        layout.addSpacing(24)
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━
        # 3. FOCAL TASK (PRODUCT KEY)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━
        key_lbl = QLabel("PRODUCT KEY")
        key_lbl.setStyleSheet("color: #8E8E93; background: transparent; font-family: '-apple-system', sans-serif; font-size: 11px; font-weight: 600; letter-spacing: 0.5px;")
        layout.addWidget(key_lbl)
        layout.addSpacing(6)
        
        self.key_input = LineEdit()
        self.key_input.setPlaceholderText("ZUG-XXXX-XXXX-XXXX")
        self.key_input.setFixedHeight(34)
        self.key_input.setStyleSheet("""
            LineEdit {
                background: rgba(255, 255, 255, 0.04);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
                color: #FFFFFF;
                font-family: "SF Mono", "Menlo", monospace;
                font-size: 13px; padding: 0 10px; letter-spacing: 1px;
            }
            LineEdit:focus { 
                border: 1px solid rgba(10, 132, 255, 0.6);
                background: rgba(255, 255, 255, 0.06);
            }
        """)
        self.key_input.textChanged.connect(self._on_key_changed)
        layout.addWidget(self.key_input)
        layout.addSpacing(16)
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━
        # 4. SUBORDINATE REFERENCE (MACHINE ID)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━
        mid_layout = QHBoxLayout()
        mid_layout.setSpacing(8)
        
        mid_lbl = QLabel("Machine ID")
        mid_lbl.setStyleSheet("color: #8E8E93; background: transparent; font-family: '-apple-system', sans-serif; font-size: 11px; font-weight: 500;")
        mid_layout.addWidget(mid_lbl)
        
        self.mid_field = QLabel()
        self.mid_field.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.mid_field.setStyleSheet("color: #AEAEB2; font-family: 'SF Mono', 'Menlo', monospace; font-size: 11.5px; letter-spacing: 0.5px; background: transparent;")
        mid_layout.addWidget(self.mid_field)
        
        copy_btn = QPushButton()
        copy_btn.setFixedSize(16, 16)
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.setIcon(FluentIcon.COPY.icon(color=QColor(142, 142, 147, 180)))
        copy_btn.setStyleSheet("QPushButton { background: transparent; border: none; } QPushButton:hover { background: rgba(255,255,255,0.1); border-radius: 4px; }")
        copy_btn.clicked.connect(self._copy_id)
        mid_layout.addWidget(copy_btn)
        
        mid_layout.addStretch(1)
        layout.addLayout(mid_layout)
        
        layout.addSpacing(20)
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━
        # 5. FOOTER (Divider + Action Buttons)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background: rgba(255, 255, 255, 0.08); border: none;")
        layout.addWidget(divider)
        layout.addSpacing(16)
        
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(12)
        
        # Ghost support icons (LEFT)
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        def open_url(url): QDesktopServices.openUrl(QUrl(url))
        
        tg_btn = QPushButton()
        tg_btn.setFixedSize(22, 22)
        tg_btn.setCursor(Qt.PointingHandCursor)
        tg_btn.setIcon(FluentIcon.SEND.icon(color=QColor(255, 255, 255, 100)))
        tg_btn.setStyleSheet("QPushButton { background: transparent; border: none; } QPushButton:hover { background: rgba(255, 255, 255, 0.1); border-radius: 4px; }")
        tg_btn.clicked.connect(lambda: open_url("https://t.me/+OsHHWTSv_bVkZTM0"))
        
        wa_btn = QPushButton()
        wa_btn.setFixedSize(22, 22)
        wa_btn.setCursor(Qt.PointingHandCursor)
        wa_btn.setIcon(FluentIcon.CHAT.icon(color=QColor(255, 255, 255, 100)))
        wa_btn.setStyleSheet("QPushButton { background: transparent; border: none; } QPushButton:hover { background: rgba(255, 255, 255, 0.1); border-radius: 4px; }")
        wa_btn.clicked.connect(lambda: open_url("https://wa.me/212663007212"))
        
        footer.addWidget(tg_btn)
        footer.addWidget(wa_btn)
        
        footer.addStretch(1)
        
        # Primary Action Pair (RIGHT)
        self.close_btn = QPushButton("Continue trial")
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setFixedHeight(28)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background: transparent; 
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 6px;
                color: #FFFFFF;
                font-family: "-apple-system", "SF Pro Text", sans-serif; font-size: 13px; font-weight: 500;
                padding: 0 16px;
            }
            QPushButton:hover { background: rgba(255, 255, 255, 0.05); }
        """)
        self.close_btn.clicked.connect(self._on_exit_clicked)
        footer.addWidget(self.close_btn)
        
        self.activate_btn = QPushButton("Activate")
        self.activate_btn.setFixedHeight(28)
        self.activate_btn.setCursor(Qt.PointingHandCursor)
        self.activate_btn.setProperty("isValid", False)
        self.activate_btn.setStyleSheet("""
            QPushButton {
                background: #2C2C2E;
                color: #8E8E93;
                border: none;
                border-radius: 6px;
                font-family: "-apple-system", "SF Pro Text", sans-serif;
                font-size: 13px; font-weight: 500;
                padding: 0 16px;
            }
            QPushButton[isValid="true"] {
                background: #0A84FF;
                color: #FFFFFF;
            }
            QPushButton[isValid="true"]:hover { 
                background: #0070DF; 
            }
        """)
        self.activate_btn.setEnabled(False)
        self.activate_btn.clicked.connect(self._activate)
        footer.addWidget(self.activate_btn)
        
        layout.addLayout(footer)
        
        self._refresh_machine_id()

    def _on_key_changed(self, text: str):
        self.key_input.blockSignals(True)
        clean = text.replace("-", "").upper()
        
        formatted = ""
        if len(clean) > 0:
            formatted += clean[:3]
        if len(clean) > 3:
            formatted += "-" + clean[3:7]
        if len(clean) > 7:
            formatted += "-" + clean[7:11]
        if len(clean) > 11:
            formatted += "-" + clean[11:15]
            
        self.key_input.setText(formatted)
        self.key_input.setCursorPosition(len(formatted))
        self.key_input.blockSignals(False)
        
        is_valid = len(clean) >= 15
        if self.activate_btn.property("isValid") != is_valid:
            self.activate_btn.setProperty("isValid", is_valid)
            self.activate_btn.setEnabled(is_valid)
            self.activate_btn.style().unpolish(self.activate_btn)
            self.activate_btn.style().polish(self.activate_btn)

    def _on_open_send(self):
        self.open_send_requested.emit()
        self.accept()

    def _on_exit_clicked(self):
        self.reject()
        
    def _copy_id(self):
        machine_id = self.mid_field.text().strip()
        if not machine_id:
            self._refresh_machine_id()
            machine_id = self.mid_field.text().strip()
        QGuiApplication.clipboard().setText(machine_id)
        InfoBar.success("Copied", "Machine ID copied to clipboard.", duration=2000, parent=self)

    def _refresh_machine_id(self):
        machine_id = (LicenseManager.get_machine_id() or "").strip().upper()
        self.mid_field.setText(machine_id)
        
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
