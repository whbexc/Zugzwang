"""
ZUGZWANG - Main Window (Aesthetic 4.0)
Pivot from Sidebar to Top-Navigation Header for a wide-screen, cinematic feel.
"""

from __future__ import annotations
import re
import asyncio

from PySide6.QtCore import Qt, QSize, QTimer, QRectF, Signal, QEvent, QUrl
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QBrush, QFont, QDesktopServices
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget, QFrame,
    QPushButton, QSizePolicy, QLabel, QMessageBox, QApplication,
)

from qfluentwidgets import (
    FluentIcon, SplashScreen, Theme, setTheme, setThemeColor,
    IconWidget, CaptionLabel, BodyLabel, PushButton, InfoBar, InfoBarPosition
)
from qframelesswindow import FramelessWindow, TitleBar

from .dashboard_page import DashboardPage
from .log_viewer_page import LogViewerPage
from .monitor_page import MonitorPage
from .results_page import ResultsPage
from .search_page import SearchPage
from .settings_page import SettingsPage
from .email_sender_page import EmailSenderPage
from .theme import Theme as AppTheme
from .stylesheet import APP_STYLESHEET
from .icons import load_icon
from .captcha_dialog import CaptchaDialog
from ..core.config import APP_VERSION, config_manager
from ..core.events import event_bus
from ..core.i18n import get_language, is_rtl, tr
from ..core.logger import get_logger, setup_logging
from ..core.models import ScrapingJob, SearchConfig
from ..services.orchestrator import orchestrator
from ..services.update_service import UpdateService

logger = get_logger(__name__)

# ── Palette (Obsidian Core) ──────────────────────────────────────────────────
_BG       = AppTheme.BG_OBSIDIAN
_HEADER   = AppTheme.BG_OBSIDIAN
_DIVIDER  = AppTheme.BORDER_LIGHT
_ACCENT   = AppTheme.ACCENT_PRIMARY

_GLOBAL_CSS = f"""
* {{
    font-family: "-apple-system", "PT Root UI", "BlinkMacSystemFont", "PT Root UI", sans-serif;
}}
QWidget {{ color: {AppTheme.TEXT_PRIMARY}; font-size: 13px; }}
QLabel {{ background: transparent; border: none; }}
/* Specialized Typography */
TitleLabel {{ font-family: "PT Root UI", sans-serif; font-size: 28px; font-weight: 600; color: {AppTheme.TEXT_PRIMARY}; }}
.SectionHeader {{ font-family: "PT Root UI", sans-serif; font-size: 11px; font-weight: 600; letter-spacing: 1.2px; color: {AppTheme.TEXT_TERTIARY}; text-transform: uppercase; }}
ElevatedCardWidget {{ background-color: {AppTheme.BG_ZINC}; border: none; border-radius: {AppTheme.RADIUS_CARD}px; }}
"""


class _HeaderButton(QPushButton):
    """Text-only navigation button matching the user provided reference."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setFixedHeight(44)
        self.setCursor(Qt.PointingHandCursor)
        self._update_style()

    def _update_style(self):
        active_color = "#FFFFFF"
        idle_color = AppTheme.TEXT_TERTIARY
        
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {active_color if self.isChecked() else idle_color};
                font-family: "PT Root UI", sans-serif;
                font-size: 13px;
                letter-spacing: 0.3px;
                padding: 0 16px;
            }}
            QPushButton:hover {{
                color: #FFFFFF;
            }}
        """)

    def setChecked(self, checked: bool):
        super().setChecked(checked)
        self._update_style()


class _Header(QFrame):
    """Horizontal navigation bar directly below the Title Bar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(52) # Increased slightly to house the nav
        self.setObjectName("GlobalHeader")
        
        # 5.0 ZUGZWANG Simulated Vibrancy nav
        self.setStyleSheet(f"""
            QFrame#GlobalHeader {{
                background-color: rgba(28, 28, 30, 0.85); /* simulated vibrancy */
                border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            }}
        """)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(16, 0, 16, 0)
        self.layout.setSpacing(4)
        self.layout.setAlignment(Qt.AlignCenter) # Center nav

    def add_button(self, btn: _HeaderButton):
        self.layout.addWidget(btn)


class _CustomTitleBar(TitleBar):
    """Minimal title bar matching the app dark style."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setFixedHeight(48)
        self.setStyleSheet(f"TitleBar {{ background-color: {_BG}; border-bottom: none; }}")

        while self.hBoxLayout.count() > 0:
            item = self.hBoxLayout.takeAt(0)
            if item.widget(): item.widget().setParent(None)

        self.hBoxLayout.setContentsMargins(0, 0, 0, 0); self.hBoxLayout.setSpacing(0)

        # Left area: Status + Name
        left_area = QWidget(); left_area.setStyleSheet("background: transparent;")
        left_layout = QHBoxLayout(left_area); left_layout.setContentsMargins(20, 0, 16, 0); left_layout.setSpacing(10)
        left_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self._status_dot = QFrame(); self._status_dot.setFixedSize(8, 8)
        self._status_dot.setStyleSheet(f"background: {AppTheme.TEXT_TERTIARY}; border-radius: 4px;")
        left_layout.addWidget(self._status_dot)

        self._name = QLabel("ZUGZWANG")
        self._name.setStyleSheet(f"color: #FFFFFF; font-family: 'PT Root UI', sans-serif; font-size: 13px; font-weight: 700; background: transparent;")
        left_layout.addWidget(self._name)

        left_area.setFixedWidth(220)
        self.hBoxLayout.addWidget(left_area)

        self.hBoxLayout.addStretch(1)

        # Center nav container (to be populated by MainWindow)
        self._center_nav_anchor = QWidget()
        self._center_nav_anchor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.hBoxLayout.addWidget(self._center_nav_anchor)

        self.hBoxLayout.addStretch(1)

        right_area = QWidget()
        right_area.setStyleSheet("background: transparent;")
        right_area.setFixedWidth(168)
        right_layout = QHBoxLayout(right_area)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_layout.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # Hide the library's own buttons - we draw our own
        self.minBtn.hide()
        self.maxBtn.hide()
        self.closeBtn.hide()

        _btn_style = """
            QPushButton {{
                background: transparent;
                border: none;
                color: #AEAEB2;
                font-size: {size}px;
                font-family: 'Segoe MDL2 Assets', 'Segoe Fluent Icons', 'Segoe UI Symbol';
                min-width: 46px; max-width: 46px;
                min-height: 48px; max-height: 48px;
                padding: 0;
            }}
            QPushButton:hover {{
                background: {hover};
                color: #FFFFFF;
            }}
            QPushButton:pressed {{
                background: {pressed};
                color: #FFFFFF;
            }}
        """

        # Minimize  (ChromeMinimize \uE921)
        self._min_btn = QPushButton("\uE921", right_area)
        self._min_btn.setStyleSheet(_btn_style.format(size=10, hover="rgba(255,255,255,0.08)", pressed="rgba(255,255,255,0.14)"))
        self._min_btn.setCursor(Qt.ArrowCursor)
        self._min_btn.setToolTip("Minimize")
        self._min_btn.clicked.connect(parent.showMinimized)
        right_layout.addWidget(self._min_btn)

        # Maximize (ChromeMaximize \uE922)
        self._max_btn = QPushButton("\uE922", right_area)
        self._max_btn.setStyleSheet(_btn_style.format(size=10, hover="rgba(255,255,255,0.08)", pressed="rgba(255,255,255,0.14)"))
        self._max_btn.setCursor(Qt.ArrowCursor)
        self._max_btn.setToolTip("Maximize")
        self._max_btn.clicked.connect(self._toggle_maximize)
        right_layout.addWidget(self._max_btn)

        # Close (ChromeClose \uE8BB)
        self._close_btn = QPushButton("\uE8BB", right_area)
        self._close_btn.setStyleSheet(_btn_style.format(size=12, hover="#C42B1C", pressed="#B8261A"))
        self._close_btn.setCursor(Qt.ArrowCursor)
        self._close_btn.setToolTip("Close")
        self._close_btn.clicked.connect(parent.close)
        right_layout.addWidget(self._close_btn)

        self.hBoxLayout.addWidget(right_area)

    def _toggle_maximize(self):
        win = self.window()
        if win.isMaximized():
            win.showNormal()
        else:
            win.showMaximized()

    def updateMaximizeButton(self, isMaximized: bool):
        """Toggle ChromeRestore \uE923 <-> ChromeMaximize \uE922"""
        self._max_btn.setText("\uE923" if isMaximized else "\uE922")
        self._max_btn.setToolTip("Restore" if isMaximized else "Maximize")

    def set_status(self, active: bool):
        color = "#0A84FF" if active else "#48484A"
        border = "2px solid rgba(10,132,255,0.4)" if active else "none"
        self._status_dot.setStyleSheet(f"background: {color}; border: {border}; border-radius: 4px;")

    def set_stats(self, count: int):
        pass

    def eventFilter(self, obj, event):
        return super().eventFilter(obj, event)


class MainWindow(FramelessWindow):
    # Signals for thread-safe UI updates from background scraper
    captcha_requested = Signal(str, bytes)
    solver_requested = Signal(str, str, list, str) # job_id, url, cookies, user_agent
    """App root window (Aesthetic 4.0) - Full-width, Top-Navigation."""

    def __init__(self):
        super().__init__()
        self._language = get_language(config_manager.settings.app_language)
        setTheme(Theme.DARK); setThemeColor(QColor(_ACCENT))
        setup_logging(config_manager.settings.log_level)
        self.setWindowTitle(f"{tr('app.title', self._language)} {APP_VERSION}")
        self.setWindowIcon(load_icon("logo-mark.png"))
        self.setTitleBar(_CustomTitleBar(self))
        self.resize(1280, 800); self.setMinimumSize(1000, 650)
        self.setStyleSheet(_GLOBAL_CSS + APP_STYLESHEET)
        QApplication.instance().setLayoutDirection(Qt.RightToLeft if is_rtl(self._language) else Qt.LeftToRight)

        self.splashScreen = SplashScreen(self.windowIcon(), self)
        self.splashScreen.setIconSize(QSize(102, 102)); self.splashScreen.raise_()

        # Pages (Initialize only Dashboard on startup for speed)
        self.dashboard_page = DashboardPage()
        
        # Registry for delayed initialization
        self._page_instances: dict[int, QWidget] = {0: self.dashboard_page}
        self._page_factories = {
            1: SearchPage,
            2: ResultsPage,
            3: MonitorPage,
            4: EmailSenderPage,
            5: SettingsPage,
            6: LogViewerPage
        }
        
        self._jobs = []
        self._active_captcha_dialog = None

        self._build_shell()
        self._connect_signals()
        # Bridge signals from background threads to UI thread via EventBridge
        from .event_bridge import event_bridge
        event_bridge.captcha_challenge.connect(self._show_captcha_dialog)
        event_bridge.solver_requested.connect(self._launch_headed_solver)
        event_bridge.job_started.connect(lambda: self.titleBar.set_status(True))
        event_bridge.job_completed.connect(lambda: self.titleBar.set_status(False))
        event_bridge.job_failed.connect(lambda: self.titleBar.set_status(False))
        event_bridge.db_updated.connect(self._on_db_updated)

        # ── Feature: What's New Changelog Popup ───────────────────────────
        from ..changelog import APP_VERSION as changelog_version
        last_seen = config_manager.settings.last_seen_version
        if last_seen != changelog_version:
            QTimer.singleShot(1000, self._show_whats_new)
            config_manager.settings.last_seen_version = changelog_version
            config_manager.save()

        # ── Improvement 3: ToastManager ───────────────────────────────────

        from .toast_manager import ToastManager
        self._toast_manager = ToastManager(self)
        self._setup_toasts(event_bridge)

        # ── Improvement 4: Keyboard Shortcuts ─────────────────────────────
        self._setup_shortcuts()

        self.splashScreen.finish()

        self.update_service = UpdateService(self)
        if config_manager.settings.auto_update_enabled:
            self.update_service.update_available.connect(self._show_update_dialog)
            QTimer.singleShot(5000, self.update_service.check)

    def _build_shell(self):
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)
        root.addWidget(self.titleBar)

        # Center nav area inside TitleBar (structural update)
        self._nav_layout = QHBoxLayout(self.titleBar._center_nav_anchor)
        self._nav_layout.setContentsMargins(0, 0, 0, 0); self._nav_layout.setSpacing(4)
        self._nav_layout.setAlignment(Qt.AlignCenter)
        
        # Full-width Stack
        self._stack = QStackedWidget(); self._stack.setStyleSheet(f"background: {_BG};")
        root.addWidget(self._stack, 1)

        # Map identifiers for text buttons
        self._page_config = [
            (0, tr("nav.dashboard", self._language)),
            (1, tr("nav.search", self._language)),
            (2, tr("nav.statistics", self._language)),
            (3, tr("nav.monitor", self._language)),
            (4, tr("nav.send", self._language)),
            (5, tr("nav.settings", self._language)),
            (6, tr("nav.logs", self._language)),
        ]

        self._page_btns = {}
        # Pre-seed stack with just the dashboard
        self._stack.addWidget(self.dashboard_page)
        
        # Create spacers/placeholders in the stack for others to maintain indices
        for _ in range(1, 7):
            placeholder = QWidget()
            self._stack.addWidget(placeholder)

        for idx, label in self._page_config:
            btn = _HeaderButton(label)
            btn.clicked.connect(lambda _, i=idx: self._switch(i))
            self._nav_layout.addWidget(btn)
            self._page_btns[idx] = btn

        self._whats_new_btn = _HeaderButton("?")
        self._whats_new_btn.setToolTip("What's New in ZUGZWANG (Ctrl+Shift+W)")
        self._whats_new_btn.setStyleSheet(btn.styleSheet() + "font-weight: bold;")
        self._whats_new_btn.clicked.connect(self._show_whats_new)
        self._nav_layout.addWidget(self._whats_new_btn)

        # ── Option 2: The Sponsor Navigation Card (Button) ────────────────
        self._support_btn = _HeaderButton("💖")
        self._support_btn.setToolTip("Support the Developer")
        self._support_btn.setStyleSheet(btn.styleSheet() + "font-size: 14px; color: #FF453A;")
        self._support_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://wa.me/212663007212?text=slm%20khoya%20khdmt%20b%20app%20dylk%20w%20bghit%20n%20supportik,")))
        self._nav_layout.addWidget(self._support_btn)

        self._switch(0)
        # Defer DB load until after the splash screen / main loop to ensure stability
        QTimer.singleShot(800, self._restore_saved_results)

    def _switch(self, idx: int):
        # Lazy initialization
        if idx not in self._page_instances and idx in self._page_factories:
            page_class = self._page_factories[idx]
            print(f"[DEBUG] Lazily initializing page {idx}: {page_class.__name__}")
            instance = page_class()
            self._page_instances[idx] = instance
            
            # Replace placeholder in stack
            old = self._stack.widget(idx)
            self._stack.removeWidget(old)
            self._stack.insertWidget(idx, instance)
            old.deleteLater()
            
            # Post-initialization signal wiring
            self._wire_lazy_signals(idx, instance)

        self._stack.setCurrentIndex(idx)
        if idx == 2:
            results_page = self._page_instances.get(2)
            if results_page:
                self._sync_results_page(results_page)
        for i, btn in self._page_btns.items():
            btn.setChecked(i == idx)

    def _wire_lazy_signals(self, idx: int, instance: QWidget):
        """Connect signals for pages created on-demand."""
        if idx == 1: # SearchPage
            instance.job_requested.connect(self._start_job)
        elif idx == 2: # ResultsPage
            instance.send_emails_to_sender.connect(self._on_send_emails)
            self._sync_results_page(instance)
        elif idx == 4: # EmailSenderPage
            pass # Currently no unique signals to MainWindow

    def switchTo(self, page: QWidget):
        idx = self._stack.indexOf(page)
        if idx >= 0: self._switch(idx)

    def _connect_signals(self):
        self.dashboard_page.navigate_to_search.connect(lambda: self._switch(1))
        self.dashboard_page.navigate_to_results.connect(lambda: self._switch(2))
        # ── Improvement 2: rerun_requested ────────────────────────────────
        self.dashboard_page.rerun_requested.connect(self._on_rerun_requested)

    def _on_rerun_requested(self, config) -> None:
        """Re-run a previous SearchConfig from a dashboard job card."""
        label = getattr(config, "job_title", "?") or "?"
        city = getattr(config, "city", "") or ""
        self._start_job(config)
        if hasattr(self, "_toast_manager"):
            self._toast_manager.show(
                f"Re-running: {label}",
                city,
                toast_type="info",
                duration=3000,
            )

    def _setup_toasts(self, event_bridge) -> None:
        """Connect event_bridge signals to ToastManager for live notifications."""
        self._result_count = 0

        def _on_result(record=None, **kw):
            self._result_count += 1
            if self._result_count % 10 == 0:
                source = ""
                if record and hasattr(record, "source_type"):
                    source = str(getattr(record.source_type, "value", "")).replace("_", " ").title()
                self._toast_manager.show(
                    f"↓ {self._result_count} leads found",
                    source, toast_type="info", duration=2500
                )
            
            # Milestone Celebration Toasts
            milestones = [20, 50, 100, 200, 300, 500, 1000, 2000, 5000, 10000]
            if self._result_count in milestones:
                self._toast_manager.show(
                    f"🎉 {self._result_count} LEADS EXTRACTED! 🎉",
                    "If ZUGZWANG is supercharging your business, grab the developer a coffee from the Dashboard!",
                    toast_type="success", duration=6000
                )

        def _on_completed(job_id=None, total_found=0, total_emails=0, **kw):
            self._result_count = 0
            source = ""
            if orchestrator.current_job and hasattr(orchestrator.current_job, "config"):
                st = getattr(orchestrator.current_job.config, "source_type", None)
                source = str(getattr(st, "value", "")).replace("_", " ").title()
            self._toast_manager.show(
                f"✓ {total_found:,} leads found",
                source, toast_type="success", duration=5000
            )

        def _on_failed(job_id=None, error="", **kw):
            self._result_count = 0
            self._toast_manager.show(
                "✗ Scrape error",
                str(error)[:80], toast_type="error", duration=5000
            )

        def _on_trial_limit(job_id=None, **kw):
            self._toast_manager.show(
                "⚠ Free trial limit reached (20/day)",
                "Activate the full version for unlimited scraping.",
                toast_type="warning", duration=5000
            )

        event_bridge.job_result.connect(lambda rec: _on_result(record=rec))
        event_bridge.job_completed.connect(lambda jid, total, emails: _on_completed(total_found=total))
        event_bridge.job_failed.connect(lambda jid, err: _on_failed(error=err))
        event_bridge.trial_limit_reached.connect(lambda jid: _on_trial_limit())

        # Support for direct toast requests via event_bus
        from ..core.events import event_bus
        
        def _on_custom_toast(title="", subtitle="", type="info", duration=4000, **kw):
            if hasattr(self, "_toast_manager"):
                self._toast_manager.show(title, subtitle, type, duration)
        
        event_bus.subscribe("toast.show", _on_custom_toast)

        # Rate limit event from core event_bus
        def _on_rate_limit(**kw):
            self._toast_manager.show(
                "⚠ Rate limit detected — slowing down",
                "", toast_type="warning", duration=3500
            )
        event_bus.subscribe("rate_limit.detected", _on_rate_limit)

    def _show_whats_new(self):
        """Displays the What's New changelog dialog."""
        from .whats_new_dialog import WhatsNewDialog
        from ..changelog import APP_VERSION
        dialog = WhatsNewDialog(current_version=APP_VERSION, parent=self)
        dialog.exec()

    def _setup_shortcuts(self):
        from PySide6.QtGui import QKeySequence, QShortcut
        # Show What's New
        self._whatsnew_shortcut = QShortcut(QKeySequence("Ctrl+Shift+W"), self)
        self._whatsnew_shortcut.activated.connect(self._show_whats_new)

        # Navigation: Ctrl+1..6
        for i in range(7):
            def _nav(checked=False, idx=i):
                self._switch(idx)
            QShortcut(QKeySequence(f"Ctrl+{i+1}"), self, activated=_nav)

        # Ctrl+, → Settings
        QShortcut(QKeySequence("Ctrl+,"), self, activated=lambda: self._switch(5))

        # Ctrl+N → New Search (switch + clear form)
        def _new_search():
            self._switch(1)
            search_page = self._page_instances.get(1)
            if search_page and hasattr(search_page, "_clear_form"):
                search_page._clear_form()
        QShortcut(QKeySequence("Ctrl+N"), self, activated=_new_search)

        # Ctrl+E → Export (navigate to stats)
        def _export():
            self._switch(2)
            results_page = self._page_instances.get(2)
            if results_page and hasattr(results_page, "_export_btn"):
                results_page._export_btn.click()
        QShortcut(QKeySequence("Ctrl+E"), self, activated=_export)

        # Ctrl+F → Focus search bar on stats page
        def _focus_search():
            self._switch(2)
            results_page = self._page_instances.get(2)
            if results_page and hasattr(results_page, "_search_input"):
                results_page._search_input.setFocus()
        QShortcut(QKeySequence("Ctrl+F"), self, activated=_focus_search)

        # Ctrl+R → Re-run last search from history
        def _rerun_last():
            rows = config_manager.get_search_history()
            if rows:
                from ..core.models import SearchConfig, SourceType
                row = rows[0]
                _, job_title, city, source, offer_type, _ = row
                st_map = {
                    "maps": SourceType.GOOGLE_MAPS,
                    "jobsuche": SourceType.JOBSUCHE,
                    "ausbildung": SourceType.AUSBILDUNG_DE,
                    "aubiplus": SourceType.AUBIPLUS_DE,
                }
                cfg = SearchConfig(
                    job_title=job_title or "",
                    city=city or "",
                    source_type=st_map.get(source or "maps", SourceType.GOOGLE_MAPS),
                    offer_type=offer_type or "Arbeit",
                )
                self._on_rerun_requested(cfg)
        QShortcut(QKeySequence("Ctrl+R"), self, activated=_rerun_last)

        # Escape → Stop job confirmation
        def _on_escape():
            if orchestrator.is_running:
                from .components import ZugzwangDialog
                dialog = ZugzwangDialog("Stop Job?", "Are you sure you want to cancel the active scraping job?", self, destructive=True)
                dialog.ok_btn.setText("STOP")
                if dialog.exec():
                    orchestrator.cancel_job()
        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=_on_escape)

        # "?" → Show shortcut help dialog
        def _show_help():
            from .shortcut_dialog import ShortcutHelpDialog
            ShortcutHelpDialog(self).exec()
        QShortcut(QKeySequence("?"), self, activated=_show_help)

        # Ctrl+Shift+W → Show What's New Dialog
        QShortcut(QKeySequence("Ctrl+Shift+W"), self, activated=self._show_whats_new)

    def _show_whats_new(self):
        from .whats_new_dialog import WhatsNewDialog
        from ..changelog import APP_VERSION
        dialog = WhatsNewDialog(current_version=APP_VERSION, parent=self)
        dialog.exec()

    def show_activation_dialog(self):
        """Centralized activation check with navigation support."""
        from .activation_dialog import ActivationDialog
        dialog = ActivationDialog(self)
        dialog.open_send_requested.connect(lambda: self._switch(4))
        return dialog.exec()

    def _show_update_dialog(self, version: str, url: str):
        """Show the macOS-style update notification."""
        from .update_dialog import UpdateDialog
        self._update_dialog = UpdateDialog(version, url, self)
        self._update_dialog.update_started.connect(self._on_update_started)
        self._update_dialog.show()

    def _on_update_started(self, url: str):
        """Handle 'Update Now' button click from dialog."""
        self.update_service.start_download(
            url,
            progress_callback=self._update_dialog.set_progress,
            finished_callback=self._on_update_downloaded,
            error_callback=self._update_dialog.set_error
        )

    def _on_update_downloaded(self, path: str):
        """Handle successful download."""
        self.update_service.apply_update(path)

    def _restore_saved_results(self):
        try:
            records = orchestrator.load_app_memory()
            self._on_db_updated(records=records or [])
        except Exception: 
            self._on_db_updated(records=[])

    def _on_db_updated(self, records=None, **kw):
        records = records or []
        # Update results page if it's already instantiated
        results_page = self._page_instances.get(2)
        if results_page:
            self._sync_results_page(results_page, fallback_records=records)
        
        self.titleBar.set_stats(len(records))
        self.dashboard_page.load_summary(len(records), sum(1 for r in records if r.email), sum(1 for r in records if r.website))
        # Ensure Recent Jobs list matches the newly loaded context
        self.dashboard_page._load_recent_jobs_from_disk()

    def _start_job(self, config: SearchConfig):
        if orchestrator.is_running: return
        try:
            orchestrator.start_job(config)
            self._switch(3) # Switch to MONITOR
        except Exception as e:
            from .components import ZugzwangDialog
            ZugzwangDialog("Error", str(e), self).exec()

    def _on_send_emails(self, emails: list[str]):
        # Ensure sender page exists
        self._switch(4) # Switch to SEND
        sender_page = self._page_instances.get(4)
        if sender_page:
            sender_page.import_emails(emails)

    def closeEvent(self, event):
        orchestrator.persist_current_job()
        if orchestrator.is_running:
            orchestrator.cancel_job()
        event.accept()

    def _on_captcha_challenge(self, job_id: str, image: bytes, **kw):
        """Callback from background thread (event_bus). Marshall to UI thread."""
        print(f"[DEBUG] event_bus: challenge received for {job_id}")
        self.captcha_requested.emit(job_id, image)

    def _show_captcha_dialog(self, job_id: str, image: bytes):
        """Actually shows the dialog (runs in main thread)."""
        print(f"[DEBUG] UI THREAD: showing solver for {job_id}")
        try:
            if not self._active_captcha_dialog:
                from .captcha_dialog import CaptchaDialog
                self._active_captcha_dialog = CaptchaDialog(job_id, self)
                self._active_captcha_dialog.finished.connect(self._on_captcha_finished)
                self._active_captcha_dialog.show()
                self._active_captcha_dialog.raise_()
                self._active_captcha_dialog.activateWindow()
            
            self._active_captcha_dialog.update_screenshot(image)
        except Exception as e:
            print(f"[DEBUG] UI THREAD ERROR: {e}")
            logger.error(f"CAPTCHA UI ERROR: {e}", exc_info=True)

    def _on_captcha_finished(self, result):
        print(f"[DEBUG] Solver finished for {self._active_captcha_dialog.job_id if self._active_captcha_dialog else 'unknown'}")
        self._active_captcha_dialog = None

    def _on_solver_requested(self, job_id: str, url: str, cookies: list, user_agent: str = "", **kw):
        """Marshall solver request to UI thread."""
        self.solver_requested.emit(job_id, url, cookies, user_agent)

    def _launch_headed_solver(self, job_id: str, url: str, cookies: list, user_agent: str = ""):
        """Open a REAL browser window for the user to solve the captcha."""
        logger.info(f"[{job_id}] Launching headed solver for {url}")
        
        # We need to run this in a way that doesn't block the UI thread but allows the user to interact
        # A simple approach is to use a QThread or just launch a subprocess.
        # But since we want to share cookies back, we'll use a dedicated worker.
        from qfluentwidgets import InfoBar, InfoBarPosition
        InfoBar.info(
            title="Sicherheitsabfrage",
            content="A browser window has opened. Please solve the captcha and close the window to continues.",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=10000,
            parent=self
        )

        async def solver_task():
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=False)
                
                context_kwargs = {}
                if user_agent:
                    context_kwargs["user_agent"] = user_agent
                
                context = await browser.new_context(**context_kwargs)
                if cookies:
                    await context.add_cookies(cookies)
                
                page = await context.new_page()
                page.set_default_timeout(0) # No timeout for manual solving
                await page.goto(url)

                def _captcha_still_present() -> str:
                    return """() => {
                        const text = document.body.innerText.toLowerCase();
                        if (document.title.toLowerCase().includes('sicherheitsabfrage')) return true;
                        const h1 = document.querySelector('h1');
                        if (h1 && h1.innerText.toLowerCase().includes('sicherheitsabfrage')) return true;
                        if (document.querySelector('#captchaForm')) return true;
                        if (document.querySelector('#kontaktdaten-captcha-input')) return true;
                        if (document.querySelector('#kontaktdaten-captcha-absenden-button')) return true;
                        if (document.querySelector('[id*="kontaktdaten-captcha"]')) return true;
                        if (text.includes('ich bin kein roboter')) return true;
                        if (text.includes('verify you are human')) return true;
                        if (text.includes('beim laden der sicherheitsabfrage')) return true;
                        return false;
                    }"""

                clear_checks = 0
                captcha_seen_once = False
                solver_started_at = asyncio.get_running_loop().time()
                while browser.is_connected():
                    pages = context.pages
                    if not pages:
                        break
                    try:
                        challenge_present = await page.evaluate(_captcha_still_present())
                        if challenge_present:
                            captcha_seen_once = True
                            clear_checks = 0
                        else:
                            if captcha_seen_once and (asyncio.get_running_loop().time() - solver_started_at) >= 4.0:
                                clear_checks += 1
                            else:
                                clear_checks = 0
                        if captcha_seen_once and clear_checks >= 2:
                            break
                    except Exception:
                        pass
                    await asyncio.sleep(1)

                final_cookies = await context.cookies()
                event_bus.emit(event_bus.SOLVER_COMPLETED, job_id=job_id, cookies=final_cookies)
                await browser.close()

        def run_it():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(solver_task())
            loop.close()

        import threading
        threading.Thread(target=run_it, daemon=True).start()

    def _sync_results_page(self, results_page: QWidget, fallback_records=None) -> None:
        """Sync full historical records from the orchestrator to the Results page."""
        records = []
        
        # Always prefer the full cumulative memory from the orchestrator
        records = orchestrator.get_app_memory_records()
        
        # If orchestrator memory is empty but we have fallback records (e.g. from a specific project load)
        if not records and fallback_records:
            records = list(fallback_records)

        if records:
            results_page.load_records(records)

    def paintEvent(self, e):
        painter = QPainter(self); painter.fillRect(self.rect(), QColor(_BG))
