"""
ZUGZWANG - Dashboard Page
Premium Obsidian Core analytics and recent activity overview.
"""

from __future__ import annotations

from collections import deque

from PySide6.QtCore import Qt, Signal, QTimer, QPropertyAnimation, QEasingCurve
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
    PushButton
)

from ..core.events import event_bus
from ..core.models import ScrapingJob
from ..core.security import LicenseManager
from .theme import Theme


class DashboardMetricCard(QFrame):
    """Metric card using macOS ZUGZWANG styling with shadow elevation."""

    def __init__(self, icon: FluentIcon, title: str, value: str = "0", meta: str = "", color: str = "#0A84FF", parent=None):
        super().__init__(parent)
        self._accent = color
        self.setFixedSize(220, 124)
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

        # ZUGZWANG Elevation Effect
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(12)
        self._shadow.setXOffset(0)
        self._shadow.setYOffset(2)
        self._shadow.setColor(QColor(0, 0, 0, 102)) # 0.4 opacity
        self.setGraphicsEffect(self._shadow)

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
        self.valueLabel.setStyleSheet(f"color: #FFFFFF; font-family: 'SF Pro Display', '-apple-system', sans-serif; font-size: 40px; font-weight: 700; background: transparent; border: none;")
        self.main_layout.addWidget(self.valueLabel)

        self.titleLabel = QLabel(title.upper())
        self.titleLabel.setStyleSheet(f"color: #8E8E93; font-family: 'SF Mono', 'Menlo', monospace; font-size: 11px; font-weight: 600; letter-spacing: 1.5px; background: transparent; border: none;")
        self.main_layout.addWidget(self.titleLabel)

    def enterEvent(self, event):
        # Lift shadow by 4px
        self._anim = QPropertyAnimation(self._shadow, b"yOffset")
        self._anim.setDuration(120)
        self._anim.setEndValue(6)
        
        self._anim_blur = QPropertyAnimation(self._shadow, b"blurRadius")
        self._anim_blur.setDuration(120)
        self._anim_blur.setEndValue(16)
        
        self._anim.start()
        self._anim_blur.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._anim = QPropertyAnimation(self._shadow, b"yOffset")
        self._anim.setDuration(120)
        self._anim.setEndValue(2)
        
        self._anim_blur = QPropertyAnimation(self._shadow, b"blurRadius")
        self._anim_blur.setDuration(120)
        self._anim_blur.setEndValue(12)
        
        self._anim.start()
        self._anim_blur.start()
        super().leaveEvent(event)

    def set_value(self, value: str):
        self.valueLabel.setText(str(value))

    def set_meta(self, text: str):
        self.metaLabel.setText(str(text).upper())

class TrialStatusCard(DashboardMetricCard):
    """Special card for free trial users, Obsidian Core style."""
    def __init__(self, parent=None):
        super().__init__(
            FluentIcon.HISTORY, "TRIAL SCRAPS", "0", "0 / 20", 
            color="#FF453A", parent=parent
        )
        self.setToolTip("Daily limit resets at midnight")
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

    def __init__(self, job: ScrapingJob, parent=None):
        super().__init__(parent)
        self.setFixedHeight(72)
        self.setObjectName("DashboardJobRow")
        self.setStyleSheet(
            f"QFrame#DashboardJobRow {{ "
            f"background: transparent; "
            f"border: none; "
            f"border-bottom: 1px solid {Theme.BORDER_SUBTLE}; "
            f"border-radius: 0; "
            f"}}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(16)

        dot = QFrame()
        dot.setObjectName("JobDot")
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(f"QFrame#JobDot {{ background: {Theme.ACCENT_PRIMARY}; border-radius: 4px; border: none; }}")
        layout.addWidget(dot, 0, Qt.AlignVCenter)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 14, 0, 14)
        text_col.setSpacing(4)

        title = QLabel(job.config.job_title or job.query_label)
        title.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {Theme.TEXT_PRIMARY}; border: none;")
        text_col.addWidget(title)

        started = str(getattr(job, "started_at", "") or "Just now")
        meta = QLabel(f"{job.total_found:,} records identified | {started[:16]}")
        meta.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px; border: none;")
        text_col.addWidget(meta)
        layout.addLayout(text_col, 1)

        status = str(job.status.value).upper()
        badge_label = QLabel(status)
        if status in {"RUNNING", "PAUSED", "PENDING"}:
            badge_label.setObjectName("BadgeInfo")
        elif status == "COMPLETED":
            badge_label.setObjectName("BadgeSuccess")
        else:
            badge_label.setObjectName("BadgeWarning")
        
        layout.addWidget(badge_label, 0, Qt.AlignVCenter)


class DashboardPage(QWidget):
    navigate_to_search = Signal()
    navigate_to_results = Signal()

    def __init__(self):
        super().__init__()
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

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.setObjectName("dashboardPage")
        self.setStyleSheet(f"QWidget#dashboardPage {{ background: {Theme.BG_OBSIDIAN}; }}")

        self.scrollArea = ScrollArea(self)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scrollArea.setStyleSheet("QScrollArea { background: transparent; border: none; }")
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
        
        self.heroTitle = QLabel("Dashboard")
        self.heroTitle.setStyleSheet(f"color: #FFFFFF; font-family: 'SF Pro Display', '-apple-system', sans-serif; font-size: 28px; font-weight: 600; background: transparent; border: none;")
        title_wrap.addWidget(self.heroTitle)

        self.heroSubtitle = QLabel("Ready for your next lead generation session.")
        self.heroSubtitle.setStyleSheet(f"color: #8E8E93; font-family: 'SF Pro Text', '-apple-system', sans-serif; font-size: 13px; background: transparent; border: none;")
        title_wrap.addWidget(self.heroSubtitle)
        
        header.addLayout(title_wrap)
        header.addStretch(1)

        from PySide6.QtWidgets import QPushButton as _QPB
        self.exportBtn = _QPB("EXPORT REPORT")
        self.exportBtn.setFixedHeight(36)
        self.exportBtn.setCursor(Qt.PointingHandCursor)
        self.exportBtn.setStyleSheet(Theme.zugzwang_button())
        header.addWidget(self.exportBtn, 0, Qt.AlignVCenter)

        self.newSearchBtn = _QPB("NEW SCRAPER")
        self.newSearchBtn.setFixedHeight(36)
        self.newSearchBtn.setCursor(Qt.PointingHandCursor)
        self.newSearchBtn.setStyleSheet(Theme.zugzwang_button())
        header.addWidget(self.newSearchBtn, 0, Qt.AlignVCenter)

        body.addLayout(header)

        # ── Metrics Grid ──────────────────────────────────────────────────────
        metrics = QHBoxLayout()
        metrics.setSpacing(16)
        metrics.addStretch(1)
        self.metric_leads = DashboardMetricCard(FluentIcon.PEOPLE, "AVAILABLE LEADS", "0", "NO DATA", color="#0A84FF")
        self.metric_websites = DashboardMetricCard(FluentIcon.GLOBE, "SITES INDEXED", "0", "LIVE", color="#5E5CE6")
        self.metric_emails = DashboardMetricCard(FluentIcon.MAIL, "EMAIL ADDRESSES", "0", "0% VALID", color="#30D158")
        self.metric_active = DashboardMetricCard(FluentIcon.DEVELOPER_TOOLS, "ACTIVE JOBS", "0", "IDLE", color="#FF9F0A")
        self.metric_trial = TrialStatusCard()
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
        jobs_lbl = QLabel("RECENT JOBS")
        jobs_lbl.setObjectName("SectionLabel")
        jobs_hdr.addWidget(jobs_lbl)
        jobs_hdr.addStretch(1)
        self.viewAllBtn = TransparentPushButton("VIEW ALL")
        self.viewAllBtn.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 10px; font-weight: 800; letter-spacing: 0.6px;")
        jobs_hdr.addWidget(self.viewAllBtn)
        left_col.addLayout(jobs_hdr)

        self.jobsHost = QFrame()
        self.jobsHost.setObjectName("DashboardTableCard")
        self.jobsHost.setStyleSheet(
            f"QFrame#DashboardTableCard {{ "
            f"background: #2C2C2E; "
            f"border: none; "
            f"border-radius: 12px; "
            f"}}"
        )
        self._jobs_shadow = QGraphicsDropShadowEffect(self.jobsHost)
        self._jobs_shadow.setBlurRadius(12)
        self._jobs_shadow.setXOffset(0)
        self._jobs_shadow.setYOffset(2)
        self._jobs_shadow.setColor(QColor(0, 0, 0, 102))
        self.jobsHost.setGraphicsEffect(self._jobs_shadow)
        jobs_host_layout = QVBoxLayout(self.jobsHost)
        jobs_host_layout.setContentsMargins(0, 0, 0, 0)
        jobs_host_layout.setSpacing(0)
        self.jobsFrame = QVBoxLayout()
        self.jobsFrame.setSpacing(0)
        jobs_host_layout.addLayout(self.jobsFrame)
        left_col.addWidget(self.jobsHost, 1)
        lower_split.addLayout(left_col, 2)

        # Right Column: Activity
        right_col = QVBoxLayout()
        right_col.setSpacing(12)

        activity_lbl = QLabel("ACTIVITY LOG")
        activity_lbl.setObjectName("SectionLabel")
        right_col.addWidget(activity_lbl)

        self.activityCard = QFrame()
        self.activityCard.setObjectName("DashboardSideCard")
        self.activityCard.setStyleSheet(
            f"QFrame#DashboardSideCard {{ "
            f"background: #2C2C2E; "
            f"border: none; "
            f"border-radius: 12px; "
            f"}}"
        )
        self._activity_shadow = QGraphicsDropShadowEffect(self.activityCard)
        self._activity_shadow.setBlurRadius(12)
        self._activity_shadow.setXOffset(0)
        self._activity_shadow.setYOffset(2)
        self._activity_shadow.setColor(QColor(0, 0, 0, 102))
        self.activityCard.setGraphicsEffect(self._activity_shadow)
        activity_layout = QVBoxLayout(self.activityCard)
        activity_layout.setContentsMargins(20, 20, 20, 20)
        activity_layout.setSpacing(16)
        activity_layout.setAlignment(Qt.AlignTop)
        self.activityLayout = activity_layout
        right_col.addWidget(self.activityCard, 1)
        
        lower_split.addLayout(right_col, 1)
        body.addLayout(lower_split, 1)

        self._refresh_job_list()
        self._refresh_activity()
        self._refresh_stats()

    def _connect_events(self):
        from .event_bridge import event_bridge
        event_bridge.job_started.connect(self._on_job_started)
        event_bridge.job_completed.connect(self._on_job_update)
        event_bridge.job_failed.connect(self._on_job_update)
        event_bridge.job_cancelled.connect(self._on_job_update)
        event_bridge.job_log.connect(self._on_job_log)
        event_bridge.export_completed.connect(self._on_export_event)
        event_bridge.export_failed.connect(self._on_export_event)

        self.newSearchBtn.clicked.connect(self.navigate_to_search.emit)
        self.viewAllBtn.clicked.connect(self.navigate_to_results.emit)
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
        summary = label or "New scraping job started"
        if source:
            summary = f"{summary} | {source.title()}"
        self._record_activity(summary)
        QTimer.singleShot(0, self._refresh_stats)

    def _on_job_update(self, job_id: str, *args):
        error = args[0] if args and isinstance(args[0], str) else ""
        if error:
            self._record_activity(f"Job {job_id[:8]} failed: {error[:60]}")
        elif job_id:
            self._record_activity(f"Job {job_id[:8]} updated")
        QTimer.singleShot(0, self._refresh_stats)
        QTimer.singleShot(0, self._refresh_job_list)

    def _on_job_log(self, job_id: str, level: str, message: str):
        level = str(level).upper()
        message = str(message).strip()
        if message:
            self._record_activity(f"{level} | {message[:60]}")

    def _on_export_event(self, **kwargs):
        fmt = str(kwargs.get("format", "")).upper()
        count = kwargs.get("count")
        error = kwargs.get("error", "")
        if error:
            self._record_activity(f"EXPORT FAILED | {fmt}")
        else:
            suffix = f" | {count} records" if count is not None else ""
            self._record_activity(f"EXPORT DONE | {fmt}{suffix}")

    def refresh(self, jobs: list[ScrapingJob]):
        self._jobs = jobs
        self._refresh_stats()
        self._refresh_job_list()

    def load_summary(self, total_records: int, total_emails: int, total_websites: int):
        self._saved_summary = (total_records, total_emails, total_websites)
        self._refresh_stats()

    def _totals(self):
        if not self._jobs and any(self._saved_summary):
            return self._saved_summary[0], self._saved_summary[1], self._saved_summary[2], 0, 0, 0, 0

        total_leads = sum(j.total_found for j in self._jobs)
        total_emails = sum(j.total_emails for j in self._jobs)
        total_websites = sum(j.total_websites for j in self._jobs)
        active_jobs = sum(1 for j in self._jobs if j.status.value in {"running", "paused", "pending"})
        completed_jobs = sum(1 for j in self._jobs if j.status.value == "completed")
        failed_jobs = sum(1 for j in self._jobs if j.status.value in {"failed", "cancelled"})
        total_jobs = len(self._jobs)
        return total_leads, total_emails, total_websites, active_jobs, completed_jobs, failed_jobs, total_jobs

    def refresh(self):
        """Public method to refresh all dashboard components."""
        self._refresh_stats()
        if hasattr(self, 'metric_trial'):
            self.metric_trial._refresh()

    def _refresh_stats(self):
        total_leads, total_emails, total_websites, active_jobs, completed_jobs, failed_jobs, total_jobs = self._totals()

        self.metric_leads.set_value(f"{total_leads:,}")
        self.metric_leads.set_meta("NO DATA" if total_leads == 0 else "READY")

        self.metric_websites.set_value(f"{total_websites:,}")
        self.metric_websites.set_meta("LIVE" if total_websites else "QUEUED")

        email_ratio = int((total_emails / total_leads) * 100) if total_leads else 0
        self.metric_emails.set_value(f"{total_emails:,}")
        self.metric_emails.set_meta(f"{email_ratio}% VALID")

        self.metric_active.set_value(f"{active_jobs}")
        self.metric_active.set_meta("RUNNING" if active_jobs else "IDLE")

        if hasattr(self, 'metric_trial'):
            self.metric_trial._refresh()

        if active_jobs:
            self.heroSubtitle.setText(f"Welcome back. {active_jobs} scraping job(s) in progress.")
        elif total_jobs:
            self.heroSubtitle.setText(f"Your workspace contains {total_jobs} executed jobs.")
        else:
            self.heroSubtitle.setText("Welcome to ZUGZWANG. Start a new scraper to begin.")

    def _refresh_job_list(self):
        while self.jobsFrame.count():
            item = self.jobsFrame.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._jobs:
            empty = QWidget()
            empty_layout = QVBoxLayout(empty)
            empty_layout.setContentsMargins(0, 48, 0, 48)
            empty_layout.setSpacing(12)
            empty_layout.setAlignment(Qt.AlignCenter)

            icon = IconWidget(FluentIcon.SEARCH)
            icon.setFixedSize(24, 24)
            icon.setStyleSheet(f"color: #3A3A3C; border: none;")
            empty_layout.addWidget(icon, 0, Qt.AlignHCenter)

            title = QLabel("NO RECENT JOBS")
            title.setStyleSheet(f"color: #636366; font-family: 'SF Pro Text', '-apple-system', sans-serif; font-size: 12px; font-weight: 600; border: none;")
            empty_layout.addWidget(title, 0, Qt.AlignHCenter)

            self.jobsFrame.addWidget(empty)
            return

        recent = list(reversed(self._jobs[-4:])) # Showing up to 4 recent jobs
        for job in recent:
            self.jobsFrame.addWidget(JobTableRow(job))

    def _refresh_activity(self):
        if not self._activity_items:
            # If no items, ensure there's a placeholder inside and no other elements.
            if not self._activity_labels:
                empty = QLabel("No system activity recorded yet. Logs will stream here during operation.")
                empty.setWordWrap(True)
                empty.setStyleSheet(f"color: {Theme.TEXT_TERTIARY}; font-size: 13px; border: none;")
                self.activityLayout.addWidget(empty)
            return

        # Initialize the fixed UI rows on first data arrival
        if not self._activity_labels:
            # Clear placeholder
            while self.activityLayout.count():
                item = self.activityLayout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            
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
                label.setWordWrap(True)
                label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                label.setStyleSheet(f"color: #8E8E93; font-family: 'SF Mono', 'Menlo', monospace; font-size: 11px; background: transparent; border: none;")

                row_layout.addWidget(dot, 0, Qt.AlignTop)
                row_layout.addWidget(label, 1, Qt.AlignTop)
                
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
