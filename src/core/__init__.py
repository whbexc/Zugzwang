"""ZUGZWANG - Core package."""
from .models import LeadRecord, SearchConfig, ScrapingJob, AppSettings, SourceType, ScrapingStatus, EmailSource
from .config import ConfigManager, config_manager, get_app_data_dir, get_data_dir, get_logs_dir, get_screenshots_dir
from .logger import setup_logging, get_logger, register_ui_log_sink
from .events import EventBus, event_bus

__all__ = [
    "LeadRecord", "SearchConfig", "ScrapingJob", "AppSettings",
    "SourceType", "ScrapingStatus", "EmailSource",
    "ConfigManager", "config_manager",
    "get_app_data_dir", "get_data_dir", "get_logs_dir", "get_screenshots_dir",
    "setup_logging", "get_logger", "register_ui_log_sink",
    "EventBus", "event_bus",
]
