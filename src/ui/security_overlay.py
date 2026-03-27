"""
ZUGZWANG - Security Overlay
Modern PIN-lock screen for local access protection.
"""

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, 
    QLineEdit, QFrame, QGraphicsDropShadowEffect
)
from qfluentwidgets import (
    PushButton, PrimaryPushButton, TransparentPushButton, 
    FluentIcon, StrongBodyLabel, CaptionLabel, IconWidget,
    SmoothScrollArea, MessageBox
)
from .theme import Theme

class SecurityOverlay(QDialog):
    """
    Premium PIN-lock screen. 
    Displays before the main window to ensure local privacy.
    """
    
    authenticated = Signal()

    def __init__(self, target_pin: str, parent=None):
        super().__init__(parent)
        self._target_pin = target_pin
        self._input_pin = ""
        
        # Make it frameless and high-z
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self._build_ui()
        
    def _build_ui(self):
        self.setFixedSize(400, 500)
        
        # Outer Shadow Container
        self.container = QFrame(self)
        self.container.setGeometry(10, 10, 380, 480)
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
        layout.setContentsMargins(40, 60, 40, 40)
        layout.setSpacing(20)
        
        # Header / Branding
        header = QVBoxLayout()
        header.setAlignment(Qt.AlignCenter)
        header.setSpacing(8)
        
        icon = IconWidget(FluentIcon.FINGERPRINT)
        icon.setFixedSize(48, 48)
        icon.setStyleSheet(f"color: {Theme.ACCENT_BLUE};")
        header.addWidget(icon, 0, Qt.AlignCenter)
        
        title = StrongBodyLabel("ZUGZWANG")
        title.setStyleSheet("font-size: 20px; color: #FFFFFF;")
        header.addWidget(title, 0, Qt.AlignCenter)
        
        subtitle = CaptionLabel("Protected by Startup Lock")
        subtitle.setStyleSheet("color: #8E8E93;")
        header.addWidget(subtitle, 0, Qt.AlignCenter)
        
        layout.addLayout(header)
        layout.addSpacing(20)
        
        # PIN Entry Field (Visualization)
        self.pin_display = QHBoxLayout()
        self.pin_display.setSpacing(12)
        self.pin_display.setAlignment(Qt.AlignCenter)
        self.dots = []
        for _ in range(4):
            dot = QFrame()
            dot.setFixedSize(14, 14)
            dot.setStyleSheet("background: #2C2C2E; border-radius: 7px; border: 1px solid rgba(255,255,255,0.1);")
            self.pin_display.addWidget(dot)
            self.dots.append(dot)
        layout.addLayout(self.pin_display)
        
        layout.addStretch()
        
        # Keypad Grid
        keypad = QGridLayout()
        keypad.setSpacing(10)
        
        nums = [
            ('1',''), ('2',''), ('3',''),
            ('4',''), ('5',''), ('6',''),
            ('7',''), ('8',''), ('9',''),
            ('C',''), ('0',''), ('⌫','')
        ]
        
        row, col = 0, 0
        for label, sub in nums:
            btn = PushButton(label)
            btn.setFixedSize(64, 64)
            btn.setStyleSheet(f"""
                PushButton {{
                    background: #2C2C2E;
                    border: 1px solid rgba(255,255,255,0.05);
                    border-radius: 32px;
                    color: #FFFFFF;
                    font-size: 18px;
                    font-weight: 500;
                }}
                PushButton:hover {{ background: #3A3A3C; border-color: {Theme.BORDER_LIGHT}; }}
                PushButton:pressed {{ background: {Theme.BG_HOVER}; }}
            """)
            if label == 'C':
                btn.clicked.connect(self._clear_pin)
                btn.setStyleSheet(btn.styleSheet() + " color: #FF453A; font-size: 14px;")
            elif label == '⌫':
                btn.clicked.connect(self._backspace)
                btn.setStyleSheet(btn.styleSheet() + " color: #8E8E93; font-size: 16px;")
            else:
                btn.clicked.connect(lambda checked=False, val=label: self._handle_press(val))
            
            keypad.addWidget(btn, row, col)
            col += 1
            if col > 2:
                col = 0
                row += 1
                
        layout.addLayout(keypad)
        
    def _handle_press(self, val: str):
        if len(self._input_pin) < 4:
            self._input_pin += val
            self._update_dots()
            
            if len(self._input_pin) == 4:
                # Give a tiny bit of time for the user to see the 4th dot
                from PySide6.QtCore import QTimer
                QTimer.singleShot(150, self._check_pin)
                
    def _backspace(self):
        if self._input_pin:
            self._input_pin = self._input_pin[:-1]
            self._update_dots()
            
    def _clear_pin(self):
        self._input_pin = ""
        self._update_dots()
        
    def _update_dots(self):
        for i, dot in enumerate(self.dots):
            if i < len(self._input_pin):
                dot.setStyleSheet(f"background: {Theme.ACCENT_BLUE}; border-radius: 7px; border: none;")
            else:
                dot.setStyleSheet("background: #2C2C2E; border-radius: 7px; border: 1px solid rgba(255,255,255,0.1);")
                
    def _check_pin(self):
        if self._input_pin == self._target_pin:
            self._on_success()
        else:
            self._on_failure()
            
    def _on_success(self):
        self.accept()
        self.authenticated.emit()
        
    def _on_failure(self):
        # Shake effect could be cool, but for now just clear and red flash
        for dot in self.dots:
            dot.setStyleSheet("background: #FF453A; border-radius: 7px; border: none;")
            
        from PySide6.QtCore import QTimer
        QTimer.singleShot(400, self._clear_pin)

    def keyPressEvent(self, event):
        """Allow physical keyboard entry."""
        key = event.text()
        if key.isdigit() and len(key) == 1:
            self._handle_press(key)
        elif event.key() == Qt.Key_BackSpace:
            self._backspace()
        elif event.key() == Qt.Key_Escape:
            self.reject()
        super().keyPressEvent(event)
mode:AGENT_MODE_EXECUTION
