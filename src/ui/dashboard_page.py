"""
ZUGZWANG - Dashboard Page
Premium Obsidian Core analytics and recent activity overview.
"""

from __future__ import annotations

import json
from collections import deque

from PySide6.QtCore import Qt, Signal, QTimer, QPropertyAnimation, QEasingCurve, QSize
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QGraphicsDropShadowEffect
)

from qfluentwidgets import (
    ScrollArea, 
    TransparentPushButton,
    ElevatedCardWidget,
    FluentIcon,
    IconWidget,
    PrimaryPushButton,
    PushButton,
    TransparentToolButton
)

from ..core.events import event_bus
from ..core.i18n import get_language, tr
from ..core.config import config_manager
from ..core.models import ScrapingJob
from ..core.security import LicenseManager
from .theme import Theme
from .components import FeedbackDialog
from ..services.orchestrator import orchestrator


class DashboardMetricCard(QFrame):
    """Metric card using macOS ZUGZWANG styling with shadow elevation."""

    def __init__(self, icon: FluentIcon, title: str, value: str = "0", meta: str = "", color: str = "#0A84FF", parent=None):
        super().__init__(parent)
        self._accent = color
        self.setFixedSize(220, 124) # Match SearchSourceCard exactly
        self.setObjectName("DashboardMetricCard")
        
        # ZUGZWANG Styling: Zinc bg, 12px radii, no border
        self.setStyleSheet(
            f"QFrame#DashboardMetricCard {{ "
            f"background: #2C2C2E; "
            f"border: none; "
            f"border-radius: 12px; "
            f"}}"
        )

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(16, 16, 16, 16)
        self.main_layout.setSpacing(6)

        # Removed ZUGZWANG Elevation Effect to fix severe UI lag

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        
        self.iconWidget = IconWidget(icon)
        self.iconWidget.setFixedSize(20, 20)
        self.iconWidget.setStyleSheet(f"color: {Theme.TEXT_SECONDARY};")
        top_row.addWidget(self.iconWidget)
        top_row.addStretch(1)

        # Pill Status Badge 
        self.metaLabelWrapper = QFrame()
        self.metaLabelWrapper.setStyleSheet(
            f"background: transparent; border: 1px solid {self._accent}; border-radius: 8px;"
        )
        l_wrap = QHBoxLayout(self.metaLabelWrapper)
        l_wrap.setContentsMargins(8, 2, 8, 2)
        self.metaLabel = QLabel(meta.upper())
        self.metaLabel.setStyleSheet(f"color: {self._accent}; font-family: 'SF Mono', 'Menlo', monospace; font-size: 10px; font-weight: 600; letter-spacing: 0.5px; background: transparent; border: none;")
        l_wrap.addWidget(self.metaLabel)
        
        top_row.addWidget(self.metaLabelWrapper)
        
        self.main_layout.addLayout(top_row)
        self.main_layout.addStretch(1)

        self.valueLabel = QLabel(value)
        self.valueLabel.setStyleSheet(f"color: #FFFFFF; font-family: 'PT Root UI', sans-serif; font-size: 32px; font-weight: 700; background: transparent; border: none;")
        self.main_layout.addWidget(self.valueLabel)

        self.titleLabel = QLabel(title.upper())
        self.titleLabel.setStyleSheet(f"color: #8E8E93; font-family: 'SF Mono', 'Menlo', monospace; font-size: 11px; font-weight: 600; letter-spacing: 1.5px; background: transparent; border: none;")
        self.main_layout.addWidget(self.titleLabel)

    def enterEvent(self, event):
        # Removed shadow lift animation to improve performance
        super().enterEvent(event)

    def leaveEvent(self, event):
        # Removed shadow drop animation to improve performance
        super().leaveEvent(event)

    def set_value(self, value: str):
        self.valueLabel.setText(str(value))

    def set_meta(self, text: str):
        self.metaLabel.setText(str(text).upper())

    def set_title(self, text: str):
        self.titleLabel.setText(str(text).upper())

class TrialStatusCard(DashboardMetricCard):
    """Special card for free trial users, Obsidian Core style."""
    def __init__(self, language: str, parent=None):
        self._language = language
        super().__init__(
            FluentIcon.HISTORY, tr("dashboard.metric.trial", self._language), "0", "0 / 20",
            color="#FF453A", parent=parent
        )
        self.setToolTip(tr("dashboard.metric.trial.tip", self._language))
        self._refresh()
        
    def _refresh(self):
        status = LicenseManager.get_trial_status()
        self.set_value(f"{status['remaining']}")
        self.set_meta(f"{status['used']} / {status['total']}")
        
        if status['is_active']:
            self.hide()
        else:
            self.show()


class JobTableRow(QFrame):
    """Compact job summary row, Obsidian Core style."""
    rerun_requested = Signal(object)  # SearchConfig

    def __init__(self, job: ScrapingJob, language: str, parent=None):
        super().__init__(parent)
        self._language = language
        self._job = job
        self.setFixedHeight(70)
        self.setObjectName("DashboardJobRow")
        self.setStyleSheet(
            f"QFrame#DashboardJobRow {{ "
            f"background: rgba(44, 44, 46, 0.4); "
            f"border: 1px solid rgba(255, 255, 255, 0.05); "
            f"border-radius: 12px; "
            f"margin: 0; "
            f"}} "
            f"QFrame#DashboardJobRow:hover {{ "
            f"background: rgba(58, 58, 60, 0.6); "
            f"border: 1px solid rgba(255, 255, 255, 0.12); "
            f"}}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(16)

        # Source-specific icon
        source = getattr(job.config, "source_type", None)
        source_val = getattr(source, "value", "unknown") if source else "unknown"
        
        icon_type = FluentIcon.SEARCH
        icon_color = Theme.ACCENT_PRIMARY
        
        if "google" in source_val.lower():
            icon_type = FluentIcon.GLOBE
            icon_color = "#4285F4"
        elif "ausbildung" in source_val.lower():
            icon_type = FluentIcon.EDUCATION
            icon_color = "#30D158"
        elif "aubi" in source_val.lower():
            icon_type = FluentIcon.GAME
            icon_color = "#FF9F0A"

        icon_widget = IconWidget(icon_type)
        icon_widget.setFixedSize(20, 20)
        icon_widget.setStyleSheet(f"color: {icon_color}; background: transparent; border: none;")
        icon_widget.setToolTip("Platform source for this search")
        layout.addWidget(icon_widget, 0, Qt.AlignVCenter)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 14, 0, 14)
        text_col.setSpacing(1)
        text_col.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        title = QLabel(job.config.job_title or job.query_label or "Untitled Search")
        title.setStyleSheet(f"font-size: 14px; font-weight: 700; color: #FFFFFF; background: transparent; border: none;")
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        title.setToolTip("Your defined search query or job title")
        text_col.addWidget(title)

        started = str(getattr(job, "started_at", "") or tr("dashboard.job.time.now", self._language))
        meta_txt = tr("dashboard.job.records", self._language).format(count=job.total_found, started=started[:16])
        if source_val != "unknown":
            meta_txt = f"{source_val.replace('_', ' ').title()}  •  {meta_txt}"
            
        meta = QLabel(meta_txt)
        meta.setStyleSheet(f"color: #8E8E93; font-size: 11px; background: transparent; border: none;")
        meta.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        meta.setToolTip(f"Found {job.total_found} total records\\nEmails: {job.total_emails}\\nWebsites: {job.total_websites}\\nErrors: {job.total_errors}")
        text_col.addWidget(meta)
        layout.addLayout(text_col, 1)

        status = str(job.status.value).upper()
        badge_label = QLabel(status)
        
        b_bg = "rgba(142, 142, 147, 0.1)"
        b_clr = "#8E8E93"
        b_border = "rgba(142, 142, 147, 0.2)"
        
        if status in {"RUNNING", "PAUSED", "PENDING"}:
            b_bg = "rgba(10, 132, 255, 0.1)"
            b_clr = "#0A84FF"
            b_border = "rgba(10, 132, 255, 0.3)"
        elif status == "COMPLETED":
            b_bg = "rgba(48, 209, 88, 0.1)"
            b_clr = "#30D158"
            b_border = "rgba(48, 209, 88, 0.3)"
        elif status == "FAILED":
            b_bg = "rgba(255, 69, 58, 0.1)"
            b_clr = "#FF453A"
            b_border = "rgba(255, 69, 58, 0.3)"

        badge_label.setStyleSheet(f"""
            QLabel {{
                background: {b_bg};
                color: {b_clr};
                border: 1px solid {b_border};
                border-radius: 6px;
                font-family: 'SF Mono', monospace;
                font-size: 10px;
                font-weight: 700;
                padding: 4px 8px;
            }}
        """)
        badge_label.setToolTip(f"Current scraping status: {status}")
        layout.addWidget(badge_label, 0, Qt.AlignVCenter)

        # RE-RUN button
        # RE-RUN button
        rerun_btn = TransparentToolButton(FluentIcon.HISTORY)
        rerun_btn.setFixedSize(36, 36)
        rerun_btn.setIconSize(QSize(18, 18))
        rerun_btn.setCursor(Qt.PointingHandCursor)
        rerun_btn.setToolTip("Click to run this search again with the same parameters")
        rerun_btn.clicked.connect(lambda: self.rerun_requested.emit(self._job.config))
        layout.addWidget(rerun_btn, 0, Qt.AlignVCenter)


class DashboardPage(QWidget):
    navigate_to_search = Signal()
    navigate_to_results = Signal()
    rerun_requested = Signal(object)  # SearchConfig

    def __init__(self):
        super().__init__()
        self._language = get_language(config_manager.settings.app_language)
        self._jobs: list[ScrapingJob] = []
        self._saved_summary = (0, 0, 0)
        self._activity_items: deque[str] = deque(maxlen=8)
        self._activity_labels: list[QLabel] = []
        self._activity_timer = QTimer(self)
        self._activity_timer.setSingleShot(True)
        self._activity_timer.setInterval(250)
        self._activity_timer.timeout.connect(self._refresh_activity)
        self._build_ui()
        self._connect_events()
        QTimer.singleShot(100, self._load_recent_jobs_from_disk)

    def _load_recent_jobs_from_disk(self):
        """Loads historical job definitions to populate the Recent Jobs list."""
        from ..core.config import get_data_dir
        import glob
        import os

        # Find all job_*.db files
        data_dir = get_data_dir()
        db_files = glob.glob(os.path.join(data_dir, "job_*.db"))
        # Sort by filename (which includes timestamp) descending
        db_files.sort(reverse=True)
        
        jobs = []
        for db_path in db_files[:6]: # Load up to last 6 metadata
            try:
                meta, _ = orchestrator._export.load_project(db_path)
                if meta:
                    from ..core.models import ScrapingStatus, SearchConfig
                    # Reconstruct ScrapingJob from meta
                    config_data = json.loads(meta.get("config_json", "{}"))
                    from ..core.models import SourceType
                    if config_data.get("source_type") and isinstance(config_data["source_type"], str):
                        config_data["source_type"] = SourceType(config_data["source_type"])
                    
                    job = ScrapingJob(
                        config=SearchConfig(**{k: v for k, v in config_data.items() if k in SearchConfig.__dataclass_fields__}),
                        status=ScrapingStatus(meta.get("status", "completed")),
                    )
                    job.id = meta.get("id", "unknown")
                    job.created_at = meta.get("created_at")
                    job.started_at = meta.get("started_at")
                    job.completed_at = meta.get("completed_at")
                    
                    stats = json.loads(meta.get("stats_json", "{}"))
                    job.total_found = stats.get("total_found", 0)
                    job.total_emails = stats.get("total_emails", 0)
                    job.total_websites = stats.get("total_websites", 0)
                    job.total_errors = stats.get("total_errors", 0)
                    
                    jobs.append(job)
            except Exception as e:
                print(f"[DASHBOARD] Failed to load historical job {db_path}: {e}")
        
        if jobs:
            self._jobs = jobs
            self._refresh_stats()
            self._refresh_job_list()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.setObjectName("dashboardPage")
        self.setStyleSheet(f"QWidget#dashboardPage {{ background: {Theme.BG_OBSIDIAN}; }}")

        # ZUGZWANG 5.0 - Static Dashboard (No scrolling allowed)
        self.scrollArea = ScrollArea(self)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scrollArea.verticalScrollBar().setFixedWidth(0)
        # Fix: qfluentwidgets.ScrollArea might not have setWheelByMouse depending on version.
        # We override the wheelEvent directly to ensure no scrolling is possible.
        self.scrollArea.wheelEvent = lambda event: event.ignore()
        self.scrollArea.setFocusPolicy(Qt.NoFocus) # Prevent keyboard scrolling
        self.scrollArea.setStyleSheet("QScrollArea { background: transparent; border: none; } QScrollBar { width: 0px; height: 0px; }")
        root.addWidget(self.scrollArea)

        content = QWidget()
        self.scrollArea.setWidget(content)

        body = QVBoxLayout(content)
        body.setContentsMargins(32, 24, 32, 32)
        body.setSpacing(32)

        # ── Header ────────────────────────────────────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(16)
        
        title_wrap = QVBoxLayout()
        title_wrap.setSpacing(4)
        
        self.heroTitle = QLabel(tr("dashboard.title", self._language))
        self.heroTitle.setStyleSheet(f"color: #FFFFFF; font-family: 'PT Root UI', sans-serif; font-size: 28px; font-weight: 600; background: transparent; border: none;")
        title_wrap.addWidget(self.heroTitle)

        self.heroSubtitle = QLabel(tr("dashboard.subtitle.ready", self._language))
        self.heroSubtitle.setStyleSheet(f"color: #8E8E93; font-family: 'PT Root UI', sans-serif; font-size: 13px; background: transparent; border: none;")
        title_wrap.addWidget(self.heroSubtitle)
        
        header.addLayout(title_wrap)
        header.addStretch(1)

        from PySide6.QtWidgets import QPushButton as _QPB
        self.exportBtn = _QPB(tr("dashboard.button.export", self._language))
        self.exportBtn.setFixedSize(160, 36)
        self.exportBtn.setCursor(Qt.PointingHandCursor)
        self.exportBtn.setStyleSheet("""
            QPushButton {
                background-color: #2C2C2E;
                border: 1px solid #3A3A3C;
                border-radius: 10px;
                color: white;
                height: 36px;
                padding: 0 18px;
                font-family: 'PT Root UI', sans-serif;
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 1.6px;
                text-transform: uppercase;
            }
            QPushButton:hover { background-color: #3A3A3C; }
        """)
        header.addWidget(self.exportBtn, 0, Qt.AlignVCenter)

        self.newSearchBtn = _QPB(tr("dashboard.button.new", self._language))
        self.newSearchBtn.setFixedSize(160, 36)
        self.newSearchBtn.setCursor(Qt.PointingHandCursor)
        self.newSearchBtn.setStyleSheet("""
            QPushButton {
                background-color: #0A84FF;
                border: none;
                border-radius: 10px;
                color: white;
                height: 36px;
                padding: 0 18px;
                font-family: 'PT Root UI', sans-serif;
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 1.6px;
                text-transform: uppercase;
            }
            QPushButton:hover { background-color: #409CFF; }
        """)
        header.addWidget(self.newSearchBtn, 0, Qt.AlignVCenter)

        self.loveBtn = _QPB(tr("dashboard.button.support", self._language))
        self.loveBtn.setFixedSize(140, 36)
        self.loveBtn.setCursor(Qt.PointingHandCursor)
        self.loveBtn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1.5px solid #3A3A3C;
                border-radius: 10px;
                color: #30D158;
                height: 36px;
                padding: 0 16px;
                font-family: 'PT Root UI', sans-serif;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1.2px;
                text-transform: uppercase;
            }
            QPushButton:hover { background-color: rgba(48, 209, 88, 0.05); border-color: rgba(48, 209, 88, 0.3); }
        """)
        self.loveBtn.clicked.connect(self._open_feedback)
        header.addWidget(self.loveBtn, 0, Qt.AlignVCenter)

        body.addLayout(header)

        # ── Metrics Grid ──────────────────────────────────────────────────────
        metrics = QHBoxLayout()
        metrics.setSpacing(16)
        metrics.addStretch(1)
        self.metric_leads = DashboardMetricCard(FluentIcon.PEOPLE, tr("dashboard.metric.leads", self._language), "0", tr("dashboard.meta.no_data", self._language), color="#0A84FF")
        self.metric_websites = DashboardMetricCard(FluentIcon.GLOBE, tr("dashboard.metric.websites", self._language), "0", tr("dashboard.meta.live", self._language), color="#5E5CE6")
        self.metric_emails = DashboardMetricCard(FluentIcon.MAIL, tr("dashboard.metric.emails", self._language), "0", tr("dashboard.meta.valid", self._language).format(ratio=0), color="#30D158")
        self.metric_active = DashboardMetricCard(FluentIcon.DEVELOPER_TOOLS, tr("dashboard.metric.active", self._language), "0", tr("dashboard.meta.idle", self._language), color="#FF9F0A")
        self.metric_trial = TrialStatusCard(self._language)
        metrics.addWidget(self.metric_leads)
        metrics.addWidget(self.metric_websites)
        metrics.addWidget(self.metric_emails)
        metrics.addWidget(self.metric_active)
        metrics.addWidget(self.metric_trial)
        metrics.addStretch(1)
        body.addLayout(metrics)

        # ── Lower Split Pane ──────────────────────────────────────────────────
        lower_split = QHBoxLayout()
        lower_split.setSpacing(24)

        # Left Column: Recent Jobs
        left_col = QVBoxLayout()
        left_col.setSpacing(12)

        jobs_hdr = QHBoxLayout()
        jobs_lbl = QLabel(tr("dashboard.section.jobs", self._language))
        jobs_lbl.setObjectName("SectionLabel")
        jobs_hdr.addWidget(jobs_lbl)
        jobs_hdr.addStretch(1)
        left_col.addLayout(jobs_hdr)

        self.jobsHost = QFrame()
        self.jobsHost.setObjectName("DashboardTableCard")
        self.jobsHost.setStyleSheet(
            f"QFrame#DashboardTableCard {{ "
            f"background: transparent; "
            f"border: none; "
            f"border-radius: 12px; "
            f"}}"
        )
        jobs_host_layout = QVBoxLayout(self.jobsHost)
        jobs_host_layout.setSpacing(8)
        self.jobsFrame = QVBoxLayout()
        self.jobsFrame.setSpacing(10)
        jobs_host_layout.addLayout(self.jobsFrame)
        left_col.addWidget(self.jobsHost, 1)
        lower_split.addLayout(left_col, 2)

        # Right Column: Activity
        right_col = QVBoxLayout()
        right_col.setSpacing(12)

        activity_lbl = QLabel(tr("dashboard.section.activity", self._language))
        activity_lbl.setObjectName("SectionLabel")
        right_col.addWidget(activity_lbl)

        self.activityCard = QFrame()
        self.activityCard.setObjectName("DashboardSideCard")
        self.activityCard.setStyleSheet(
            f"QFrame#DashboardSideCard {{ "
            f"background: transparent; "
            f"border: none; "
            f"border-radius: 12px; "
            f"}}"
        )
        activity_layout = QVBoxLayout(self.activityCard)
        activity_layout.setContentsMargins(0, 0, 0, 0)
        activity_layout.setSpacing(8)
        activity_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.activityLayout = activity_layout
        right_col.addWidget(self.activityCard, 1)
        
        lower_split.addLayout(right_col, 1)
        lower_split.setStretch(0, 2)
        lower_split.setStretch(1, 1)
        body.addLayout(lower_split, 1)

        self._refresh_job_list()
        self._refresh_activity()
        self._refresh_stats()

    def _open_feedback(self):
        msg = FeedbackDialog(self.window())
        msg.exec()

    def _connect_events(self):
        from .event_bridge import event_bridge
        event_bridge.job_started.connect(self._on_job_started)
        event_bridge.job_completed.connect(self._on_job_update)
        event_bridge.job_failed.connect(self._on_job_update)
        event_bridge.job_cancelled.connect(self._on_job_update)
        event_bridge.job_log.connect(self._on_job_log)
        event_bridge.export_completed.connect(self._on_export_event)
        event_bridge.export_failed.connect(self._on_export_event)
        event_bridge.job_progress.connect(lambda _: self._refresh_stats())
        event_bridge.job_result.connect(self._on_live_result)

        self.newSearchBtn.clicked.connect(self.navigate_to_search.emit)
        self.exportBtn.clicked.connect(self.navigate_to_results.emit)

    def _record_activity(self, text: str):
        if not text:
            return
        self._activity_items.appendleft(text)
        if not self._activity_timer.isActive():
            self._activity_timer.start()

    def _on_job_started(self, job_id: str, config=None):
        label = getattr(config, "job_title", "") if config else ""
        source = getattr(getattr(config, "source_type", None), "value", "")
        summary = label or tr("dashboard.activity.job_started", self._language)
        if source:
            summary = f"{summary} | {source.title()}"
        self._record_activity(summary)
        QTimer.singleShot(0, self._refresh_stats)

    def _on_job_update(self, job_id: str, *args):
        error = args[0] if args and isinstance(args[0], str) else ""
        if error:
            self._record_activity(tr("dashboard.activity.job_failed", self._language).format(job=job_id[:8], error=error[:60]))
        elif job_id:
            self._record_activity(tr("dashboard.activity.job_updated", self._language).format(job=job_id[:8]))
        
        # Ensure the current job is added to the historical list if not present
        active = orchestrator.current_job
        if active and active.id == job_id:
            if active not in self._jobs:
                self._jobs.insert(0, active)
        
        QTimer.singleShot(0, self._refresh_stats)
        QTimer.singleShot(0, self._refresh_job_list)

    def _on_job_log(self, job_id: str, level: str, message: str):
        level = str(level).upper()
        message = str(message).strip()
        if message:
            self._record_activity(f"{level} | {message[:60]}")

    def _on_live_result(self, record):
        """Adds a live finding note to the activity log."""
        if hasattr(record, "name") and record.name:
            self._record_activity(tr("dashboard.activity.found", self._language).format(name=record.name[:40]))

    def _on_export_event(self, **kwargs):
        fmt = str(kwargs.get("format", "")).upper()
        count = kwargs.get("count")
        error = kwargs.get("error", "")
        if error:
            self._record_activity(tr("dashboard.activity.export_failed", self._language).format(fmt=fmt))
        else:
            suffix = f" | {count} records" if count is not None else ""
            self._record_activity(tr("dashboard.activity.export_done", self._language).format(fmt=fmt, suffix=suffix))

    def refresh(self, jobs: list[ScrapingJob] = None):
        """Unified refresh: update with new jobs list OR just refresh stats/trial."""
        if jobs is not None:
            self._jobs = jobs
            self._refresh_job_list()
        
        self._refresh_stats()
        if hasattr(self, 'metric_trial'):
            self.metric_trial._refresh()

    def load_summary(self, total_records: int, total_emails: int, total_websites: int):
        self._saved_summary = (total_records, total_emails, total_websites)
        self._refresh_stats()

    def _totals(self):
        # Always use the global database metrics from _saved_summary as the base
        # MainWindow provides this via load_summary from job_memory.db
        total_leads = self._saved_summary[0]
        total_emails = self._saved_summary[1]
        total_websites = self._saved_summary[2]
        
        # Include active job from orchestrator if not already in self._jobs
        active_job = orchestrator.current_job
        if active_job and active_job not in self._jobs:
            total_leads += active_job.total_found
            total_emails += active_job.total_emails
            total_websites += active_job.total_websites

        active_jobs_count = sum(1 for j in self._jobs if j.status.value in {"running", "paused", "pending"})
        if active_job and active_job.status.value in {"running", "paused", "pending"} and active_job not in self._jobs:
            active_jobs_count += 1
            
        completed_jobs = sum(1 for j in self._jobs if j.status.value == "completed")
        failed_jobs = sum(1 for j in self._jobs if j.status.value in {"failed", "cancelled"})
        total_jobs = len(self._jobs) + (1 if active_job and active_job not in self._jobs else 0)
        
        return total_leads, total_emails, total_websites, active_jobs_count, completed_jobs, failed_jobs, total_jobs


    def _refresh_stats(self):
        total_leads, total_emails, total_websites, active_jobs, completed_jobs, failed_jobs, total_jobs = self._totals()

        self.metric_leads.set_value(f"{total_leads:,}")
        self.metric_leads.set_title(tr("dashboard.metric.leads", self._language))
        self.metric_leads.set_meta(tr("dashboard.meta.no_data", self._language) if total_leads == 0 else tr("dashboard.meta.ready", self._language))

        self.metric_websites.set_value(f"{total_websites:,}")
        self.metric_websites.set_title(tr("dashboard.metric.websites", self._language))
        self.metric_websites.set_meta(tr("dashboard.meta.live", self._language) if total_websites else tr("dashboard.meta.queued", self._language))

        email_ratio = int((total_emails / total_leads) * 100) if total_leads else 0
        self.metric_emails.set_value(f"{total_emails:,}")
        self.metric_emails.set_title(tr("dashboard.metric.emails", self._language))
        self.metric_emails.set_meta(tr("dashboard.meta.valid", self._language).format(ratio=email_ratio))

        self.metric_active.set_value(f"{active_jobs}")
        self.metric_active.set_title(tr("dashboard.metric.active", self._language))
        self.metric_active.set_meta(tr("dashboard.meta.running", self._language) if active_jobs else tr("dashboard.meta.idle", self._language))

        if hasattr(self, 'metric_trial'):
            self.metric_trial._refresh()

        if active_jobs:
            self.heroSubtitle.setText(tr("dashboard.subtitle.running", self._language).format(count=active_jobs))
        elif total_jobs:
            self.heroSubtitle.setText(tr("dashboard.subtitle.workspace", self._language).format(count=total_jobs))
        else:
            self.heroSubtitle.setText(tr("dashboard.subtitle.welcome", self._language))

    def _refresh_job_list(self):
        while self.jobsFrame.count():
            item = self.jobsFrame.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._jobs:
            from .components import EmptyStateWidget
            empty = EmptyStateWidget(
                FluentIcon.SEARCH,
                title=tr("dashboard.empty.jobs", self._language),
                description="No scraping jobs run yet. Start a new search to see history here.",
                button_text="New Search",
                button_callback=self.navigate_to_search.emit
            )
            self.jobsFrame.addWidget(empty)
            return

        # Sort by completion date or creation date if not completed
        self._jobs.sort(key=lambda j: j.completed_at or j.created_at, reverse=True)
        
        # Take the top 4 (most recent)
        recent = self._jobs[:4]
        for job in recent:
            row = JobTableRow(job, self._language)
            row.rerun_requested.connect(self.rerun_requested.emit)
            self.jobsFrame.addWidget(row)


    def _refresh_activity(self):
        if not self._activity_items:
            # If no items, ensure there's a placeholder inside and no other elements.
            if not self._activity_labels:
                # Clear existing
                while self.activityLayout.count():
                    item = self.activityLayout.takeAt(0)
                    if item.widget(): item.widget().deleteLater()
                
                # Left alignment for empty state
                self.activityLayout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
                
                placeholder_container = QWidget()
                placeholder_container.setStyleSheet("background: transparent; border: none;")
                pv = QVBoxLayout(placeholder_container)
                pv.setAlignment(Qt.AlignCenter)
                pv.setSpacing(12)

                icon = IconWidget(FluentIcon.RINGER)
                icon.setFixedSize(28, 28)
                icon.setStyleSheet(f"color: #444446; border: none;") # Muted icon
                pv.addWidget(icon, 0, Qt.AlignHCenter)

                empty = QLabel(tr("dashboard.empty.activity", self._language))
                empty.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-family: 'SF Mono', 'Menlo', monospace; font-size: 11px; font-weight: 600; letter-spacing: 1px; border: none;")
                pv.addWidget(empty, 0, Qt.AlignHCenter)

                desc = QLabel(tr("dashboard.empty.activity.body", self._language))
                desc.setWordWrap(True)
                desc.setAlignment(Qt.AlignCenter)
                desc.setStyleSheet(f"color: {Theme.TEXT_TERTIARY}; font-size: 12px; border: none;")
                desc.setFixedWidth(200)
                pv.addWidget(desc, 0, Qt.AlignHCenter)
                
                self.activityLayout.addWidget(placeholder_container)
            return

        # Initialize the fixed UI rows on first data arrival
        if not self._activity_labels:
            # Clear placeholder
            while self.activityLayout.count():
                item = self.activityLayout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            
            self.activityLayout.setContentsMargins(0, 0, 0, 0)
            self.activityLayout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            
            # Pre-create 8 rows maximum
            for _ in range(8):
                row = QWidget()
                row.setStyleSheet("QWidget { background: transparent; border: none; }")
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 2, 0, 2)
                row_layout.setSpacing(10)

                dot = QLabel("●")
                dot.setStyleSheet(f"color: #30D158; font-size: 8px; background: transparent; border: none;")
                dot.setFixedWidth(10)
                dot.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

                label = QLabel("")
                label.setWordWrap(False)
                label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                label.setStyleSheet(f"color: #8E8E93; font-family: 'SF Mono', 'Menlo', monospace; font-size: 11px; background: transparent; border: none;")
                label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                row_layout.addWidget(dot, 0, Qt.AlignTop)
                row_layout.addWidget(label, 1, Qt.AlignTop)
                
                # Polish the row appearance: no padding, tight spacing
                row_layout.setContentsMargins(0, 0, 0, 0)
                
                self._activity_labels.append(label)
                self.activityLayout.addWidget(row)
                row.hide() # Hidden until needed

        snapshot = list(self._activity_items)
        for i, label in enumerate(self._activity_labels):
            if i < len(snapshot):
                label.setText(snapshot[i])
                label.parentWidget().show()
            else:
                label.parentWidget().hide()
