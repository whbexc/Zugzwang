"""
ZUGZWANG - Monitor Page
Modern Fluent 2030 Edition live scraping monitor.
"""

from __future__ import annotations

import queue
import re
import time
from typing import Optional

from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QWidget, QFrame, QGridLayout, QLabel, 
    QTextBrowser, QSizePolicy, QPushButton, QGraphicsOpacityEffect
)

from qfluentwidgets import (
    CardWidget, ElevatedCardWidget, PrimaryPushButton, PushButton, TransparentPushButton,
    TitleLabel, SubtitleLabel, BodyLabel, CaptionLabel, StrongBodyLabel, InfoBadge,
    ProgressBar, IconWidget, FluentIcon, SimpleCardWidget, ScrollArea, MessageBox
)

from ..core.events import event_bus
from ..core.config import config_manager
from ..core.i18n import get_language, tr
from ..services.orchestrator import orchestrator
from .theme import Theme



_URL_RE = re.compile(r"(https?://[^\s]+)")


class MetricTile(QFrame):
    """High-end metric tile for the monitor."""
    def __init__(self, title: str, value: str = "0", meta: str = "",
                 icon: FluentIcon = FluentIcon.INFO,
                 color: str = "#0A84FF"):
        super().__init__()
        self.setMinimumHeight(100)
        self.setStyleSheet("MetricTile { background: #2C2C2E; border-radius: 12px; border: none; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)

        top = QHBoxLayout()
        top.setSpacing(8)
        
        icon_w = IconWidget(icon)
        icon_w.setFixedSize(18, 18)
        icon_w.setStyleSheet(f"color: {color}; background: transparent; border: none;")
        top.addWidget(icon_w)

        self._title = QLabel(str(title).upper())
        self._title.setStyleSheet("color: #8E8E93; font-family: '-apple-system', sans-serif; font-size: 11px; font-weight: 600; letter-spacing: 1.5px; background: transparent; border: none;")
        top.addWidget(self._title)
        top.addStretch(1)
        layout.addLayout(top)

        row = QHBoxLayout()
        self._value = QLabel(value)
        self._value.setStyleSheet(f"color: {color}; font-family: 'PT Root UI', sans-serif; font-size: 36px; font-weight: 700; background: transparent; border: none; padding: 0; margin-top: 4px;")
        row.addWidget(self._value)
        row.addStretch()

        self._meta = QLabel(meta)
        self._meta.setStyleSheet("color: #636366; font-family: '-apple-system', sans-serif; font-size: 11px; font-weight: 500; background: transparent; border: none;")
        row.addWidget(self._meta, 0, Qt.AlignBottom)
        layout.addLayout(row)

    def set_value(self, text: str) -> None:
        self._value.setText(text)

    def set_meta(self, text: str) -> None:
        self._meta.setText(text)

class MonitorControlButton(QPushButton):
    """Custom high-fidelity button with stable icon/text alignment."""
    def __init__(self, text: str, is_danger: bool = False, is_primary: bool = False, 
                 is_success: bool = False, is_warning: bool = False):
        super().__init__()
        self.setFixedHeight(36)
        self.setCursor(Qt.PointingHandCursor)
        self.setText(text.upper())
        self.is_danger = is_danger
        self.is_primary = is_primary
        self.is_success = is_success
        self.is_warning = is_warning
        self._set_style()

    def _set_style(self):
        if self.is_danger:
            self.setStyleSheet(Theme.zugzwang_danger_button())
        elif self.is_primary:
            self.setStyleSheet(Theme.zugzwang_primary_button())
        elif self.is_success:
            self.setStyleSheet(Theme.zugzwang_success_button())
        elif self.is_warning:
            self.setStyleSheet(Theme.zugzwang_warning_button())
        else:
            self.setStyleSheet(Theme.zugzwang_button())


class MonitorPage(QWidget):
    """Live scraping monitor rebuilt with PySide6-Fluent-Widgets."""

    def __init__(self):
        super().__init__()
        self._is_paused = False
        self._job_start_time = 0.0
        self._total_expected_results = 0
        self._user_scrolling = False
        self._active_job_id: Optional[str] = None
        self._update_queue: queue.Queue = queue.Queue()
        self._language = get_language(config_manager.settings.app_language)

        self._build_ui()
        self._connect_events()

        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._drain_queue)
        self._timer.start()

    def _build_ui(self):
        self.setStyleSheet("MonitorPage { background: #1C1C1E; }")
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 32)
        root.setSpacing(20)

        # ── Page Header ────────────────────────────────────────────────────────
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 4)

        self._page_title = QLabel(tr("monitor.title", self._language))
        self._page_title.setStyleSheet("color: white; font-family: 'PT Root UI', sans-serif; font-size: 28px; font-weight: 600; letter-spacing: 0.3px;")
        header_row.addWidget(self._page_title)
        header_row.addStretch(1)

        self._status_badge = QLabel(tr("monitor.status.idle", self._language))
        self._status_badge.setAlignment(Qt.AlignCenter)
        self._status_badge.setStyleSheet("color: #FF9F0A; background: #2C2C2E; border-radius: 6px; padding: 4px 10px; font-family: 'PT Root UI', monospace; font-size: 11px; font-weight: 600;")
        header_row.addWidget(self._status_badge, 0, Qt.AlignVCenter)
        root.addLayout(header_row)

        # ── Workspace ─────────────────────────────────────────────────────────
        workspace = QHBoxLayout()
        workspace.setSpacing(20)
        root.addLayout(workspace, 1)

        left_col = QVBoxLayout()
        left_col.setSpacing(20)
        workspace.addLayout(left_col, 6)

        right_col = QVBoxLayout()
        right_col.setSpacing(0)
        workspace.addLayout(right_col, 4)

        # ── Hero Card ─────────────────────────────────────────────────────────
        hero = QFrame()
        hero.setStyleSheet("QFrame { background: #2C2C2E; border-radius: 14px; border: none; }")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(24, 24, 24, 24)
        hero_layout.setSpacing(16)

        title_row = QHBoxLayout()
        self._query_label = QLabel(tr("monitor.query.idle", self._language))
        self._query_label.setStyleSheet("color: white; font-family: 'PT Root UI', sans-serif; font-size: 15px; font-weight: 600;")
        title_row.addWidget(self._query_label, 1)
        
        self._status_line = QLabel(tr("monitor.status_line.idle", self._language))
        self._status_line.setStyleSheet("color: #8E8E93; font-family: '-apple-system', sans-serif; font-size: 13px;")
        title_row.addWidget(self._status_line, 0, Qt.AlignRight)
        hero_layout.addLayout(title_row)

        # Progress bar spec
        from PySide6.QtWidgets import QProgressBar
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(4)
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                background: #3A3A3C;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background: #0A84FF;
                border-radius: 2px;
            }
        """)
        hero_layout.addWidget(self._progress_bar)

        prog_hdr = QHBoxLayout()
        self._progress_label = QLabel(tr("monitor.status.idle", self._language).capitalize())
        self._progress_label.setStyleSheet("color: #8E8E93; font-family: 'PT Root UI', sans-serif; font-size: 13px;")
        prog_hdr.addWidget(self._progress_label, 1)
        self._pct_label = QLabel("0%")
        self._pct_label.setStyleSheet("color: #0A84FF; font-family: 'PT Root UI', monospace; font-size: 13px; font-weight: 600;")
        prog_hdr.addWidget(self._pct_label)
        hero_layout.addLayout(prog_hdr)

        # Time pills
        def _time_pill(default_text):
            lbl = QLabel(default_text)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("color: #8E8E93; background: #1C1C1E; border-radius: 6px; padding: 4px 8px; font-family: 'PT Root UI', monospace; font-size: 12px; font-weight: 500;")
            return lbl

        time_row = QHBoxLayout()
        time_row.setSpacing(8)
        self._elapsed_value = _time_pill(f"{tr('monitor.label.elapsed', self._language)} 00:00:00")
        self._remaining_value = _time_pill(f"{tr('monitor.label.remaining', self._language)} —")
        time_row.addWidget(self._elapsed_value)
        time_row.addWidget(self._remaining_value)
        
        time_row.addStretch()
        
        self._btn_pause = MonitorControlButton(tr("monitor.button.pause", self._language), is_warning=True)
        self._btn_pause.setEnabled(False)
        self._btn_pause.clicked.connect(self._pause)
        time_row.addWidget(self._btn_pause)
        self._btn_resume = MonitorControlButton(tr("monitor.button.resume", self._language), is_success=True)
        self._btn_resume.setEnabled(False)
        self._btn_resume.clicked.connect(self._resume)
        time_row.addWidget(self._btn_resume)
        self._btn_cancel = MonitorControlButton(tr("monitor.button.stop", self._language), is_danger=True)
        self._btn_cancel.setEnabled(False)
        self._btn_cancel.clicked.connect(self._cancel)
        time_row.addWidget(self._btn_cancel)
        
        hero_layout.addLayout(time_row)
        left_col.addWidget(hero)

        # ── Metrics Grid ──────────────────────────────────────────────────────
        self._card_found  = MetricTile(tr("monitor.metric.found", self._language),  "0", "+0/s",        FluentIcon.PEOPLE, "#0A84FF")
        self._card_emails = MetricTile(tr("monitor.metric.emails", self._language), "0", "0% coverage", FluentIcon.MAIL,   "#30D158")
        self._card_sites  = MetricTile(tr("monitor.metric.sites", self._language),  "0", "domains",     FluentIcon.GLOBE,  "#FFD60A")
        self._card_errors = MetricTile(tr("monitor.metric.errors", self._language), "0", "warnings",    FluentIcon.INFO,   "#FF453A")

        tiles_grid = QGridLayout()
        tiles_grid.setSpacing(16)
        tiles_grid.addWidget(self._card_found,  0, 0)
        tiles_grid.addWidget(self._card_emails, 0, 1)
        tiles_grid.addWidget(self._card_sites,  1, 0)
        tiles_grid.addWidget(self._card_errors, 1, 1)
        left_col.addLayout(tiles_grid)
        left_col.addStretch(1)

        # ── Activity Stream ────────────────────────────────────────────────────
        activity_card = QFrame()
        activity_card.setStyleSheet("QFrame { background: #2C2C2E; border-radius: 14px; border: none; }")
        act_layout = QVBoxLayout(activity_card)
        act_layout.setContentsMargins(20, 16, 20, 20)
        act_layout.setSpacing(12)

        act_head = QHBoxLayout()
        stream_lbl = QLabel(tr("monitor.section.activity", self._language))
        stream_lbl.setStyleSheet("color: #636366; font-family: '-apple-system', sans-serif; font-weight: 600; font-size: 11px; letter-spacing: 1.5px;")
        act_head.addWidget(stream_lbl)
        act_head.addStretch()
        
        self._live_badge = QLabel(tr("monitor.badge.live", self._language))
        self._live_badge.setStyleSheet("color: #30D158; font-family: 'PT Root UI', monospace; font-size: 11px; font-weight: 600;")
        act_head.addWidget(self._live_badge)
        act_layout.addLayout(act_head)

        from PySide6.QtWidgets import QStackedWidget
        self._stream_stack = QStackedWidget()
        act_layout.addWidget(self._stream_stack, 1)

        from .components import EmptyStateWidget
        self._empty_state = EmptyStateWidget(
            FluentIcon.INFO,
            title=tr("monitor.section.activity", self._language),
            description="The live activity stream will appear here when a job starts."
        )
        self._stream_stack.addWidget(self._empty_state)

        self._log_tail = QTextBrowser()
        self._log_tail.setOpenExternalLinks(True)
        self._log_tail.setStyleSheet("""
            QTextBrowser {
                background-color: transparent;
                border: none;
                font-family: 'SF Mono', 'JetBrains Mono', monospace;
                padding: 0;
                color: #8E8E93;
                font-size: 11px;
                line-height: 1.4;
                selection-background-color: rgba(10, 132, 255, 0.3);
            }
        """)
        self._stream_stack.addWidget(self._log_tail)

        # Show empty state initially
        self._stream_stack.setCurrentWidget(self._empty_state)

        right_col.addWidget(activity_card, 1)

        scrollbar = self._log_tail.verticalScrollBar()
        scrollbar.valueChanged.connect(self._on_log_scrolled)

    def header_action_widgets(self) -> list[QWidget]:
        return []

    def _connect_events(self):
        from .event_bridge import event_bridge
        event_bridge.job_started.connect(self._on_started)
        event_bridge.job_progress.connect(self._on_progress)
        event_bridge.job_completed.connect(self._on_completed)
        event_bridge.job_failed.connect(self._on_failed)
        event_bridge.job_paused.connect(self._on_paused)
        event_bridge.job_cancelled.connect(self._on_cancelled)
        event_bridge.job_log.connect(self._on_log)
        event_bridge.trial_limit_reached.connect(self._on_trial_limit_reached)

    def _on_started(self, job_id="", config=None, **kw):
        data = {"job_id": job_id}
        if config:
            data.update(
                {
                    "job_title": config.job_title or "",
                    "city": config.city or config.country or "",
                    "source_type": config.source_type.value if config.source_type else "",
                    "max_results": config.max_results,
                }
            )
        self._active_job_id = job_id
        self._update_queue.put(("started", data))

    def _on_progress(self, data: dict):
        total_found = data.get("total_found", 0)
        total_emails = data.get("total_emails", 0)
        total_websites = data.get("total_websites", 0)
        total_errors = data.get("total_errors", 0)
        completion = data.get("completion", 0.0)
        
        self._update_queue.put(
            (
                "progress",
                {
                    "found": int(total_found),
                    "emails": int(total_emails),
                    "websites": int(total_websites),
                    "errors": int(total_errors),
                    "pct": int(completion * 100),
                },
            )
        )

    def _on_completed(self, job_id: str = "", *args, **kw):
        self._update_queue.put(("completed", {}))

    def _on_failed(self, job_id: str = "", error: str = "", *args, **kw):
        err_str = str(error) if error is not None else "Unknown error"
        self._update_queue.put(("failed", {"error": err_str[:120]}))

    def _on_paused(self, job_id: str = "", *args, **kw):
        self._update_queue.put(("paused", {}))

    def _on_cancelled(self, job_id: str = "", *args, **kw):
        self._update_queue.put(("cancelled", {}))

    def _on_log(self, job_id: str = "", level: str = "INFO", message: str = "", *args, **kw):
        if self._active_job_id and job_id and job_id != self._active_job_id:
            return
        self._update_queue.put(("log", {"level": str(level), "message": str(message)}))

    def _on_trial_limit_reached(self, job_id: str):
        if self._active_job_id and job_id and job_id != self._active_job_id:
            return
        self._update_queue.put(("trial_limit", {}))

    def _drain_queue(self):
        while not self._update_queue.empty():
            try:
                event_type, data = self._update_queue.get_nowait()
            except queue.Empty:
                break

            if event_type == "started":
                self._ui_started(data)
            elif event_type == "progress":
                self._ui_progress(data)
            elif event_type == "completed":
                self._ui_completed()
            elif event_type == "failed":
                self._ui_failed(data.get("error", ""))
            elif event_type == "paused":
                self._ui_paused()
            elif event_type == "cancelled":
                self._ui_cancelled()
            elif event_type == "log":
                self._ui_log(data.get("level", "INFO"), data.get("message", ""))
            elif event_type == "trial_limit":
                self._ui_trial_limit()

    def _ui_started(self, data: dict):
        self._job_start_time = time.monotonic()
        job_title = data.get("job_title", "")
        city = data.get("city", "")
        self._total_expected_results = data.get("max_results", 0)

        query_text = f"{job_title} — {city}" if city else (job_title or "Unnamed Search")
        self._query_label.setText(query_text)
        self._status_line.setText(tr("monitor.status_line.running", self._language))
        self._status_line.setStyleSheet("color: #30D158; font-family: '-apple-system', sans-serif; font-size: 13px;")
        
        self._status_badge.setText(tr("monitor.status.running", self._language))
        self._status_badge.setStyleSheet("color: #30D158; background: rgba(48,209,88,0.15); border-radius: 6px; padding: 4px 10px; font-family: 'PT Root UI', monospace; font-size: 11px; font-weight: 600;")
        
        self._progress_bar.setValue(0)
        self._progress_label.setText(tr("monitor.progress.init", self._language))
        self._pct_label.setText("0%")
        self._elapsed_value.setText(f"{tr('monitor.label.elapsed', self._language)} 00:00:00")
        self._remaining_value.setText(f"{tr('monitor.label.remaining', self._language)} —")
        
        self._btn_pause.setEnabled(True)
        self._btn_resume.setEnabled(False)
        self._btn_cancel.setEnabled(True)
        self._is_paused = False
        self._log_tail.clear()

        self._card_found.set_value("0")
        self._card_found.set_meta("+0/s")
        self._card_emails.set_value("0")
        self._card_emails.set_meta("0% accuracy")
        self._card_sites.set_value("0")
        self._card_sites.set_meta("domains")
        self._card_errors.set_value("0")
        self._card_errors.set_meta("warnings")

    def _ui_progress(self, data: dict):
        found = data.get("found", 0)
        emails = data.get("emails", 0)
        websites = data.get("websites", 0)
        errors = data.get("errors", 0)
        pct = data.get("pct", 0)

        self._card_found.set_value(f"{found:,}")
        self._card_found.set_meta(self._rate_meta(found))

        self._card_emails.set_value(f"{emails:,}")
        accuracy = int((emails / found) * 100) if found else 0
        self._card_emails.set_meta(f"{accuracy}% coverage")

        self._card_sites.set_value(f"{websites:,}")
        
        self._card_errors.set_value(f"{errors:,}")

        self._progress_bar.setValue(pct)
        self._pct_label.setText(f"{pct}%")
        self._progress_label.setText(tr("monitor.progress.scanning", self._language))
        elapsed = time.monotonic() - self._job_start_time
        self._elapsed_value.setText(f"{tr('monitor.label.elapsed', self._language)} {self._format_time(elapsed, fixed=True)}")
        if 0 < pct < 100:
            total_est = elapsed / (pct / 100.0)
            remaining = max(total_est - elapsed, 0)
            self._remaining_value.setText(f"{tr('monitor.label.remaining', self._language)} {self._format_time(remaining, fixed=True)}")
        else:
            self._remaining_value.setText(f"{tr('monitor.label.remaining', self._language)} 00:00:00")

    def _ui_completed(self):
        self._progress_bar.setValue(100)
        self._pct_label.setText("100%")
        self._status_line.setText(tr("monitor.status_line.success", self._language))
        self._status_line.setStyleSheet("color: #30D158; font-family: '-apple-system', sans-serif; font-size: 13px;")
        
        self._status_badge.setText(tr("monitor.status.done", self._language))
        self._status_badge.setStyleSheet("color: #30D158; background: rgba(48,209,88,0.15); border-radius: 6px; padding: 4px 10px; font-family: 'PT Root UI', monospace; font-size: 11px; font-weight: 600;")
        
        self._progress_label.setText(tr("monitor.progress.done", self._language))
        self._elapsed_value.setText(f"{tr('monitor.label.elapsed', self._language)} {self._format_time(time.monotonic() - self._job_start_time, fixed=True)}")
        self._remaining_value.setText(f"{tr('monitor.label.remaining', self._language)} —")
        self._btn_pause.setEnabled(False)
        self._btn_resume.setEnabled(False)
        self._btn_cancel.setEnabled(False)
        self._ui_log("INFO", "=== Job completed successfully ===")

    def _ui_failed(self, error: str):
        self._status_line.setText(tr("monitor.status_line.failed", self._language).format(error=error or 'Unexpected error'))
        self._status_line.setStyleSheet("color: #FF453A; font-family: '-apple-system', sans-serif; font-size: 13px;")
        
        self._status_badge.setText(tr("monitor.status.failed", self._language))
        self._status_badge.setStyleSheet("color: #FF453A; background: rgba(255,69,58,0.15); border-radius: 6px; padding: 4px 10px; font-family: 'PT Root UI', monospace; font-size: 11px; font-weight: 600;")
        
        self._progress_label.setText(tr("monitor.progress.failed", self._language))
        self._btn_pause.setEnabled(False)
        self._btn_resume.setEnabled(False)
        self._btn_cancel.setEnabled(False)

    def _ui_paused(self):
        self._status_line.setText(tr("monitor.status_line.paused", self._language))
        self._status_line.setStyleSheet("color: #FF9F0A; font-family: '-apple-system', sans-serif; font-size: 13px;")
        self._status_badge.setText(tr("monitor.status.paused", self._language))
        self._status_badge.setStyleSheet("color: #FF9F0A; background: rgba(255,159,10,0.15); border-radius: 6px; padding: 4px 10px; font-family: 'PT Root UI', monospace; font-size: 11px; font-weight: 600;")
        self._progress_label.setText(tr("monitor.progress.paused", self._language))
        self._btn_pause.setEnabled(False)
        self._btn_resume.setEnabled(True)
        self._btn_cancel.setEnabled(True)
        self._is_paused = True
        self._ui_log("WARNING", "=== Job paused ===")

    def _ui_cancelled(self):
        self._status_line.setText(tr("monitor.status_line.cancelled", self._language))
        self._status_line.setStyleSheet("color: #FF9F0A; font-family: '-apple-system', sans-serif; font-size: 13px;")
        self._status_badge.setText(tr("monitor.status.idle", self._language))
        self._status_badge.setStyleSheet("color: #FF9F0A; background: #2C2C2E; border-radius: 6px; padding: 4px 10px; font-family: 'PT Root UI', monospace; font-size: 11px; font-weight: 600;")
        self._progress_label.setText(tr("monitor.progress.cancelled", self._language))
        self._btn_pause.setEnabled(False)
        self._btn_resume.setEnabled(False)
        self._btn_cancel.setEnabled(False)
        self._ui_log("WARNING", "=== Job cancelled ===")

    def _ui_trial_limit(self):
        """Show the trial limit dialog and stop UI timers."""
        self._status_line.setText(tr("monitor.status.trial", self._language))
        self._status_line.setStyleSheet("color: #FF453A; font-family: '-apple-system', sans-serif; font-size: 13px;")
        
        self._status_badge.setText("TRIAL OVER")
        self._status_badge.setStyleSheet("color: #FF453A; background: rgba(255,69,58,0.15); border-radius: 6px; padding: 4px 10px; font-family: 'PT Root UI', monospace; font-size: 11px; font-weight: 600;")
        
        self._progress_label.setText("Daily limit of 20 scraps reached. Upgrade to unlock unlimited scraping.")
        self._btn_pause.setEnabled(False)
        self._btn_resume.setEnabled(False)
        self._btn_cancel.setEnabled(False)
        
        from .components import ZugzwangDialog
        dialog = ZugzwangDialog(
            "Trial Limit Reached",
            "You have reached your daily limit of 20 lead extractions.\n\nPlease upgrade to the Professional version to continue scraping without limits.",
            self.window()
        )
        # Re-set OK button text to "UPGRADE" and Cancel to "CLOSE" for better conversion
        dialog.ok_btn.setText("UPGRADE NOW")
        dialog.cancel_btn.setText("CLOSE")
        if dialog.exec():
            self.window().show_activation_dialog()

    def _ui_log(self, level: str, message: str):
        color_map = {
            "ERROR": Theme.DANGER,
            "WARNING": Theme.WARNING,
            "INFO": Theme.TEXT_PRIMARY,
            "DEBUG": Theme.TEXT_SECONDARY,
        }
        color = color_map.get(level.upper(), Theme.TEXT_PRIMARY)
        
        # Clean up the message: remove [job-id] prefix
        display_msg = message or ""
        active_id = self._active_job_id
        if active_id and display_msg.startswith(f"[{active_id}]"):
            prefix_len = len(active_id) + 2
            display_msg = display_msg[prefix_len:].strip()
        
        safe_msg = display_msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        linked_msg = _URL_RE.sub(fr'<a href="\1" style="color: {Theme.ACCENT_BLUE}; text-decoration: none;">\1</a>', safe_msg)
        html_msg = (
            f'<div style="margin-bottom: 2px;">'
            f'<span style="color:rgba(255,255,255,0.25); font-weight: 600;">{time.strftime("%H:%M:%S")}</span> '
            f'<span style="color:{color};">{linked_msg}</span>'
            f'</div>'
        )
        def _append():
            if self._stream_stack.currentWidget() != self._log_tail:
                self._stream_stack.setCurrentWidget(self._log_tail)
            self._log_tail.append(html_msg)
            if not self._user_scrolling:
                scrollbar = self._log_tail.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())
        _append()

    def _pause(self):
        orchestrator.pause_job()

    def _resume(self):
        orchestrator.resume_job()
        self._status_line.setText(tr("monitor.status_line.running", self._language))
        self._status_line.setStyleSheet("color: #30D158; font-family: '-apple-system', sans-serif; font-size: 13px;")
        
        self._status_badge.setText(tr("monitor.status.running", self._language))
        self._status_badge.setStyleSheet("color: #30D158; background: rgba(48,209,88,0.15); border-radius: 6px; padding: 4px 10px; font-family: 'PT Root UI', monospace; font-size: 11px; font-weight: 600;")
        
        self._progress_label.setText("Resuming network activity...")
        self._btn_pause.setEnabled(True)
        self._btn_resume.setEnabled(False)
        self._btn_cancel.setEnabled(True)
        self._is_paused = False
        self._ui_log("INFO", "=== Job resumed ===")

    def _cancel(self):
        from .components import ZugzwangDialog
        msg = ZugzwangDialog(
            tr("monitor.dialog.stop.title", self._language),
            tr("monitor.dialog.stop.body", self._language),
            self.window(),
            destructive=True
        )
        if msg.exec():
            orchestrator.cancel_job()

    def _on_log_scrolled(self, value):
        scrollbar = self._log_tail.verticalScrollBar()
        self._user_scrolling = value < scrollbar.maximum() - 5

    def _clear_log(self):
        self._log_tail.clear()

    @staticmethod
    def _rate_meta(found: int) -> str:
        if found <= 0:
            return "+0/s"
        per_second = max(1, min(24, found // 120))
        return f"+{per_second}/s"

    @staticmethod
    def _format_time(seconds: float, fixed: bool = False) -> str:
        total = max(0, int(seconds))
        hours, rem = divmod(total, 3600)
        minutes, secs = divmod(rem, 60)
        if fixed:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        if hours > 0:
            return f"{hours}h {minutes}m"
        if minutes > 0:
            return f"{minutes}m {secs:02d}s"
        return f"{secs}s"
