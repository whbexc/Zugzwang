import typing
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect, QSize, QUrl
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QDesktopServices, QKeySequence, QBrush
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QFrame, 
    QPushButton, QWidget, QGraphicsOpacityEffect
)
from .theme import Theme
from ..changelog import CHANGELOG, CHANGELOG_AR, APP_VERSION
from ..core.config import config_manager
from ..core.i18n import get_language, is_rtl

class HoverChangeRow(QFrame):
    """A row that highlights on hover."""
    def __init__(self, pill_widget, text_widget, is_rtl: bool, parent=None):
        super().__init__(parent)
        self.setFixedHeight(34)
        self.setStyleSheet("""
            HoverChangeRow {
                background: transparent;
                border-radius: 6px;
            }
            HoverChangeRow:hover {
                background: rgba(255, 255, 255, 0.03);
            }
        """)
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 0, 8, 0)
        row.setSpacing(10)
        
        # Flex layout: vertically center align items
        txt_wrapper = QWidget()
        txt_layout = QVBoxLayout(txt_wrapper)
        txt_layout.setContentsMargins(0, 0, 0, 0)
        txt_layout.addWidget(text_widget, 0, Qt.AlignVCenter)

        if is_rtl:
            row.addWidget(txt_wrapper, 1, Qt.AlignVCenter)
            row.addWidget(pill_widget, 0, Qt.AlignVCenter)
        else:
            row.addWidget(pill_widget, 0, Qt.AlignVCenter)
            row.addWidget(txt_wrapper, 1, Qt.AlignVCenter)

class WhatsNewDialog(QDialog):
    def __init__(self, current_version: str = APP_VERSION, parent=None):
        super().__init__(parent)
        self.current_version = current_version
        self._language = get_language(config_manager.settings.app_language)
        self._is_rtl = is_rtl(self._language)
        self._changelog_data = CHANGELOG_AR if self._language == "ar" else CHANGELOG
        
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Cover the whole parent to draw the backdrop
        if parent:
            self.resize(parent.size())
        else:
            self.resize(1000, 800)
            
        self._build_ui()
        self._start_animations()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'main_container'):
            cx = self.width() // 2 - 260
            cy = self.height() // 2 - 310
            self.main_container.move(cx, cy)

    def paintEvent(self, event):
        # Draw the semi-transparent backdrop
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 166)) # ~0.65 opacity black
        painter.end()

    def _build_ui(self):
        # ── 1. DIALOG CONTAINER ─────────────────────────────────────
        self.main_container = QFrame(self)
        self.main_container.setFixedSize(520, 620)
        self.main_container.setStyleSheet("""
            QFrame#MainContainer {
                background-color: #1C1C1E;
                border-radius: 16px;
                border: 1px solid #3A3A3C;
            }
        """)
        self.main_container.setObjectName("MainContainer")
        
        cx = self.width() // 2 - 260
        cy = self.height() // 2 - 310
        self.main_container.move(cx, cy)
        
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(0.0)
        self.main_container.setGraphicsEffect(self.opacity_effect)

        # We clip children inside the main container
        container_layout = QVBoxLayout(self.main_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # ── 2. HEADER ──────────────────────────────────────────────
        header = QFrame()
        header.setStyleSheet("background: transparent; border: none;")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(28, 28, 28, 0)
        header_layout.setSpacing(0)

        top_row = QFrame()
        top_row.setFixedHeight(32)
        
        # Absolute close button
        close_btn = QPushButton("✕", top_row)
        close_btn.setFixedSize(16, 16)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: none; color: #8E8E93;
                font-family: 'SF Pro Display', sans-serif; font-size: 14px; font-weight: bold; padding: 0;
            }
            QPushButton:hover { color: #FFFFFF; }
        """)
        close_btn.clicked.connect(self.close_animated)
        close_btn.move(520 - 28 - 16, 0) # align with 28px padding right

        icon_title_layout = QHBoxLayout(top_row)
        icon_title_layout.setContentsMargins(0, 0, 0, 0)
        icon_title_layout.setSpacing(12)

        self.sparkle_label = QLabel("✦")
        self.sparkle_label.setFixedSize(32, 32)
        self.sparkle_label.setAlignment(Qt.AlignCenter)
        self.sparkle_label.setStyleSheet("color: #0A84FF; font-size: 32px; background: transparent; border: none;")

        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(3)
        
        self.title_label = QLabel("What's New")
        self.title_label.setStyleSheet("color: #FFFFFF; font-family: 'Zariantz', '-apple-system', 'SF Pro Display', sans-serif; font-size: 24px; font-weight: 600; background: transparent; border: none;")
        
        self.subtitle_label = QLabel(f"ZUGZWANG v{self.current_version}")
        self.subtitle_label.setStyleSheet("color: #636366; font-family: 'SF Mono', monospace; font-size: 11px; background: transparent; border: none;")
        
        title_col.addWidget(self.title_label)
        
        if self._is_rtl:
            icon_title_layout.addStretch()
            icon_title_layout.addLayout(title_col)
            icon_title_layout.addWidget(self.sparkle_label)
            self.title_label.setAlignment(Qt.AlignRight)
            self.subtitle_label.setAlignment(Qt.AlignRight)
            self.title_label.setText("ما الجديد")
            self.subtitle_label.setText(f"ZUGZWANG الإصدار {self.current_version}")
        else:
            icon_title_layout.addWidget(self.sparkle_label)
            icon_title_layout.addLayout(title_col)
            icon_title_layout.addStretch()

        header_layout.addWidget(top_row)
        
        # Subtitle positioning hack (to align it starting under the title text, not the icon)
        sub_container = QHBoxLayout()
        sub_container.setContentsMargins(44 if not self._is_rtl else 0, 3, 44 if self._is_rtl else 0, 0)
        sub_container.addWidget(self.subtitle_label)
        if not self._is_rtl: sub_container.addStretch()
        else: sub_container.insertStretch(0)
        header_layout.addLayout(sub_container)

        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet("background: #3A3A3C; border: none; margin-top: 20px;")
        header_layout.addWidget(div)

        container_layout.addWidget(header)

        # ── 6. SCROLLABLE CONTENT ───────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFixedWidth(520) # Constrain exactly
        scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                width: 4px;
                background: transparent;
                margin: 4px 0;
            }
            QScrollBar::handle:vertical {
                background: #3A3A3C;
                border-radius: 2px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #48484A;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
            QWidget#ScrollContent {
                background: transparent;
            }
        """)

        content = QWidget()
        content.setObjectName("ScrollContent")
        content.setFixedWidth(520)
        self.list_layout = QVBoxLayout(content)
        self.list_layout.setContentsMargins(28, 20, 28, 20)
        self.list_layout.setSpacing(0)
        
        self._populate_changelog()
        
        scroll.setWidget(content)
        container_layout.addWidget(scroll, 1)

        # ── 8. FOOTER ───────────────────────────────────────────────
        footer = QFrame()
        footer.setStyleSheet("background: transparent; border: none;")
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(28, 0, 28, 14)
        footer_layout.setSpacing(14)

        div_foot = QFrame()
        div_foot.setFixedHeight(1)
        div_foot.setStyleSheet("background: #3A3A3C; border: none;")
        footer_layout.addWidget(div_foot)

        # ── Option 3: The What's New Supporter Footer ──────────────────────
        support_box = QFrame()
        support_box.setStyleSheet("background: rgba(10, 132, 255, 0.08); border-radius: 8px;")
        sb_layout = QHBoxLayout(support_box)
        sb_layout.setContentsMargins(12, 10, 12, 10)
        sb_layout.setSpacing(10)
        
        sb_icon = QLabel("💖")
        sb_icon.setStyleSheet("background: transparent; border: none; font-size: 14px;")
        sb_layout.addWidget(sb_icon)
        
        sb_text = QLabel("ZUGZWANG is free and built with endless coffee.\nGot leads? Consider supporting the development!")
        sb_text.setStyleSheet("color: #4EA1FF; font-size: 11px; font-family: 'PT Root UI', 'SF Pro Text', sans-serif; background: transparent; border: none;")
        sb_layout.addWidget(sb_text, 1)
        
        sb_btn = QPushButton("☕ Support")
        sb_btn.setCursor(Qt.PointingHandCursor)
        sb_btn.setStyleSheet("""
            QPushButton {
                background: rgba(10, 132, 255, 0.15);
                color: #0A84FF;
                border: 1px solid rgba(10, 132, 255, 0.3);
                border-radius: 6px;
                padding: 4px 10px;
                font-family: 'PT Root UI', sans-serif;
                font-weight: 600;
                font-size: 10px;
            }
            QPushButton:hover { background: rgba(10, 132, 255, 0.25); border: 1px solid rgba(10, 132, 255, 0.5); }
        """)
        sb_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://wa.me/212663007212?text=slm%20khoya%20khdmt%20b%20app%20dylk%20w%20bghit%20n%20supportik,")))
        sb_layout.addWidget(sb_btn)
        
        footer_layout.addWidget(support_box)

        foot_row = QHBoxLayout()
        foot_row.setContentsMargins(0, 0, 0, 0)
        foot_row.setSpacing(0)
        
        view_text = "عرض سجل التغييرات الكامل ←" if self._language == "ar" else "View full changelog →"
        view_full = QPushButton(view_text)
        view_full.setCursor(Qt.PointingHandCursor)
        view_full.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #48484A;
                border: none;
                font-family: 'Zariantz', '-apple-system', 'SF Pro Text', sans-serif;
                font-size: 12px;
                text-align: left;
                padding: 0;
            }
            QPushButton:hover { color: #8E8E93; }
        """)
        view_full.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/whbexc/Zugzwang")))
        
        got_it_text = "حسناً" if self._language == "ar" else "GOT IT"
        self.got_it_btn = QPushButton(got_it_text)
        self.got_it_btn.setCursor(Qt.PointingHandCursor)
        self.got_it_btn.setFixedHeight(34)
        self.got_it_btn.setStyleSheet("""
            QPushButton {
                background: #0A84FF;
                color: white;
                border: none;
                border-radius: 8px;
                font-family: 'Zariantz', '-apple-system', 'SF Pro Semibold', sans-serif;
                font-size: 12px;
                font-weight: 600;
                letter-spacing: 1.2px;
                text-transform: uppercase;
                padding: 0 20px;
            }
            QPushButton:hover { background: #409CFF; }
        """)
        self.got_it_btn.clicked.connect(self.close_animated)
        
        if self._is_rtl:
            foot_row.addWidget(self.got_it_btn)
            foot_row.addStretch()
            foot_row.addWidget(view_full)
        else:
            foot_row.addWidget(view_full)
            foot_row.addStretch()
            foot_row.addWidget(self.got_it_btn)

        footer_layout.addLayout(foot_row)
        container_layout.addWidget(footer)

    def _populate_changelog(self):
        for i, version_data in enumerate(self._changelog_data):
            # ── 7. VERSION BLOCK SPACING (Separator above versions except first)
            if i > 0:
                sep = QFrame()
                sep.setFixedHeight(1)
                sep.setStyleSheet("background: #2C2C2E; border: none; margin: 16px 0;")
                self.list_layout.addWidget(sep)
            
            self._build_version_block(version_data)
        
        self.list_layout.addStretch()

    def _build_version_block(self, data):
        # ── 4. VERSION HEADERS
        hdr_widget = QWidget()
        hdr = QHBoxLayout(hdr_widget)
        hdr.setContentsMargins(0, 0, 0, 10) # 10px below header before items
        hdr.setSpacing(8)

        v_lbl = QLabel(data["version"] if self._language == "ar" else "v" + data["version"])
        v_lbl.setStyleSheet("color: #FFFFFF; font-family: 'Zariantz', '-apple-system', 'SF Pro Display', sans-serif; font-size: 17px; font-weight: 500; background: transparent; border: none;")
        
        lbl_badge = None
        if data.get("label"):
            lbl_badge = QLabel(data["label"].upper())
            # "LATEST" badge: transparent inline with 1px border
            lbl_badge.setStyleSheet("""
                QLabel {
                    background: transparent;
                    border: 1px solid #30D158;
                    color: #30D158;
                    font-family: 'Zariantz', '-apple-system', 'SF Pro Semibold', sans-serif;
                    font-size: 9px;
                    font-weight: 600;
                    letter-spacing: 1.4px;
                    text-transform: uppercase;
                    border-radius: 5px;
                    padding: 2px 8px;
                    height: 18px;
                }
            """)
            lbl_badge.setFixedHeight(18)
        
        d_lbl = QLabel(data["date"])
        d_lbl.setStyleSheet("color: #636366; font-family: 'Zariantz', '-apple-system', 'SF Pro Text', sans-serif; font-size: 12px; background: transparent; border: none;")
        
        if self._is_rtl:
            hdr.addWidget(d_lbl, 0, Qt.AlignVCenter)
            hdr.addStretch()
            if lbl_badge: hdr.addWidget(lbl_badge, 0, Qt.AlignVCenter)
            hdr.addWidget(v_lbl, 0, Qt.AlignVCenter)
        else:
            hdr.addWidget(v_lbl, 0, Qt.AlignVCenter)
            if lbl_badge: hdr.addWidget(lbl_badge, 0, Qt.AlignVCenter)
            hdr.addStretch()
            hdr.addWidget(d_lbl, 0, Qt.AlignVCenter)

        self.list_layout.addWidget(hdr_widget)

        # ── 3 & 5 & 7. CHANGE ITEM ROWS
        items_container = QWidget()
        items_layout = QVBoxLayout(items_container)
        items_layout.setContentsMargins(0, 0, 0, 0)
        items_layout.setSpacing(4) # 4px gap between items

        for change in data.get("changes", []):
            c_type = change["type"].lower()
            if c_type == "new":
                c_clr = "#30D158"
                rgba_bg = "rgba(48,209,88,0.12)"
                rgba_border = "rgba(48,209,88,0.35)"
            elif c_type == "improved":
                c_clr = "#0A84FF"
                rgba_bg = "rgba(10,132,255,0.12)"
                rgba_border = "rgba(10,132,255,0.35)"
            elif c_type == "fixed":
                c_clr = "#FF9F0A"
                rgba_bg = "rgba(255,159,10,0.12)"
                rgba_border = "rgba(255,159,10,0.35)"
            elif c_type == "removed" or c_type == "deleted":
                c_clr = "#FF453A"
                rgba_bg = "rgba(255,69,58,0.12)"
                rgba_border = "rgba(255,69,58,0.35)"
            else:
                c_clr = "#8E8E93"
                rgba_bg = "rgba(142,142,147,0.12)"
                rgba_border = "rgba(142,142,147,0.35)"

            type_label = data.get("type_labels", {}).get(c_type, c_type.upper())

            # ── 3. CHANGE TYPE BADGES
            pill = QLabel(type_label)
            pill.setAlignment(Qt.AlignCenter)
            pill.setFixedSize(64, 20)
            pill.setStyleSheet(f"""
                QLabel {{
                    background: {rgba_bg};
                    border: 1px solid {rgba_border};
                    border-radius: 4px;
                    color: {c_clr};
                    font-family: 'Zariantz', '-apple-system', 'SF Pro Semibold', sans-serif;
                    font-size: 9px;
                    font-weight: 600;
                    letter-spacing: 1.2px;
                    text-transform: uppercase;
                }}
            """)
            
            txt = QLabel(change["text"])
            txt.setWordWrap(True)
            txt.setStyleSheet("color: #AEAEB2; font-family: 'Zariantz', '-apple-system', 'SF Pro Text', sans-serif; font-size: 13px; line-height: 1.4; background: transparent; border: none;")
            if self._is_rtl:
                txt.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            else:
                txt.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                
            row_widget = HoverChangeRow(pill, txt, self._is_rtl)
            items_layout.addWidget(row_widget)
            
        self.list_layout.addWidget(items_container)

    def _start_animations(self):
        self.fade_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_anim.setDuration(200)
        self.fade_anim.setStartValue(0.0)
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.setEasingCurve(QEasingCurve.InOutQuad)
        
        self.geom_anim = QPropertyAnimation(self.main_container, b"geometry")
        self.geom_anim.setDuration(250)
        self.geom_anim.setEasingCurve(QEasingCurve.OutBack)
        
        cx, cy = self.width() // 2, self.height() // 2
        # 95% start
        sw, sh = int(520 * 0.95), int(620 * 0.95)
        start_rect = QRect(cx - sw//2, cy - sh//2, sw, sh)
        end_rect = QRect(cx - 260, cy - 310, 520, 620)
        
        self.geom_anim.setStartValue(start_rect)
        self.geom_anim.setEndValue(end_rect)
        
        self.main_container.setGeometry(start_rect)
        
        self.fade_anim.start()
        self.geom_anim.start()

    def close_animated(self):
        self.fade_out = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_out.setDuration(120)
        self.fade_out.setStartValue(1.0)
        self.fade_out.setEndValue(0.0)
        self.fade_out.setEasingCurve(QEasingCurve.OutQuad)
        
        # Fade backdrop manually or just close immediately
        self.fade_out.finished.connect(self.accept)
        self.fade_out.start()

