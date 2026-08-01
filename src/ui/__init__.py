"""ZUGZWANG - UI package."""
from .main_window import MainWindow
from .email_sender_page import EmailSenderPage
from .dashboard_page import DashboardPage
from .search_page import SearchPage
from .results_page import ResultsPage
from .edit_page import EditPage
from .monitor_page import MonitorPage
from .settings_page import SettingsPage
from .log_viewer_page import LogViewerPage

__all__ = [
    "MainWindow",
    "EmailSenderPage",
    "DashboardPage",
    "SearchPage",
    "ResultsPage",
    "EditPage",
    "MonitorPage",
    "SettingsPage",
    "LogViewerPage",
]
