"""
ZUGZWANG - Event Bus
Thread-safe pub/sub event system for decoupled communication
between scraping services and the UI layer.
"""

from __future__ import annotations
import threading
from collections import defaultdict
from typing import Any, Callable


class EventBus:
    """
    Simple, thread-safe publish/subscribe event bus.
    Services emit events; UI components subscribe and react.
    """

    # Canonical event names
    JOB_STARTED = "job.started"
    JOB_PROGRESS = "job.progress"
    JOB_RESULT = "job.result"
    JOB_COMPLETED = "job.completed"
    JOB_FAILED = "job.failed"
    JOB_PAUSED = "job.paused"
    JOB_CANCELLED = "job.cancelled"
    JOB_LOG = "job.log"
    CAPTCHA_CHALLENGE = "captcha.challenge"
    CAPTCHA_INTERACTION = "captcha.interaction"
    SOLVER_REQUESTED = "solver.requested"
    SOLVER_COMPLETED = "solver.completed"
    TRIAL_LIMIT_REACHED = "trial.limit_reached"

    EXPORT_STARTED = "export.started"
    EXPORT_COMPLETED = "export.completed"
    EXPORT_FAILED = "export.failed"

    SETTINGS_CHANGED = "settings.changed"
    DB_UPDATED = "db.updated"

    def __init__(self):
        self._listeners: dict[str, list[Callable]] = defaultdict(list)
        self._lock = threading.Lock()

    def subscribe(self, event: str, callback: Callable[..., Any]) -> None:
        with self._lock:
            self._listeners[event].append(callback)

    def unsubscribe(self, event: str, callback: Callable[..., Any]) -> None:
        with self._lock:
            try:
                self._listeners[event].remove(callback)
            except ValueError:
                pass

    def emit(self, event: str, **data: Any) -> None:
        with self._lock:
            callbacks = list(self._listeners.get(event, []))
        for cb in callbacks:
            try:
                cb(**data)
            except Exception as e:
                pass  # Individual handler failures must not propagate


# Global event bus instance
event_bus = EventBus()
