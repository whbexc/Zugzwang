"""
ZUGZWANG - Activity Log Viewer
Terminal × macOS Console aesthetic — monospace precision, surgical clarity.
"""

from __future__ import annotations

import queue
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QWidget, QTextBrowser,
    QFileDialog, QLabel, QSizePolicy
)
from PySide6.QtGui import QColor

from qfluentwidgets import (
    SearchLineEdit, ComboBox, PushButton,
    LineEdit, InfoBar
)

from ..core.logger import register_ui_log_sink
from ..core.i18n import get_language, tr
from ..core.config import config_manager
from .theme import Theme


# ── Level badge palette ───────────────────────────────────────────────────────
_LEVEL_CFG = {
    "INFO":     {"color": "#0A84FF", "bg": "rgba(10,132,255,0.12)"},
    "DEBUG":    {"color": "#8E8E93", "bg": "rgba(142,142,147,0.10)"},
    "WARNING":  {"color": "#FF9F0A", "bg": "rgba(255,159,10,0.12)"},
    "WARN":     {"color": "#FF9F0A", "bg": "rgba(255,159,10,0.12)"},
    "ERROR":    {"color": "#FF453A", "bg": "rgba(255,69,58,0.12)"},
    "CRITICAL": {"color": "#FF453A", "bg": "rgba(255,69,58,0.12)"},
}

_SCROLLBAR_QSS = """
    QScrollBar:vertical {
        border: none;
        background: transparent;
        width: 4px;
        margin: 0;
    }
    QScrollBar::handle:vertical {
        background: #3A3A3C;
        border-radius: 2px;
        min-height: 20px;
    }
    QScrollBar::handle:vertical:hover { background: #636366; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
"""


class LogViewerPage(QWidget):
    """Activity Logs — Terminal × macOS Console aesthetic."""

    def __init__(self):
        super().__init__()
        self._all_logs: list = []  # tuples: (dt, timestamp, level, name, message)
        self._pending_logs: queue.Queue = queue.Queue()
        self._session_start: datetime = datetime.now()  # for LAST SESSION filter
        self._language = get_language(config_manager.settings.app_language)
        self._build_ui()
        self._load_initial_logs() # Load from file first
        register_ui_log_sink(self._receive_log)

        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._drain_log_queue)
        self._timer.start()

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(0)

        # ── 1. Page title ────────────────────────────────────────────────────
        title_box = QWidget()
        tl = QVBoxLayout(title_box); tl.setContentsMargins(0, 0, 0, 14)
        title = QLabel(tr("logs.title", self._language))
        title.setStyleSheet(
            "color: white;"
            "font-family: 'PT Root UI', sans-serif;"
            "font-size: 28px; font-weight: 600; background: transparent;"
        )
        tl.addWidget(title)
        root.addWidget(title_box, 0)

        # ── 2. Controls Row ──────────────────────────────────────────────────
        ctrl_row = QHBoxLayout(); ctrl_row.setSpacing(8); ctrl_row.setContentsMargins(0, 0, 0, 12)

        self._search_input = SearchLineEdit()
        self._search_input.setPlaceholderText(tr("logs.placeholder.search", self._language))
        self._search_input.setFixedWidth(320)
        self._search_input.setFixedHeight(36)
        self._search_input.textChanged.connect(self._apply_filter)
        self._search_input.setStyleSheet("""
            SearchLineEdit {
                background: #1C1C1E;
                border: 1px solid #3A3A3C;
                border-radius: 8px;
                color: white;
                font-family: 'PT Root UI', sans-serif;
                font-size: 13px;
                padding: 0 10px;
            }
            SearchLineEdit:focus { border-color: #0A84FF; }
        """)
        ctrl_row.addWidget(self._search_input)

        self._level_filter = ComboBox()
        self._level_filter.addItems([
            tr("logs.filter.all_levels", self._language), 
            "DEBUG", "INFO", "WARNING", "ERROR"
        ])
        self._level_filter.currentIndexChanged.connect(self._apply_filter)
        self._level_filter.setFixedHeight(36)
        self._level_filter.setFixedWidth(148)
        self._level_filter.setStyleSheet("""
            ComboBox {
                background: #2C2C2E;
                border: 1px solid #3A3A3C;
                border-radius: 8px;
                color: white;
                font-family: 'PT Root UI', sans-serif;
                font-size: 13px;
                padding: 0 10px;
            }
            ComboBox:focus { border-color: #0A84FF; }
        """)
        ctrl_row.addWidget(self._level_filter)

        self._time_filter = ComboBox()
        self._time_filter.addItems([
            tr("logs.filter.all_time", self._language),
            tr("logs.filter.last_hour", self._language),
            tr("logs.filter.today", self._language),
            tr("logs.filter.last_7_days", self._language),
            tr("logs.filter.last_30_days", self._language),
            tr("logs.filter.last_session", self._language)
        ])
        self._time_filter.currentIndexChanged.connect(self._apply_filter)
        self._time_filter.setFixedHeight(36)
        self._time_filter.setFixedWidth(170)  # Wider to fit 'LAST SESSION'
        self._time_filter.setStyleSheet("""
            ComboBox {
                background: #2C2C2E;
                border: 1px solid #3A3A3C;
                border-radius: 8px;
                color: white;
                font-family: 'PT Root UI', sans-serif;
                font-size: 13px;
                padding: 0 10px;
            }
            ComboBox:focus { border-color: #0A84FF; }
        """)
        ctrl_row.addWidget(self._time_filter)
        ctrl_row.addStretch()

        for label, key, handler, danger in [
            ("EXPORT",    "logs.button.export", self._export_logs, False),
            ("CLEAR ALL", "logs.button.clear",  self._clear,       True),
        ]:
            btn = PushButton(tr(key, self._language))
            btn.setFixedHeight(36)
            if danger:
                btn.setStyleSheet(Theme.zugzwang_danger_button())
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background: #2C2C2E; border: 1px solid #3A3A3C; border-radius: 8px;
                        color: #D1D1D6;
                        font-family: 'PT Root UI', sans-serif;
                        font-weight: 600; font-size: 13px;
                        letter-spacing: 1.2px; text-transform: uppercase;
                        padding: 0 16px;
                    }
                    QPushButton:hover { background: #333333; color: white; }
                """)
            btn.clicked.connect(handler)
            ctrl_row.addWidget(btn)
            if label == "EXPORT":
                self._export_btn = btn
            else:
                self._clear_btn = btn

        root.addLayout(ctrl_row)

        # ── 3. Log Panel ─────────────────────────────────────────────────────
        panel = QFrame()
        panel.setObjectName("LogPanel")
        panel.setStyleSheet("""
            QFrame#LogPanel {
                background: #1A1A1A;
                border-radius: 10px;
                border: 1px solid #2C2C2C;
            }
        """)
        panel_vl = QVBoxLayout(panel)
        panel_vl.setContentsMargins(8, 8, 8, 8)
        panel_vl.setSpacing(8)

        # Tab strip + entry count + live dot
        tab_row = QHBoxLayout(); tab_row.setSpacing(8); tab_row.setContentsMargins(4, 4, 4, 0)

        pill = QLabel(tr("logs.section.live", self._language))
        pill.setStyleSheet("""
            color: #1C1C1E;
            background: white;
            border-radius: 6px;
            font-family: 'PT Root UI', sans-serif;
            font-weight: 600; font-size: 12px;
            padding: 3px 10px;
        """)
        tab_row.addWidget(pill)

        self._entries_label = QLabel(tr("logs.badge.entries", self._language).format(count=0))
        self._entries_label.setMinimumWidth(90)  # Prevent truncation
        self._entries_label.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self._entries_label.setStyleSheet("""
            color: #8E8E93;
            background: #2C2C2E;
            border: 1px solid #3A3A3C;
            border-radius: 6px;
            font-family: 'SF Mono', 'Cascadia Code', monospace;
            font-size: 11px;
            font-weight: 600;
            padding: 3px 10px;
            letter-spacing: 0.6px;
        """)
        tab_row.addWidget(self._entries_label)
        tab_row.addStretch()

        # Pulsing green live dot
        self._live_dot = QLabel("●")
        self._live_dot.setStyleSheet("color: #30D158; font-size: 10px; background: transparent;")
        tab_row.addWidget(self._live_dot)

        live_label = QLabel(tr("logs.status.live", self._language))
        live_label.setStyleSheet(
            "color: #30D158; font-size: 10px; font-weight: 600;"
            "font-family: 'PT Root UI', monospace; background: transparent;"
        )
        tab_row.addWidget(live_label)
        panel_vl.addLayout(tab_row)

        # Divider
        div = QFrame(); div.setFixedHeight(1)
        div.setStyleSheet("background: #2C2C2E; border: none;")
        panel_vl.addWidget(div)

        # Log browser
        self._log_view = QTextBrowser()
        self._log_view.setReadOnly(True)
        self._log_view.setOpenExternalLinks(False)
        self._log_view.setStyleSheet("""
            QTextBrowser {
                background: transparent;
                border: none;
                font-family: 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
                font-size: 12px;
                line-height: 1.7;
                color: #D1D1D6;
                padding: 4px 8px;
            }
        """ + _SCROLLBAR_QSS)
        panel_vl.addWidget(self._log_view, 1)

        root.addWidget(panel, 1)

        # Start pulsing animation
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(800)
        self._pulse_timer.timeout.connect(self._pulse_dot)
        self._pulse_timer.start()
        self._pulse_state = True

    # ── Pulse animation ───────────────────────────────────────────────────────

    def _pulse_dot(self):
        self._pulse_state = not self._pulse_state
        color = "#30D158" if self._pulse_state else "#1D5C33"
        self._live_dot.setStyleSheet(f"color: {color}; font-size: 10px; background: transparent;")

    # ── Log pipeline ──────────────────────────────────────────────────────────

    def header_action_widgets(self) -> list[QWidget]:
        return []

    def _receive_log(self, level: str, name: str, message: str) -> None:
        now = datetime.now()
        timestamp = now.strftime("%H:%M:%S")
        self._pending_logs.put((now, timestamp, str(level), str(name), str(message)))

    def _drain_log_queue(self) -> None:
        changed = False
        while not self._pending_logs.empty():
            try:
                item = self._pending_logs.get_nowait()
            except queue.Empty:
                break
            self._all_logs.append(item)
            changed = True
        if changed:
            self._apply_filter()

    def _time_cutoff(self):
        """Return cutoff datetime or None for ALL TIME."""
        from datetime import timedelta
        idx = self._time_filter.currentIndex()
        now = datetime.now()
        if idx == 1: # LAST HOUR
            return now - timedelta(hours=1)
        elif idx == 2: # TODAY
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif idx == 3: # LAST 7 DAYS
            return now - timedelta(days=7)
        elif idx == 4: # LAST 30 DAYS
            return now - timedelta(days=30)
        elif idx == 5: # LAST SESSION
            return self._session_start
        return None  # ALL TIME

    def _load_initial_logs(self):
        """Read existing logs from today's log file."""
        from ..core.config import get_logs_dir
        log_file = get_logs_dir() / f"zugzwang_{datetime.now().strftime('%Y%m%d')}.log"
        if not log_file.exists():
            return
            
        try:
            content = log_file.read_text(encoding="utf-8")
            lines = content.splitlines()[-200:] # Last 200 lines
            for line in lines:
                # Format: 2026-03-30 02:21:34 | INFO     | leadhunter.core.config         | message
                parts = line.split("|", 3)
                if len(parts) == 4:
                    ts_str = parts[0].strip()
                    lvl = parts[1].strip()
                    nm = parts[2].strip()
                    msg = parts[3].strip()
                    
                    try:
                        dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                        timestamp = dt.strftime("%H:%M:%S")
                        self._all_logs.append((dt, timestamp, lvl, nm, msg))
                    except:
                        continue
            self._apply_filter()
        except Exception:
            pass

    def _apply_filter(self):
        self._log_view.clear()
        search   = self._search_input.text().strip().lower()
        selected = self._selected_level()
        cutoff   = self._time_cutoff()
        visible_count = 0

        if not self._all_logs:
            self._log_view.setHtml(self._empty_state_html())
            self._entries_label.setText(tr("logs.badge.entries", self._language).format(count=0))
            return

        html_blocks = []
        for entry in self._all_logs:
            dt, timestamp, level, name, message = entry
            if cutoff and dt < cutoff:
                continue
            haystack = " ".join([timestamp, level, name, message]).lower()
            if selected and level.upper() != selected:
                continue
            if search and search not in haystack:
                continue
            visible_count += 1
            html_blocks.append(self._format_entry(timestamp, level, name, message))

        if not html_blocks:
            self._log_view.setHtml(self._empty_state_html())
        else:
            self._log_view.setHtml(
                '<div style="font-family: SF Mono, Cascadia Code, Consolas, monospace; '
                'font-size: 12px; line-height: 1.7;">'
                + "".join(html_blocks) + "</div>"
            )
        self._entries_label.setText(tr("logs.badge.entries", self._language).format(count=visible_count))
        self._scroll_to_bottom()

    def _selected_level(self) -> str:
        idx = self._level_filter.currentIndex()
        if idx == 0: return ""
        return self._level_filter.currentText().strip().upper()

    def _format_entry(self, timestamp: str, level: str, name: str, message: str) -> str:
        cfg = _LEVEL_CFG.get(level.upper(), {"color": "#D1D1D6", "bg": "rgba(255,255,255,0.05)"})
        safe_msg  = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        safe_name = name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        lvl_badge = (
            f'<span style="color:{cfg["color"]}; background:{cfg["bg"]}; '
            f'border-radius:4px; padding:1px 5px; font-size:10px; font-weight:700;">'
            f'{level.upper()}</span>'
        )
        return (
            '<div style="padding:2px 0; white-space:pre-wrap;">'
            f'<span style="color:#636366;">{timestamp}</span>'
            f'&nbsp;&nbsp;{lvl_badge}&nbsp;&nbsp;'
            f'<span style="color:#48484A;">[{safe_name}]</span>&nbsp;'
            f'<span style="color:#D1D1D6;">{safe_msg}</span>'
            "</div>"
        )

    def _empty_state_html(self) -> str:
        return """
        <div style="display:flex; flex-direction:column; align-items:center;
                    justify-content:center; height:200px; text-align:center;
                    padding-top: 60px;">
            <div style="font-size:32px; color:#3A3A3C; margin-bottom:10px;">⌘</div>
            <div style="color:#48484A; font-family:'PT Root UI',sans-serif; font-size:13px;">
                {tr("logs.empty.title", self._language)}
            </div>
            <div style="color:#3A3A3C; font-family:'PT Root UI',sans-serif; font-size:11px;
                        margin-top:4px;">
                {tr("logs.empty.subtitle", self._language)}
            </div>
        </div>
        """

    def _clear(self):
        self._all_logs.clear()
        self._log_view.setHtml(self._empty_state_html())
        self._entries_label.setText(tr("logs.badge.entries", self._language).format(count=0))

    def _export_logs(self):
        if not self._all_logs:
            InfoBar.warning("No Logs", "No logs available to export.", parent=self)
            return
        default_name = f"logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Logs", str(Path.home() / default_name), "Text Files (*.txt)"
        )
        if path:
            lines = [f"{ts} | {lv} | {nm} | {msg}" for ts, lv, nm, msg in self._all_logs]
            Path(path).write_text("\n".join(lines), encoding="utf-8")

    def _scroll_to_bottom(self):
        scrollbar = self._log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
