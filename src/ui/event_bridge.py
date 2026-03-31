"""
ZUGZWANG - Thread-Safe Event Bridge
Bridges the pure-python event_bus to Qt Signals to ensure
safe UI updates from background scraper threads.
"""

from PySide6.QtCore import QObject, Signal
from ..core.events import event_bus
from ..core.logger import get_logger

logger = get_logger(__name__)

class EventBridge(QObject):
    """
    Singleton QObject that subscribes to event_bus and emits Qt Signals.
    UI components should connect to these signals for thread-safe updates.
    """
    # Job Lifecycle
    job_started = Signal(str, object)   # job_id, config
    job_progress = Signal(dict)         # stats dict
    job_completed = Signal(str, int, int) # job_id, results, emails
    job_failed = Signal(str, str)       # job_id, error
    job_cancelled = Signal(str)         # job_id
    job_paused = Signal(str)            # job_id
    job_result = Signal(object)         # LeadRecord
    job_log = Signal(str, str, str)     # job_id, level, message
    trial_limit_reached = Signal(str)   # job_id

    # System Events
    db_updated = Signal(list)           # new_records
    export_completed = Signal(str, str, int) # format, path, count
    export_failed = Signal(str, str)    # format, error

    # Bridge/HITL
    captcha_challenge = Signal(str, bytes) # job_id, image_bytes
    solver_requested = Signal(str, str, list, str) # job_id, url, cookies, user_agent

    _instance = None

    def __init__(self):
        super().__init__()
        self._setup_subscribers()

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = EventBridge()
        return cls._instance

    def _setup_subscribers(self):
        # Job Lifecycle
        event_bus.subscribe(event_bus.JOB_STARTED, self._on_job_started)
        event_bus.subscribe(event_bus.JOB_PROGRESS, self._on_job_progress)
        event_bus.subscribe(event_bus.JOB_COMPLETED, self._on_job_completed)
        event_bus.subscribe(event_bus.JOB_FAILED, self._on_job_failed)
        event_bus.subscribe(event_bus.JOB_CANCELLED, self._on_job_cancelled)
        event_bus.subscribe(event_bus.JOB_PAUSED, self._on_job_paused)
        event_bus.subscribe(event_bus.JOB_RESULT, self._on_job_result)
        event_bus.subscribe(event_bus.JOB_LOG, self._on_job_log)

        # System
        event_bus.subscribe(event_bus.DB_UPDATED, self._on_db_updated)
        event_bus.subscribe(event_bus.EXPORT_COMPLETED, self._on_export_completed)
        event_bus.subscribe(event_bus.EXPORT_FAILED, self._on_export_failed)

        # HITL
        event_bus.subscribe(event_bus.CAPTCHA_CHALLENGE, self._on_captcha_challenge)
        event_bus.subscribe(event_bus.SOLVER_REQUESTED, self._on_solver_requested)
        event_bus.subscribe(event_bus.TRIAL_LIMIT_REACHED, self._on_trial_limit_reached)

    # ── Internal Callbacks (running in background thread) ──

    def _on_job_started(self, job_id: str, config=None, **k):
        self.job_started.emit(job_id, config)

    def _on_job_progress(self, **data):
        self.job_progress.emit(data)

    def _on_job_completed(self, job_id: str, total_found: int = 0, total_emails: int = 0, **k):
        self.job_completed.emit(job_id, total_found, total_emails)

    def _on_job_failed(self, job_id: str, error: str, **k):
        self.job_failed.emit(job_id, error)

    def _on_job_cancelled(self, job_id: str, **k):
        self.job_cancelled.emit(job_id)

    def _on_job_paused(self, job_id: str, **k):
        self.job_paused.emit(job_id)

    def _on_job_result(self, record, **k):
        self.job_result.emit(record)

    def _on_job_log(self, job_id: str, level: str, message: str, **k):
        self.job_log.emit(job_id, level, message)

    def _on_db_updated(self, records: list, **k):
        self.db_updated.emit(records)

    def _on_export_completed(self, format: str, path: str, count: int = 0, **k):
        self.export_completed.emit(format, path, count)

    def _on_export_failed(self, format: str, error: str, **k):
        self.export_failed.emit(format, error)

    def _on_captcha_challenge(self, job_id: str, image: bytes, **k):
        self.captcha_challenge.emit(job_id, image)

    def _on_solver_requested(self, job_id: str, url: str, cookies: list, user_agent: str = "", **k):
        self.solver_requested.emit(job_id, url, cookies, user_agent)

    def _on_trial_limit_reached(self, job_id: str, **k):
        self.trial_limit_reached.emit(job_id)

# Convenience access
event_bridge = EventBridge.instance()
