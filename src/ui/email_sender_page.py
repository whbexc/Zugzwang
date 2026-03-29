"""
ZUGZWANG - Email Sender Page
Fully functional SMTP email sender with threading, attachments, persistence, and progress tracking.
Aesthetic 3.0: Senior Grade macOS Design.
"""

from __future__ import annotations

import os
import smtplib
import ssl
import time
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFrame, QLabel,
    QLineEdit, QTextEdit, QFileDialog, QSizePolicy, QStackedWidget, QTextBrowser,
    QPlainTextEdit, QScrollArea
)
from .components import StatCard, SectionCard, MacSwitch
from qfluentwidgets import (
    InfoBadge, ProgressBar,
    PushButton, PrimaryPushButton, TransparentPushButton, ToolButton,
    ElevatedCardWidget, FluentIcon, LineEdit, PlainTextEdit,
    ScrollArea
)

from ..core.events import event_bus
from .theme import Theme
from ..core.config import config_manager


class _SendSignals(QObject):
    log = Signal(str, str)        # message, level
    progress = Signal(int, int)   # current, total
    finished = Signal(int, int, bool) # sent, failed, was_aborted
    error = Signal(str)           # global error


class EmailSenderPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._attachments: list[str] = []
        self._successful_emails: list[str] = []
        self._sending = False
        self._stop_requested = False
        self._active_server = None
        self._signals = _SendSignals()
        self._isPreview = False
        
        self._signals.log.connect(self._on_log)
        self._signals.progress.connect(self._on_progress)
        self._signals.finished.connect(self._on_finished)
        self._signals.error.connect(self._on_error)
        
        self._init_widgets()
        self._build_ui()
        self._restore_fields()
        self._connect_buttons()

    def import_emails(self, emails: list[str]):
        """Populates the recipient list from external sources (e.g., Results library)."""
        if not emails:
            return
        
        # Canonicalize and join
        text = "\n".join(emails)
        self._recipients_text.setPlainText(text)
        self._on_recipients_changed() # Update internal counts

    def _init_widgets(self):
        # Step 1 Widgets
        self._smtp_host = LineEdit(); self._smtp_host.setPlaceholderText("smtp.gmail.com")
        self._smtp_port = LineEdit(); self._smtp_port.setText("587"); self._smtp_port.setFixedWidth(70)
        self._smtp_user = LineEdit(); self._smtp_user.setPlaceholderText("user@domain.com")
        self._smtp_pass = LineEdit(); self._smtp_pass.setPlaceholderText("••••••••"); self._smtp_pass.setEchoMode(QLineEdit.Password)
        
        self._auth_switch = MacSwitch()
        self._ssl_switch = MacSwitch()
        self._tls_switch = MacSwitch()
        
        # Step 2 Widgets
        self._from_name = LineEdit(); self._from_name.setPlaceholderText("John Doe")
        self._reply_to = LineEdit(); self._reply_to.setPlaceholderText("reply@domain.com")
        self._subject = LineEdit(); self._subject.setPlaceholderText("Broadcast Subject Line")
        
        self._body_stack = QStackedWidget()
        self._body_stack.setMinimumHeight(150)
        self._body_text = PlainTextEdit()
        self._body_text.setPlaceholderText("Compose your message here...")
        self._body_stack.addWidget(self._body_text)
        
        self._body_preview = QTextBrowser()
        self._body_preview.setOpenExternalLinks(True)
        self._body_stack.addWidget(self._body_preview)
        
        self._type_toggle = MacSwitch()
        self._preview_btn = ToolButton(FluentIcon.VIEW)
        self._attach_btn = ToolButton(FluentIcon.ADD)
        self._attach_clear_btn = ToolButton(FluentIcon.DELETE)
        self._attach_badge = QLabel("0 FILES")
        
        # Step 3 Widgets
        self._btn_dedup = PushButton("CLEAN")
        self._btn_dedup.setStyleSheet(Theme.secondary_button())
        self._rec_count = QLabel("0 EMAIL(S)")
        self._recipients_text = PlainTextEdit()
        self._recipients_text.setMinimumHeight(100)
        self._recipients_text.setPlaceholderText("recipients@example.com (one per line)")
        
        self._status_log = QTextEdit()
        self._status_log.setReadOnly(True)
        self._status_log.setText("Awaiting manual broadcast...")
        
        self._interval_input = LineEdit(); self._interval_input.setText("15")
        self._interval_input.setFixedWidth(70)
        
        self._batch_size = LineEdit(); self._batch_size.setText("100")
        self._batch_size.setFixedWidth(70)
        
        self._btn_purge_sent = PushButton("PURGE SENT")
        
        self._btn_send_one = PushButton("SEND ONE")
        self._btn_stop = PushButton("STOP")
        self._btn_stop.setEnabled(False)
        self._btn_export = PushButton("EXPORT SENT")
        self._btn_send_all = PushButton("SEND ALL")
        self._btn_clear_data = PushButton("CLEAR ALL")

    def _build_ui(self):
        self.setObjectName("emailPage")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        host = QWidget()
        host.setObjectName("emailPageHost")
        host.setStyleSheet("QWidget#emailPageHost { background: #1C1C1E; }")
        root.addWidget(host)
        
        body = QVBoxLayout(host)
        body.setContentsMargins(24, 16, 24, 16)
        body.setSpacing(10)

        # ── Header Section ───────────────────────────────────────────────────
        header_widget = QWidget()
        header_widget.setFixedHeight(52)
        header_h = QHBoxLayout(header_widget)
        header_h.setContentsMargins(0, 0, 0, 0)
        header_h.setSpacing(12)
        
        self._page_title = QLabel("ZUGZWANG Broadcast")
        self._page_title.setStyleSheet("color: white; font-family: 'PT Root UI', sans-serif; font-weight: 600; font-size: 28px;")
        header_h.addWidget(self._page_title)
        
        self._status_badge = QLabel("READY")
        self._status_badge.setStyleSheet("background: #1C3A1C; border: 1px solid #30D158; color: #30D158; font-family: 'PT Root UI', sans-serif; font-weight: 500; font-size: 10px; letter-spacing: 1.4px; border-radius: 6px; padding: 3px 10px;")
        header_h.addWidget(self._status_badge, 0, Qt.AlignVCenter)
        
        header_h.addStretch(1)

        self._btn_send_one.setFixedHeight(36)
        self._btn_send_one.setCursor(Qt.PointingHandCursor)
        self._btn_send_one.setStyleSheet(Theme.zugzwang_success_button())
        header_h.addWidget(self._btn_send_one)
        
        self._btn_stop.setFixedHeight(36)
        self._btn_stop.setCursor(Qt.PointingHandCursor)
        self._btn_stop.setStyleSheet(Theme.secondary_button())
        header_h.addWidget(self._btn_stop)

        self._btn_clear_data.setFixedHeight(36)
        self._btn_clear_data.setStyleSheet(Theme.zugzwang_danger_button())
        self._btn_clear_data.clicked.connect(self._clear_all_data)
        header_h.addWidget(self._btn_clear_data)

        self._btn_send_all.setFixedHeight(36)
        self._btn_send_all.setCursor(Qt.PointingHandCursor)
        self._btn_send_all.setStyleSheet(Theme.zugzwang_primary_button())
        header_h.addWidget(self._btn_send_all)

        body.addWidget(header_widget)
        

        # ── Step 1: Identity & Credentials ───────────────────────────────────
        body.addWidget(self._step_card("1", "ZUGZWANG Identity", self._build_identity_section(), compact=True))

        # ── Main Side-by-Side Area ──────────────────────────────────────────
        workflow_h = QHBoxLayout()
        workflow_h.setSpacing(10)
        
        self._card2 = self._step_card("2", "Audience & Payload", self._build_payload_section())
        self._card3 = self._step_card("3", "Broadcast Monitor", self._build_monitor_section())
        
        workflow_h.addWidget(self._card2, 55)
        workflow_h.addWidget(self._card3, 45)
        body.addLayout(workflow_h, 1)





    def _step_card(self, num: str, title: str, content: QWidget, compact: bool = False) -> QFrame:
        card = QFrame()
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        card.setMinimumHeight(0)
        card.setStyleSheet("QFrame { background: #2C2C2E; border-radius: 14px; border: none; }")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(8)

        hdr = QHBoxLayout()
        hdr.setSpacing(12)
        badge = QLabel(num)
        badge.setFixedSize(20, 20)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet("color: white; background: #0A84FF; border-radius: 10px; font-family: 'PT Root UI', sans-serif; font-weight: 700; font-size: 11px;")
        hdr.addWidget(badge)

        ttl = QLabel(title.upper())
        ttl.setStyleSheet("color: #8E8E93; font-family: 'PT Root UI', sans-serif; font-weight: 600; font-size: 11px; letter-spacing: 1.6px; background: transparent; border: none;")
        hdr.addWidget(ttl)
        hdr.addStretch(1)
        layout.addLayout(hdr)

        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet("background: #3A3A3C; border: none;")
        layout.addWidget(div)

        layout.addWidget(content, 1 if not compact else 0)
        return card

    def _build_identity_section(self) -> QWidget:
        container = QWidget()
        container.setFixedHeight(90)
        container.setStyleSheet("QWidget { background: transparent; border: none; }")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 5, 0, 0)
        layout.setSpacing(10)

        grid = QGridLayout()
        grid.setSpacing(10)
        
        self._style_input(self._smtp_host)
        self._style_input(self._smtp_port)
        self._style_input(self._smtp_user)
        self._style_input(self._smtp_pass)
        
        grid.addWidget(self._field_label("SMTP"), 0, 0)
        grid.addWidget(self._field_label("PORT"), 0, 1)
        grid.addWidget(self._field_label("USERNAME"), 0, 2)
        grid.addWidget(self._field_label("SECURITY TOKEN"), 0, 3)
        
        grid.addWidget(self._smtp_host, 1, 0)
        grid.addWidget(self._smtp_port, 1, 1)
        grid.addWidget(self._smtp_user, 1, 2)
        grid.addWidget(self._smtp_pass, 1, 3)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(2, 3)
        grid.setColumnStretch(3, 3)
        
        layout.addLayout(grid, 1)

        v_opt = QVBoxLayout()
        v_opt.setSpacing(14)
        v_opt.addLayout(self._make_switch_row("AUTHENTICATE", self._auth_switch, "#0A84FF"))
        v_opt.addLayout(self._make_switch_row("SECURE SSL", self._ssl_switch, "#3A3A3C"))
        v_opt.addLayout(self._make_switch_row("TLS HANDSHAKE", self._tls_switch, "#0A84FF"))
        layout.addLayout(v_opt)
        return container

    def _build_payload_section(self) -> QWidget:
        container = QWidget()
        container.setMinimumHeight(0)
        container.setStyleSheet("QWidget { background: transparent; border: none; }")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 5, 0, 0)
        layout.setSpacing(10)
        
        send_widget = QWidget()
        send_widget.setFixedHeight(62)
        send_row = QHBoxLayout(send_widget)
        send_row.setContentsMargins(0, 0, 0, 0)
        send_row.setSpacing(10)
        self._style_input(self._from_name)
        self._style_input(self._reply_to)
        send_row.addLayout(self._make_field("SENDER NAME", self._from_name), 1)
        send_row.addLayout(self._make_field("REPLY-TO ADDRESS", self._reply_to), 1)
        layout.addWidget(send_widget)

        self._style_input(self._subject)
        sub_container = QWidget()
        sub_container.setFixedHeight(62)
        sub_layout = QVBoxLayout(sub_container)
        sub_layout.setContentsMargins(0, 0, 0, 0)
        sub_layout.setSpacing(4)
        sub_layout.addWidget(self._field_label("BROADCAST SUBJECT"))
        sub_layout.addWidget(self._subject)
        layout.addWidget(sub_container)

        col_body = QVBoxLayout()
        col_body.setContentsMargins(0, 0, 0, 0)
        col_body.setSpacing(4)

        lbl_row_host = QWidget()
        lbl_row_host.setFixedHeight(32)
        lbl_row = QHBoxLayout(lbl_row_host)
        lbl_row.setContentsMargins(0, 0, 0, 0)
        lbl_row.setSpacing(8)
        lbl_row.addWidget(self._field_label("MESSAGE CONTENT"))
        lbl_row.addStretch()
        
        from PySide6.QtCore import QSize
        for btn, tip in [(self._preview_btn, "Preview"), (self._attach_btn, "Attach Files"), (self._attach_clear_btn, "Clear Attachments")]:
            btn.setFixedSize(24, 24)
            btn.setIconSize(QSize(16, 16))
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip(tip)
            btn.setStyleSheet("""
                ToolButton { background: transparent; border: none; border-radius: 6px; color: #636366; }
                ToolButton:hover { color: #FFFFFF; }
            """)
            lbl_row.addWidget(btn)
        
        self._attach_clear_btn.setStyleSheet("""
            ToolButton { background: transparent; border: none; border-radius: 6px; color: #636366; }
            ToolButton:hover { color: #FF453A; }
        """)
        
        self._attach_badge.setStyleSheet("color: #636366; font-family: 'PT Root UI', monospace; font-size: 11px; background: transparent;")
        lbl_row.addWidget(self._attach_badge)
        
        lbl_row.addSpacing(14)
        
        html_lbl = QLabel("HTML")
        html_lbl.setStyleSheet("color: #8E8E93; font-family: 'PT Root UI', sans-serif; font-size: 12px; background: transparent; border: none;")
        lbl_row.addWidget(html_lbl)
        
        self._type_toggle.toggled.connect(self._save_fields)
        lbl_row.addWidget(self._type_toggle)
        col_body.addWidget(lbl_row_host)
 
        self._body_stack.setMinimumHeight(0)
        self._style_plaintext(self._body_text)
        col_body.addWidget(self._body_stack, 1)
        layout.addLayout(col_body, 1)
        return container

    def _build_monitor_section(self) -> QWidget:
        container = QWidget()
        container.setMinimumHeight(0)
        container.setStyleSheet("QWidget { background: transparent; border: none; }")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 5, 0, 0)
        layout.setSpacing(10)

        rec_widget = QWidget()
        rec_widget.setFixedHeight(44)
        rec_h = QHBoxLayout(rec_widget)
        rec_h.setContentsMargins(0, 0, 0, 0)
        rec_h.setSpacing(12)
        
        self._style_input(self._interval_input)
        self._interval_input.setFixedHeight(34)
        self._interval_input.setFixedWidth(52)
        
        iv_lbl = self._field_label("INTERVAL (S)")
        rec_h.addWidget(iv_lbl, 0, Qt.AlignVCenter)
        rec_h.addWidget(self._interval_input, 0, Qt.AlignVCenter)
        
        bs_lbl = self._field_label("BATCH SIZE")
        rec_h.addWidget(bs_lbl, 0, Qt.AlignVCenter)
        
        self._style_input(self._batch_size)
        self._batch_size.setFixedHeight(34)
        self._batch_size.setFixedWidth(64)
        rec_h.addWidget(self._batch_size, 0, Qt.AlignVCenter)
        
        rec_h.addStretch(1)

        self._btn_dedup.setFixedHeight(34)
        self._btn_dedup.setFixedWidth(100)
        self._btn_dedup.setStyleSheet(Theme.zugzwang_danger_button())
        rec_h.addWidget(self._btn_dedup, 0, Qt.AlignVCenter)
        
        self._btn_purge_sent.setFixedHeight(34)
        self._btn_purge_sent.setFixedWidth(140)
        self._btn_purge_sent.setStyleSheet(Theme.zugzwang_danger_button())
        rec_h.addWidget(self._btn_purge_sent, 0, Qt.AlignVCenter)
        
        self._rec_count.setStyleSheet("color: #0A84FF; font-family: 'PT Root UI', monospace; font-size: 11px; font-weight: 600; background: transparent;")
        rec_h.addWidget(self._rec_count, 0, Qt.AlignVCenter)
        layout.addWidget(rec_widget)

        # Side-by-Side Monitor Area
        monitor_split = QHBoxLayout()
        monitor_split.setSpacing(12)
        
        # Left: Recipients
        rec_col = QVBoxLayout()
        rec_col.setSpacing(6)
        
        lbl_rec = self._field_label("RECIPIENT QUEUE")
        lbl_rec.setFixedHeight(28)
        rec_col.addWidget(lbl_rec)
        
        # Re-use existing recipients text
        self._style_plaintext(self._recipients_text)
        rec_col.addWidget(self._recipients_text, 1)
        monitor_split.addLayout(rec_col, 5) # 50/50 balance
        
        # Right: Log Stack
        log_stack = QVBoxLayout()
        log_stack.setSpacing(6)
        lbl_log = self._field_label("BROADCAST ACTIVITY LOG")
        lbl_log.setFixedHeight(28)
        log_stack.addWidget(lbl_log)
        
        self._status_log.setStyleSheet("""
            QTextEdit {
                background: #1A1A1A;
                border: 1px solid #3A3A3C;
                border-radius: 10px;
                padding: 12px;
                color: #48484A;
                font-family: 'PT Root UI', monospace;
                font-size: 12px;
                line-height: 1.8;
            }
        """)
        # Remove fixed height to let it expand naturally with the recipient panel
        log_stack.addWidget(self._status_log, 1)
        
        monitor_split.addLayout(log_stack, 5)
        layout.addLayout(monitor_split, 1)

        # Gmail Policy Notice - Spanning Full Width at Bottom
        notice_card = QFrame()
        notice_card.setObjectName("NoticeCard")
        notice_card.setStyleSheet("QFrame#NoticeCard { background: rgba(10, 132, 255, 0.08); border: none; border-radius: 10px; }")
        notice_h = QHBoxLayout(notice_card); notice_h.setContentsMargins(12, 10, 12, 10); notice_h.setSpacing(10)
        
        from qfluentwidgets import IconWidget
        n_ic = IconWidget(FluentIcon.INFO); n_ic.setFixedSize(16, 16); n_ic.setStyleSheet("background: transparent; border: none; color: #0A84FF;")
        notice_h.addWidget(n_ic)
        
        n_txt = QLabel("Gmail Policy: Sending >100 emails/day may flag your account as spam. Use batching for safety.")
        n_txt.setStyleSheet("color: #4EA1FF; font-size: 11px; font-weight: 500; font-family: 'PT Root UI', sans-serif;")
        notice_h.addWidget(n_txt, 1)
        
        layout.addWidget(notice_card)

        return container

    def _clear_all_data(self):
        # Identity
        self._smtp_host.clear()
        self._smtp_port.setText("587")
        self._smtp_user.clear()
        self._smtp_pass.clear()
        self._auth_switch.setChecked(True)
        self._ssl_switch.setChecked(False)
        self._tls_switch.setChecked(True)
        
        # Payload
        self._from_name.clear()
        self._reply_to.clear()
        self._subject.clear()
        self._body_text.clear()
        self._type_toggle.setChecked(False)
        
        # Persistence
        self._save_fields()

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text.upper())
        label.setStyleSheet("color: #8E8E93; font-family: 'PT Root UI', sans-serif; font-size: 10px; font-weight: 600; letter-spacing: 1.3px; background: transparent; border: none;")
        return label

    def _make_field(self, label: str, widget: QWidget) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(4)
        col.addWidget(self._field_label(label))
        col.addWidget(widget)
        return col

    def _style_input(self, widget: QWidget) -> None:
        widget.setFixedHeight(34)
        widget.setStyleSheet("""
            QLineEdit {
                background: #1C1C1E;
                border: 1px solid #3A3A3C;
                border-radius: 8px;
                color: white;
                font-family: 'PT Root UI', sans-serif;
                font-size: 13px;
                padding: 0 12px;
            }
            QLineEdit:focus {
                border: 1px solid #0A84FF;
            }
        """)

    def _style_plaintext(self, widget: QWidget) -> None:
        widget.setStyleSheet("""
            QPlainTextEdit, QTextEdit {
                background: #1A1A1A;
                border: 1px solid #3A3A3C;
                border-radius: 10px;
                padding: 12px;
                color: #8E8E93;
                font-family: 'PT Root UI', monospace;
                font-size: 12px;
            }
            QPlainTextEdit:focus, QTextEdit:focus {
                border: 1px solid #0A84FF;
            }
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 4px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #3A3A3C;
                min-height: 20px;
                border-radius: 2px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

    def _make_switch_row(self, text: str, switch: MacSwitch, on_color: str) -> QHBoxLayout:
        h = QHBoxLayout()
        h.setSpacing(10)
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #AEAEB2; font-family: 'PT Root UI', sans-serif; font-size: 10px; font-weight: 500; background: transparent; border: none;")
        
        switch.setOnColor(on_color)
        
        h.addWidget(switch)
        h.addWidget(lbl)
        h.setAlignment(lbl, Qt.AlignLeft)
        h.addStretch()
        return h


    # ── Signal Handlers & Logic ──────────────────────────────────────────────
    def _connect_buttons(self):
        self._btn_clear_data.clicked.connect(self._clear_all_data)
        self._preview_btn.clicked.connect(self._toggle_preview)
        self._attach_btn.clicked.connect(self._on_attach)
        self._attach_clear_btn.clicked.connect(self._on_attach_clear)
        self._btn_dedup.clicked.connect(self._on_dedup)
        self._btn_send_one.clicked.connect(self._send_test)
        self._btn_send_all.clicked.connect(self._send_all)
        self._btn_stop.clicked.connect(self._on_stop)
        self._btn_purge_sent.clicked.connect(self._on_purge_sent)
        self._btn_export.clicked.connect(self._on_export)
        self._recipients_text.textChanged.connect(self._on_recipients_changed)
        
        # Persistence hooks for all fields
        self._smtp_host.textChanged.connect(self._save_fields)
        self._smtp_port.textChanged.connect(self._save_fields)
        self._smtp_user.textChanged.connect(self._save_fields)
        self._smtp_pass.textChanged.connect(self._save_fields)
        self._from_name.textChanged.connect(self._save_fields)
        self._reply_to.textChanged.connect(self._save_fields)
        self._subject.textChanged.connect(self._save_fields)
        self._body_text.textChanged.connect(self._save_fields)
        self._interval_input.textChanged.connect(self._save_fields)
        
        self._auth_switch.toggled.connect(self._save_fields)
        self._ssl_switch.toggled.connect(self._save_fields)
        self._tls_switch.toggled.connect(self._save_fields)
        self._type_toggle.toggled.connect(self._save_fields)

    def _on_log(self, message: str, level: str):
        color = "#FFFFFF"
        if level == "WARNING": color = "#FF9F0A"
        elif level == "ERROR": color = "#FF453A"
        elif level == "SUCCESS": color = "#32D74B"
        
        self._status_log.append(f'<span style="color: {color}">{message}</span>')
        self._status_log.verticalScrollBar().setValue(self._status_log.verticalScrollBar().maximum())

    def _on_progress(self, current: int, total: int):
        self._status_badge.setText(f"SENDING {current}/{total}")

    def _on_finished(self, sent: int, failed: int, was_aborted: bool):
        self._set_sending_state(False)
        self._status_badge.setText("ABORTED" if was_aborted else "FINISHED")
        msg = f"Broadcast aborted by user. Sent: {sent}, Failed: {failed}" if was_aborted else f"Broadcast concluded. Sent: {sent}, Failed: {failed}"
        color = "#FF453A" if was_aborted else "#4EA1FF"
        self._status_log.append(f'<span style="color: {color}">{msg}</span>')

    def _on_error(self, message: str):
        self._on_log(message, "ERROR")

    def _toggle_preview(self):
        self._isPreview = not self._isPreview
        if self._isPreview:
            self._body_preview.setHtml(self._body_text.toPlainText())
            self._body_stack.setCurrentIndex(1)
            self._preview_btn.setText("EDIT MODE")
        else:
            self._body_stack.setCurrentIndex(0)
            self._preview_btn.setText("PREVIEW CONTENT")

    def _on_attach(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Attach Files")
        if files:
            self._attachments = files
            self._attach_badge.setText(f"{len(files)} FILES")
            self._on_log(f"Attached {len(files)} file(s).", "INFO")

    def _on_attach_clear(self):
        if self._attachments:
            count = len(self._attachments)
            self._attachments = []
            self._attach_badge.setText("0 FILES")
            self._on_log(f"Cleared {count} attachment(s).", "WARNING")

    def _on_dedup(self):
        text = self._recipients_text.toPlainText()
        emails = list(dict.fromkeys([e.strip() for e in text.splitlines() if e.strip()]))
        self._recipients_text.setPlainText("\n".join(emails))
        self._rec_count.setText(f"{len(emails)} EMAIL(S)")
        self._on_log(f"De-duplicated list. {len(emails)} unique recipients.", "SUCCESS")

    def _on_stop(self):
        self._stop_requested = True
        self._on_log("Stop requested by user...", "WARNING")
        # Aggressive Stop: Force close the connection if it exists
        if self._active_server:
            try:
                self._active_server.close()
                self._on_log("Active connection forced to close.", "WARNING")
            except: pass

    def _on_purge_sent(self):
        if not self._successful_emails:
            self._on_log("No successful transmissions to purge.", "WARNING")
            return
            
        current_text = self._recipients_text.toPlainText().splitlines()
        purged = [e.strip() for e in current_text if e.strip() and e.strip() not in self._successful_emails]
        
        self._recipients_text.setPlainText("\n".join(purged))
        self._successful_emails = [] # Clear tracking after purge
        self._on_recipients_changed()
        self._on_log(f"Purged sent emails from queue. {len(purged)} remaining.", "SUCCESS")

    def _on_export(self):
        if not self._successful_emails:
            self._on_log("No successful transmissions to export.", "WARNING")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Successful Emails", "broadcast_sent.txt", "Text Files (*.txt)")
        if path:
            with open(path, "w") as f: f.write("\n".join(self._successful_emails))
            self._on_log(f"Exported to {Path(path).name}", "SUCCESS")

    def import_emails(self, emails: list[str]):
        """Public API for MainWindow to push leads here."""
        if not emails: return
        clean_new = [e.strip() for e in emails if e.strip()]
        current = self._recipients_text.toPlainText().splitlines()
        combined = list(dict.fromkeys([e.strip() for e in current + clean_new if e.strip()]))
        
        self._recipients_text.setPlainText("\n".join(combined))
        self._rec_count.setText(f"{len(combined)} EMAIL(S)")
        self._on_log(f"Imported {len(clean_new)} lead(s). Total recipients: {len(combined)}", "SUCCESS")

    def _send_test(self):
        recs = [e.strip() for e in self._recipients_text.toPlainText().splitlines() if e.strip()]
        if not recs: return self._on_log("No recipients in queue.", "ERROR")
        self._log(f"Executing test broadcast to {recs[0]}...")
        self._set_sending_state(True)
        threading.Thread(target=self._worker_send, args=([recs[0]],), daemon=True).start()

    def _send_all(self):
        recs = [e.strip() for e in self._recipients_text.toPlainText().splitlines() if e.strip()]
        if not recs: return self._on_log("Recipient queue empty.", "ERROR")
        self._log("Initiating global broadcast...")
        self._set_sending_state(True)
        threading.Thread(target=self._worker_send, args=(recs,), daemon=True).start()

    def _set_sending_state(self, sending: bool):
        self._sending = sending
        self._stop_requested = False
        self._btn_send_all.setEnabled(not sending)
        self._btn_send_one.setEnabled(not sending)
        self._btn_stop.setEnabled(sending)
        self._status_badge.setText("SENDING" if sending else "READY")

    def _log(self, text: str, level: str = "INFO"):
        self._signals.log.emit(text, level)

    def _worker_send(self, recipients: list[str]):
        sent = 0; failed = 0; total = len(recipients)
        try: interval = max(1, int(self._interval_input.text().strip()))
        except: interval = 5

        try:
            self._log("Initializing SMTP Handshake...")
            self._active_server = self._create_smtp_connection()
            if self._stop_requested:
                try: self._active_server.quit()
                except: pass
                self._active_server = None
                self._signals.finished.emit(0, 0, True)
                return
            self._log("Authenticated successfully.", "SUCCESS")
        except Exception as e:
            if self._stop_requested:
                self._signals.finished.emit(0, 0, True)
            else:
                self._signals.error.emit(f"Handshake Failed: {e}")
                self._signals.finished.emit(0, 0, False)
            return

        # Respect Batch Size
        try: 
            bs = int(self._batch_size.text().strip())
            if bs < len(recipients):
                self._log(f"Limiting broadcast to batch size of {bs}...", "WARNING")
                recipients = recipients[:bs]
                total = bs
        except: pass

        for i, rec in enumerate(recipients):
            if self._stop_requested: break
            try:
                msg = self._build_message(rec)
                if self._stop_requested: break
                
                self._active_server.send_message(msg)
                sent += 1
                self._successful_emails.append(rec)
                self._log(f"Sent to {rec} ({i+1}/{total})", "INFO")
            except Exception as e:
                if self._stop_requested: break
                failed += 1
                self._log(f"Error for {rec}: {e}", "ERROR")
            
            self._signals.progress.emit(i+1, total)
            if i < total - 1 and not self._stop_requested:
                time.sleep(interval)

        try: 
            if self._active_server:
                self._active_server.quit()
        except: pass
        self._active_server = None
        self._signals.finished.emit(sent, failed, self._stop_requested)

    def _build_message(self, recipient: str) -> MIMEMultipart:
        msg = MIMEMultipart()
        msg["From"] = f"{self._from_name.text()} <{self._smtp_user.text().strip()}>"
        
        reply_addr = self._reply_to.text().strip()
        if reply_addr:
            msg["Reply-To"] = reply_addr
            
        msg["To"] = recipient
        msg["Subject"] = self._subject.text()
        msg.attach(MIMEText(self._body_text.toPlainText(), "html" if self._type_toggle.isChecked() else "plain"))

        # Attach files
        for file_path in self._attachments:
            if not os.path.exists(file_path):
                continue
            
            try:
                part = MIMEBase("application", "octet-stream")
                with open(file_path, "rb") as f:
                    part.set_payload(f.read())
                
                encoders.encode_base64(part)
                filename = os.path.basename(file_path)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename=\"{filename}\""
                )
                msg.attach(part)
            except Exception as e:
                self._log(f"Failed to attach {file_path}: {e}", "ERROR")

        return msg

    def _create_smtp_connection(self):
        host = self._smtp_host.text().strip()
        port = int(self._smtp_port.text().strip())
        if self._ssl_switch.isChecked():
            server = smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=15)
        else:
            server = smtplib.SMTP(host, port, timeout=15)
            if self._tls_switch.isChecked():
                server.starttls(context=ssl.create_default_context())
        if self._auth_switch.isChecked():
            server.login(self._smtp_user.text().strip(), self._smtp_pass.text().strip())
        return server

    def _save_fields(self):
        config_manager.update(
            email_smtp_host=self._smtp_host.text(),
            email_smtp_port=self._smtp_port.text(),
            email_smtp_user=self._smtp_user.text(),
            email_smtp_pass=self._smtp_pass.text(),
            email_from_name=self._from_name.text(),
            email_reply_to=self._reply_to.text(),
            email_smtp_auth=self._auth_switch.isChecked(),
            email_smtp_ssl=self._ssl_switch.isChecked(),
            email_smtp_tls=self._tls_switch.isChecked(),
            email_body_html=self._type_toggle.isChecked(),
            email_subject=self._subject.text(),
            email_body=self._body_text.toPlainText(),
            email_interval=self._interval_input.text(),
            email_recipients=self._recipients_text.toPlainText()
        )

    def _restore_fields(self):
        s = config_manager.settings
        self._smtp_host.setText(s.email_smtp_host)
        self._smtp_port.setText(s.email_smtp_port)
        self._smtp_user.setText(s.email_smtp_user)
        self._smtp_pass.setText(s.email_smtp_pass)
        self._from_name.setText(s.email_from_name)
        self._reply_to.setText(s.email_reply_to)
        self._auth_switch.setChecked(s.email_smtp_auth)
        self._ssl_switch.setChecked(s.email_smtp_ssl)
        self._tls_switch.setChecked(s.email_smtp_tls)
        self._type_toggle.setChecked(s.email_body_html)
        self._subject.setText(s.email_subject)
        self._body_text.setPlainText(s.email_body)
        self._interval_input.setText(s.email_interval)
        self._recipients_text.setPlainText(s.email_recipients)
        self._on_recipients_changed()

    def _on_recipients_changed(self):
        """Updates the numeric badge showing the current target count."""
        raw = self._recipients_text.toPlainText().strip()
        count = len([r for r in raw.split("\n") if r.strip()])
        self._rec_count.setText(f"{count} EMAIL(S)")

    # End of class
