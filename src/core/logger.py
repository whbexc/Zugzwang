"""
ZUGZWANG - Logging System
Structured logging with file rotation and UI log sink support.
"""

from __future__ import annotations
import logging
import logging.handlers
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from .config import get_logs_dir

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Module-level log sink for forwarding to UI
_ui_log_sink: Optional[Callable[[str, str, str], None]] = None


def register_ui_log_sink(sink: Callable[[str, str, str], None]) -> None:
    """Register a callable that receives (level, logger_name, message) for UI display."""
    global _ui_log_sink
    _ui_log_sink = sink


import re
from .events import event_bus

class UISinkHandler(logging.Handler):
    """Forwards log records to the event bus and registered UI sink."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
            
            # Simple [job-id] extraction for standard scraper logs
            job_id = ""
            if msg.startswith("["):
                end_sq = msg.find("]")
                if end_sq != -1:
                    potential_id = msg[1:end_sq]
                    if len(potential_id) >= 8: # Basic check for UUID or similar
                        job_id = potential_id

            # Emit to event bus for Runtime Monitor / Dashboard
            event_bus.emit(
                event_bus.JOB_LOG,
                job_id=job_id,
                message=msg,
                level=record.levelname
            )

            # Also forward to legacy sink if registered (LogViewerPage)
            if _ui_log_sink:
                _ui_log_sink(record.levelname, record.name, msg)
        except Exception:
            pass


def setup_logging(level: str = "INFO") -> None:
    """Configure application-wide logging."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(numeric_level)

    # Clear existing handlers
    root.handlers.clear()

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    console.setLevel(numeric_level)
    root.addHandler(console)

    # Rotating file handler
    log_file = get_logs_dir() / f"zugzwang_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=7,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(numeric_level)
    root.addHandler(file_handler)

    # UI sink handler
    ui_handler = UISinkHandler()
    ui_handler.setFormatter(formatter)
    ui_handler.setLevel(numeric_level)
    root.addHandler(ui_handler)

    # Silence noisy third-party loggers
    for noisy in ["playwright", "asyncio", "urllib3", "httpx"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
