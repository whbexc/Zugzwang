"""
ZUGZWANG - Settings Page
Apple macOS System Preferences — Obsidian Edition.
"""

from __future__ import annotations
import re

from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QDoubleValidator, QColor, QPainter, QBrush
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QWidget, QGridLayout, QFrame,
    QLabel, QPushButton as _QPBtn, QScrollArea, QSizePolicy
)

from qfluentwidgets import (
    ElevatedCardWidget, StrongBodyLabel, BodyLabel, CaptionLabel,
    SpinBox, DoubleSpinBox, ComboBox, TextEdit,
    PrimaryPushButton, PushButton, FluentIcon, SearchLineEdit,
    LineEdit, InfoBar, IconWidget, SwitchButton
)

from ..core.config import config_manager
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
        self._build_ui()
        self._load_values()
        self._connect_change_tracking()

    # ── Widget Factories ─────────────────────────────────────────────────────

    def _row(self, title: str, widget: QWidget, caption: str = "") -> QWidget:
        """A standard macOS-style left-label / right-control row."""
        frame = QFrame()
        frame.setFixedHeight(48)
        frame.setStyleSheet(
            "QFrame { background: transparent; border-radius: 4px; border: none; }"
            "QFrame:hover { background: #3A3A3C; }"
        )
        hl = QHBoxLayout(frame)
        hl.setContentsMargins(12, 4, 12, 4)
        hl.setSpacing(12)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("color: white; font-family: 'PT Root UI', sans-serif; font-size: 14px; background: transparent; border: none;")
        text_col.addWidget(title_lbl)
        if caption:
            cap = QLabel(caption)
            cap.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 11px; background: transparent; border: none;")
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
        card.setStyleSheet(f"QFrame#StepCard{num} {{ background: #2C2C2E; border-radius: 14px; border: none; }}")
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

        tl = QLabel(title.upper())
        tl.setStyleSheet(
            "color: #8E8E93; font-family: 'PT Root UI', sans-serif; font-size: 11px; font-weight: 600; "
            "letter-spacing: 1.6px; background: transparent; border: none;"
        )
        hdr.addWidget(tl); hdr.addStretch()
        vl.addLayout(hdr)

        if has_divider:
            div = QFrame(); div.setFixedHeight(1)
            div.setStyleSheet("background: #3A3A3C; border: none;")
            vl.addWidget(div)

        vl.addWidget(content, 1) # FIX 3: Content fills card
        return card

    def _sw(self) -> SwitchButton:
        s = SwitchButton()
        return s

    def _style_combo(self, combo: QWidget) -> None:
        combo.setStyleSheet(Theme.combo_box())

    def _style_input(self, widget: QWidget) -> None:
        if isinstance(widget, (TextEdit, TextEdit)): # TextEdit needs padding etc
             widget.setStyleSheet(Theme.text_edit())
        else:
             widget.setStyleSheet(Theme.line_edit())

    # ── Main Layout ──────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20) # FIX 3: Exact padding
        root.setSpacing(0) # Spacing handled by internal components

        # Header Title
        title_box = QWidget()
        tl = QVBoxLayout(title_box); tl.setContentsMargins(0, 0, 0, 12)
        title = QLabel("Settings")
        title.setStyleSheet("color: white; font-family: 'PT Root UI', sans-serif; font-size: 28px; font-weight: 600;")
        tl.addWidget(title)
        root.addWidget(title_box, 0)

        # Top Row (3 columns)
        top_row = QHBoxLayout()
        top_row.setSpacing(12)
        top_row.addWidget(self._card("1", "Scraping Engine",    self._build_scraping()))
        top_row.addWidget(self._card("2", "Email Discovery",   self._build_email()))
        top_row.addWidget(self._card("3", "Protection & Sync", self._build_protection()))

        # Bottom Row (2 columns, 50/50 split)
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(12)
        bottom_row.addWidget(self._card("4", "Network & Identity",self._build_network()))
        bottom_row.addWidget(self._card("5", "System Core",       self._build_system()))

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
        vl = QVBoxLayout(container); vl.setContentsMargins(0, 0, 0, 0); vl.setSpacing(6)

        self._chk_headless = self._sw()
        self._chk_robots   = self._sw()
        vl.addWidget(self._row("Headless Browser Mode", self._chk_headless))
        vl.addWidget(self._row("Respect Robots.txt",    self._chk_robots))

        # Inputs (LineEdits = 0 Arrows)
        self._delay_min   = LineEdit(); self._delay_min.setFixedSize(84, 40)
        self._delay_max   = LineEdit(); self._delay_max.setFixedSize(84, 40)
        self._max_results = LineEdit(); self._max_results.setFixedSize(84, 40)
        
        dv = QDoubleValidator(0.5, 60.0, 1, self); dv.setNotation(QDoubleValidator.StandardNotation)
        iv = QDoubleValidator(5, 10000, 0, self); iv.setNotation(QDoubleValidator.StandardNotation)
        
        self._delay_min.setValidator(dv); self._delay_max.setValidator(dv); self._max_results.setValidator(iv)
        for widget in [self._delay_min, self._delay_max, self._max_results]: 
            widget.setStyleSheet("""
                LineEdit {
                    background: #1C1C1E;
                    border: 1px solid #3A3A3C;
                    border-radius: 8px;
                    color: white;
                    font-family: 'PT Root UI', monospace;
                    font-size: 13px;
                    padding: 8px;
                }
            """)

        spin_frame = QFrame()
        spin_frame.setStyleSheet(f"QFrame {{ background: {Theme.BG_HOVER_LIGHT}; border-radius: 8px; border: none; }}")
        spin_hl = QHBoxLayout(spin_frame); spin_hl.setContentsMargins(12, 11, 12, 11); spin_hl.setSpacing(16)
        for label, widget in [("MIN (S)", self._delay_min), ("MAX (S)", self._delay_max), ("LIMIT", self._max_results)]:
            col = QVBoxLayout(); col.setSpacing(4)
            l = QLabel(label); l.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 10px; font-weight: 700; background: transparent;")
            col.addWidget(l); col.addWidget(widget)
            spin_hl.addLayout(col)
        spin_hl.addStretch()
        vl.addWidget(spin_frame)
        vl.addStretch()
        return container

    def _build_email(self) -> QWidget:
        container = QWidget(); container.setStyleSheet("background: transparent;")
        vl = QVBoxLayout(container); vl.setContentsMargins(0, 0, 0, 0); vl.setSpacing(6)

        self._chk_scrape_emails       = self._sw()
        self._chk_debug_screenshots   = self._sw()
        vl.addWidget(self._row("Deep Scan",    self._chk_scrape_emails))
        vl.addWidget(self._row("Debug Output", self._chk_debug_screenshots))

        vl.addWidget(self._section_label("Discovery Paths"))
        self._discovery_paths = TextEdit()
        # FIX 5: flex scroll behavior
        self._discovery_paths.setMinimumHeight(0) 
        self._discovery_paths.setPlaceholderText("impressum\nkontakt\nkarriere\njobs")
        self._discovery_paths.setStyleSheet("""
            QTextEdit {
                background: #1A1A1A;
                color: #8E8E93;
                font-family: 'PT Root UI', monospace;
                font-size: 12px;
                line-height: 1.8;
                border: 1px solid #3A3A3C;
                border-radius: 8px;
                padding: 10px 12px;
            }
            QScrollBar:vertical { width: 4px; background: transparent; }
            QScrollBar::handle:vertical { background: #3A3A3C; border-radius: 2px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)
        vl.addWidget(self._discovery_paths, 1) # flex factor 1
        return container

    def _build_network(self) -> QWidget:
        container = QWidget(); container.setStyleSheet("background: transparent;")
        vl = QVBoxLayout(container); vl.setContentsMargins(0, 0, 0, 0); vl.setSpacing(6)

        self._chk_proxy = self._sw()
        self._chk_proxy.checkedChanged.connect(self._on_proxy_toggled)
        vl.addWidget(self._row("Custom Proxy Routing", self._chk_proxy))

        proxy_frame = QFrame()
        proxy_frame.setStyleSheet(f"QFrame {{ background: {Theme.BG_HOVER_LIGHT}; border-radius: 8px; border: none; }}")
        ph = QHBoxLayout(proxy_frame); ph.setContentsMargins(10, 8, 10, 8); ph.setSpacing(8)
        self._proxy_url  = SearchLineEdit(); self._proxy_url.setFixedHeight(40); self._proxy_url.setPlaceholderText("http://user:pass@proxy.com")
        self._proxy_port = LineEdit();       self._proxy_port.setFixedHeight(40); self._proxy_port.setPlaceholderText("8080"); self._proxy_port.setFixedWidth(70)
        self._style_input(self._proxy_url); self._style_input(self._proxy_port)
        ph.addWidget(self._proxy_url, 1); ph.addWidget(self._proxy_port)
        vl.addWidget(proxy_frame)

        vl.addWidget(self._section_label("User Agents Pool"))
        self._user_agents = TextEdit()
        # FIX 4: flex scroll behavior
        self._user_agents.setMinimumHeight(0)
        self._user_agents.setStyleSheet("""
            QTextEdit {
                background: #1A1A1A;
                color: #8E8E93;
                font-family: 'PT Root UI', monospace;
                font-size: 11px;
                line-height: 1.7;
                border: 1px solid #3A3A3C;
                border-radius: 8px;
                padding: 10px 12px;
            }
            QScrollBar:vertical { width: 4px; background: transparent; }
            QScrollBar::handle:vertical { background: #3A3A3C; border-radius: 2px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)
        vl.addWidget(self._user_agents, 1) # flex factor 1
        return container

    def _build_system(self) -> QWidget:
        container = QWidget(); container.setStyleSheet("background: transparent;")
        vl = QVBoxLayout(container); vl.setContentsMargins(0, 0, 0, 0); vl.setSpacing(0)

        # 1. LOGGING + TIMEOUT labels/inputs
        # ── Group 1: Modern Settings Rows ─────────────────────────────────────
        # Instead of generic columns, we use a "macOS Settings Row" pattern.
        # This increases the vertical height but significantly boosts legibility and "premium" feel.
        
        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        
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

        # Logging Row
        self._log_level = ComboBox(); self._log_level.setFixedHeight(30); self._log_level.setFixedWidth(110)
        self._log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self._log_level.setStyleSheet("ComboBox { background: #2C2C2E; border: 1px solid #3A3A3C; border-radius: 6px; color: white; padding: 0 8px; font-size: 12px; } ComboBox:hover { background: #3A3A3C; }")
        conf_vl.addWidget(_setting_row(FluentIcon.HISTORY, "Logging Level", "Control log verbosity.", self._log_level))
        
        # Divider
        div = QFrame(); div.setFixedHeight(1); div.setStyleSheet("background: rgba(255, 255, 255, 0.04); margin: 0 10px;")
        conf_vl.addWidget(div)

        # Timeout Row
        self._request_timeout = LineEdit(); self._request_timeout.setFixedSize(70, 30)
        self._request_timeout.setValidator(QDoubleValidator(1, 300, 0, self))
        self._request_timeout.setStyleSheet("LineEdit { background: #2C2C2E; border: 1px solid #3A3A3C; border-radius: 6px; color: white; font-family: 'PT Root UI', monospace; font-size: 12px; padding: 0 8px; } LineEdit:focus { border-color: #0A84FF; }")
        conf_vl.addWidget(_setting_row(FluentIcon.SETTING, "Timeout (s)", "Max request duration.", self._request_timeout))
        
        top_split.addWidget(conf_group, 3)

        # ── RIGHT: Action Stack ──────────────────────────────────────────
        action_vl = QVBoxLayout(); action_vl.setSpacing(8); action_vl.setContentsMargins(0, 0, 0, 0)
        
        from PySide6.QtWidgets import QPushButton
        class _Btn(QPushButton): pass

        self._save_btn = _Btn("SAVE CONFIGURATIONS")
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

        self._reset_btn = _Btn("RESET DEFAULTS")
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

        # ── Group 2: Danger Zone card ──────────────────────────────────────────
        danger_card = QFrame()
        danger_card.setObjectName("DangerCard")
        danger_card.setStyleSheet("QFrame#DangerCard { background: rgba(255, 69, 58, 0.05); border: 1px solid rgba(255, 69, 58, 0.12); border-radius: 12px; }")
        danger_hl = QHBoxLayout(danger_card); danger_hl.setContentsMargins(16, 12, 16, 12); danger_hl.setSpacing(12)
        
        from qfluentwidgets import IconWidget
        d_ic = IconWidget(FluentIcon.INFO); d_ic.setFixedSize(16, 16); d_ic.setStyleSheet("color: #FF453A;")
        danger_hl.addWidget(d_ic)

        dtxt = QVBoxLayout(); dtxt.setSpacing(2); dtxt.setContentsMargins(0, 0, 0, 0)
        dh = QLabel("DATABASE PERSISTENCE"); dh.setStyleSheet("color: rgba(255, 69, 58, 0.9); font-size: 10px; font-weight: 800; letter-spacing: 1px;")
        db = QLabel("Permanently purge all locally cached records and results."); db.setStyleSheet("color: #8E8E93; font-size: 11px;")
        dtxt.addWidget(dh); dtxt.addWidget(db)
        danger_hl.addLayout(dtxt, 1)

        self._clear_btn = _Btn("WIPE DATA")
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
        for btn in (self._reset_btn, self._save_btn, self._clear_btn):
            btn.setStyle(QStyleFactory.create("Fusion"))

        vl.addWidget(danger_card)
        vl.addStretch()
        return container



    def _build_protection(self) -> QWidget:
        container = QWidget(); container.setStyleSheet("background: transparent;")
        vl = QVBoxLayout(container); vl.setContentsMargins(0, 0, 0, 0); vl.setSpacing(8)

        # PIN controls merged for density
        pin_ctrls = QWidget()
        ph = QHBoxLayout(pin_ctrls); ph.setContentsMargins(0,0,0,0); ph.setSpacing(8)
        self._btn_set_pin = PushButton("CHANGE PIN"); self._btn_set_pin.setStyleSheet(Theme.secondary_button())
        self._btn_set_pin.setFixedHeight(36)
        self._chk_security_enabled = self._sw()
        ph.addWidget(self._btn_set_pin); ph.addWidget(self._chk_security_enabled)
        vl.addWidget(self._row("Startup PIN Lock", pin_ctrls, "Enable 4-digit security."))

        # Auto Update
        self._chk_auto_update = self._sw()
        vl.addWidget(self._row("Auto Update", self._chk_auto_update, "GitHub core sync."))

        # Core Repo URL
        url_frame = QFrame()
        url_frame.setStyleSheet("QFrame { background: transparent; border: none; }")
        uh = QHBoxLayout(url_frame); uh.setContentsMargins(12, 0, 12, 0); uh.setSpacing(10)
        self._git_repo_url = LineEdit(); self._git_repo_url.setFixedHeight(34)
        self._git_repo_url.setPlaceholderText("Core Repo URL")
        self._git_repo_url.setStyleSheet("""
            LineEdit {
                background: #1C1C1E;
                border: 1px solid #3A3A3C;
                border-radius: 8px;
                color: white;
                font-family: 'PT Root UI', sans-serif;
                font-size: 13px;
                padding: 0 10px;
            }
        """)
        uh.addWidget(self._git_repo_url)
        vl.addWidget(url_frame)

        # Product License
        lic_frame = QFrame()
        lh = QHBoxLayout(lic_frame); lh.setContentsMargins(12, 8, 12, 0); lh.setSpacing(10)
        lt = QVBoxLayout(); lt.setSpacing(2)
        lbl = QLabel("Product License"); lbl.setStyleSheet("color: white; font-family: 'PT Root UI', sans-serif; font-size: 13px; font-weight: 600;")
        self._lic_desc = QLabel("Activating..."); self._lic_desc.setStyleSheet("background: transparent; border: none;")
        lt.addWidget(lbl); lt.addWidget(self._lic_desc); lh.addLayout(lt, 1)
        
        self._btn_activate = PushButton("ACTIVATE"); self._btn_activate.setStyleSheet(Theme.primary_button())
        self._btn_activate.setFixedHeight(36)
        self._btn_deactivate = PushButton("RESET TO TRIAL"); self._btn_deactivate.setStyleSheet(Theme.secondary_button())
        self._btn_deactivate.setFixedHeight(36)
        self._btn_deactivate.clicked.connect(self._reset_to_trial)
        
        lh.addWidget(self._btn_deactivate)
        lh.addWidget(self._btn_activate)
        vl.addWidget(lic_frame)

        vl.addStretch()
        return container

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
            status = '● Activated (PRO)'
            color = "#30D158"
            btn_text = "CHANGE LICENSE"
        else:
            status = '○ Trial / Unactivated'
            color = "#8E8E93"
            btn_text = "ACTIVATE"
            
        self._lic_desc.setText(
            f'<span style="color: {color}; font-family: \'SF Mono\'; font-size: 11px;">{status}</span>'
            f' <span style="color: #3A3A3C; font-family: \'SF Mono\'; font-size: 11px;">|</span>'
            f' <span style="color: #636366; font-family: \'SF Mono\'; font-size: 11px;">Machine ID: {mid}</span>'
        )
        self._btn_activate.setText(btn_text)
        self._btn_activate.setVisible(not is_active)
        self._btn_deactivate.setVisible(is_active)

    def header_action_widgets(self) -> list[QWidget]:
        return []

    def _connect_change_tracking(self):
        for chk in [self._chk_headless, self._chk_robots, self._chk_scrape_emails,
                    self._chk_debug_screenshots, self._chk_proxy,
                    self._chk_security_enabled, self._chk_auto_update]:
            chk.checkedChanged.connect(self._mark_dirty)
        self._chk_security_enabled.checkedChanged.connect(self._on_security_toggled)
        self._btn_activate.clicked.connect(self._open_activation)
        self._btn_set_pin.clicked.connect(self._change_pin)
        for te in [self._discovery_paths, self._user_agents, self._delay_min, 
                    self._delay_max, self._max_results, self._request_timeout]:
            te.textChanged.connect(self._mark_dirty)
        self._proxy_url.textChanged.connect(self._mark_dirty)
        self._proxy_port.textChanged.connect(self._mark_dirty)
        self._git_repo_url.textChanged.connect(self._mark_dirty)
        self._log_level.currentIndexChanged.connect(self._mark_dirty)

    def _mark_dirty(self):
        if not self._dirty:
            self._dirty = True
            self._save_btn.setText("SAVE CONFIGURATIONS *")

    def _mark_clean(self):
        self._dirty = False
        self._save_btn.setText("SAVE CONFIGURATIONS")

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
        self._discovery_paths.setPlainText("\n".join(s.email_discovery_paths))
        self._chk_proxy.setChecked(s.proxy_enabled)
        # Handle transition from proxy_url to proxies list
        main_proxy = s.proxies[0] if s.proxies else ""
        self._proxy_url.setText(main_proxy)
        self._proxy_url.setEnabled(s.proxy_enabled)
        self._proxy_port.setText(self._extract_proxy_port(main_proxy))
        self._proxy_port.setEnabled(s.proxy_enabled)
        self._user_agents.setPlainText("\n".join(s.user_agents))
        idx = self._log_level.findText(s.log_level)
        if idx >= 0:
            self._log_level.setCurrentIndex(idx)
        self._chk_security_enabled.setChecked(s.security_enabled)
        self._btn_set_pin.setVisible(s.security_enabled)
        self._git_repo_url.setText(s.git_repo_url)
        self._chk_auto_update.setChecked(s.auto_update_enabled)
        self._update_license_display()
        self._mark_clean()

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
        paths = [p.strip() for p in self._discovery_paths.toPlainText().splitlines() if p.strip()]
        user_agents = [ua.strip() for ua in self._user_agents.toPlainText().splitlines() if ua.strip()]
        
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
            log_level=self._log_level.currentText(),
            security_enabled=self._chk_security_enabled.isChecked(),
            git_repo_url=self._git_repo_url.text().strip(),
            auto_update_enabled=self._chk_auto_update.isChecked()
        )
        self._mark_clean()
        InfoBar.success("Saved", "Settings Configuration Saved", duration=2000, parent=self.window())

    def _reset(self):
        from .components import ZugzwangDialog
        msg = ZugzwangDialog(
            "Restore Defaults",
            "Reset all settings to factory defaults? This will overwrite your current configuration.",
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
            InfoBar.warning("Job Running", "Stop the current scraping job before clearing saved leads.", parent=self.window())
            return
        
        from .components import ZugzwangDialog
        msg = ZugzwangDialog(
            "Wipe Local DB",
            "Delete all saved leads from the app memory? This permanently clears the restored library.",
            self.window(),
            destructive=True
        )
        if msg.exec():
            try:
                orchestrator.clear_app_memory()
                InfoBar.success("Cleaned", "Saved leads DB cleared", duration=2000, parent=self.window())
            except Exception as e:
                InfoBar.error("Clean Failed", f"Could not clear saved leads: {e}", parent=self.window())
