"""
ZUGZWANG - Logging System
Structured logging with file rotation and UI log sink support.
"""

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

_NOISY_INFO_LOGGERS = (
    "src.services.maps_scraper",
    "src.services.website_crawler",
    "src.services.jobsuche_scraper",
    "src.services.ausbildung_scraper",
    "src.services.aubiplus_scraper",
    "src.services.azubiyo_scraper",
    "src.services.browser",
)


def register_ui_log_sink(sink: Callable[[str, str, str], None]) -> None:
    """Register a callable that receives (level, logger_name, message) for UI display."""
    global _ui_log_sink
    _ui_log_sink = sink


import re
from .events import event_bus
import time
import html as html_lib

# Performance: Pre-compiled regex for log formatting in background
_URL_RE = re.compile(r"(https?://[^\s]+)")

class UISinkHandler(logging.Handler):
    """Forwards log records to the event bus and registered UI sink."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
            
            # Simple [job-id] extraction for standard scraper logs
            job_id = ""
            display_msg = msg
            if msg.startswith("["):
                end_sq = msg.find("]")
                if end_sq != -1:
                    potential_id = msg[1:end_sq]
                    if len(potential_id) >= 8:
                        job_id = potential_id
                        display_msg = msg[end_sq+1:].strip()

            # Pre-format HTML in the background thread to offload UI thread
            safe_msg = html_lib.escape(display_msg)
            
            # Basic URL linking
            color_blue = "#0A84FF"
            linked_msg = _URL_RE.sub(fr'<a href="\1" style="color: {color_blue}; text-decoration: none;">\1</a>', safe_msg)
            
            level_colors = {
                "ERROR": "#FF453A",
                "WARNING": "#FF9F0A",
                "INFO": "#FFFFFF", # Theme default
                "DEBUG": "#8E8E93"
            }
            color = level_colors.get(record.levelname, "#FFFFFF")
            
            timestamp = time.strftime("%H:%M:%S")
            html_msg = (
                f'<div style="margin-bottom: 2px;">'
                f'<span style="color:rgba(255,255,255,0.25); font-weight: 600;">{timestamp}</span> '
                f'<span style="color:{color};">{linked_msg}</span>'
                f'</div>'
            )

            summary = display_msg.strip()
            if summary.startswith("===") and summary.endswith("==="):
                summary = summary.strip("= ").strip()
            if len(summary) > 72:
                summary = summary[:69].rstrip() + "..."

            # Emit to event bus for Runtime Monitor
            event_bus.emit(
                event_bus.JOB_LOG,
                job_id=job_id,
                message=msg, # Backwards compatibility
                html=html_msg,
                summary=summary,
                level=record.levelname
            )

            # Also forward to legacy sink if registered (LogViewerPage)
            if _ui_log_sink:
                _ui_log_sink(record.levelname, record.name, msg)
        except Exception:
            pass


class HighVolumeScrapeFilter(logging.Filter):
    """Suppress INFO/DEBUG chatter from scraper hot paths."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno >= logging.WARNING:
            return True
        return not record.name.startswith(_NOISY_INFO_LOGGERS)


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
    console.addFilter(HighVolumeScrapeFilter())
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
    file_handler.addFilter(HighVolumeScrapeFilter())
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
