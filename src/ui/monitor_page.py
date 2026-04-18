"""
ZUGZWANG - Monitor Page
Modern Fluent 2030 Edition live scraping monitor.
"""

from __future__ import annotations

import queue
import time
from typing import Optional

from PySide6.QtCore import Qt, QTimer, QSize, Signal
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QWidget, QFrame, QGridLayout, QLabel,
    QTextEdit, QSizePolicy, QPushButton, QGraphicsOpacityEffect
)

from qfluentwidgets import (
    CardWidget, ElevatedCardWidget, PrimaryPushButton, PushButton, TransparentPushButton,
    TitleLabel, SubtitleLabel, BodyLabel, CaptionLabel, StrongBodyLabel, InfoBadge,
    ProgressBar, IconWidget, FluentIcon, SimpleCardWidget, ScrollArea, MessageBox
)

from ..core.config import config_manager
from ..core.i18n import get_language, tr
from ..services.orchestrator import orchestrator
from .theme import Theme

class MetricTile(QFrame):
    """Compact premium metric tile — vertical card layout."""
    def __init__(self, title: str, value: str = "0", meta: str = "",
                 icon: FluentIcon = FluentIcon.INFO,
                 color: str = "#0A84FF"):
        super().__init__()
        self.setMinimumHeight(0)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        self.setStyleSheet("""
            MetricTile {
                background: #2C2C2E;
                border-radius: 12px;
                border: 1px solid rgba(255,255,255,0.06);
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        # ── Row 1: Icon + Meta Chip + Title ──────────────────────────────────
        top = QHBoxLayout()
        top.setSpacing(10)
        top.setContentsMargins(0, 0, 0, 0)

        # Icon
        icon_wrap = QFrame()
        icon_wrap.setFixedSize(22, 22)
        icon_wrap.setStyleSheet(f"""
            QFrame {{
                background: rgba({r},{g},{b},0.12);
                border: 1px solid rgba({r},{g},{b},0.22);
                border-radius: 6px;
            }}
        """)
        icon_l = QHBoxLayout(icon_wrap)
        icon_l.setContentsMargins(0, 0, 0, 0)
        icon_w = IconWidget(icon)
        icon_w.setFixedSize(12, 12)
        icon_w.setStyleSheet(f"color: {color}; background: transparent; border: none;")
        icon_l.addWidget(icon_w, 0, Qt.AlignCenter)
        top.addWidget(icon_wrap, 0, Qt.AlignVCenter)

        # Title
        self._title = QLabel(str(title).upper())
        self._title.setStyleSheet(
            "color: #8E8E93; font-family: '-apple-system', sans-serif; "
            "font-size: 11px; font-weight: 600; letter-spacing: 1.4px; "
            "background: transparent; border: none;"
        )
        top.addWidget(self._title, 0, Qt.AlignVCenter)

        # Meta chip ("warning", etc) - now after title
        self._meta = QLabel(meta)
        self._meta.setAlignment(Qt.AlignCenter)
        self._meta.setStyleSheet(f"""
            color: rgba({r},{g},{b},1.0);
            background: rgba({r},{g},{b},0.10);
            border: 1px solid rgba({r},{g},{b},0.22);
            border-radius: 6px;
            font-family: '-apple-system', sans-serif;
            font-size: 9px;
            font-weight: 700;
            padding: 2px 8px;
        """)
        top.addWidget(self._meta, 0, Qt.AlignVCenter)
        top.addStretch()
        root.addLayout(top)

        # ── Row 2: Large main value below ────────────────────────────────────
        self._value = QLabel(value)
        self._value.setStyleSheet(
            f"color: {color}; font-family: 'PT Root UI', sans-serif; "
            "font-size: 36px; font-weight: 700; background: transparent; border: none;"
        )
        self._value.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        root.addWidget(self._value)

        root.addStretch(1)


    def set_value(self, text: str) -> None:
        if self._value.text() != text:
            self._value.setText(text)

    def set_meta(self, text: str) -> None:
        if self._meta.text() != text:
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
        # Override default theme padding for tighter monitor layout
        padding_fix = "QPushButton { padding: 0 10px; }"
        if self.is_danger:
            self.setStyleSheet(Theme.zugzwang_danger_button() + padding_fix)
            self.setFixedWidth(100)
        elif self.is_primary:
            self.setStyleSheet(Theme.zugzwang_primary_button() + padding_fix)
            self.setFixedWidth(190)
        elif self.is_success:
            self.setStyleSheet(Theme.zugzwang_success_button() + padding_fix)
            self.setFixedWidth(100)
        elif self.is_warning:
            self.setStyleSheet(Theme.zugzwang_warning_button() + padding_fix)
            self.setFixedWidth(100)
        else:
            self.setStyleSheet(Theme.zugzwang_button() + padding_fix)
            self.setFixedWidth(100)


class MonitorPage(QWidget):
    """Live scraping monitor rebuilt with PySide6-Fluent-Widgets."""
    scrape_more_requested = Signal(object) # emits SearchConfig

    def __init__(self):
        super().__init__()
        self._current_config = None
        self._is_paused = False
        self._job_start_time = 0.0
        self._total_expected_results = 0
        self._user_scrolling = False
        self._active_job_id: Optional[str] = None
        self._update_queue: queue.Queue = queue.Queue()
        self._dropped_log_count = 0
        self._language = get_language(config_manager.settings.app_language)

        self._build_ui()
        self._connect_events()

        self._timer = QTimer(self)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self._drain_queue)
        self._timer.start()

    def _build_ui(self):
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("MonitorPage { background: #1C1C1E; }")
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 32)
        root.setSpacing(18)

        # ── Page Header ────────────────────────────────────────────────────────
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 4)

        self._page_title = QLabel(tr("monitor.title", self._language))
        self._page_title.setStyleSheet("color: white; font-family: 'PT Root UI', sans-serif; font-size: 22px; font-weight: 600; letter-spacing: 0.3px;")
        header_row.addWidget(self._page_title)
        header_row.addStretch(1)

        self._status_badge = QLabel(tr("monitor.status.idle", self._language))
        self._status_badge.setAlignment(Qt.AlignCenter)
        self._status_badge.setStyleSheet("color: #FF9F0A; background: #2C2C2E; border-radius: 6px; padding: 4px 10px; font-family: 'PT Root UI', monospace; font-size: 10px; font-weight: 600;")
        header_row.addWidget(self._status_badge, 0, Qt.AlignVCenter)
        root.addLayout(header_row)

        # ── Workspace ─────────────────────────────────────────────────────────
        workspace = QHBoxLayout()
        workspace.setSpacing(20)
        root.addLayout(workspace, 1)

        left_col = QVBoxLayout()
        left_col.setSpacing(20)
        workspace.addLayout(left_col, 44)

        right_col = QVBoxLayout()
        right_col.setSpacing(0)
        workspace.addLayout(right_col, 56)

        # ── Hero Card ─────────────────────────────────────────────────────────
        hero = QFrame()
        hero.setStyleSheet("QFrame { background: #2C2C2E; border-radius: 14px; border: none; }")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(24, 24, 24, 24)
        hero_layout.setSpacing(16)

        title_row = QHBoxLayout()
        self._query_label = QLabel(tr("monitor.query.idle", self._language))
        self._query_label.setStyleSheet("color: white; font-family: 'PT Root UI', sans-serif; font-size: 14px; font-weight: 600;")
        title_row.addWidget(self._query_label, 1)
        
        self._status_line = QLabel(tr("monitor.status_line.idle", self._language))
        self._status_line.setStyleSheet("color: #8E8E93; font-family: '-apple-system', sans-serif; font-size: 12px;")
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
        self._progress_label.setStyleSheet("color: #8E8E93; font-family: 'PT Root UI', sans-serif; font-size: 12px;")
        prog_hdr.addWidget(self._progress_label, 1)
        self._pct_label = QLabel("0%")
        self._pct_label.setStyleSheet("color: #0A84FF; font-family: 'PT Root UI', monospace; font-size: 12px; font-weight: 600;")
        prog_hdr.addWidget(self._pct_label)
        hero_layout.addLayout(prog_hdr)

        time_row = QHBoxLayout()
        time_row.setContentsMargins(0, 4, 0, 0)
        time_row.setSpacing(12)
        
        time_row.addStretch(1)
        
        # Right side: Control Buttons
        more_text = tr("monitor.button.scrape_more", self._language)
        if more_text == "monitor.button.scrape_more":
            more_text = "SEARCH MORE"
        self._btn_more = MonitorControlButton(more_text, is_primary=True)
        self._btn_more.setEnabled(False)
        self._btn_more.clicked.connect(self._scrape_more)
        time_row.addWidget(self._btn_more)

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
        tiles_grid.setHorizontalSpacing(14)
        tiles_grid.setVerticalSpacing(14)
        tiles_grid.addWidget(self._card_found,  0, 0)
        tiles_grid.addWidget(self._card_emails, 0, 1)
        tiles_grid.addWidget(self._card_sites,  1, 0)
        tiles_grid.addWidget(self._card_errors, 1, 1)
        tiles_grid.setRowStretch(0, 1)
        tiles_grid.setRowStretch(1, 1)
        tiles_grid.setColumnStretch(0, 1)
        tiles_grid.setColumnStretch(1, 1)
        left_col.addLayout(tiles_grid, 1)

        # ── Session Snapshot (left col, below metrics) ───────────────────────
        self._session_card = QFrame()
        self._session_card.setStyleSheet("QFrame { background: #2C2C2E; border-radius: 14px; border: none; }")
        session_layout = QVBoxLayout(self._session_card)
        session_layout.setContentsMargins(20, 16, 20, 16)
        session_layout.setSpacing(12)

        session_head = QHBoxLayout()
        session_lbl = QLabel("SESSION SNAPSHOT")
        session_lbl.setStyleSheet("color: #636366; font-family: '-apple-system', sans-serif; font-weight: 600; font-size: 10px; letter-spacing: 1.5px;")
        session_head.addWidget(session_lbl)
        session_head.addStretch(1)

        self._session_state = QLabel("IDLE")
        self._session_state.setStyleSheet("color: #FF9F0A; font-family: 'PT Root UI', monospace; font-size: 10px; font-weight: 700;")
        session_head.addWidget(self._session_state)
        session_layout.addLayout(session_head)

        self._snapshot_note = QLabel("Summary of the current search session and latest event.")
        self._snapshot_note.setWordWrap(True)
        self._snapshot_note.setStyleSheet("color: #8E8E93; font-family: '-apple-system', sans-serif; font-size: 11px;")
        session_layout.addWidget(self._snapshot_note)

        def _snapshot_tile(title: str, value: str, tall: bool = False):
            tile = QFrame()
            tile.setStyleSheet("QFrame { background: #1C1C1E; border-radius: 8px; border: none; }")
            tile_l = QVBoxLayout(tile)
            tile_l.setContentsMargins(12, 8, 12, 8)
            tile_l.setSpacing(2)
            if tall:
                tile.setMinimumHeight(60)
            title_lbl = QLabel(title.upper())
            title_lbl.setStyleSheet("color: #636366; font-family: '-apple-system', sans-serif; font-size: 9px; font-weight: 700; letter-spacing: 1.2px;")
            value_lbl = QLabel(value)
            value_lbl.setWordWrap(True)
            value_lbl.setStyleSheet("color: #E5E5EA; font-family: 'PT Root UI', sans-serif; font-size: 11px; font-weight: 600;")
            tile_l.addWidget(title_lbl)
            tile_l.addWidget(value_lbl)
            return tile, value_lbl

        detail_grid = QGridLayout()
        detail_grid.setHorizontalSpacing(8)
        detail_grid.setVerticalSpacing(8)
        self._snapshot_source, self._snapshot_source_value = _snapshot_tile("Source", "-")
        self._snapshot_city, self._snapshot_city_value = _snapshot_tile("City", "-")
        self._snapshot_limit, self._snapshot_limit_value = _snapshot_tile("Target", "-")
        self._snapshot_updated, self._snapshot_updated_value = _snapshot_tile("Last update", "-")
        self._snapshot_event, self._snapshot_event_value = _snapshot_tile("Latest event", "Waiting for a search to begin.", tall=True)

        detail_grid.addWidget(self._snapshot_source, 0, 0)
        detail_grid.addWidget(self._snapshot_city, 0, 1)
        detail_grid.addWidget(self._snapshot_limit, 1, 0)
        detail_grid.addWidget(self._snapshot_updated, 1, 1)
        detail_grid.addWidget(self._snapshot_event, 2, 0, 1, 2)
        session_layout.addLayout(detail_grid)

        left_col.addWidget(self._session_card, 1)

        # ── Activity Stream (full right column) ───────────────────────────────
        activity_card = QFrame()
        activity_card.setStyleSheet("QFrame { background: #2C2C2E; border-radius: 14px; border: none; }")
        act_layout = QVBoxLayout(activity_card)
        act_layout.setContentsMargins(20, 16, 20, 12)  # Reduced bottom margin
        act_layout.setSpacing(12)

        act_head = QHBoxLayout()
        stream_lbl = QLabel(tr("monitor.section.activity", self._language))
        stream_lbl.setStyleSheet("color: #636366; font-family: '-apple-system', sans-serif; font-weight: 600; font-size: 10px; letter-spacing: 1.5px;")
        act_head.addWidget(stream_lbl)
        act_head.addStretch(1)
        
        self._elapsed_value = QLabel(f"{tr('monitor.label.elapsed', self._language).upper()} 00:00:00")
        self._elapsed_value.setStyleSheet("color: #636366; font-family: 'SF Mono', 'JetBrains Mono', monospace; font-size: 10px; font-weight: 500;")
        act_head.addWidget(self._elapsed_value)
        
        act_head.addSpacing(12)
        
        self._remaining_value = QLabel(f"{tr('monitor.label.remaining', self._language).upper()} —")
        self._remaining_value.setStyleSheet("color: #636366; font-family: 'SF Mono', 'JetBrains Mono', monospace; font-size: 10px; font-weight: 500;")
        act_head.addWidget(self._remaining_value)
        
        act_head.addSpacing(16)
        
        self._live_badge = QLabel(tr("monitor.badge.live", self._language))
        self._live_badge.setStyleSheet("color: #30D158; font-family: 'PT Root UI', monospace; font-size: 9px; font-weight: 600;")
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
        self._empty_state.setMinimumHeight(0)
        self._stream_stack.addWidget(self._empty_state)

        self._log_tail = QTextEdit()
        self._log_tail.setReadOnly(True)
        self._log_tail.setUndoRedoEnabled(False)
        self._log_tail.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self._log_tail.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._log_tail.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._log_tail.setStyleSheet("""
            QTextEdit {
                background-color: transparent;
                border: none;
                font-family: 'SF Mono', 'JetBrains Mono', monospace;
                padding: 0;
                color: #8E8E93;
                font-size: 11px;
                line-height: 1.5;
                selection-background-color: rgba(10, 132, 255, 0.3);
            }
        """)
        self._log_tail.document().setDocumentMargin(0)
        self._stream_stack.addWidget(self._log_tail)
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
        event_bridge.job_result.connect(self._on_result)
        event_bridge.job_completed.connect(self._on_completed)
        event_bridge.job_failed.connect(self._on_failed)
        event_bridge.job_paused.connect(self._on_paused)
        event_bridge.job_resumed.connect(self._on_resumed)
        event_bridge.job_cancelled.connect(self._on_cancelled)
        event_bridge.job_log.connect(self._on_log)
        event_bridge.trial_limit_reached.connect(self._on_trial_limit_reached)

    def _on_started(self, job_id="", config=None, **kw):
        self._current_config = config
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
        self._update_queue.put(
            (
                "progress",
                {
                    "found": int(data.get("total_found", 0)),
                    "emails": int(data.get("total_emails", 0)),
                    "websites": int(data.get("total_websites", 0)),
                    "errors": int(data.get("total_errors", 0)),
                    "pct": int(data.get("completion", 0.0) * 100),
                },
            )
        )

    def _on_result(self, record):
        company = getattr(record, "company_name", None) or "Unnamed employer"
        title = getattr(record, "job_title", None) or "-"
        city = getattr(record, "city", None) or getattr(record, "region", None) or getattr(record, "country", None) or "-"
        
        email = bool(getattr(record, "email", None))
        phone = bool(getattr(record, "phone", None))
        website = bool(getattr(record, "website", None))
        duplicate = bool(getattr(record, "is_duplicate", False))
        
        self._update_queue.put(
            (
                "result",
                {
                    "company": str(company).strip(),
                    "title": str(title).strip(),
                    "city": str(city).strip(),
                    "email": email,
                    "phone": phone,
                    "website": website,
                    "duplicate": duplicate,
                },
            )
        )

    def _on_log(self, job_id: str = "", level: str = "INFO", message: str = "", *args, **kw):
        if self._active_job_id and job_id and job_id != self._active_job_id:
            return
        self._update_queue.put(("log", {"level": str(level), "message": str(message)}))

    def _on_completed(self, job_id: str = "", *args, **kw):
        self._update_queue.put(("completed", {}))

    def _on_failed(self, job_id: str = "", error: str = "", *args, **kw):
        err_str = str(error) if error is not None else "Unknown error"
        self._update_queue.put(("failed", {"error": err_str[:120]}))

    def _on_paused(self, job_id: str = "", *args, **kw):
        self._update_queue.put(("paused", {}))

    def _on_resumed(self, job_id: str = "", *args, **kw):
        self._update_queue.put(("resumed", {}))

    def _on_cancelled(self, job_id: str = "", *args, **kw):
        self._update_queue.put(("cancelled", {}))

    def _on_trial_limit_reached(self, job_id: str):
        if self._active_job_id and job_id and job_id != self._active_job_id:
            return
        self._update_queue.put(("trial_limit", {}))

    from src.diagnostics import monitor_slot
    @monitor_slot
    def _drain_queue(self):
        """Processes pending UI updates in batches."""
            
        processed_count = 0
        max_per_tick = 15  # Lowered: prevents >100ms slot time under heavy load
        batch_lines = []
        last_log_summary = None
        latest_progress = None
        
        while not self._update_queue.empty() and processed_count < max_per_tick:
            try:
                event_type, data = self._update_queue.get_nowait()
                processed_count += 1
            except queue.Empty:
                break

            if event_type == "started":
                self._ui_started(data)
            elif event_type == "progress":
                latest_progress = data
            elif event_type == "completed":
                self._ui_completed()
            elif event_type == "failed":
                self._ui_failed(data.get("error", ""))
            elif event_type == "paused":
                self._ui_paused()
            elif event_type == "resumed":
                self._ui_resumed()
            elif event_type == "cancelled":
                self._ui_cancelled()
            elif event_type == "result":
                line, summary = self._prepare_result_line(data)
                batch_lines.append(line)
                last_log_summary = summary
            elif event_type == "log":
                line = data.get("line")
                summary = data.get("summary")
                if not line:
                    # Fallback for events that don't have pre-formatted plain text
                    line, summary = self._prepare_log(data.get("level", "INFO"), data.get("message", ""))

                batch_lines.append(line)
                if summary:
                    last_log_summary = summary
            elif event_type == "trial_limit":
                self._ui_trial_limit()

        if latest_progress:
            self._ui_progress(latest_progress)

        if self._dropped_log_count:
            batch_lines.append(f"{time.strftime('%H:%M:%S')} [monitor] throttled {self._dropped_log_count} verbose log lines")
            self._dropped_log_count = 0

        # Apply log batch in one go
        if batch_lines:
            self._apply_logs_batch(batch_lines, last_log_summary)

    def _ui_started(self, data: dict):
        self._job_start_time = time.monotonic()
        job_title = data.get("job_title", "")
        city = data.get("city", "")
        self._total_expected_results = data.get("max_results", 0)

        query_text = f"{job_title} — {city}" if city else (job_title or "Unnamed Search")
        self._query_label.setText(query_text)
        self._status_line.setText(tr("monitor.status_line.running", self._language))
        self._status_line.setStyleSheet("color: #30D158; font-family: '-apple-system', sans-serif; font-size: 12px;")
        self._session_state.setText("RUNNING")
        self._session_state.setStyleSheet("color: #30D158; font-family: 'PT Root UI', monospace; font-size: 10px; font-weight: 600;")
        
        self._status_badge.setText(tr("monitor.status.running", self._language))
        self._status_badge.setStyleSheet("color: #30D158; background: rgba(48,209,88,0.15); border-radius: 6px; padding: 4px 10px; font-family: 'PT Root UI', monospace; font-size: 10px; font-weight: 600;")
        self._snapshot_note.setText("Live session metadata and the most recent event are shown here.")
        self._snapshot_source_value.setText(str(data.get('source_type', '')).upper() or "-")
        self._snapshot_city_value.setText(city or "-")
        self._snapshot_limit_value.setText(str(self._total_expected_results or "-"))
        self._snapshot_updated_value.setText(time.strftime("%H:%M:%S"))
        self._snapshot_event_value.setText("Session started. Waiting for the first event...")
        
        self._progress_bar.setValue(0)
        self._progress_label.setText("Searching...")
        self._pct_label.setText("0%")
        self._elapsed_value.setText(f"{tr('monitor.label.elapsed', self._language)} 00:00:00")
        self._remaining_value.setText(f"{tr('monitor.label.remaining', self._language)} —")
        
        self._btn_more.setEnabled(True)
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

        if self._progress_bar.value() != pct:
            self._progress_bar.setValue(pct)
        if self._pct_label.text() != f"{pct}%":
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
        self._snapshot_note.setText("The latest event updates below while the full log keeps streaming on the right.")
        self._snapshot_updated_value.setText(time.strftime("%H:%M:%S"))

    def _ui_completed(self):
        self._progress_bar.setValue(100)
        self._pct_label.setText("100%")
        self._status_line.setText(tr("monitor.status_line.success", self._language))
        self._status_line.setStyleSheet("color: #30D158; font-family: '-apple-system', sans-serif; font-size: 12px;")
        self._session_state.setText("DONE")
        self._session_state.setStyleSheet("color: #30D158; font-family: 'PT Root UI', monospace; font-size: 10px; font-weight: 600;")
        
        self._status_badge.setText(tr("monitor.status.done", self._language))
        self._status_badge.setStyleSheet("color: #30D158; background: rgba(48,209,88,0.15); border-radius: 6px; padding: 4px 10px; font-family: 'PT Root UI', monospace; font-size: 10px; font-weight: 600;")
        self._snapshot_note.setText("The latest run finished successfully.")
        self._snapshot_event_value.setText("Job completed successfully.")
        self._snapshot_updated_value.setText(time.strftime("%H:%M:%S"))
        
        self._progress_label.setText(tr("monitor.progress.done", self._language))
        self._elapsed_value.setText(f"{tr('monitor.label.elapsed', self._language)} {self._format_time(time.monotonic() - self._job_start_time, fixed=True)}")
        self._remaining_value.setText(f"{tr('monitor.label.remaining', self._language)} —")
        self._btn_more.setEnabled(False)
        self._btn_pause.setEnabled(False)
        self._btn_resume.setEnabled(False)
        self._btn_cancel.setEnabled(False)
        self._ui_log("INFO", "=== Job completed successfully ===")

    def _ui_failed(self, error: str):
        self._status_line.setText(tr("monitor.status_line.failed", self._language).format(error=error or 'Unexpected error'))
        self._status_line.setStyleSheet("color: #FF453A; font-family: '-apple-system', sans-serif; font-size: 12px;")
        self._session_state.setText("ERROR")
        self._session_state.setStyleSheet("color: #FF453A; font-family: 'PT Root UI', monospace; font-size: 10px; font-weight: 600;")
        
        self._status_badge.setText(tr("monitor.status.failed", self._language))
        self._status_badge.setStyleSheet("color: #FF453A; background: rgba(255,69,58,0.15); border-radius: 6px; padding: 4px 10px; font-family: 'PT Root UI', monospace; font-size: 10px; font-weight: 600;")
        self._snapshot_note.setText("Check the activity log for the error details and retry when ready.")
        self._snapshot_event_value.setText(error or "Unexpected error")
        self._snapshot_updated_value.setText(time.strftime("%H:%M:%S"))
        
        self._progress_label.setText(tr("monitor.progress.failed", self._language))
        self._btn_more.setEnabled(False)
        self._btn_pause.setEnabled(False)
        self._btn_resume.setEnabled(False)
        self._btn_cancel.setEnabled(False)

    def _ui_paused(self):
        self._status_line.setText(tr("monitor.status_line.paused", self._language))
        self._status_line.setStyleSheet("color: #FF9F0A; font-family: '-apple-system', sans-serif; font-size: 12px;")
        self._session_state.setText("PAUSED")
        self._session_state.setStyleSheet("color: #FF9F0A; font-family: 'PT Root UI', monospace; font-size: 10px; font-weight: 600;")
        self._status_badge.setText(tr("monitor.status.paused", self._language))
        self._status_badge.setStyleSheet("color: #FF9F0A; background: rgba(255,159,10,0.15); border-radius: 6px; padding: 4px 10px; font-family: 'PT Root UI', monospace; font-size: 10px; font-weight: 600;")
        self._snapshot_note.setText("The session is paused. Resume to continue or stop to discard the run.")
        self._snapshot_event_value.setText("Job paused.")
        self._snapshot_updated_value.setText(time.strftime("%H:%M:%S"))
        self._progress_label.setText(tr("monitor.progress.paused", self._language))
        self._btn_pause.setEnabled(False)
        self._btn_resume.setEnabled(True)
        self._btn_cancel.setEnabled(True)
        self._is_paused = True
        self._ui_log("WARNING", "=== Job paused ===")

    def _ui_resumed(self):
        self._status_line.setText(tr("monitor.status_line.running", self._language))
        self._status_line.setStyleSheet("color: #30D158; font-family: '-apple-system', sans-serif; font-size: 12px;")
        
        self._status_badge.setText(tr("monitor.status.running", self._language))
        self._status_badge.setStyleSheet("color: #30D158; background: rgba(48,209,88,0.15); border-radius: 6px; padding: 4px 10px; font-family: 'PT Root UI', monospace; font-size: 10px; font-weight: 600;")
        self._session_state.setText("RUNNING")
        self._session_state.setStyleSheet("color: #30D158; font-family: 'PT Root UI', monospace; font-size: 10px; font-weight: 600;")

        self._progress_label.setText("Resuming activity...")
        self._btn_pause.setEnabled(True)
        self._btn_resume.setEnabled(False)
        self._btn_cancel.setEnabled(True)
        self._is_paused = False
        self._snapshot_event_value.setText("Job resumed.")
        self._snapshot_updated_value.setText(time.strftime("%H:%M:%S"))
        self._ui_log("INFO", "=== Job resumed ===")

    def _ui_cancelled(self):
        self._status_line.setText(tr("monitor.status_line.cancelled", self._language))
        self._status_line.setStyleSheet("color: #FF9F0A; font-family: '-apple-system', sans-serif; font-size: 12px;")
        self._session_state.setText("IDLE")
        self._session_state.setStyleSheet("color: #FF9F0A; font-family: 'PT Root UI', monospace; font-size: 10px; font-weight: 600;")
        self._status_badge.setText(tr("monitor.status.idle", self._language))
        self._status_badge.setStyleSheet("color: #FF9F0A; background: #2C2C2E; border-radius: 6px; padding: 4px 10px; font-family: 'PT Root UI', monospace; font-size: 10px; font-weight: 600;")
        self._snapshot_note.setText("Waiting for a search to begin.")
        self._snapshot_source_value.setText("-")
        self._snapshot_city_value.setText("-")
        self._snapshot_limit_value.setText("-")
        self._snapshot_updated_value.setText("-")
        self._snapshot_event_value.setText("No activity yet.")
        self._progress_label.setText(tr("monitor.progress.cancelled", self._language))
        self._btn_more.setEnabled(False)
        self._btn_pause.setEnabled(False)
        self._btn_resume.setEnabled(False)
        self._btn_cancel.setEnabled(False)
        self._ui_log("WARNING", "=== Job cancelled ===")

    def _ui_trial_limit(self):
        """Show the trial limit dialog and stop UI timers."""
        self._status_line.setText(tr("monitor.status.trial", self._language))
        self._status_line.setStyleSheet("color: #FF453A; font-family: '-apple-system', sans-serif; font-size: 12px;")
        
        self._status_badge.setText("TRIAL OVER")
        self._status_badge.setStyleSheet("color: #FF453A; background: rgba(255,69,58,0.15); border-radius: 6px; padding: 4px 10px; font-family: 'PT Root UI', monospace; font-size: 10px; font-weight: 600;")
        
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

    def _prepare_log(self, level: str, message: str) -> tuple[str, str]:
        """Prepare one colorful log line and a short summary."""
        display_msg = message or ""
        active_id = self._active_job_id
        if active_id and display_msg.startswith(f"[{active_id}]"):
            prefix_len = len(active_id) + 2
            display_msg = display_msg[prefix_len:].strip()
        
        summary = display_msg.strip()
        if summary.startswith("===") and summary.endswith("==="):
            summary = summary.strip("= ").strip()
        if len(summary) > 72:
            summary = summary[:69].rstrip() + "..."

        level_text = str(level or "INFO").upper()
        
        # Color mapping
        colors = {
            "INFO": "#0A84FF",     # Blue
            "WARNING": "#FF9F0A",  # Orange
            "ERROR": "#FF453A",   # Red
            "SUCCESS": "#30D158", # Green
            "DEBUG": "#8E8E93"     # Gray
        }
        color = colors.get(level_text, "#8E8E93")
        
        timestamp = f"<span style='color: #636366;'>{time.strftime('%H:%M:%S')}</span>"
        tag = f"<span style='color: {color}; font-weight: bold;'>[{level_text}]</span>"
        content = f"<span style='color: #E5E5EA;'>{display_msg}</span>"
        
        line = f"{timestamp} {tag} {content}"
        return line, summary

    def _prepare_result_line(self, data: dict) -> tuple[str, str]:
        company = str(data.get("company") or "Unnamed employer").strip()
        title = str(data.get("title") or "-").strip()
        city = str(data.get("city") or "-").strip()
        
        email_val = data.get("email")
        email_color = "#30D158" if email_val else "#636366"
        email_text = f"<span style='color: {email_color};'>email={'YES' if email_val else 'NO'}</span>"
        
        phone_val = data.get("phone")
        phone_color = "#30D158" if phone_val else "#636366"
        phone_text = f"<span style='color: {phone_color};'>phone={'YES' if phone_val else 'NO'}</span>"
        
        site_val = data.get("website")
        site_color = "#30D158" if site_val else "#636366"
        site_text = f"<span style='color: {site_color};'>{'SITE' if site_val else 'NO-SITE'}</span>"
        
        duplicate_text = ""
        if data.get("duplicate"):
            duplicate_text = " | <span style='color: #FFD60A; font-weight: bold;'>LIBRARY</span>"
            
        summary = f"{company} | {title}" if len(company) + len(title) <= 72 else f"{company[:30]}... | {title[:30]}..."
        
        timestamp = f"<span style='color: #636366;'>{time.strftime('%H:%M:%S')}</span>"
        tag = f"<span style='color: #30D158; font-weight: bold;'>[LEAD]</span>"
        content = f"<span style='color: #FFFFFF; font-weight: 600;'>{company}</span> | <span style='color: #AEAEB2;'>{title}</span> | <span style='color: #636366;'>{city}</span> | {email_text} | {phone_text} | {site_text}{duplicate_text}"
        
        line = f"{timestamp} {tag} {content}"
        return line, summary

    def _apply_logs_batch(self, batch_lines: list[str], last_summary: str | None):
        """Append a batch of log lines using fast batching.

        Appends multiple lines and trims the document if it exceeds the limit.
        Trimming is done in a single block operation to avoid multiple layout passes.
        """
        if not batch_lines:
            return

        if self._stream_stack.currentWidget() != self._log_tail:
            self._stream_stack.setCurrentWidget(self._log_tail)

        # Disable updates for mass insertion
        self._log_tail.setUpdatesEnabled(False)
        try:
            for line in batch_lines:
                if line:
                    self._log_tail.append(line)

            # Cap the log size efficiently (bulk removal)
            doc = self._log_tail.document()
            MAX_LINES = 2000
            TRIM_THRESHOLD = 200 # Only trim when 200 lines over, to avoid trimming every tick
            
            if doc.blockCount() > MAX_LINES + TRIM_THRESHOLD:
                to_remove = doc.blockCount() - MAX_LINES
                cursor = self._log_tail.textCursor()
                cursor.movePosition(cursor.MoveOperation.Start)
                # Select the first N blocks (lines)
                for _ in range(to_remove):
                    cursor.movePosition(cursor.MoveOperation.NextBlock, cursor.MoveMode.KeepAnchor)
                # Remove them all in one go
                cursor.removeSelectedText()
        finally:
            self._log_tail.setUpdatesEnabled(True)

        if last_summary:
            self._snapshot_event_value.setText(last_summary)
            self._snapshot_updated_value.setText(time.strftime("%H:%M:%S"))

        if not self._user_scrolling:
            scrollbar = self._log_tail.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def _ui_log(self, level: str, message: str):
        """Fallback for individual logs if needed (now batched via _drain_queue)."""
        line, summary = self._prepare_log(level, message)
        self._apply_logs_batch([line], summary)

    def _scrape_more(self):
        if self._current_config:
            self.scrape_more_requested.emit(self._current_config)

    def _pause(self):
        orchestrator.pause_job()

    def _resume(self):
        orchestrator.resume_job()
        self._btn_resume.setEnabled(False)

    def _cancel(self):
        from .components import ZugzwangDialog
        msg = ZugzwangDialog(
            tr("monitor.dialog.stop.title", self._language),
            tr("monitor.dialog.stop.body", self._language),
            self.window(),
            destructive=True
        )
        # Non-blocking: connect accepted signal *before* open() so the
        # dialog returns immediately and never stalls the main event loop.
        msg.accepted.connect(orchestrator.cancel_job)
        msg.open()

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
            return f"{minutes}m {secs}s"
        return f"{secs}s"
