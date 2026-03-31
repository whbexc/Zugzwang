"""
ZUGZWANG - Main Window (Aesthetic 4.0)
Pivot from Sidebar to Top-Navigation Header for a wide-screen, cinematic feel.
"""

from __future__ import annotations
import re
import asyncio

from PySide6.QtCore import Qt, QSize, QTimer, QRectF, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QBrush, QFont
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
        self._name.setStyleSheet(f"color: #FFFFFF; font-family: 'PT Root UI', sans-serif; font-size: 14px; font-weight: 600; background: transparent;")
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
        right_area.setFixedWidth(220)
        right_layout = QHBoxLayout(right_area)
        right_layout.setContentsMargins(0, 0, 10, 0)
        right_layout.setSpacing(0)
        right_layout.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # Window control buttons (Force High-Visibility White)
        for btn in [self.minBtn, self.maxBtn, self.closeBtn]:
            btn.setFixedSize(46, 40)
            btn.setNormalColor(Qt.white)
            btn.setHoverColor(Qt.white)
            btn.setPressedColor(Qt.white)
            btn.setStyleSheet("background: transparent; border: none;")
            right_layout.addWidget(btn)

        self.hBoxLayout.addWidget(right_area)

    def set_status(self, active: bool):
        color = "#0A84FF" if active else "#48484A"
        border = "2px solid rgba(10,132,255,0.4)" if active else "none"
        self._status_dot.setStyleSheet(f"background: {color}; border: {border}; border-radius: 4px;")

    def set_stats(self, count: int):
        pass


class MainWindow(FramelessWindow):
    # Signals for thread-safe UI updates from background scraper
    captcha_requested = Signal(str, bytes)
    solver_requested = Signal(str, str, list, str) # job_id, url, cookies, user_agent
    """App root window (Aesthetic 4.0) - Full-width, Top-Navigation."""

    def __init__(self):
        super().__init__()
        setTheme(Theme.DARK); setThemeColor(QColor(_ACCENT))
        setup_logging(config_manager.settings.log_level)
        self.setWindowTitle(f"ZUGZWANG {APP_VERSION}")
        self.setWindowIcon(load_icon("logo-mark.png"))
        self.setTitleBar(_CustomTitleBar(self))
        self.resize(1280, 800); self.setMinimumSize(1000, 650)
        self.setStyleSheet(_GLOBAL_CSS + APP_STYLESHEET)

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
        self._connect_signals(); self._restore_saved_results()
        # Bridge signals from background threads to UI thread via EventBridge
        from .event_bridge import event_bridge
        event_bridge.captcha_challenge.connect(self._show_captcha_dialog)
        event_bridge.solver_requested.connect(self._launch_headed_solver)
        event_bridge.job_started.connect(lambda: self.titleBar.set_status(True))
        event_bridge.job_completed.connect(lambda: self.titleBar.set_status(False))
        event_bridge.job_failed.connect(lambda: self.titleBar.set_status(False))
        event_bridge.db_updated.connect(self._on_db_updated)
        
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
            (0, "DASHBOARD"),
            (1, "SEARCH"),
            (2, "STATISTICS"),
            (3, "MONITOR"),
            (4, "SEND"),
            (5, "SETTINGS"),
            (6, "LOGS"),
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

        self._switch(0)
        # Defer DB load until after the splash screen / main loop
        QTimer.singleShot(500, self._restore_saved_results)

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
        for i, btn in self._page_btns.items():
            btn.setChecked(i == idx)

    def _wire_lazy_signals(self, idx: int, instance: QWidget):
        """Connect signals for pages created on-demand."""
        if idx == 1: # SearchPage
            instance.job_requested.connect(self._start_job)
        elif idx == 2: # ResultsPage
            instance.send_emails_to_sender.connect(self._on_send_emails)
            # Seed with any already-loaded results
            records = orchestrator.load_app_memory()
            if records: instance.load_records(records)
        elif idx == 4: # EmailSenderPage
            pass # Currently no unique signals to MainWindow

    def switchTo(self, page: QWidget):
        idx = self._stack.indexOf(page)
        if idx >= 0: self._switch(idx)

    def _connect_signals(self):
        self.dashboard_page.navigate_to_search.connect(lambda: self._switch(1))
        self.dashboard_page.navigate_to_results.connect(lambda: self._switch(2))

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
            if records: self._on_db_updated(records=records)
        except Exception: pass

    def _on_db_updated(self, records=None, **kw):
        records = records or []
        # Update results page if it's already instantiated
        results_page = self._page_instances.get(2)
        if results_page:
            results_page.load_records(records)
        
        self.titleBar.set_stats(len(records))
        self.dashboard_page.load_summary(len(records), sum(1 for r in records if r.email), sum(1 for r in records if r.website))

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
        if orchestrator.is_running: orchestrator.cancel_job()
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
                
                # Wait for user to close the browser
                while True:
                    if browser.is_connected():
                        pages = context.pages
                        if not pages: break
                        await asyncio.sleep(1)
                    else: break
                
                # Get updated cookies
                final_cookies = await context.cookies()
                await browser.close()
                
                # Notify scraper
                event_bus.emit(event_bus.SOLVER_COMPLETED, job_id=job_id, cookies=final_cookies)

        def run_it():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(solver_task())
            loop.close()

        import threading
        threading.Thread(target=run_it, daemon=True).start()

    def paintEvent(self, e):
        painter = QPainter(self); painter.fillRect(self.rect(), QColor(_BG))
