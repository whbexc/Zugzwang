import typing
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect, QSize, QUrl
from PySide6.QtGui import QColor, QFont, QIcon, QPixmap, QPainter, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QFrame, 
    QPushButton, QWidget, QGraphicsOpacityEffect
)
from qfluentwidgets import FluentIcon, IconWidget
from .theme import Theme
from ..changelog import CHANGELOG, CHANGELOG_AR, APP_VERSION
from ..core.config import config_manager
from ..core.i18n import get_language, is_rtl

class WhatsNewDialog(QDialog):
    def __init__(self, current_version: str = APP_VERSION, parent=None):
        super().__init__(parent)
        self.current_version = current_version
        self._language = get_language(config_manager.settings.app_language)
        self._is_rtl = is_rtl(self._language)
        
        # Select appropriate changelog
        self._changelog_data = CHANGELOG_AR if self._language == "ar" else CHANGELOG
        
        self._setup_window()
        self._build_ui()
        self._start_animations()

    def _toggle_language(self):
        """Toggle between English and Arabic."""
        # Switch language
        new_lang = "en" if self._language == "ar" else "ar"
        self._language = new_lang
        self._is_rtl = is_rtl(new_lang)
        self._changelog_data = CHANGELOG_AR if new_lang == "ar" else CHANGELOG
        
        # Rebuild body
        self._update_ui_texts()
        self._clear_layout(self.list_layout)
        self._populate_changelog()
        
    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _update_ui_texts(self):
        # Update title/subtitle
        title_text = "ما الجديد" if self._language == "ar" else "What's New"
        self.title_label.setText(title_text)
        self.title_label.setAlignment(Qt.AlignRight if self._is_rtl else Qt.AlignLeft)
        
        sub_text = f"ZUGZWANG الإصدار {self.current_version}" if self._language == "ar" else f"ZUGZWANG v{self.current_version}"
        self.subtitle_label.setText(sub_text)
        self.subtitle_label.setAlignment(Qt.AlignRight if self._is_rtl else Qt.AlignLeft)
        
        # Update button
        btn_text = "حسناً" if self._language == "ar" else "GOT IT"
        self.got_it_btn.setText(btn_text)
        
        # Reshuffle header layout WITHOUT deleting widgets
        # We manually take items out to avoid deleteLater()
        while self.top_row_layout.count():
            self.top_row_layout.takeAt(0)
            
        if self._is_rtl:
            self.top_row_layout.addStretch()
            self.top_row_layout.addLayout(self.title_col_layout)
            self.top_row_layout.addWidget(self.sparkle_label, 0, Qt.AlignTop)
        else:
            self.top_row_layout.addWidget(self.sparkle_label, 0, Qt.AlignTop)
            self.top_row_layout.addLayout(self.title_col_layout)
            self.top_row_layout.addStretch()

    def _setup_window(self):
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(520, 600)

    def _build_ui(self):
        # Main container with border radius and background
        self.main_container = QFrame(self)
        self.main_container.setFixedSize(self.size())
        self.main_container.setStyleSheet("""
            QFrame {
                background-color: #1C1C1E;
                border-radius: 16px;
                border: 1px solid #3A3A3C;
            }
        """)
        
        # Apply opacity effect for fade animation
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self.opacity_effect)

        layout = QVBoxLayout(self.main_container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── HEADER ──────────────────────────────────────────────
        header = QFrame()
        header.setStyleSheet("background: transparent; border: none;")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(28, 28, 28, 0)
        header_layout.setSpacing(0)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(12)

        # Sparkle icon
        self.sparkle_label = QLabel("✦")
        self.sparkle_label.setStyleSheet("color: #0A84FF; font-size: 32px; font-weight: bold; background: transparent; border: none;")

        # Titles
        self.title_col_layout = QVBoxLayout()
        self.title_col_layout.setContentsMargins(0, 0, 0, 0)
        self.title_col_layout.setSpacing(4)
        
        self.title_label = QLabel("")
        self.title_label.setStyleSheet("color: #FFFFFF; font-family: '-apple-system', 'SF Pro Display', sans-serif; font-size: 24px; font-weight: 600; background: transparent; border: none;")
        self.title_col_layout.addWidget(self.title_label)
        
        self.subtitle_label = QLabel("")
        self.subtitle_label.setStyleSheet("color: #636366; font-family: 'SF Mono', monospace; font-size: 12px; background: transparent; border: none;")
        self.title_col_layout.addWidget(self.subtitle_label)
        
        self.top_row_layout = top_row
        
        # Add globe/language button
        lang_btn = QPushButton()
        lang_btn.setFixedSize(32, 32)
        lang_btn.setCursor(Qt.PointingHandCursor)
        lang_btn.setToolTip("Toggle Language / تبديل اللغة")
        
        # Add icon to button
        icon_wrapper = QHBoxLayout(lang_btn)
        icon_wrapper.setContentsMargins(0, 0, 0, 0)
        globe_icon = IconWidget(FluentIcon.GLOBE, lang_btn)
        globe_icon.setFixedSize(16, 16)
        globe_icon.setStyleSheet("background: transparent; border: none; color: #FFFFFF;")
        icon_wrapper.addWidget(globe_icon, 0, Qt.AlignCenter)

        lang_btn.setStyleSheet("""
            QPushButton {
                background: #2C2C2E; border: 1px solid #3A3A3C;
                border-radius: 16px;
            }
            QPushButton:hover { background: #3A3A3C; border-color: #4A4A4C; }
        """)
        lang_btn.clicked.connect(self._toggle_language)
        
        # Close Button
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: none; color: #636366;
                font-size: 14px; font-weight: bold;
            }
            QPushButton:hover { color: #FFFFFF; }
        """)
        close_btn.clicked.connect(self.accept)

        # Header Control Row (Language + Close)
        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 20, 0)
        controls.setSpacing(10)
        controls.addStretch()
        controls.addWidget(lang_btn)
        controls.addWidget(close_btn)
        header_layout.addLayout(controls)

        header_layout.addLayout(top_row)
        
        # Hairline divider
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet("background: #3A3A3C; border: none; margin-top: 20px;")
        header_layout.addWidget(div)

        layout.addWidget(header)

        # ── SCROLLABLE CONTENT ───────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 4px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.15);
                border-radius: 2px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(255, 255, 255, 0.3);
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
        self.list_layout = QVBoxLayout(content)
        self.list_layout.setContentsMargins(28, 20, 28, 20)
        self.list_layout.setSpacing(0)
        
        self._populate_changelog()

        # self.list_layout.addStretch()  <- Removed as stretch is in _populate_changelog
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        # ── FOOTER ───────────────────────────────────────────────
        footer = QFrame()
        footer.setStyleSheet("background: transparent; border: none;")
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(28, 0, 28, 16)
        footer_layout.setSpacing(16)

        div_foot = QFrame()
        div_foot.setFixedHeight(1)
        div_foot.setStyleSheet("background: #3A3A3C; border: none;")
        footer_layout.addWidget(div_foot)

        foot_row = QHBoxLayout()
        foot_row.setContentsMargins(0, 0, 0, 0)
        
        view_text = "عرض سجل التغييرات الكامل ←" if self._language == "ar" else "View full changelog →"
        view_full = QPushButton(view_text)
        view_full.setCursor(Qt.PointingHandCursor)
        view_full.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #636366;
                border: none;
                font-family: '-apple-system', 'SF Pro Text', sans-serif;
                font-size: 12px;
                text-align: left;
            }
            QPushButton:hover {
                color: #0A84FF;
            }
        """)
        view_full.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/whbexc/Zugzwang")))
        if not self._is_rtl:
            foot_row.addWidget(view_full)
            foot_row.addStretch()
        
        got_it_text = "حسناً" if self._language == "ar" else "GOT IT"
        self.got_it_btn = QPushButton(got_it_text)
        self.got_it_btn.setCursor(Qt.PointingHandCursor)
        self.got_it_btn.setMinimumSize(80, 36)
        self.got_it_btn.setStyleSheet("""
            QPushButton {
                background: #0A84FF;
                color: white;
                border: none;
                border-radius: 8px;
                font-family: '-apple-system', 'SF Pro Display', sans-serif;
                font-size: 12px;
                font-weight: 600;
                letter-spacing: 1.4px;
                padding: 6px 16px;
                padding-bottom: 8px;
            }
            QPushButton:hover {
                background: #409CFF;
            }
        """)
        self.got_it_btn.clicked.connect(self.close_animated)
        
        if self._is_rtl:
            foot_row.addWidget(self.got_it_btn)
            foot_row.addStretch()
            foot_row.addWidget(view_full)
        else:
            foot_row.addWidget(self.got_it_btn)

        footer_layout.addLayout(foot_row)
        layout.addWidget(footer)
        
        self._update_ui_texts()

    def _populate_changelog(self):
        """Populate the vertical list with version blocks."""
        for i, version_data in enumerate(self._changelog_data):
            self._build_version_block(version_data, self.list_layout)
            # Separator removed as per user request
        
        self.list_layout.addStretch()

    def _build_version_block(self, data, parent_layout):
        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        hdr.setSpacing(10)

        v_lbl = QLabel(data["version"] if self._language == "ar" else "v" + data["version"])
        v_lbl.setStyleSheet("color: #FFFFFF; font-family: '-apple-system', 'SF Pro Display', sans-serif; font-size: 20px; font-weight: 700; background: transparent; border: none;")
        
        lbl_badge = None
        if data.get("label"):
            l_color = data.get("label_color", "#8E8E93")
            lbl_badge = QLabel(data["label"])
            lbl_badge.setStyleSheet(f"""
                QLabel {{
                    background: transparent;
                    border: 1px solid {l_color};
                    color: {l_color};
                    font-family: '-apple-system', 'SF Pro Display', sans-serif;
                    font-size: 10px;
                    font-weight: 600;
                    letter-spacing: 1.4px;
                    border-radius: 6px;
                    padding: 2px 8px;
                }}
            """)
        
        d_lbl = QLabel(data["date"])
        d_lbl.setStyleSheet("color: #636366; font-family: '-apple-system', 'SF Pro Text', sans-serif; font-size: 12px; background: transparent; border: none;")
        
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

        parent_layout.addLayout(hdr)

        for change in data.get("changes", []):
            row = QHBoxLayout()
            row.setContentsMargins(0, 12, 0, 0)
            row.setSpacing(10)

            c_type = change["type"].lower()
            if c_type == "new":
                c_clr = "#30D158"
                rgba_bg = "rgba(48,209,88,0.1)"
                rgba_border = "rgba(48,209,88,0.3)"
            elif c_type == "improved":
                c_clr = "#0A84FF"
                rgba_bg = "rgba(10,132,255,0.1)"
                rgba_border = "rgba(10,132,255,0.3)"
            elif c_type == "fixed":
                c_clr = "#FF9F0A"
                rgba_bg = "rgba(255,159,10,0.1)"
                rgba_border = "rgba(255,159,10,0.3)"
            elif c_type == "removed":
                c_clr = "#FF453A"
                rgba_bg = "rgba(255,69,58,0.1)"
                rgba_border = "rgba(255,69,58,0.3)"
            else:
                c_clr = "#8E8E93"
                rgba_bg = "rgba(142,142,147,0.1)"
                rgba_border = "rgba(142,142,147,0.3)"

            # Replace c_type with generic logic for localizing
            type_label = data.get("type_labels", {}).get(c_type, c_type.upper())

            pill = QLabel(type_label)
            pill.setAlignment(Qt.AlignCenter)
            pill.setMinimumWidth(44)
            pill.setStyleSheet(f"""
                QLabel {{
                    background: {rgba_bg};
                    border: 1px solid {rgba_border};
                    border-radius: 4px;
                    color: {c_clr};
                    font-family: 'SF Mono', monospace;
                    font-size: 10px;
                    font-weight: 600;
                    padding: 3px 6px;
                }}
            """)
            
            txt = QLabel(change["text"])
            txt.setWordWrap(True)
            txt.setStyleSheet("color: #AEAEB2; font-family: '-apple-system', 'SF Pro Text', sans-serif; font-size: 13px; line-height: 1.5; background: transparent; border: none;")
            if self._is_rtl:
                txt.setAlignment(Qt.AlignRight | Qt.AlignTop)
                row.addWidget(txt, 1, Qt.AlignTop)
                row.addWidget(pill, 0, Qt.AlignTop)
            else:
                row.addWidget(pill, 0, Qt.AlignTop)
                row.addWidget(txt, 1, Qt.AlignTop)

            parent_layout.addLayout(row)


    def _start_animations(self):
        # Fade In
        self.fade_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_anim.setDuration(200)
        self.fade_anim.setStartValue(0.0)
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.setEasingCurve(QEasingCurve.InOutQuad)
        
        # Scale In (simulate by animating geometry)
        self.geom_anim = QPropertyAnimation(self, b"geometry")
        self.geom_anim.setDuration(200)
        self.geom_anim.setEasingCurve(QEasingCurve.OutBack)
        
        screen_geo = self.parent().geometry() if self.parent() else QRect(0, 0, 1920, 1080)
        cx = screen_geo.center().x()
        cy = screen_geo.center().y()
        
        # 95% start
        sw, sh = int(520 * 0.95), int(600 * 0.95)
        start_rect = QRect(cx - sw//2, cy - sh//2, sw, sh)
        end_rect = QRect(cx - 260, cy - 300, 520, 600)
        
        self.geom_anim.setStartValue(start_rect)
        self.geom_anim.setEndValue(end_rect)
        
        self.setGeometry(start_rect) # Initial
        
        self.fade_anim.start()
        self.geom_anim.start()

    def close_animated(self):
        self.fade_out = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_out.setDuration(150)
        self.fade_out.setStartValue(1.0)
        self.fade_out.setEndValue(0.0)
        self.fade_out.setEasingCurve(QEasingCurve.OutQuad)
        self.fade_out.finished.connect(self.accept)
        self.fade_out.start()
