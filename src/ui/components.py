"""
ZUGZWANG - Reusable UI Components
Shared widgets used across multiple pages.
"""

from __future__ import annotations
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal, QSize, QPropertyAnimation, QEasingCurve, Property, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QBrush
from PySide6.QtWidgets import (
    QWidget, QLabel, QHBoxLayout, QVBoxLayout,
    QPushButton, QFrame, QSizePolicy, QDialog,
)

from .icons import apply_button_icon


class StatCard(QFrame):
    """Dashboard stat card showing a metric with label and subtitle."""

    def __init__(self, title: str, value: str = "-", subtitle: str = "", color: str = "#212A3B"):
        super().__init__()
        self.setObjectName("Card")
        self._color = color

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(4)

        self._title_lbl = QLabel(title.upper())
        self._title_lbl.setObjectName("CardTitle")

        self._value_lbl = QLabel(value)
        self._value_lbl.setObjectName("CardValue")
        self._value_lbl.setStyleSheet(f"color: {color};")

        self._sub_lbl = QLabel(subtitle)
        self._sub_lbl.setObjectName("CardSub")

        layout.addWidget(self._title_lbl)
        layout.addWidget(self._value_lbl)
        layout.addWidget(self._sub_lbl)

    def set_value(self, value: str) -> None:
        self._value_lbl.setText(value)

    def set_subtitle(self, text: str) -> None:
        self._sub_lbl.setText(text)


class SectionCard(QFrame):
    """Reusable rounded section container with an optional header row."""

    def __init__(self, title: str = "", subtitle: str = ""):
        super().__init__()
        self.setObjectName("SectionCard")

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(20, 20, 20, 20)
        self._layout.setSpacing(16)

        self._header = QWidget()
        self._header_layout = QHBoxLayout(self._header)
        self._header_layout.setContentsMargins(0, 0, 0, 0)
        self._header_layout.setSpacing(10)

        self._title_wrap = QWidget()
        title_layout = QVBoxLayout(self._title_wrap)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(2)

        self._title_label = QLabel(title)
        self._title_label.setObjectName("SectionCardTitle")
        title_layout.addWidget(self._title_label)

        self._subtitle_label = QLabel(subtitle)
        self._subtitle_label.setObjectName("SectionCardSubtitle")
        self._subtitle_label.setVisible(bool(subtitle))
        title_layout.addWidget(self._subtitle_label)

        self._header_layout.addWidget(self._title_wrap)
        self._header_layout.addStretch()

        self._layout.addWidget(self._header)
        self._header.setVisible(bool(title or subtitle))

    def add_header_widget(self, widget: QWidget) -> None:
        self._header_layout.addWidget(widget)

    def body_layout(self) -> QVBoxLayout:
        return self._layout

    def set_title(self, title: str, subtitle: str = "") -> None:
        self._title_label.setText(title)
        self._subtitle_label.setText(subtitle)
        self._subtitle_label.setVisible(bool(subtitle))
        self._header.setVisible(bool(title or subtitle))


class StatusBadge(QLabel):
    """Colored badge label for status display."""

    STATUS_STYLES = {
        "running": "BadgeInfo",
        "completed": "BadgeSuccess",
        "failed": "BadgeError",
        "paused": "BadgeWarning",
        "cancelled": "BadgeWarning",
        "pending": "BadgeWarning",
        "idle": "BadgeInfo",
    }

    def __init__(self, status: str = "idle"):
        super().__init__()
        self.setAlignment(Qt.AlignCenter)
        self.set_status(status)

    def set_status(self, status: str) -> None:
        self.setText(status.upper())
        obj_name = self.STATUS_STYLES.get(status.lower(), "BadgeInfo")
        self.setObjectName(obj_name)
        # Force style refresh
        self.style().unpolish(self)
        self.style().polish(self)


class SectionHeader(QWidget):
    """Page section header with title and optional subtitle."""

    def __init__(self, title: str, subtitle: str = ""):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("PageHeader")
        layout.addWidget(title_lbl)

        if subtitle:
            sub_lbl = QLabel(subtitle)
            sub_lbl.setObjectName("PageSubtitle")
            layout.addWidget(sub_lbl)


class Divider(QFrame):
    """Horizontal divider line."""

    def __init__(self):
        super().__init__()
        self.setFrameShape(QFrame.HLine)
        self.setObjectName("SectionDivider")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(1)


class FieldLabel(QLabel):
    """Styled field label for form inputs."""

    def __init__(self, text: str):
        super().__init__(text)
        self.setObjectName("FieldLabel")


def make_field(label: str, widget: QWidget) -> QVBoxLayout:
    """Helper to create a labeled form field layout."""
    layout = QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    layout.addWidget(FieldLabel(label))
    layout.addWidget(widget)
    return layout


def make_button(
    text: str,
    style: str = "SecondaryBtn",
    icon: str = "",
    tooltip: str = "",
) -> QPushButton:
    """Factory for styled buttons."""
    btn = QPushButton(text)
    btn.setObjectName(style)
    btn.setCursor(Qt.PointingHandCursor)
    if icon:
        apply_button_icon(btn, icon)
    if tooltip:
        btn.setToolTip(tooltip)
    return btn


class EmptyState(QFrame):
    """Friendly empty state widget shown when no results exist."""

    def __init__(self, icon: str = "", title: str = "No results yet", body: str = ""):
        super().__init__()
        self.setObjectName("EmptyState")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setMinimumHeight(170)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(10)

        if icon:
            icon_lbl = QLabel(icon)
            icon_lbl.setObjectName("EmptyStateIcon")
            icon_lbl.setAlignment(Qt.AlignCenter)
            layout.addWidget(icon_lbl)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("EmptyStateTitle")
        title_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_lbl)

        if body:
            body_lbl = QLabel(body)
            body_lbl.setObjectName("EmptyStateBody")
            body_lbl.setAlignment(Qt.AlignCenter)
            body_lbl.setWordWrap(True)
            body_lbl.setMaximumWidth(440)
            body_lbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
            layout.addWidget(body_lbl)


class WorkspaceListItem(QFrame):
    """Dense clickable item used in the middle workspace list."""

    activated = Signal(str)

    def __init__(self, key: str, title: str, meta: str = "", preview: str = "", badge: str = ""):
        super().__init__()
        self._key = key
        self.setObjectName("WorkspaceItem")
        self.setProperty("active", False)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(74)
        self.setAccessibleName(title)
        self.setAccessibleDescription("Workspace item")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)

        self._title = QLabel(title)
        self._title.setObjectName("WorkspaceItemTitle")
        self._title.setWordWrap(False)
        top_row.addWidget(self._title, 1)

        self._badge = QLabel(badge)
        self._badge.setObjectName("WorkspaceItemBadge")
        self._badge.setVisible(bool(badge))
        top_row.addWidget(self._badge)
        layout.addLayout(top_row)

        self._meta = QLabel(meta)
        self._meta.setObjectName("WorkspaceItemMeta")
        self._meta.setWordWrap(False)
        self._meta.setVisible(bool(meta))
        layout.addWidget(self._meta)

        self._preview = QLabel(preview)
        self._preview.setObjectName("WorkspaceItemPreview")
        self._preview.setWordWrap(False)
        self._preview.setMaximumHeight(18)
        self._preview.setVisible(bool(preview))
        layout.addWidget(self._preview)

    @property
    def key(self) -> str:
        return self._key

    def set_active(self, active: bool) -> None:
        self.setProperty("active", active)
        self.style().unpolish(self)
        self.style().polish(self)

    def update_content(self, title: str, meta: str = "", preview: str = "", badge: str = "") -> None:
        self._title.setText(title)
        self._meta.setText(meta)
        self._meta.setVisible(bool(meta))
        self._preview.setText(preview)
        self._preview.setVisible(bool(preview))
        self._badge.setText(badge)
        self._badge.setVisible(bool(badge))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.activated.emit(self._key)
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.activated.emit(self._key)
            event.accept()
            return
        super().keyPressEvent(event)


class ZugzwangDialog(QDialog):
    """
    Premium macOS ZUGZWANG Style Dialog.
    Centered text, high-fidelity geometry, and Apple-style buttons to match Image 3.
    """
    def __init__(self, title: str, message: str, parent=None, destructive: bool = False):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(480, 260)
        
        # Main shadow/glass container
        self.container = QFrame(self)
        self.container.setObjectName("DialogContainer")
        self.container.setFixedSize(480, 260)
        self.container.setStyleSheet("""
            QFrame#DialogContainer {
                background-color: #1E1E1E;
                border: 1px solid #323232;
                border-radius: 18px;
            }
        """)
        
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(40, 42, 40, 36)
        layout.setSpacing(12)
        
        # Header/Text area
        text_layout = QVBoxLayout()
        text_layout.setSpacing(10)
        text_layout.setAlignment(Qt.AlignCenter)
        
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #FFFFFF; font-family: 'PT Root UI', 'PT Root UI'; font-size: 26px; font-weight: 800; background: transparent;")
        self.title_label.setAlignment(Qt.AlignCenter)
        
        self.message_label = QLabel(message)
        self.message_label.setStyleSheet("color: #D1D1D6; font-family: 'PT Root UI', 'PT Root UI'; font-size: 15px; font-weight: 400; line-height: 1.4; background: transparent;")
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setWordWrap(True)
        
        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.message_label)
        layout.addLayout(text_layout)
        
        layout.addStretch()
        
        # Action Row
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(16)
        btn_layout.setAlignment(Qt.AlignCenter)
        
        # OK Button (Red #FF453A)
        self.ok_btn = QPushButton("OK")
        self.ok_btn.setFixedSize(160, 48)
        self.ok_btn.setCursor(Qt.PointingHandCursor)
        self.ok_btn.setStyleSheet("""
            QPushButton {
                background: #FF453A;
                border: none;
                border-radius: 14px;
                color: #FFFFFF;
                font-family: 'PT Root UI', 'PT Root UI';
                font-size: 16px;
                font-weight: 700;
            }
            QPushButton:hover { background: #FF5C52; }
            QPushButton:pressed { background: #E03E34; }
        """)
        self.ok_btn.clicked.connect(self.accept)
        
        # Cancel Button (Dark #2C2C2E)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedSize(160, 48)
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background: #2C2C2E;
                border: 1px solid #3A3A3C;
                border-radius: 14px;
                color: #FFFFFF;
                font-family: 'PT Root UI', 'PT Root UI';
                font-size: 16px;
                font-weight: 500;
            }
            QPushButton:hover { background: #3A3A3C; border-color: #48484A; }
            QPushButton:pressed { background: #242426; }
        """)
        self.cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)
        
        if parent:
            center = parent.geometry().center()
            self.move(center.x() - self.width() // 2, center.y() - self.height() // 2 - 20)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

class FeedbackDialog(QDialog):
    """
    Premium Feedback & Recommendation Dialog.
    Direct links to Telegram/WhatsApp and one-click recommendation.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(480, 560)
        
        # Main shadow/glass container
        self.container = QFrame(self)
        self.container.setObjectName("FeedbackContainer")
        self.container.setFixedSize(480, 560)
        self.container.setStyleSheet("""
            QFrame#FeedbackContainer {
                background-color: #1C1C1E;
                border: 1px solid #323232;
                border-radius: 20px;
            }
        """)
        
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(40, 42, 40, 36)
        layout.setSpacing(15)
        
        # Header/Text area (Grouped in a widget to prevent layout drift)
        header_widget = QWidget()
        hl = QVBoxLayout(header_widget); hl.setContentsMargins(0,0,0,0); hl.setSpacing(10)
        self.icon_lbl = QLabel("❤️")
        self.icon_lbl.setStyleSheet("font-size: 40px; background: transparent;")
        self.icon_lbl.setAlignment(Qt.AlignCenter)
        self.title_label = QLabel("Love ZUGZWANG?")
        self.title_label.setStyleSheet("color: #FFFFFF; font-family: 'PT Root UI'; font-size: 26px; font-weight: 800; background: transparent;")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.message_label = QLabel("Support the developer or recommend us to a friend!")
        self.message_label.setStyleSheet("color: #8E8E93; font-family: 'PT Root UI'; font-size: 15px; font-weight: 400; line-height: 1.4; background: transparent;")
        self.message_label.setAlignment(Qt.AlignCenter); self.message_label.setWordWrap(True)
        hl.addWidget(self.icon_lbl); hl.addWidget(self.title_label); hl.addWidget(self.message_label)
        layout.addWidget(header_widget)

        # 1. Social Sharing Section
        social_box = QWidget()
        sl = QVBoxLayout(social_box); sl.setContentsMargins(0,5,0,5); sl.setSpacing(10)
        share_title = QLabel("PROMOTE ON SOCIAL MEDIA")
        share_title.setStyleSheet("color: #8E8E93; font-family: 'SF Mono'; font-size: 10px; font-weight: 700; letter-spacing: 1.5px;")
        share_title.setAlignment(Qt.AlignCenter)
        sl.addWidget(share_title)

        srow = QHBoxLayout(); srow.setSpacing(10)
        self.x_btn = self._create_btn("X", "#000000", "#1A1A1A", is_half=True)
        self.x_btn.clicked.connect(lambda: self._on_share("x"))
        self.fb_btn = self._create_btn("FACEBOOK", "#1877F2", "#2D88FF", is_half=True)
        self.fb_btn.clicked.connect(lambda: self._on_share("fb"))
        self.wa_share_btn = self._create_btn("WHATSAPP", "#25D366", "#2CE071", is_half=True)
        self.wa_share_btn.clicked.connect(lambda: self._on_share("wa"))
        self.ig_btn = self._create_btn("INSTAGRAM", "#E4405F", "#F55376", is_half=True)
        self.ig_btn.clicked.connect(lambda: self._on_share("ig"))
        srow.addWidget(self.x_btn); srow.addWidget(self.fb_btn); srow.addWidget(self.wa_share_btn); srow.addWidget(self.ig_btn)
        sl.addLayout(srow)
        layout.addWidget(social_box)

        # 2. Main Copy CTA (Large & Vibrant)
        self.rec_btn = self._create_btn("COPY PROMO TEXT & LINKS ❤️", "#0A84FF", "#409CFF")
        self.rec_btn.setFixedHeight(50)
        self.rec_btn.setStyleSheet(self.rec_btn.styleSheet() + """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0A84FF, stop:1 #0070E0);
                font-size: 14px; font-weight: 800; border-radius: 12px;
            }
        """)
        self.rec_btn.clicked.connect(self._on_recommend)
        layout.addWidget(self.rec_btn)

        # 3. Direct Contact Section
        contact_box = QWidget()
        cl = QVBoxLayout(contact_box); cl.setContentsMargins(0,5,0,5); cl.setSpacing(10)
        contact_title = QLabel("DIRECT SUPPORT")
        contact_title.setStyleSheet("color: #8E8E93; font-family: 'SF Mono'; font-size: 10px; font-weight: 700; letter-spacing: 1.5px;")
        contact_title.setAlignment(Qt.AlignCenter)
        cl.addWidget(contact_title)

        crow = QHBoxLayout(); crow.setSpacing(10)
        self.tg_btn = self._create_btn("TELEGRAM", "#2C2C2E", "#3A3A3C", is_half=True)
        self.tg_btn.clicked.connect(self._on_telegram)
        self.wa_btn = self._create_btn("WHATSAPP", "#2C2C2E", "#3A3A3C", is_half=True)
        self.wa_btn.clicked.connect(self._on_whatsapp)
        crow.addWidget(self.tg_btn); crow.addWidget(self.wa_btn)
        cl.addLayout(crow)
        layout.addWidget(contact_box)

        layout.addStretch()

        # 4. Close (Bottom)
        self.close_btn = QPushButton("CLOSE WINDOW")
        self.close_btn.setCursor(Qt.PointingHandCursor); self.close_btn.setFixedHeight(30)
        self.close_btn.setStyleSheet("color: #48484A; font-family: 'PT Root UI'; font-size: 11px; font-weight: 600; border: none; background: transparent;")
        self.close_btn.clicked.connect(self.reject)
        layout.addWidget(self.close_btn, 0, Qt.AlignCenter)

        if parent:
            center = parent.geometry().center()
            self.move(center.x() - self.width() // 2, center.y() - self.height() // 2)

    def _create_btn(self, text: str, bg: str, hover: str, is_half: bool = False) -> QPushButton:
        btn = QPushButton(text)
        if not is_half: btn.setFixedHeight(46)
        else: btn.setFixedHeight(44)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {bg};
                border: none;
                border-radius: 12px;
                color: #FFFFFF;
                font-family: 'PT Root UI';
                font-size: 13px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }}
            QPushButton:hover {{ background: {hover}; }}
        """)
        return btn

    def _on_telegram(self):
        import webbrowser
        webbrowser.open("https://t.me/+OsHHWTSv_bVkZTM0")

    def _on_whatsapp(self):
        import webbrowser
        webbrowser.open("https://wa.me/212663007212")

    def _on_share(self, platform: str):
        import webbrowser
        from urllib.parse import quote
        
        msg = ("supportina bach nkmlo lkhdma ela l app, ana khdam b had l app w kt3awni bach njm3 w nsyft Bewerbungen, "
               "dkhl l goupe telegram w atfhm klchi, merci : https://t.me/+OsHHWTSv_bVkZTM0 w dkhl lien bach "
               "telechargiha direct : https://github.com/whbexc/Zugzwang/releases")
        
        if platform == "x":
            # Share on X (Twitter)
            url = f"https://twitter.com/intent/tweet?text={quote(msg)}"
            webbrowser.open(url)
        elif platform == "fb":
            # Share on Facebook
            # Note: FB sharer primarily uses the 'u' (URL) but 'quote' works for the text body in some contexts
            url = f"https://www.facebook.com/sharer/sharer.php?u=https://github.com/whbexc/Zugzwang/releases&quote={quote(msg)}"
            webbrowser.open(url)
        elif platform == "wa":
            # Share on WhatsApp
            url = f"https://wa.me/?text={quote(msg)}"
            webbrowser.open(url)
        elif platform == "ig":
            # Instagram Fallback: Copy to clipboard and open IG
            from PySide6.QtGui import QGuiApplication
            QGuiApplication.clipboard().setText(msg)
            self.rec_btn.setText("TEXT COPIED! OPENING INSTAGRAM...")
            from PySide6.QtCore import QTimer
            QTimer.singleShot(2000, lambda: self.rec_btn.setText("COPY PROMO LINK & TEXT"))
            webbrowser.open("https://www.instagram.com/")

    def _on_recommend(self):
        from PySide6.QtGui import QClipboard, QGuiApplication
        from PySide6.QtCore import QTimer
        
        msg = ("supportina bach nkmlo lkhdma ela l app, ana khdam b had l app w kt3awni bach njm3 w nsyft Bewerbungen, "
               "dkhl l goupe telegram w atfhm klchi, merci : https://t.me/+OsHHWTSv_bVkZTM0 w dkhl lien bach "
               "telechargiha direct : https://github.com/whbexc/Zugzwang/releases")
        
        QGuiApplication.clipboard().setText(msg)
        self.rec_btn.setText("PROMO TEXT COPIED!")
        QTimer.singleShot(2500, lambda: self.rec_btn.setText("COPY PROMO LINK & TEXT"))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

class MacSwitch(QWidget):
    """Premium macOS-style toggle switch with smooth animations."""
    toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(34, 20)
        self.setCursor(Qt.PointingHandCursor)
        self._checked = False
        
        self._on_color = QColor("#30D158")
        self._thumb_x = 2.0
        self._anim = QPropertyAnimation(self, b"thumb_x", self)
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.OutBack)

    def setOnColor(self, color: str | QColor):
        self._on_color = QColor(color)
        self.update()

    @Property(float)
    def thumb_x(self):
        return self._thumb_x

    @thumb_x.setter
    def thumb_x(self, x: float):
        self._thumb_x = x
        self.update()

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool):
        self._checked = checked
        self._anim.stop()
        self._anim.setEndValue(16.0 if checked else 2.0)
        self._anim.start()
        self.update()

    def setEnabled(self, enabled: bool):
        super().setEnabled(enabled)
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.isEnabled():
            self.setChecked(not self._checked)
            self.toggled.emit(self._checked)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        track_color = self._on_color if self._checked else QColor("#3A3A3C")
        if not self.isEnabled():
            track_color.setAlpha(128)
        painter.setBrush(QBrush(track_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, 34, 20, 10, 10)

        thumb_rect = QRectF(self._thumb_x, 2, 16, 16)
        painter.setBrush(QBrush(QColor(0, 0, 0, 40)))
        painter.drawEllipse(thumb_rect.translated(0, 1))
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        painter.drawEllipse(thumb_rect)
        painter.end()



