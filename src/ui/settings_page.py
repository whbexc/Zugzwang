"""
ZUGZWANG - Settings Page
Apple macOS System Preferences — Obsidian Edition.
"""

from __future__ import annotations
import re, os

from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QDoubleValidator, QColor, QPainter, QBrush
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QWidget, QGridLayout, QFrame,
    QLabel, QPushButton as _QPBtn, QScrollArea, QSizePolicy
)

from qfluentwidgets import (
    ElevatedCardWidget, StrongBodyLabel, BodyLabel, CaptionLabel,
    SpinBox, DoubleSpinBox, TextEdit,
    PrimaryPushButton, PushButton, FluentIcon, SearchLineEdit,
    LineEdit, InfoBar, IconWidget
)
from .components import MacSwitch, MacComboBox, StatCard, SectionCard, FlowLayout
from .theme import Theme

from ..core.config import config_manager
from ..core.i18n import SUPPORTED_LANGUAGES, get_language, tr
from ..services.orchestrator import orchestrator
from ..core.security import LicenseManager
from .theme import Theme


_PROXY_RE = re.compile(r"^(https?|socks5)://", re.IGNORECASE)

# ── Shared style helpers ─────────────────────────────────────────────────────
# Removed ad-hoc button styles in favor of Theme.primary/secondary/danger methods.


from .components import StatCard, SectionCard

class SettingsPage(QWidget):
    """Apple macOS System Preferences–style settings workspace."""

    def __init__(self):
        super().__init__()
        self._dirty = False
        self._cache_cleanup_in_progress = False
        self._language = get_language(config_manager.settings.app_language)
        self._original_state = {}
        self._build_ui()
        self._load_values()
        self._connect_change_tracking()
        self._update_deep_scan_state()
        config_manager.cache_cleanup_finished.connect(self._on_cache_cleanup_finished)

    # ── Widget Factories ─────────────────────────────────────────────────────

    def _row(self, title: str, widget: QWidget, caption: str = "", icon: FluentIcon = None) -> QWidget:
        """A standard macOS-style left-label / right-control row."""
        frame = QFrame()
        frame.setFixedHeight(48 if caption else 34)
        frame.setStyleSheet(
            "QFrame { background: transparent; border-radius: 4px; border: none; }"
        )
        hl = QHBoxLayout(frame)
        hl.setContentsMargins(12, 4, 12, 4)
        hl.setSpacing(12)
        
        if icon:
            ic = IconWidget(icon)
            ic.setFixedSize(16, 16)
            ic.setStyleSheet("IconWidget { color: #8E8E93; } IconWidget:disabled { color: #3A3A3C; }")
            hl.addWidget(ic)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            "QLabel { color: white; font-family: 'PT Root UI', sans-serif; font-size: 14px; background: transparent; border: none; } "
            "QLabel:disabled { color: #4A4A4C; }"
        )
        text_col.addWidget(title_lbl)
        if caption:
            cap = QLabel(caption)
            cap.setStyleSheet(
                f"QLabel {{ color: {Theme.TEXT_SECONDARY}; font-size: 11px; background: transparent; border: none; }} "
                "QLabel:disabled { color: #3A3A3C; }"
            )
            cap.setWordWrap(True)
            text_col.addWidget(cap)

        hl.addLayout(text_col, 1)
        hl.addWidget(widget, 0, Qt.AlignVCenter | Qt.AlignRight)
        return frame

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(
            "color: #8E8E93; font-family: 'PT Root UI', sans-serif; font-size: 11px; font-weight: 600; "
            "letter-spacing: 1.6px; background: transparent; border: none;"
        )
        return lbl

    def _divider(self) -> QFrame:
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background: {Theme.BORDER_LIGHT}; border: none;")
        return div

    def _card(self, num: str, title: str, content: QWidget, has_divider: bool = True) -> QFrame:
        card = QFrame()
        card.setObjectName(f"StepCard{num}")
        card.setStyleSheet(f"QFrame#StepCard{num} {{ background: transparent; border-radius: 14px; border: 1px solid #2C2C2E; }}")
        vl = QVBoxLayout(card)
        vl.setContentsMargins(16, 18, 16, 18) # FIX 3: exact padding
        vl.setSpacing(10)

        # Header: blue numbered badge + uppercase title
        hdr = QHBoxLayout(); hdr.setSpacing(12)
        badge = QFrame(); badge.setObjectName(f"Badge{num}"); badge.setFixedSize(20, 20)
        badge.setStyleSheet(f"QFrame#Badge{num} {{ background: #0A84FF; border-radius: 10px; border: none; }}")
        bl = QHBoxLayout(badge); bl.setContentsMargins(0, 0, 0, 0)
        bn = QLabel(num); bn.setAlignment(Qt.AlignCenter)
        bn.setStyleSheet("color: white; font-family: 'PT Root UI', sans-serif; font-size: 11px; font-weight: 700; background: transparent; border: none;")
        bl.addWidget(bn)
        hdr.addWidget(badge)

        tl = QLabel(str(title).upper() if title else f"SECTION {num}")
        tl.setStyleSheet(
            "color: #8E8E93; font-family: 'PT Root UI', sans-serif; font-size: 11px; font-weight: 800; "
            "letter-spacing: 1.5px; background: transparent; border: none;"
        )
        hdr.addWidget(tl); hdr.addStretch()
        vl.addLayout(hdr)

        if has_divider:
            div = QFrame(); div.setFixedHeight(1)
            div.setStyleSheet("background: #3A3A3C; border: none;")
            vl.addWidget(div)

        vl.addWidget(content, 1) # FIX 3: Content fills card
        return card

    def _sw(self) -> MacSwitch:
        s = MacSwitch()
        return s

    def _style_combo(self, combo: QWidget) -> None:
        combo.setStyleSheet("""
            QComboBox {
                background: #3A3A3C;
                border: 1px solid #4A4A4C;
                border-radius: 8px;
                color: #FFFFFF;
                font-family: 'PT Root UI', sans-serif;
                font-size: 12px;
                font-weight: 600;
                padding: 0 12px;
            }
            QComboBox:hover {
                border: 1px solid #5A5A5C;
            }
            QComboBox:focus {
                border: 1px solid #0A84FF;
            }
        """)

    def _style_input(self, widget: QWidget) -> None:
        if hasattr(widget, "setCustomFocusedBorderColor"):
            from PySide6.QtGui import QColor
            widget.setCustomFocusedBorderColor(QColor(0,0,0,0), QColor(0,0,0,0))
        widget.setStyleSheet("""
            LineEdit, QLineEdit, SearchLineEdit, TextEdit, QTextEdit {
                background-color: #252528;
                border: 1px solid #2C2C2E;
                border-radius: 8px;
                color: #FFFFFF;
                padding-left: 10px;
                padding-top: 4px;
                padding-bottom: 4px;
                font-family: 'PT Root UI', sans-serif;
                font-size: 13px;
                font-weight: 500;
            }
            LineEdit:focus, QLineEdit:focus, SearchLineEdit:focus, TextEdit:focus, QTextEdit:focus {
                border: 1px solid #0A84FF;
                background-color: #2C2C2E;
            }
            LineEdit:disabled, QLineEdit:disabled, SearchLineEdit:disabled, TextEdit:disabled, QTextEdit:disabled {
                background-color: #1C1C1E;
                color: #636366;
            }
        """)

    # ── Main Layout ──────────────────────────────────────────────────────────

    def _build_ui(self):
        self.setObjectName("SettingsPage")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.ClickFocus)
        self.setStyleSheet(f"QWidget#SettingsPage {{ background: {Theme.BG_OBSIDIAN}; }}")
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20) # FIX 3: Exact padding
        root.setSpacing(0) # Spacing handled by internal components


        # Top Row (3 columns)
        top_row = QHBoxLayout()
        top_row.setSpacing(12)
        top_row.addWidget(self._card("1", tr("settings.scraping.title", self._language),    self._build_scraping()))
        top_row.addWidget(self._card("2", tr("settings.email.title", self._language),   self._build_email()))
        top_row.addWidget(self._card("3", tr("settings.protection.title", self._language), self._build_protection()))

        # Bottom Row (2 columns, 50/50 split)
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(12)
        bottom_row.addWidget(self._card("4", "SYSTEM PREFERENCES", self._build_network()))
        bottom_row.addWidget(self._card("5", tr("settings.system", self._language), self._build_system()))

        # Grid Container (100vh behavior via flex: 1)
        grid_container = QWidget()
        grid_container.setStyleSheet("background: transparent;")
        gv = QVBoxLayout(grid_container)
        gv.setSpacing(12)
        gv.setContentsMargins(0, 0, 0, 0)
        gv.addLayout(top_row, 1)
        gv.addLayout(bottom_row, 1)
        
        root.addWidget(grid_container, 1)
        
        # FIX 1: Removed bottom bar, buttons moved to Section 5

    # ── Section Builders ─────────────────────────────────────────────────────

    def _build_scraping(self) -> QWidget:
        container = QWidget(); container.setStyleSheet("background: transparent;")
        vl = QVBoxLayout(container); vl.setContentsMargins(0, 0, 0, 0); vl.setSpacing(4)

        # 1. Browser Engine Selection
        self._engine_combo = MacComboBox()
        self._engine_combo.addItem("Chromium (Bundled)", "chromium")
        self._engine_combo.addItem("Google Chrome", "chrome")
        self._engine_combo.addItem("Microsoft Edge", "msedge")
        self._engine_combo.addItem("Apple Safari", "safari")
        self._engine_combo.addItem("Mozilla Firefox", "firefox")
        self._engine_combo.addItem("Brave Browser", "brave")
        self._engine_combo.addItem("Arc Browser", "arc")
        self._style_combo(self._engine_combo)
        self._engine_combo.currentIndexChanged.connect(self._on_engine_changed)

        # 2. Toggles (Headless + Robots) side-by-side
        self._chk_headless = self._sw()
        self._chk_robots   = self._sw()
        toggles_row = QHBoxLayout()
        toggles_row.setContentsMargins(0, 0, 0, 0); toggles_row.setSpacing(6)
        
        headless_frame = self._row(tr("settings.headless.title", self._language), self._chk_headless, icon=FluentIcon.COMMAND_PROMPT)
        robots_frame = self._row(tr("settings.robots.title", self._language), self._chk_robots, icon=FluentIcon.ROBOT)
        toggles_row.addWidget(headless_frame)
        toggles_row.addWidget(robots_frame)
        vl.addLayout(toggles_row)

        # 3. Inputs (LineEdits) all in one frame
        self._delay_min   = LineEdit(); self._delay_min.setFixedHeight(36)
        self._delay_max   = LineEdit(); self._delay_max.setFixedHeight(36)
        self._max_results = LineEdit(); self._max_results.setFixedHeight(36)
        self._max_retries = LineEdit(); self._max_retries.setFixedHeight(36)
        self._max_concurrent = LineEdit(); self._max_concurrent.setFixedHeight(36)
        
        dv = QDoubleValidator(0.5, 60.0, 1, self); dv.setNotation(QDoubleValidator.StandardNotation)
        iv = QDoubleValidator(5, 10000, 0, self); iv.setNotation(QDoubleValidator.StandardNotation)
        rv = QDoubleValidator(0, 10, 0, self); rv.setNotation(QDoubleValidator.StandardNotation)
        cv = QDoubleValidator(1, 20, 0, self); cv.setNotation(QDoubleValidator.StandardNotation)
        
        self._delay_min.setValidator(dv); self._delay_max.setValidator(dv); self._max_results.setValidator(iv)
        self._max_retries.setValidator(rv); self._max_concurrent.setValidator(cv)
        
        for widget in [self._delay_min, self._delay_max, self._max_results, self._max_retries, self._max_concurrent]:
            self._style_input(widget)

        spin_frame = QFrame()
        spin_frame.setStyleSheet(f"QFrame {{ background: {Theme.BG_HOVER_LIGHT}; border-radius: 8px; border: none; }}")
        spin_hl = QHBoxLayout(spin_frame); spin_hl.setContentsMargins(12, 11, 12, 11); spin_hl.setSpacing(12)
        for label_key, widget in [
            ("MIN", self._delay_min), 
            ("MAX", self._delay_max), 
            ("LIMIT", self._max_results),
            ("RETRY", self._max_retries),
            ("JOBS", self._max_concurrent)
        ]:
            col = QVBoxLayout(); col.setSpacing(4)
            l = QLabel(label_key); l.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 10px; font-weight: 700; background: transparent;")
            col.addWidget(l); col.addWidget(widget)
            spin_hl.addLayout(col)
        vl.addWidget(spin_frame)
        vl.addSpacing(2)

        # 4. Proxy + Rotate UA Toggles side-by-side
        self._chk_proxy = self._sw()
        self._chk_proxy.toggled.connect(self._on_proxy_toggled)
        self._chk_rotate_ua = self._sw()

        net_toggles_row = QHBoxLayout()
        net_toggles_row.setContentsMargins(0, 0, 0, 0); net_toggles_row.setSpacing(6)
        proxy_toggle_frame = self._row("Custom Proxy", self._chk_proxy, icon=FluentIcon.GLOBE)
        rotate_toggle_frame = self._row("Rotate UA", self._chk_rotate_ua, icon=FluentIcon.SYNC)
        net_toggles_row.addWidget(proxy_toggle_frame)
        net_toggles_row.addWidget(rotate_toggle_frame)
        vl.addLayout(net_toggles_row)

        # 5. Proxy URL/Port
        proxy_frame = QFrame()
        proxy_frame.setStyleSheet(f"QFrame {{ background: {Theme.BG_HOVER_LIGHT}; border-radius: 8px; border: none; }}")
        ph = QHBoxLayout(proxy_frame); ph.setContentsMargins(10, 8, 10, 8); ph.setSpacing(8)
        self._proxy_url  = SearchLineEdit(); self._proxy_url.setFixedHeight(30); self._proxy_url.setPlaceholderText("http://user:pass@proxy.com")
        self._proxy_port = LineEdit();       self._proxy_port.setFixedHeight(30); self._proxy_port.setPlaceholderText("8080"); self._proxy_port.setFixedWidth(70)
        self._style_input(self._proxy_url); self._style_input(self._proxy_port)
        ph.addWidget(self._proxy_url, 1); ph.addWidget(self._proxy_port)
        vl.addWidget(proxy_frame)

        # 6. User Agents
        ua_header = QHBoxLayout()
        ua_header.setSpacing(8)
        ua_header.addWidget(self._section_label("USER AGENTS POOL"))
        self._ua_count_lbl = QLabel("0 AGENTS")
        self._ua_count_lbl.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 10px; font-weight: 600; background: transparent; border: none;")
        ua_header.addWidget(self._ua_count_lbl)
        ua_header.addStretch()
        vl.addLayout(ua_header)

        self._user_agents = TextEdit()
        self._user_agents.setMinimumHeight(120)
        self._style_input(self._user_agents)
        vl.addWidget(self._user_agents)

        vl.addWidget(self._row("Browser Engine", self._engine_combo, icon=FluentIcon.APPLICATION))

        vl.addStretch()
        return container

    def _build_email(self) -> QWidget:
        container = QWidget(); container.setStyleSheet("background: transparent;")
        vl = QVBoxLayout(container); vl.setContentsMargins(0, 0, 0, 0); vl.setSpacing(4)

        # ── ROW 1: Toggle rows (no caption, tight) ───────────────────────────
        self._chk_scrape_emails = self._sw()
        self._chk_debug_screenshots = self._sw()

        vl.addWidget(self._row("Deep Scan", self._chk_scrape_emails, icon=FluentIcon.SEARCH))
        self._debug_out_frame = self._row("Debug Output", self._chk_debug_screenshots, icon=FluentIcon.DEVELOPER_TOOLS)
        vl.addWidget(self._debug_out_frame)

        # ── ROW 2: Discovery Paths ───────────────────────────────────────────
        paths_title = QLabel("DISCOVERY PATHS (COMMA SEPARATED)")
        paths_title.setStyleSheet(
            "color: #8E8E93; font-family: 'PT Root UI', sans-serif; "
            "font-size: 10px; font-weight: 600; letter-spacing: 1.3px; "
            "background: transparent; border: none; padding-left: 4px;"
        )
        vl.addSpacing(2)
        vl.addWidget(paths_title)

        self._discovery_paths_edit = TextEdit()
        self._discovery_paths_edit.setMinimumHeight(95)
        self._discovery_paths_edit.setPlaceholderText("impressum, kontakt, karriere...")
        self._style_input(self._discovery_paths_edit)
        vl.addWidget(self._discovery_paths_edit)

        # ── ROW 3: Depth + Timeout ───────────────────────────────────────────
        vl.addSpacing(6)
        depth_frame = QFrame()
        depth_frame.setStyleSheet(f"QFrame {{ background: {Theme.BG_HOVER_LIGHT}; border-radius: 8px; border: none; }}")
        depth_hl = QHBoxLayout(depth_frame); depth_hl.setContentsMargins(12, 8, 12, 8); depth_hl.setSpacing(16)

        self._max_depth = LineEdit(); self._max_depth.setFixedHeight(30); self._max_depth.setMinimumWidth(60)
        ddv = QDoubleValidator(1, 10, 0, self); ddv.setNotation(QDoubleValidator.StandardNotation)
        self._max_depth.setValidator(ddv)
        self._style_input(self._max_depth)

        self._disc_timeout = LineEdit(); self._disc_timeout.setFixedHeight(30); self._disc_timeout.setMinimumWidth(60)
        dtv = QDoubleValidator(5, 300, 0, self); dtv.setNotation(QDoubleValidator.StandardNotation)
        self._disc_timeout.setValidator(dtv)
        self._style_input(self._disc_timeout)

        for lbl_text, widget in [("DEPTH", self._max_depth), ("TIMEOUT (S)", self._disc_timeout)]:
            col = QVBoxLayout(); col.setSpacing(4)
            l = QLabel(lbl_text); l.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 10px; font-weight: 700; background: transparent;")
            col.addWidget(l); col.addWidget(widget)
            depth_hl.addLayout(col)
        depth_hl.addStretch()
        vl.addWidget(depth_frame)

        smtp_title = QLabel("SMTP CONFIGURATION")
        smtp_title.setStyleSheet(
            "color: #8E8E93; font-family: 'PT Root UI', sans-serif; "
            "font-size: 10px; font-weight: 600; letter-spacing: 1.3px; "
            "background: transparent; border: none; padding-left: 4px;"
        )
        vl.addSpacing(4)
        vl.addWidget(smtp_title)

        smtp_frame = QFrame()
        smtp_frame.setStyleSheet(f"QFrame {{ background: {Theme.BG_HOVER_LIGHT}; border-radius: 8px; border: none; }}")
        smtp_hl = QHBoxLayout(smtp_frame); smtp_hl.setContentsMargins(12, 8, 12, 8); smtp_hl.setSpacing(8)

        self._smtp_host_cfg = LineEdit()
        self._smtp_host_cfg.setFixedHeight(30)
        self._smtp_host_cfg.setPlaceholderText("smtp.gmail.com")
        self._style_input(self._smtp_host_cfg)

        self._smtp_port_cfg = LineEdit()
        self._smtp_port_cfg.setFixedHeight(30)
        self._smtp_port_cfg.setFixedWidth(60)
        self._smtp_port_cfg.setPlaceholderText("587")
        self._style_input(self._smtp_port_cfg)

        smtp_hl.addWidget(self._smtp_host_cfg, 1)
        smtp_hl.addWidget(self._smtp_port_cfg, 0)
        vl.addWidget(smtp_frame)

        self._chk_validate = self._sw()
        self._email_val_frame = self._row("Email Validation", self._chk_validate, icon=FluentIcon.MAIL)
        vl.addWidget(self._email_val_frame)

        vl.addStretch()
        return container

    # ── Discovery Paths management removed (handled entirely via TextEdit value) ──


    def _build_network(self) -> QWidget:
        """Repurposed as System Preferences to fix UI overlap."""
        container = QWidget(); container.setStyleSheet("background: transparent;")
        vl = QVBoxLayout(container); vl.setContentsMargins(0, 0, 0, 0); vl.setSpacing(8)

        conf_group = QFrame()
        conf_group.setObjectName("PrefGroup")
        conf_group.setStyleSheet("""
            QFrame#PrefGroup {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                          stop:0 rgba(44, 44, 46, 0.4),
                                          stop:1 rgba(28, 28, 30, 0.3));
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 14px;
            }
        """)
        conf_vl = QVBoxLayout(conf_group); conf_vl.setContentsMargins(16, 6, 16, 6); conf_vl.setSpacing(0)

        def _setting_row(icon: FluentIcon, title: str, description: str, widget: QWidget):
            row = QFrame()
            row.setStyleSheet("background: transparent; border: none;")
            row_hl = QHBoxLayout(row); row_hl.setContentsMargins(0, 8, 0, 8); row_hl.setSpacing(12)
            from qfluentwidgets import IconWidget
            ic = IconWidget(icon); ic.setFixedSize(16, 16); ic.setStyleSheet("color: #8E8E93;")
            row_hl.addWidget(ic)
            txt_vl = QVBoxLayout(); txt_vl.setSpacing(2); txt_vl.setContentsMargins(0, 0, 0, 0)
            t = QLabel(title); t.setStyleSheet("color: white; font-size: 13px; font-weight: 600;")
            d = QLabel(description); d.setStyleSheet("color: #8E8E93; font-size: 11px;")
            txt_vl.addWidget(t); txt_vl.addWidget(d)
            row_hl.addLayout(txt_vl, 1); row_hl.addWidget(widget)
            return row

        # 1. Auto Save
        self._chk_auto_save = self._sw()
        conf_vl.addWidget(_setting_row(FluentIcon.SAVE, "Auto Save", "Save settings automatically.", self._chk_auto_save))
        div3 = QFrame(); div3.setFixedHeight(1); div3.setStyleSheet("background: rgba(255, 255, 255, 0.04); margin: 0 10px;"); conf_vl.addWidget(div3)

        # 2. Job Notifications
        self._chk_notify = self._sw()
        conf_vl.addWidget(_setting_row(FluentIcon.RINGER, "Job Notifications", "Notify when scraping finishes.", self._chk_notify))
        div4 = QFrame(); div4.setFixedHeight(1); div4.setStyleSheet("background: rgba(255, 255, 255, 0.04); margin: 0 10px;"); conf_vl.addWidget(div4)

        # 3. Log Retention
        self._log_retention = MacComboBox()
        self._log_retention.setFixedWidth(120); self._log_retention.setFixedHeight(30)
        self._log_retention.addItems(["7 DAYS", "30 DAYS", "90 DAYS", "FOREVER"])
        self._style_combo(self._log_retention)
        conf_vl.addWidget(_setting_row(FluentIcon.HISTORY, "Log Retention", "How long to keep log files.", self._log_retention))
        div5 = QFrame(); div5.setFixedHeight(1); div5.setStyleSheet("background: rgba(255, 255, 255, 0.04); margin: 0 10px;"); conf_vl.addWidget(div5)

        self._default_export_dir = LineEdit(); self._default_export_dir.setFixedSize(280, 30)
        self._default_export_dir.setPlaceholderText("Browse...")
        self._default_export_dir.setReadOnly(True)
        self._default_export_dir.setFocusPolicy(Qt.NoFocus)
        self._default_export_dir.setCursor(Qt.PointingHandCursor)
        self._style_input(self._default_export_dir)
        
        def _browse_export_dir(event):
            from PySide6.QtWidgets import QFileDialog
            import os
            start_path = self._default_export_dir.text() or os.path.expanduser("~")
            path = QFileDialog.getExistingDirectory(self, "Select Export Directory", start_path)
            if path:
                self._default_export_dir.setText(path)
                
        self._default_export_dir.mousePressEvent = _browse_export_dir
        conf_vl.addWidget(_setting_row(FluentIcon.FOLDER, "Export Directory", "Default path for exports.", self._default_export_dir))

        vl.addWidget(conf_group)

        # ── Product License (moved from Card 3) ──────────────────────────────
        vl.addSpacing(8)
        lic_card = QFrame()
        lic_card.setObjectName("LicCard")
        lic_card.setStyleSheet(
            "QFrame#LicCard { background: rgba(48, 209, 88, 0.07); "
            "border: 1px solid rgba(48, 209, 88, 0.18); border-radius: 12px; }"
        )
        lic_hl = QHBoxLayout(lic_card); lic_hl.setContentsMargins(16, 12, 16, 12); lic_hl.setSpacing(12)
        
        l_ic = IconWidget(FluentIcon.CERTIFICATE.icon(color=QColor("#30D158")))
        l_ic.setFixedSize(16, 16)
        lic_hl.addWidget(l_ic)
        
        lic_lt = QVBoxLayout(); lic_lt.setSpacing(2); lic_lt.setContentsMargins(0, 0, 0, 0)
        lic_lbl = QLabel("PRODUCT LICENSE")
        lic_lbl.setStyleSheet("color: rgba(48, 209, 88, 0.95); font-size: 10px; font-weight: 800; letter-spacing: 1px;")
        self._lic_desc_card4 = QLabel("Loading..."); self._lic_desc_card4.setStyleSheet("color: #8E8E93; font-size: 11px; background: transparent;")
        lic_lt.addWidget(lic_lbl); lic_lt.addWidget(self._lic_desc_card4)
        lic_hl.addLayout(lic_lt, 1)

        self._btn_deactivate_card4 = _QPBtn(tr("settings.button.reset_trial", self._language).upper())
        self._btn_deactivate_card4.setFixedSize(160, 40)
        self._btn_deactivate_card4.setCursor(Qt.PointingHandCursor)
        self._btn_deactivate_card4.setStyleSheet("""
            QPushButton {
                background-color: #2C2C2E;
                border: none;
                border-radius: 10px;
                color: #8E8E93;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 1.4px;
                padding: 0 12px;
            }
            QPushButton:hover { background-color: #3A3A3C; color: #E5E5EA; }
            QPushButton:pressed { background-color: #2C2C2E; }
        """)
        self._btn_deactivate_card4.clicked.connect(self._reset_to_trial)
        lic_hl.addWidget(self._btn_deactivate_card4)

        self._btn_activate_card4 = _QPBtn(tr("settings.button.activate", self._language).upper())
        self._btn_activate_card4.setFixedSize(160, 40)
        self._btn_activate_card4.setCursor(Qt.PointingHandCursor)
        self._btn_activate_card4.setStyleSheet("""
            QPushButton {
                background-color: #0F3A20;
                border: none;
                border-radius: 10px;
                color: #30D158;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 1.4px;
                padding: 0 12px;
            }
            QPushButton:hover { background-color: #144C2A; color: #4CD964; }
            QPushButton:pressed { background-color: #0F3A20; }
        """)
        lic_hl.addWidget(self._btn_activate_card4)
        vl.addWidget(lic_card)

        vl.addStretch()
        return container

    def _build_system(self) -> QWidget:
        container = QWidget(); container.setStyleSheet("background: transparent;")
        vl = QVBoxLayout(container); vl.setContentsMargins(0, 0, 0, 0); vl.setSpacing(0)

        # 1. LOGGING + TIMEOUT labels/inputs
        # ── Group 1: Modern Settings Rows ─────────────────────────────────────
        # Instead of generic columns, we use a "macOS Settings Row" pattern.
        # This increases the vertical height but significantly boosts legibility and "premium" feel.
        
        # ── Group 1: Modern Split Layout ─────────────────────────────────────
        # Left: Config Rows | Right: Action Cluster
        top_split = QHBoxLayout(); top_split.setSpacing(16); top_split.setContentsMargins(0, 0, 0, 0)

        # ── LEFT: Config Group ──────────────────────────────────────────
        conf_group = QFrame()
        conf_group.setObjectName("LeftConfigGroup")
        conf_group.setStyleSheet("""
            QFrame#LeftConfigGroup {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                                          stop:0 rgba(44, 44, 46, 0.4), 
                                          stop:1 rgba(28, 28, 30, 0.3));
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 14px;
            }
        """)
        conf_vl = QVBoxLayout(conf_group); conf_vl.setContentsMargins(16, 8, 16, 8); conf_vl.setSpacing(0)

        def _setting_row(icon: FluentIcon, title: str, description: str, widget: QWidget):
            row = QFrame()
            row.setStyleSheet("background: transparent; border: none;")
            row_hl = QHBoxLayout(row); row_hl.setContentsMargins(0, 8, 0, 8); row_hl.setSpacing(12)
            from qfluentwidgets import IconWidget
            ic = IconWidget(icon); ic.setFixedSize(16, 16); ic.setStyleSheet("color: #8E8E93;")
            row_hl.addWidget(ic)
            txt_vl = QVBoxLayout(); txt_vl.setSpacing(2); txt_vl.setContentsMargins(0, 0, 0, 0)
            t = QLabel(title); t.setStyleSheet("color: white; font-size: 13px; font-weight: 600;")
            d = QLabel(description); d.setStyleSheet("color: #8E8E93; font-size: 11px;")
            txt_vl.addWidget(t); txt_vl.addWidget(d)
            row_hl.addLayout(txt_vl, 1); row_hl.addWidget(widget)
            return row

        # Timeout Row
        self._request_timeout = LineEdit(); self._request_timeout.setFixedSize(70, 30)
        self._request_timeout.setValidator(QDoubleValidator(1, 300, 0, self))
        self._style_input(self._request_timeout)
        conf_vl.addWidget(_setting_row(FluentIcon.SETTING, tr("settings.timeout.title", self._language), tr("settings.timeout.desc", self._language), self._request_timeout))

        div = QFrame(); div.setFixedHeight(1); div.setStyleSheet("background: rgba(255, 255, 255, 0.04); margin: 0 10px;")
        conf_vl.addWidget(div)

        self._language_combo = MacComboBox(); self._language_combo.setFixedHeight(30); self._language_combo.setFixedWidth(140)
        self._style_combo(self._language_combo)
        for code, label in SUPPORTED_LANGUAGES.items():
            self._language_combo.addItem(label, userData=code)
        conf_vl.addWidget(_setting_row(FluentIcon.LANGUAGE, tr("settings.language.title", self._language), tr("settings.language.desc", self._language), self._language_combo))

        top_split.addWidget(conf_group, 3)

        # ── RIGHT: Action Stack ──────────────────────────────────────────
        action_vl = QVBoxLayout(); action_vl.setSpacing(8); action_vl.setContentsMargins(0, 0, 0, 0)
        
        from PySide6.QtWidgets import QPushButton
        class _Btn(QPushButton): pass

        self._save_btn = _Btn(tr("settings.button.save", self._language))
        self._save_btn.setFixedHeight(36)
        self._save_btn.setMinimumWidth(200)
        self._save_btn.setCursor(Qt.PointingHandCursor)
        self._save_btn.setStyleSheet("""
            _Btn {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0A84FF, stop:1 #0070E0);
                border: none; border-radius: 8px; color: white;
                font-size: 11px; font-weight: 700; letter-spacing: 0.8px; text-transform: uppercase;
                padding: 0 16px;
                text-align: center;
            }
            _Btn:hover { background: #409CFF; }
        """)
        self._save_btn.clicked.connect(self._save)
        action_vl.addWidget(self._save_btn)

        self._reset_btn = _Btn(tr("settings.button.reset", self._language))
        self._reset_btn.setFixedHeight(36)
        self._reset_btn.setMinimumWidth(200)
        self._reset_btn.setCursor(Qt.PointingHandCursor)
        self._reset_btn.setStyleSheet("""
            _Btn {
                background-color: transparent; border: 1.5px solid #3A3A3C;
                border-radius: 8px; color: #8E8E93;
                font-size: 11px; font-weight: 600; letter-spacing: 1.2px; text-transform: uppercase;
            }
            _Btn:hover { color: white; border-color: #48484A; background: rgba(255,255,255,0.03); }
        """)
        self._reset_btn.clicked.connect(self._reset)
        action_vl.addWidget(self._reset_btn)
        
        action_vl.addStretch()
        top_split.addLayout(action_vl, 1)

        vl.addLayout(top_split)
        vl.addSpacing(16)

        # ── Group 2: Cache cleanup card ───────────────────────────────────────
        cache_card = QFrame()
        cache_card.setObjectName("CacheCard")
        cache_card.setStyleSheet("QFrame#CacheCard { background: rgba(255, 159, 10, 0.05); border: 1px solid rgba(255, 159, 10, 0.14); border-radius: 12px; }")
        cache_hl = QHBoxLayout(cache_card); cache_hl.setContentsMargins(16, 12, 16, 12); cache_hl.setSpacing(12)

        c_ic = IconWidget(FluentIcon.SYNC.icon(color=QColor("#FFB340")))
        c_ic.setFixedSize(16, 16)
        cache_hl.addWidget(c_ic)

        ctxt = QVBoxLayout(); ctxt.setSpacing(2); ctxt.setContentsMargins(0, 0, 0, 0)
        ch = QLabel("CACHED APPDATA"); ch.setStyleSheet("color: rgba(255, 159, 10, 0.95); font-size: 10px; font-weight: 800; letter-spacing: 1px;")
        cb = QLabel("Reset stale AppData settings and local cache while keeping SMTP and scraped leads."); cb.setStyleSheet("color: #8E8E93; font-size: 11px;")
        ctxt.addWidget(ch); ctxt.addWidget(cb)
        cache_hl.addLayout(ctxt, 1)

        self._clean_cache_btn = _Btn("CLEAN CACHE")
        self._clean_cache_btn.setFixedSize(140, 40)
        self._clean_cache_btn.setCursor(Qt.PointingHandCursor)
        self._clean_cache_btn.setStyleSheet("""
            _Btn {
                background-color: #3A2A12;
                border: none;
                border-radius: 10px;
                color: #FFB340;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 1.4px;
                text-transform: uppercase;
                padding: 0 12px;
            }
            _Btn:hover { background-color: #483419; color: #FFC15C; }
            _Btn:pressed { background-color: #523A18; }
        """)
        self._clean_cache_btn.clicked.connect(self._clear_cached_appdata)
        cache_hl.addWidget(self._clean_cache_btn)

        vl.addWidget(cache_card)
        vl.addSpacing(12)

        # ── Group 3: Danger Zone card ──────────────────────────────────────────
        danger_card = QFrame()
        danger_card.setObjectName("DangerCard")
        danger_card.setStyleSheet("QFrame#DangerCard { background: rgba(255, 69, 58, 0.05); border: 1px solid rgba(255, 69, 58, 0.12); border-radius: 12px; }")
        danger_hl = QHBoxLayout(danger_card); danger_hl.setContentsMargins(16, 12, 16, 12); danger_hl.setSpacing(12)
        
        d_ic = IconWidget(FluentIcon.INFO.icon(color=QColor("#FF453A")))
        d_ic.setFixedSize(16, 16)
        danger_hl.addWidget(d_ic)

        dtxt = QVBoxLayout(); dtxt.setSpacing(2); dtxt.setContentsMargins(0, 0, 0, 0)
        dh = QLabel("DATABASE PERSISTENCE"); dh.setStyleSheet("color: rgba(255, 69, 58, 0.9); font-size: 10px; font-weight: 800; letter-spacing: 1px;")
        db = QLabel("Permanently purge all locally cached records and results."); db.setStyleSheet("color: #8E8E93; font-size: 11px;")
        dtxt.addWidget(dh); dtxt.addWidget(db)
        danger_hl.addLayout(dtxt, 1)

        self._clear_btn = _Btn(tr("settings.button.wipe", self._language))
        self._clear_btn.setFixedSize(140, 40)
        self._clear_btn.setCursor(Qt.PointingHandCursor)
        self._clear_btn.setStyleSheet("""
            _Btn {
                background-color: #3C1A1A;
                border: none;
                border-radius: 10px;
                color: #FF453A;
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 1.8px;
                text-transform: uppercase;
                padding: 0 12px;
            }
            _Btn:hover { background-color: #4A2020; color: #FF6259; }
            _Btn:pressed { background-color: #5A1F1F; }
        """)
        self._clear_btn.clicked.connect(self._clear_saved_leads)
        danger_hl.addWidget(self._clear_btn)
        
        from PySide6.QtWidgets import QStyleFactory
        for btn in (self._reset_btn, self._save_btn, self._clean_cache_btn, self._clear_btn):
            btn.setStyle(QStyleFactory.create("Fusion"))

        vl.addWidget(danger_card)
        vl.addStretch()
        return container



    def _build_protection(self) -> QWidget:
        container = QWidget(); container.setStyleSheet("background: transparent;")
        vl = QVBoxLayout(container); vl.setContentsMargins(0, 0, 0, 0); vl.setSpacing(4)

        # PIN controls hidden per user request (kept for state compatibility)
        self._btn_set_pin = PushButton(tr("settings.button.change_license", self._language).replace("LICENSE", "PIN"))
        self._btn_set_pin.hide()
        self._chk_security_enabled = self._sw()
        self._chk_security_enabled.hide()

        # Auto Update
        self._chk_auto_update = self._sw()
        vl.addWidget(self._row(tr("settings.auto_update.title", self._language), self._chk_auto_update, tr("settings.auto_update.desc", self._language), icon=FluentIcon.UPDATE))

        # Core Repo URL
        url_frame = QFrame()
        url_frame.setStyleSheet("QFrame { background: transparent; border: none; }")
        uh = QHBoxLayout(url_frame); uh.setContentsMargins(12, 0, 12, 0); uh.setSpacing(10)
        self._git_repo_url = LineEdit(); self._git_repo_url.setFixedHeight(34)
        self._git_repo_url.setPlaceholderText(tr("settings.repo.placeholder", self._language))
        self._style_input(self._git_repo_url)
        uh.addWidget(self._git_repo_url)
        vl.addWidget(url_frame)

        # Product License moved to Card 4 — keep widgets for state compatibility
        lic_frame_hidden = QFrame(); lic_frame_hidden.hide()
        lh_h = QHBoxLayout(lic_frame_hidden); lh_h.setContentsMargins(0, 0, 0, 0)
        self._lic_desc = QLabel(tr("settings.license.activating", self._language)); self._lic_desc.hide()
        self._btn_activate = _QPBtn(tr("settings.button.activate", self._language)); self._btn_activate.hide()
        self._btn_deactivate = PushButton(tr("settings.button.reset_trial", self._language))
        self._btn_deactivate.hide()
        self._btn_deactivate.clicked.connect(self._reset_to_trial)


        # ── New: Update Channel + Automatic Backup ───────────────────────────
        self._update_channel = MacComboBox()
        self._update_channel.setFixedWidth(140); self._update_channel.setFixedHeight(36)
        self._update_channel.addItems(["STABLE", "BETA", "DEV"])
        self._style_combo(self._update_channel)
        vl.addWidget(self._row("Update Channel", self._update_channel, "Release stream preference.", icon=FluentIcon.TAG))

        self._chk_backup = self._sw()
        vl.addWidget(self._row("Automatic Backup", self._chk_backup, "Back up settings periodically.", icon=FluentIcon.SAVE))
        
        self._backup_dir = LineEdit(); self._backup_dir.setFixedSize(280, 30)
        self._backup_dir.setPlaceholderText("Browse...")
        self._backup_dir.setReadOnly(True)
        self._backup_dir.setFocusPolicy(Qt.NoFocus)
        self._backup_dir.setCursor(Qt.PointingHandCursor)
        self._style_input(self._backup_dir)
        
        def _browse_backup_dir(event):
            from PySide6.QtWidgets import QFileDialog
            import os
            start_path = self._backup_dir.text() or os.path.expanduser("~")
            path = QFileDialog.getExistingDirectory(self, "Select Backup Directory", start_path)
            if path:
                self._backup_dir.setText(path)
                
        self._backup_dir.mousePressEvent = _browse_backup_dir
        vl.addWidget(self._row("Backup Location", self._backup_dir, "Destination for automatic backups.", icon=FluentIcon.FOLDER))

        vl.addSpacing(8)

        # ── Update Card (blue, styled like CLEAN CACHE) ───────────────────────
        update_card = QFrame()
        update_card.setObjectName("UpdateCard")
        update_card.setStyleSheet(
            "QFrame#UpdateCard { background: rgba(10, 132, 255, 0.07); "
            "border: 1px solid rgba(10, 132, 255, 0.18); border-radius: 12px; }"
        )
        update_hl = QHBoxLayout(update_card)
        update_hl.setContentsMargins(16, 12, 16, 12)
        update_hl.setSpacing(12)

        u_ic = IconWidget(FluentIcon.UPDATE.icon(color=QColor("#0A84FF")))
        u_ic.setFixedSize(16, 16)
        update_hl.addWidget(u_ic)

        utxt = QVBoxLayout(); utxt.setSpacing(2); utxt.setContentsMargins(0, 0, 0, 0)
        uh = QLabel("SOFTWARE UPDATE"); uh.setStyleSheet("color: rgba(10, 132, 255, 0.95); font-size: 10px; font-weight: 800; letter-spacing: 1px;")
        ub = QLabel("Check GitHub for a newer version and download it automatically.")
        ub.setStyleSheet("color: #8E8E93; font-size: 11px;")
        utxt.addWidget(uh); utxt.addWidget(ub)
        update_hl.addLayout(utxt, 1)

        self._check_update_btn = _QPBtn("CHECK FOR UPDATES")
        self._check_update_btn.setFixedSize(160, 40)
        self._check_update_btn.setCursor(Qt.PointingHandCursor)
        self._check_update_btn.setStyleSheet("""
            QPushButton {
                background-color: #0A2540;
                border: none;
                border-radius: 10px;
                color: #0A84FF;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 1.4px;
                padding: 0 12px;
            }
            QPushButton:hover { background-color: #0D3060; color: #4DA6FF; }
            QPushButton:pressed { background-color: #0A2540; }
        """)
        self._check_update_btn.clicked.connect(self._trigger_update_check)
        update_hl.addWidget(self._check_update_btn)

        vl.addWidget(update_card)

        vl.addStretch()
        return container

    def _on_engine_changed(self):
        engine = self._engine_combo.currentData()
        self._mark_dirty()

    # ── Logic ─────────────────────────────────────────────────────────────

    def _on_security_toggled(self, enabled: bool):
        self._btn_set_pin.setVisible(enabled)
        if enabled and not config_manager.settings.security_pin:
            self._change_pin()
            if not config_manager.settings.security_pin:
                self._chk_security_enabled.setChecked(False)

    def _change_pin(self):
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QDialogButtonBox
        from qfluentwidgets import LineEdit as FLineEdit, StrongBodyLabel, CaptionLabel

        from .components import ZugzwangDialog
        # Use a more specialized dialog for PIN entry that matches ZUGZWANG style
        class ZugzwangPinDialog(QDialog):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
                self.setAttribute(Qt.WA_TranslucentBackground)
                self.setFixedSize(400, 280)
                self._drag_pos = None
                
                self.container = QFrame(self)
                self.container.setObjectName("DialogContainer")
                self.container.setFixedSize(400, 280)
                self.container.setStyleSheet("""
                    QFrame#DialogContainer {
                        background-color: #1E1E1E;
                        border: 1px solid #323232;
                        border-radius: 18px;
                    }
                """)
                
                layout = QVBoxLayout(self.container)
                layout.setContentsMargins(35, 35, 35, 30)
                layout.setSpacing(12)
                
                title_lbl = QLabel("SET SECURITY PIN")
                title_lbl.setAlignment(Qt.AlignCenter)
                title_lbl.setStyleSheet("color: #FFFFFF; font-family: 'PT Root UI'; font-size: 22px; font-weight: 800;")
                layout.addWidget(title_lbl)
                
                desc_lbl = QLabel("Required for application launch.")
                desc_lbl.setAlignment(Qt.AlignCenter)
                desc_lbl.setStyleSheet("color: #8E8E93; font-size: 13px;")
                layout.addWidget(desc_lbl)
                
                self.pin_input = LineEdit()
                self.pin_input.setPlaceholderText("4-Digit PIN")
                self.pin_input.setMaxLength(4)
                self.pin_input.setEchoMode(LineEdit.Password)
                self.pin_input.setAlignment(Qt.AlignCenter)
                self.pin_input.setFixedSize(180, 42)
                self.pin_input.setStyleSheet("""
                    LineEdit {
                        background: #2C2C2E;
                        border: 1px solid #3A3A3C;
                        border-radius: 8px;
                        color: #0A84FF;
                        font-family: 'PT Root UI', monospace;
                        font-size: 18px;
                        font-weight: 700;
                    }
                """)
                layout.addWidget(self.pin_input, 0, Qt.AlignCenter)
                
                layout.addStretch()
                
                btn_row = QHBoxLayout()
                btn_row.setSpacing(12)
                
                self.ok_btn = QPushButton("Save PIN")
                self.ok_btn.setFixedSize(150, 44)
                self.ok_btn.setCursor(Qt.PointingHandCursor)
                self.ok_btn.setStyleSheet("""
                    QPushButton {
                        background: #0A84FF;
                        border: none;
                        border-radius: 8px;
                        color: #FFFFFF;
                        font-family: 'PT Root UI';
                        font-size: 15px;
                        font-weight: 700;
                    }
                    QPushButton:hover { background: #007AFF; }
                    QPushButton:pressed { background: #0062CC; }
                """)
                self.ok_btn.clicked.connect(self.accept)
                
                self.cancel_btn = QPushButton("Cancel")
                self.cancel_btn.setFixedSize(150, 44)
                self.cancel_btn.setCursor(Qt.PointingHandCursor)
                self.cancel_btn.setStyleSheet("""
                    QPushButton {
                        background: #2C2C2E;
                        border: 1px solid #3A3A3C;
                        border-radius: 8px;
                        color: #FFFFFF;
                        font-family: 'PT Root UI';
                        font-size: 15px;
                        font-weight: 500;
                    }
                    QPushButton:hover { background: #3A3A3C; }
                """)
                self.cancel_btn.clicked.connect(self.reject)
                
                btn_row.addWidget(self.ok_btn)
                btn_row.addWidget(self.cancel_btn)
                layout.addLayout(btn_row)

            def mousePressEvent(self, event):
                if event.button() == Qt.LeftButton:
                    self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
                    event.accept()

            def mouseMoveEvent(self, event):
                if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
                    self.move(event.globalPos() - self._drag_pos)
                    event.accept()

        dialog = ZugzwangPinDialog(self.window())
        if dialog.exec():
            pin = dialog.pin_input.text().strip()
            if len(pin) == 4 and pin.isdigit():
                config_manager.update(security_pin=pin)
                InfoBar.success("PIN Updated", "Startup lock PIN has been changed.", duration=2000, parent=self.window())
                return True
            else:
                InfoBar.error("Invalid PIN", "PIN must be exactly 4 digits.", duration=3000, parent=self.window())
                return False
        return False

    def _open_activation(self):
        if self.window().show_activation_dialog():
            self._update_license_display()

    def _reset_to_trial(self):
        from .components import ZugzwangDialog
        msg = ZugzwangDialog(
            "Revert to Trial",
            "Are you sure you want to deactivate the license and return to Trial mode? (Limits will apply)",
            self.window()
        )
        if msg.exec():
            # Clear license in settings via config_manager
            config_manager.update(is_activated=False, license_key=None)
            self._update_license_display()
            # Also update other pages
            self.window().dashboard_page.refresh()
            InfoBar.success("Reverted", "Application is now in Trial mode.", duration=2000, parent=self.window())

    def _update_license_display(self):
        mid = LicenseManager.get_machine_id()
        is_active = LicenseManager.is_active()
        
        if is_active:
            status = tr('settings.license.status.activated', self._language)
            color = "#30D158"
            btn_text = tr("settings.button.change_license", self._language)
        else:
            status = tr('settings.license.status.trial', self._language)
            color = "#8E8E93"
            btn_text = tr("settings.button.activate", self._language)
            
        mid_label = tr("settings.license.machine_id", self._language)
        self._lic_desc.setText(
            f'<span style="color: {color}; font-family: \'Menlo\'; font-size: 11px;">{status}</span>'
            f' <span style="color: #3A3A3C; font-family: \'Menlo\'; font-size: 11px;">|</span>'
            f' <span style="color: #636366; font-family: \'Menlo\'; font-size: 11px;">{mid_label}: {mid}</span>'
        )
        # Keep Card 4 label in sync
        self._lic_desc_card4.setText(
            f'<span style="color: {color}; font-size: 11px;">{status}</span>'
            f' <span style="color: #636366; font-size: 11px;">| {mid_label}: {mid}</span>'
        )
        # Card 3 stubs: always keep hidden (orphaned widgets, display is in Card 4)
        self._btn_activate.setVisible(False)
        self._btn_deactivate.setVisible(False)
        # Card 4 buttons drive the actual UI
        self._btn_activate_card4.setText(btn_text)
        self._btn_activate_card4.setVisible(not is_active)
        self._btn_deactivate_card4.setVisible(is_active)

    def header_action_widgets(self) -> list[QWidget]:
        return []

    def _connect_change_tracking(self):
        for chk in [self._chk_headless, self._chk_robots, self._chk_proxy,
                    self._chk_security_enabled, self._chk_auto_update,
                    self._chk_scrape_emails, self._chk_debug_screenshots,
                    self._chk_validate, self._chk_rotate_ua, self._chk_auto_save,
                    self._chk_notify, self._chk_backup]:
            chk.toggled.connect(self._smart_mark_dirty)
        self._chk_security_enabled.toggled.connect(self._on_security_toggled)
        self._chk_scrape_emails.toggled.connect(self._update_deep_scan_state)
        self._btn_activate.clicked.connect(self._open_activation)
        self._btn_activate_card4.clicked.connect(self._open_activation)
        self._btn_set_pin.clicked.connect(self._change_pin)
        for te in [self._user_agents, self._delay_min, 
                    self._delay_max, self._max_results, self._request_timeout,
                    self._discovery_paths_edit, self._smtp_host_cfg, self._smtp_port_cfg,
                    self._max_retries, self._max_concurrent, self._max_depth,
                    self._disc_timeout, self._default_export_dir, self._backup_dir]:
            te.textChanged.connect(self._smart_mark_dirty)
        self._user_agents.textChanged.connect(self._update_ua_count)
        self._proxy_url.textChanged.connect(self._smart_mark_dirty)
        self._proxy_port.textChanged.connect(self._smart_mark_dirty)
        self._git_repo_url.textChanged.connect(self._smart_mark_dirty)
        for cb in [self._language_combo, self._engine_combo, self._update_channel, self._log_retention]:
            cb.currentIndexChanged.connect(self._smart_mark_dirty)

    # ── Smart State Tracking ─────────────────────────────────────────────────

    def _snapshot_state(self):
        """Capture the current state as the clean baseline."""
        self._original_state = self._get_current_state_dict()

    def _get_current_state_dict(self):
        return dict(
            delay_min=self._delay_min.text(), delay_max=self._delay_max.text(),
            max_results=self._max_results.text(), timeout=self._request_timeout.text(),
            max_retries=self._max_retries.text(), max_concurrent=self._max_concurrent.text(),
            headless=self._chk_headless.isChecked(), robots=self._chk_robots.isChecked(),
            scrape=self._chk_scrape_emails.isChecked(), debug=self._chk_debug_screenshots.isChecked(),
            validate=self._chk_validate.isChecked(),
            max_depth=self._max_depth.text(), disc_timeout=self._disc_timeout.text(),
            paths=self._discovery_paths_edit.toPlainText(),
            proxy=self._chk_proxy.isChecked(), proxy_url=self._proxy_url.text(),
            proxy_port=self._proxy_port.text(),
            uas=self._user_agents.toPlainText(), rotate_ua=self._chk_rotate_ua.isChecked(),
            security=self._chk_security_enabled.isChecked(),
            repo=self._git_repo_url.text(), auto_update=self._chk_auto_update.isChecked(),
            lang=self._language_combo.currentData(), engine=self._engine_combo.currentData(),
            smtp_host=self._smtp_host_cfg.text(), smtp_port=self._smtp_port_cfg.text(),
            auto_save=self._chk_auto_save.isChecked(), notify=self._chk_notify.isChecked(),
            backup=self._chk_backup.isChecked(),
            update_channel=self._update_channel.currentText(),
            log_retention=self._log_retention.currentText(),
            export_dir=self._default_export_dir.text(),
            backup_dir=self._backup_dir.text(),
        )

    def _smart_mark_dirty(self, *args):
        """Compare current state to snapshot. If identical, revert to clean."""
        current = self._get_current_state_dict()
        is_dirty = current != self._original_state
        if is_dirty != self._dirty:
            self._dirty = is_dirty
            if is_dirty:
                self._save_btn.setText(tr("settings.button.save", self._language) + " *")
            else:
                self._save_btn.setText(tr("settings.button.save", self._language))

    def _mark_dirty(self):
        """Legacy fallback."""
        self._smart_mark_dirty()

    def _mark_clean(self):
        self._dirty = False
        self._save_btn.setText(tr("settings.button.save", self._language))

    def _update_ua_count(self):
        """Update the UA count label."""
        uas = [ua.strip() for ua in self._user_agents.toPlainText().splitlines() if ua.strip()]
        self._ua_count_lbl.setText(f"{len(uas)} AGENT{'S' if len(uas) != 1 else ''}")

    def _update_deep_scan_state(self):
        """Enable/disable discovery-related fields based on Deep Scan toggle."""
        is_on = self._chk_scrape_emails.isChecked()
        self._discovery_paths_edit.setEnabled(is_on)
        self._debug_out_frame.setEnabled(is_on)
        self._email_val_frame.setEnabled(is_on)
        self._max_depth.setEnabled(is_on)
        self._disc_timeout.setEnabled(is_on)

    def _on_proxy_toggled(self, enabled: bool):
        self._proxy_url.setEnabled(enabled)
        self._proxy_port.setEnabled(enabled)

    def _load_values(self):
        s = config_manager.settings
        self._delay_min.setText(str(s.default_delay_min))
        self._delay_max.setText(str(s.default_delay_max))
        self._max_results.setText(str(s.default_max_results))
        self._request_timeout.setText(str(getattr(s, "default_request_timeout", 30)))
        self._chk_headless.setChecked(s.default_headless)
        self._chk_robots.setChecked(s.default_respect_robots)
        self._chk_scrape_emails.setChecked(s.default_scrape_emails)
        self._chk_debug_screenshots.setChecked(s.debug_screenshots)
        self._discovery_paths_edit.setPlainText(", ".join(s.email_discovery_paths))
        self._chk_proxy.setChecked(s.proxy_enabled)
        # Handle transition from proxy_url to proxies list
        main_proxy = s.proxies[0] if s.proxies else ""
        self._proxy_url.setText(main_proxy)
        self._proxy_url.setEnabled(s.proxy_enabled)
        self._proxy_port.setText(self._extract_proxy_port(main_proxy))
        self._proxy_port.setEnabled(s.proxy_enabled)
        self._user_agents.setPlainText("\n".join(s.user_agents))
        self._chk_security_enabled.setChecked(s.security_enabled)
        self._btn_set_pin.setVisible(s.security_enabled)
        self._git_repo_url.setText(s.git_repo_url)
        self._chk_auto_update.setChecked(s.auto_update_enabled)

        # New fields
        self._max_retries.setText(str(getattr(s, "default_max_retries", 3)))
        self._max_concurrent.setText(str(getattr(s, "max_concurrent_jobs", 5)))
        self._chk_validate.setChecked(getattr(s, "validate_emails", True))
        self._max_depth.setText(str(getattr(s, "max_discovery_depth", 2)))
        self._disc_timeout.setText(str(getattr(s, "discovery_timeout", 60)))
        self._chk_rotate_ua.setChecked(getattr(s, "rotate_user_agent", False))
        self._chk_auto_save.setChecked(getattr(s, "auto_save", True))
        self._chk_notify.setChecked(getattr(s, "notify_job_completion", True))
        self._chk_backup.setChecked(getattr(s, "auto_backup", True))
        self._default_export_dir.setText(getattr(s, "default_export_dir", ""))
        self._backup_dir.setText(getattr(s, "backup_dir", ""))
        
        # Load Browser Engine
        engine = getattr(s, "browser_engine", "chromium")
        for idx in range(self._engine_combo.count()):
            if self._engine_combo.itemData(idx) == engine:
                self._engine_combo.setCurrentIndex(idx)
                break


        target_language = get_language(getattr(s, "app_language", "en"))
        for idx in range(self._language_combo.count()):
            if self._language_combo.itemData(idx) == target_language:
                self._language_combo.setCurrentIndex(idx)
                break
        self._update_license_display()

        # SMTP
        self._smtp_host_cfg.setText(getattr(s, "email_smtp_host", "smtp.gmail.com"))
        self._smtp_port_cfg.setText(getattr(s, "email_smtp_port", "587"))

        self._mark_clean()
        self._update_ua_count()
        self._snapshot_state()

    @staticmethod
    def _extract_proxy_port(proxy_url: str) -> str:
        if ":" not in proxy_url:
            return ""
        tail = proxy_url.rsplit(":", 1)[-1]
        return tail if tail.isdigit() else ""

    def _validate(self) -> bool:
        try:
            min_v = float(self._delay_min.text())
            max_v = float(self._delay_max.text())
        except ValueError:
            InfoBar.error("Validation Error", "Delays must be numbers", parent=self.window())
            return False

        if min_v >= max_v:
            InfoBar.error("Validation Error", "Min Delay must be less than Max Delay", parent=self.window())
            return False
        if self._chk_proxy.isChecked():
            url = self._proxy_url.text().strip()
            if not url:
                InfoBar.error("Validation Error", "Proxy URL is required", parent=self.window())
                return False
            elif not _PROXY_RE.match(url):
                InfoBar.error("Validation Error", "URL must start with http://, https://, or socks5://", parent=self.window())
                return False
        return True

    def _save(self):
        if not self._validate():
            return
        paths = [p.strip().lower() for p in self._discovery_paths_edit.toPlainText().split(",") if p.strip()]
        user_agents = [ua.strip() for ua in self._user_agents.toPlainText().splitlines() if ua.strip()]
        
        previous_language = get_language(config_manager.settings.app_language)
        selected_language = get_language(self._language_combo.currentData() or "en")

        config_manager.update(
            default_delay_min=float(self._delay_min.text()),
            default_delay_max=float(self._delay_max.text()),
            default_max_results=int(float(self._max_results.text())),
            default_request_timeout=int(float(self._request_timeout.text())),
            default_headless=self._chk_headless.isChecked(),
            default_scrape_emails=self._chk_scrape_emails.isChecked(),
            default_respect_robots=self._chk_robots.isChecked(),
            debug_screenshots=self._chk_debug_screenshots.isChecked(),
            email_discovery_paths=paths,
            blacklisted_domains=config_manager.settings.blacklisted_domains,
            whitelisted_domains=config_manager.settings.whitelisted_domains,
            proxy_enabled=self._chk_proxy.isChecked(),
            proxies=[self._proxy_url.text().strip()] if self._proxy_url.text().strip() else [],
            user_agents=user_agents or config_manager.settings.user_agents,
            log_level=config_manager.settings.log_level,
            app_language=selected_language,
            security_enabled=self._chk_security_enabled.isChecked(),
            git_repo_url=self._git_repo_url.text().strip(),
            auto_update_enabled=self._chk_auto_update.isChecked(),
            browser_engine=self._engine_combo.currentData(),
            # SMTP
            email_smtp_host=self._smtp_host_cfg.text().strip() or "smtp.gmail.com",
            email_smtp_port=self._smtp_port_cfg.text().strip() or "587",
            # New fields
            max_concurrent_jobs=int(float(self._max_concurrent.text() or "5")),
            notify_job_completion=self._chk_notify.isChecked(),
            default_export_dir=self._default_export_dir.text().strip(),
            auto_backup=self._chk_backup.isChecked(),
            backup_dir=self._backup_dir.text().strip(),
        )
        self._language = selected_language
        self._mark_clean()
        self._snapshot_state()
        InfoBar.success(tr("settings.saved", self._language), tr("settings.saved.body", self._language), duration=2000, parent=self.window())
        if selected_language != previous_language:
            InfoBar.info(tr("settings.title", self._language), tr("settings.language.restart", self._language), duration=3000, parent=self.window())

    def _reset(self):
        from .components import ZugzwangDialog
        msg = ZugzwangDialog(
            tr("settings.dialog.reset.title", self._language),
            tr("settings.dialog.reset.body", self._language),
            self.window()
        )
        if msg.exec():
            config_manager.reset()
            # FIX 5: Force 4 core entries on reset
            config_manager.update(email_discovery_paths=[
                "impressum", "kontakt", "karriere", "stellenangebote", "jobs",
                "bewerbung", "über uns", "team", "datenschutz", "kontaktformular"
            ])
            self._load_values()
            InfoBar.info("Restored", "Factory defaults applied", duration=2000, parent=self.window())

    def _clear_saved_leads(self):
        if orchestrator.is_running:
            InfoBar.warning(tr("monitor.status.running", self._language), "Stop current job first.", parent=self.window())
            return
        
        from .components import ZugzwangDialog
        msg = ZugzwangDialog(
            tr("settings.dialog.wipe.title", self._language),
            tr("settings.dialog.wipe.body", self._language),
            self.window(),
            destructive=True
        )
        if msg.exec():
            try:
                orchestrator.clear_app_memory()
                InfoBar.success("Cleaned", "Saved leads DB cleared", duration=2000, parent=self.window())
            except Exception as e:
                InfoBar.error("Clean Failed", f"Could not clear saved leads: {e}", parent=self.window())

    def _clear_cached_appdata(self):
        if orchestrator.is_running:
            InfoBar.warning(tr("monitor.status.running", self._language), "Stop current job first.", parent=self.window())
            return
        if self._cache_cleanup_in_progress:
            return

        from .components import ZugzwangDialog
        msg = ZugzwangDialog(
            "Clean Cached AppData",
            "This will reset old AppData settings and local cache to a fresh-install state while keeping SMTP setup and scraped leads. Continue?",
            self.window(),
            destructive=True
        )
        if msg.exec():
            self._cache_cleanup_in_progress = True
            self._clean_cache_btn.setEnabled(False)
            config_manager.clear_cached_app_data_async()

    def _on_cache_cleanup_finished(self, success: bool, error: str):
        if not self._cache_cleanup_in_progress:
            return
        self._cache_cleanup_in_progress = False
        self._clean_cache_btn.setEnabled(True)

        if success:
            self._load_values()
            InfoBar.success("Cache Cleaned", "Old AppData settings were reset. SMTP and saved leads were preserved.", duration=2500, parent=self.window())
        else:
            InfoBar.error("Cleanup Failed", f"Could not clean cached AppData: {error}", parent=self.window())

    def _trigger_update_check(self):
        self._check_update_btn.setEnabled(False)
        self._check_update_btn.setText("CHECKING...")
        try:
            from ..services.update_service import UpdateService
            self._update_svc = UpdateService(self)
            self._update_svc.update_available.connect(self._on_update_available)
            self._update_svc.no_update_available.connect(self._on_no_update)
            self._update_svc.check()
        except Exception as e:
            InfoBar.warning("Check Failed", str(e), duration=3000, parent=self.window())
            self._check_update_btn.setEnabled(True)
            self._check_update_btn.setText("CHECK FOR UPDATES")

    def _on_update_available(self, version: str, url: str):
        self._check_update_btn.setEnabled(True)
        self._check_update_btn.setText("CHECK FOR UPDATES")
        InfoBar.success(
            "Update Available",
            f"Version {version} is ready — download from GitHub.",
            duration=5000, parent=self.window()
        )

    def _on_no_update(self):
        self._check_update_btn.setEnabled(True)
        self._check_update_btn.setText("CHECK FOR UPDATES")
        InfoBar.info(
            "Up to Date",
            "You are running the latest version.",
            duration=3000, parent=self.window()
        )

