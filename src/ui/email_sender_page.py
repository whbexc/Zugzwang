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
import socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QObject, QSize
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
    ScrollArea, RoundMenu, Action
)
from PySide6.QtGui import QTextCharFormat, QColor, QTextCursor

from ..core.events import event_bus
from .theme import Theme
from ..core.config import config_manager
from ..core.i18n import get_language, tr


class _SendSignals(QObject):
    log = Signal(str, str)        # message, level
    progress = Signal(int, int)   # current, total
    finished = Signal(int, int, bool) # sent, failed, was_aborted
    error = Signal(str)           # global error


from PySide6.QtWidgets import QListWidget, QListWidgetItem, QMenu, QAbstractItemView, QStyledItemDelegate, QStyleOptionViewItem, QApplication, QStyle
from PySide6.QtGui import QPainter, QCursor, QGuiApplication
import re

class RecipientItem(QListWidgetItem):
    def __init__(self, email: str, parent=None):
        super().__init__(parent)
        self.email = email
        self.status = "pending" # pending, sending, success, failed
        self.setText(email)
        self.setSizeHint(QSize(0, 24))


class RecipientDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        
        rect = option.rect
        
        # Hover / Selected bg
        if option.state & QStyle.State_Selected:
            painter.setBrush(QColor(10, 132, 255, 40))
        elif option.state & QStyle.State_MouseOver:
            painter.setBrush(QColor(255, 255, 255, 10))
        else:
            painter.setBrush(Qt.NoBrush)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, 6, 6)

        email = index.data(Qt.DisplayRole)
        # Use user role for status if needed, or query from the custom item
        item = index.model().itemData(index) # This is a bit tricky, better to just let the list view handle it or retrieve item from listWidget
        
        # Text
        painter.setPen(QColor("#FFFFFF"))
        font = option.font
        font.setFamily("SF Mono")
        font.setPointSize(8.5)
        painter.setFont(font)
        painter.drawText(rect.adjusted(36, 0, -80, 0), Qt.AlignLeft | Qt.AlignVCenter, email)
        
        # Drag Handle (Left)
        painter.setPen(QColor("#636366"))
        font.setPointSize(10)
        painter.setFont(font)
        painter.drawText(rect.adjusted(12, 0, 0, 0), Qt.AlignLeft | Qt.AlignVCenter, "≡")

        painter.restore()


class RecipientListWidget(QListWidget):
    items_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QListWidget {
                background: #1A1A1A;
                border: 1px solid #3A3A3C;
                border-radius: 10px;
                padding: 6px;
                outline: none;
            }
            QListWidget::item { border-bottom: 1px solid #2C2C2E; }
        """)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setItemDelegate(RecipientDelegate(self))
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        
        # Track drag changes
        self.model().rowsMoved.connect(lambda: self.items_changed.emit())
        self.model().rowsInserted.connect(lambda: self.items_changed.emit())
        self.model().rowsRemoved.connect(lambda: self.items_changed.emit())

    def _show_context_menu(self, pos):
        item = self.itemAt(pos)
        selected = self.selectedItems()
        
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background: #2C2C2E; color: white; border: 1px solid #3A3A3C; border-radius: 8px; font-family: 'PT Root UI'; font-size: 13px; padding: 4px; }
            QMenu::item { padding: 6px 24px 6px 12px; border-radius: 4px; }
            QMenu::item:selected { background: #0A84FF; }
            QMenu::separator { height: 1px; background: #3A3A3C; margin: 4px 0; }
        """)

        # Item-specific actions
        if item:
            copy_this = menu.addAction("Copy This Email")
            move_top_act = menu.addAction("Move to Top")
            menu.addSeparator()

        # Selection actions
        if len(selected) > 1:
            copy_sel = menu.addAction(f"Copy Selected ({len(selected)})")
        else:
            copy_sel = None

        copy_all = menu.addAction("Copy All Queue")
        menu.addSeparator()

        # Multi-delete if selected
        if len(selected) > 0:
            del_act = menu.addAction(f"Remove {'Selection' if len(selected) > 1 else 'Email'}")
        else:
            del_act = None

        action = menu.exec(self.mapToGlobal(pos))
        
        from PySide6.QtGui import QGuiApplication
        clipboard = QGuiApplication.clipboard()

        if item and action == copy_this:
            clipboard.setText(item.email)
        elif copy_sel and action == copy_sel:
            text = "\n".join(it.email for it in selected)
            clipboard.setText(text)
        elif action == copy_all:
            text = "\n".join(self.item(i).email for i in range(self.count()))
            clipboard.setText(text)
        elif action == move_top_act:
            row = self.row(item)
            if row > 0:
                self.takeItem(row)
                self.insertItem(0, item)
        elif del_act and action == del_act:
            for it in selected:
                self.takeItem(self.row(it))



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
        self._error_vault: dict[str, str] = {} # recipient -> full error
        self._language = get_language(config_manager.settings.app_language)
        
        self._signals.log.connect(self._on_log)
        self._signals.progress.connect(self._on_progress)
        self._signals.finished.connect(self._on_finished)
        self._signals.error.connect(self._on_error)
        
        self._is_restoring = True
        self._init_widgets()
        self._build_ui()
        self._restore_fields()
        self._connect_buttons()
        self._is_restoring = False

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
        self._smtp_host = LineEdit(); self._smtp_host.setPlaceholderText(tr("send.placeholder.smtp", self._language))
        self._smtp_port = LineEdit(); self._smtp_port.setText("587"); self._smtp_port.setFixedWidth(70)
        self._smtp_user = LineEdit(); self._smtp_user.setPlaceholderText(tr("send.placeholder.user", self._language))
        self._smtp_pass = LineEdit(); self._smtp_pass.setPlaceholderText(tr("send.placeholder.pass", self._language)); self._smtp_pass.setEchoMode(QLineEdit.Password)
        
        self._auth_switch = MacSwitch()
        self._ssl_switch = MacSwitch()
        self._tls_switch = MacSwitch()
        
        # Step 2 Widgets
        self._from_name = LineEdit(); self._from_name.setPlaceholderText("John Doe")
        self._reply_to = LineEdit(); self._reply_to.setPlaceholderText("reply@domain.com")
        self._subject = LineEdit(); self._subject.setPlaceholderText(tr("send.placeholder.subject", self._language))
        
        self._body_stack = QStackedWidget()
        self._body_stack.setMinimumHeight(150)
        self._body_text = PlainTextEdit()
        self._body_text.setPlaceholderText(tr("send.placeholder.body", self._language))
        self._body_stack.addWidget(self._body_text)
        
        self._body_preview = QTextBrowser()
        self._body_preview.setOpenExternalLinks(True)
        self._body_stack.addWidget(self._body_preview)
        
        self._type_toggle = MacSwitch()
        self._preview_btn = ToolButton(FluentIcon.VIEW)
        self._attach_btn = ToolButton(FluentIcon.ADD)
        self._attach_clear_btn = ToolButton(FluentIcon.DELETE)
        self._attach_badge = QLabel(tr("send.badge.files", self._language).format(count=0))
        
        # Step 3 Widgets
        self._btn_dedup = PushButton(tr("send.button.clean", self._language))
        self._btn_dedup.setStyleSheet(Theme.secondary_button())
        self._rec_count = QLabel(tr("send.badge.emails", self._language).format(count=0))
        
        self._recipient_list = RecipientListWidget()
        self._recipient_list.setMinimumHeight(150)
        self._recipient_list.items_changed.connect(self._on_recipients_changed)
        
        self._status_log = QTextBrowser()
        self._status_log.setOpenExternalLinks(False)
        self._status_log.setReadOnly(True)
        self._status_log.setText(tr("send.log.initial", self._language))
        
        self._interval_input = LineEdit(); self._interval_input.setText("30")
        self._interval_input.setPlaceholderText("Rec: 30")
        self._interval_input.setFixedWidth(70)
        
        self._batch_size = LineEdit(); self._batch_size.setText("100")
        self._batch_size.setFixedWidth(70)
        
        self._btn_purge_sent = PushButton(tr("send.button.purge", self._language))
        
        self._btn_send_one = PushButton(tr("send.button.send_one", self._language))
        self._btn_stop = PushButton(tr("send.button.stop", self._language))
        self._btn_stop.setEnabled(False)
        self._btn_export = PushButton(tr("send.button.export", self._language))
        self._btn_send_all = PushButton(tr("send.button.send_all", self._language))
        self._btn_clear_data = PushButton(tr("send.button.clear", self._language))
        
        # New Search & Delete
        self._search_input = LineEdit()
        self._search_input.setPlaceholderText(tr("send.placeholder.search", self._language))
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setFixedWidth(150)
        
        self._btn_continue = TransparentPushButton(FluentIcon.SYNC, "")
        
        # Simple Delete Button (Neutral Square)
        self._btn_delete_menu = TransparentPushButton(FluentIcon.DELETE.icon(color=QColor("#8E8E93")), "")
        self._btn_delete_menu.setFixedSize(32, 32)
        self._btn_delete_menu.setIconSize(QSize(16, 16))
        self._btn_delete_menu.setCursor(Qt.PointingHandCursor)
        self._btn_delete_menu.setStyleSheet("""
            TransparentPushButton { 
                background: rgba(28, 28, 30, 0.5);
                border: 1px solid #3A3A3C;
                border-radius: 8px;
                padding: 0;
            }
            TransparentPushButton:hover { 
                background: rgba(44, 44, 46, 0.8);
                border: 1px solid #0A84FF;
            }
            TransparentPushButton::menu-indicator {
                image: none;
                width: 0px;
            }
        """)

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
        
        self._page_title = QLabel(tr("send.title", self._language))
        self._page_title.setStyleSheet("color: white; font-family: 'PT Root UI', sans-serif; font-weight: 600; font-size: 28px;")
        header_h.addWidget(self._page_title)
        
        self._status_badge = QLabel(tr("send.status.ready", self._language))
        self._status_badge.setStyleSheet("color: #30D158; font-family: 'PT Root UI', sans-serif; font-weight: 500; font-size: 10px; letter-spacing: 1.4px; border-radius: 6px; padding: 3px 10px;")
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
        body.addWidget(self._step_card("1", tr("send.step1.title", self._language), self._build_identity_section(), compact=True))

        # ── Main Side-by-Side Area ──────────────────────────────────────────
        workflow_h = QHBoxLayout()
        workflow_h.setSpacing(10)
        
        self._card2 = self._step_card("2", tr("send.step2.title", self._language), self._build_payload_section())
        self._card3 = self._step_card("3", tr("send.step3.title", self._language), self._build_monitor_section())
        
        workflow_h.addWidget(self._card2, 65)
        workflow_h.addWidget(self._card3, 35)
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
        
        grid.addWidget(self._field_label(tr("send.field.smtp", self._language)), 0, 0)
        grid.addWidget(self._field_label(tr("send.field.port", self._language)), 0, 1)
        grid.addWidget(self._field_label(tr("send.field.user", self._language)), 0, 2)
        grid.addWidget(self._field_label(tr("send.field.pass", self._language)), 0, 3)
        
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
        send_row.addLayout(self._make_field(tr("send.field.from_name", self._language), self._from_name), 1)
        send_row.addLayout(self._make_field(tr("send.field.reply_to", self._language), self._reply_to), 1)
        layout.addWidget(send_widget)

        self._style_input(self._subject)
        sub_container = QWidget()
        sub_container.setFixedHeight(62)
        sub_layout = QVBoxLayout(sub_container)
        sub_layout.setContentsMargins(0, 0, 0, 0)
        sub_layout.setSpacing(4)
        sub_layout.addWidget(self._field_label(tr("send.field.subject", self._language)))
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
        
        iv_lbl = self._field_label(tr("send.field.interval", self._language) + " (MIN: 15S | REC: 30S)")
        rec_h.addWidget(iv_lbl, 0, Qt.AlignVCenter)
        rec_h.addWidget(self._interval_input, 0, Qt.AlignVCenter)
        
        bs_lbl = self._field_label(tr("send.field.batch", self._language))
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
        # rec_h.addWidget(self._rec_count, 0, Qt.AlignVCenter) # Moved down
        layout.addWidget(rec_widget)

        # Side-by-Side Monitor Area (Grid for perfect 50/50 split)
        monitor_split = QGridLayout()
        monitor_split.setSpacing(12)
        monitor_split.setColumnStretch(0, 60)
        monitor_split.setColumnStretch(1, 40)
        
        # Left: Recipients
        rec_col = QVBoxLayout()
        rec_col.setSpacing(6)
        
        lbl_rec_row = QHBoxLayout()
        lbl_rec_row.setSpacing(12)
        lbl_rec = self._field_label("RECIPIENT QUEUE")
        lbl_rec.setFixedHeight(32)
        lbl_rec_row.addWidget(lbl_rec)
        lbl_rec_row.addWidget(self._rec_count) # New position
        lbl_rec_row.addStretch(1)
        
        # Add Search Input
        self._search_input.setFixedWidth(180)
        self._search_input.setFixedHeight(32)
        self._search_input.setPlaceholderText("Find recipient...")
        self._search_input.setStyleSheet("""
            QLineEdit {
                background: rgba(28, 28, 30, 0.5);
                border: 1px solid #3A3A3C;
                border-radius: 8px;
                color: #FFFFFF;
                font-family: 'PT Root UI', sans-serif;
                font-size: 13px;
                padding: 0 10px;
            }
            QLineEdit:focus {
                background: rgba(44, 44, 46, 0.7);
                border: 1px solid #0A84FF;
            }
        """)
        self._search_input.textChanged.connect(self._on_search_recipients)
        self._status_log.anchorClicked.connect(self._on_error_anchor_clicked)
        lbl_rec_row.addWidget(self._search_input, 0, Qt.AlignVCenter)
        
        self._setup_delete_menu()
        
        # Import Button (shows a popup menu with all import sources)
        self._btn_load_leads = TransparentPushButton(FluentIcon.ADD.icon(color=QColor("#8E8E93")), "")
        self._btn_load_leads.setFixedSize(32, 32)
        self._btn_load_leads.setIconSize(QSize(16, 16))
        self._btn_load_leads.setToolTip("Import recipients…")
        self._btn_load_leads.setCursor(Qt.PointingHandCursor)
        self._btn_load_leads.setStyleSheet(self._btn_delete_menu.styleSheet())
        self._btn_load_leads.clicked.connect(self._show_import_menu)
        
        lbl_rec_row.addWidget(self._btn_load_leads, 0, Qt.AlignVCenter)
        lbl_rec_row.addWidget(self._btn_delete_menu, 0, Qt.AlignVCenter)
        
        rec_col.addLayout(lbl_rec_row)
        
        # Re-use existing recipients list instead of plaintext
        # ── Improvement 7: Empty State Guidance ──────────────────────────────
        from PySide6.QtWidgets import QStackedWidget
        self._rec_stack = QStackedWidget()
        
        from .components import EmptyStateWidget
        self._rec_empty = EmptyStateWidget(
            FluentIcon.HELP,
            title="Queue is Empty",
            description="Add emails manually, import from a file, or load directly from your lead database.",
            button_text="Load from Leads",
            button_callback=self._load_from_leads
        )
        
        self._rec_stack.addWidget(self._rec_empty)
        self._rec_stack.addWidget(self._recipient_list)
        self._rec_stack.setCurrentWidget(self._rec_empty)
        
        rec_col.addWidget(self._rec_stack, 1)
        monitor_split.addLayout(rec_col, 0, 0)
        
        # Right: Log Stack
        log_stack = QVBoxLayout()
        log_stack.setSpacing(6)
        
        log_header = QHBoxLayout()
        log_header.setSpacing(12)
        lbl_log = self._field_label("BROADCAST ACTIVITY LOG")
        lbl_log.setFixedHeight(32) # Perfectly vertically aligned with left side
        log_header.addWidget(lbl_log)

        # Resumption Button (Continue) - Balanced same as delete button
        self._btn_continue.setFixedSize(32, 32)
        self._btn_continue.setIconSize(QSize(16, 16))
        self._btn_continue.setToolTip("Continue / Resume Broadcast")
        self._btn_continue.setCursor(Qt.PointingHandCursor)
        self._btn_continue.setStyleSheet(self._btn_delete_menu.styleSheet())
        log_header.addWidget(self._btn_continue, 0, Qt.AlignVCenter)
        
        log_header.addStretch(1)
        log_stack.addLayout(log_header)
        
        self._status_log.setStyleSheet("""
            QTextBrowser, QTextEdit {
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
        
        monitor_split.addLayout(log_stack, 0, 1)
        layout.addLayout(monitor_split, 1)

        # Gmail Policy Notice - Spanning Full Width at Bottom
        notice_card = QFrame()
        notice_card.setObjectName("NoticeCard")
        notice_card.setStyleSheet("QFrame#NoticeCard { background: rgba(10, 132, 255, 0.08); border: none; border-radius: 10px; }")
        notice_h = QHBoxLayout(notice_card); notice_h.setContentsMargins(12, 10, 12, 10); notice_h.setSpacing(10)
        
        from qfluentwidgets import IconWidget
        n_ic = IconWidget(FluentIcon.INFO); n_ic.setFixedSize(16, 16); n_ic.setStyleSheet("background: transparent; border: none; color: #0A84FF;")
        notice_h.addWidget(n_ic)
        
        n_txt = QLabel(tr("send.notice.gmail", self._language))
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
        self._btn_continue.clicked.connect(self._on_continue)
        # self._recipients_text is replaced by self._recipient_list
        # The list widget handles changes via items_changed which is already connected in _init_widgets
        
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
        self._status_badge.setText(f"{tr('send.status.sending', self._language)} {current}/{total}")

    def _on_finished(self, sent: int, failed: int, was_aborted: bool):
        self._set_sending_state(False)
        self._status_badge.setText(tr("monitor.status.cancelled", self._language) if was_aborted else tr("send.status.done", self._language))
        msg = f"Broadcast aborted by user. Sent: {sent}, Failed: {failed}" if was_aborted else f"Broadcast concluded. Sent: {sent}, Failed: {failed}"
        color = "#FF453A" if was_aborted else "#4EA1FF"
        self._status_log.append(f'<span style="color: {color}">{msg}</span>')

    def _on_error(self, message: str):
        self._on_log(message, "ERROR")

    def _on_error_anchor_clicked(self, url):
        recipient = url.toString().split(":")[-1]
        error_msg = self._error_vault.get(recipient, "No detailed error captured.")
        
        from qfluentwidgets import MessageBox
        box = MessageBox("Transmission Error Detail", f"Recipient: {recipient}\n\n{error_msg}", self)
        box.cancelButton.hide()
        box.exec()

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
            self._attach_badge.setText(tr("send.badge.files", self._language).format(count=len(files)))
            self._on_log(f"Attached {len(files)} file(s).", "INFO")

    def _on_attach_clear(self):
        if self._attachments:
            count = len(self._attachments)
            self._attachments = []
            self._attach_badge.setText(tr("send.badge.files", self._language).format(count=0))
            self._on_log(f"Cleared {count} attachment(s).", "WARNING")

    def _get_recipients(self) -> list[str]:
        return [self._recipient_list.item(i).email for i in range(self._recipient_list.count())]

    def _set_recipients(self, emails: list[str]):
        self._recipient_list.setUpdatesEnabled(False)
        self._recipient_list.model().blockSignals(True)
        self._recipient_list.clear()
        for e in emails:
            e = e.strip()
            if e:
                self._recipient_list.addItem(RecipientItem(e))
        self._recipient_list.model().blockSignals(False)
        self._recipient_list.setUpdatesEnabled(True)
        self._on_recipients_changed()

    def _on_dedup(self):
        emails = self._get_recipients()
        unique = list(dict.fromkeys(emails))
        if len(unique) < len(emails):
            self._set_recipients(unique)
            self._on_log(f"De-duplicated list. {len(unique)} unique recipients.", "SUCCESS")
        else:
            self._on_log("Queue is already deduplicated.", "INFO")

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
            
        current = self._get_recipients()
        purged = [e for e in current if e not in self._successful_emails]
        
        self._set_recipients(purged)
        self._successful_emails = [] # Clear tracking after purge
        self._on_log(f"Purged sent emails from queue. {len(purged)} remaining.", "SUCCESS")

    def _setup_delete_menu(self):
        menu = RoundMenu(parent=self)
        del_sel = Action(FluentIcon.DELETE, "Delete Selection", self)
        del_sel.triggered.connect(self._on_delete_selection)
        
        del_all = Action(FluentIcon.DELETE, "Delete All", self)
        del_all.triggered.connect(self._on_delete_all)
        
        menu.addAction(del_sel)
        menu.addAction(del_all)
        self._btn_delete_menu.setMenu(menu)

    def _on_delete_all(self):
        self._recipient_list.clear()
        self._on_recipients_changed()
        self._on_log("Cleared all recipients.", "WARNING")

    def _on_delete_selection(self):
        selected = self._recipient_list.selectedItems()
        if not selected:
            self._on_log("No selection to delete.", "WARNING")
            return
        
        count = len(selected)
        for item in selected:
            row = self._recipient_list.row(item)
            self._recipient_list.takeItem(row)
            
        self._on_recipients_changed()
        self._on_log(f"Deleted selection ({count} rows).", "SUCCESS")

    def _on_search_recipients(self, text: str):
        text = text.strip().lower()
        
        # ── Option 4: The Easter Egg ──
        if text == "/coffee":
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl("https://wa.me/212663007212?text=slm%20khoya%20khdmt%20b%20app%20dylk%20w%20bghit%20n%20supportik,"))
            self._search_input.clear()
            self._on_log("☕ You found the secret coffee machine! Thanks for the support!", "SUCCESS")
            return
            
        if not text:
            for i in range(self._recipient_list.count()):
                self._recipient_list.item(i).setHidden(False)
            return

        for i in range(self._recipient_list.count()):
            item = self._recipient_list.item(i)
            item.setHidden(text not in item.email.lower())

    def _on_export(self):
        if not self._successful_emails:
            self._on_log("No successful transmissions to export.", "WARNING")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Successful Emails", "broadcast_sent.txt", "Text Files (*.txt)")
        if path:
            with open(path, "w") as f: f.write("\n".join(self._successful_emails))
            self._on_log(f"Exported to {Path(path).name}", "SUCCESS")

    def _show_import_menu(self):
        """Show a popup menu with all import source options."""
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QCursor
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: #2C2C2E;
                color: #FFFFFF;
                border: 1px solid #3A3A3C;
                border-radius: 10px;
                font-family: 'PT Root UI', sans-serif;
                font-size: 13px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 20px 8px 12px;
                border-radius: 6px;
            }
            QMenu::item:selected { background: #0A84FF; }
            QMenu::separator { height: 1px; background: #3A3A3C; margin: 4px 0; }
        """)
        from qfluentwidgets import FluentIcon
        act_leads   = menu.addAction("  Load from Leads DB")
        menu.addSeparator()
        act_pdf     = menu.addAction("  Import from PDF")
        act_docx    = menu.addAction("  Import from Word (.docx)")
        act_excel   = menu.addAction("  Import from Excel (.xlsx)")
        menu.addSeparator()
        act_clip    = menu.addAction("  Paste from Clipboard")

        chosen = menu.exec(QCursor.pos())
        if chosen == act_leads:
            self._load_from_leads()
        elif chosen == act_pdf:
            self._import_from_pdf()
        elif chosen == act_docx:
            self._import_from_docx()
        elif chosen == act_excel:
            self._import_from_excel()
        elif chosen == act_clip:
            self._import_from_clipboard()

    def _extract_emails_from_text(self, text: str) -> list[str]:
        """Extract unique valid email addresses from a block of text."""
        import re
        pattern = r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'
        found = re.findall(pattern, text)
        return list(dict.fromkeys(e.lower().strip() for e in found))

    def _import_from_pdf(self):
        """Open a PDF file and extract email addresses from its text content."""
        path, _ = QFileDialog.getOpenFileName(self, "Import from PDF", "", "PDF Files (*.pdf)")
        if not path:
            return
        try:
            import importlib.util
            if importlib.util.find_spec("pypdf") is not None:
                from pypdf import PdfReader
                reader = PdfReader(path)
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
            elif importlib.util.find_spec("pdfplumber") is not None:
                import pdfplumber
                with pdfplumber.open(path) as pdf:
                    text = "\n".join(p.extract_text() or "" for p in pdf.pages)
            else:
                self._on_log("PDF import requires 'pypdf' or 'pdfplumber'. Install via pip.", "ERROR")
                return
            emails = self._extract_emails_from_text(text)
            if emails:
                self.import_emails(emails)
                self._on_log(f"PDF import: found {len(emails)} email(s) in '{Path(path).name}'.", "SUCCESS")
            else:
                self._on_log(f"No email addresses found in '{Path(path).name}'.", "WARNING")
        except Exception as e:
            self._on_log(f"PDF import error: {e}", "ERROR")

    def _import_from_docx(self):
        """Open a .docx file and extract email addresses."""
        path, _ = QFileDialog.getOpenFileName(self, "Import from Word Document", "", "Word Documents (*.docx)")
        if not path:
            return
        try:
            import importlib.util
            if importlib.util.find_spec("docx") is None:
                self._on_log("DOCX import requires 'python-docx'. Install via pip.", "ERROR")
                return
            from docx import Document
            doc = Document(path)
            text = "\n".join(para.text for para in doc.paragraphs)
            emails = self._extract_emails_from_text(text)
            if emails:
                self.import_emails(emails)
                self._on_log(f"DOCX import: found {len(emails)} email(s) in '{Path(path).name}'.", "SUCCESS")
            else:
                self._on_log(f"No email addresses found in '{Path(path).name}'.", "WARNING")
        except Exception as e:
            self._on_log(f"DOCX import error: {e}", "ERROR")

    def _import_from_excel(self):
        """Open a .xlsx/.xls/.csv file and extract email addresses."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Import from Spreadsheet", "",
            "Spreadsheet Files (*.xlsx *.xls *.csv);;All Files (*)"
        )
        if not path:
            return
        try:
            suffix = Path(path).suffix.lower()
            text = ""
            if suffix == ".csv":
                import csv
                with open(path, newline="", encoding="utf-8", errors="replace") as f:
                    text = "\n".join(",".join(row) for row in csv.reader(f))
            else:
                import importlib.util
                if importlib.util.find_spec("openpyxl") is not None:
                    import openpyxl
                    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
                    rows = []
                    for ws in wb.worksheets:
                        for row in ws.iter_rows(values_only=True):
                            rows.append(" ".join(str(c) for c in row if c is not None))
                    text = "\n".join(rows)
                elif importlib.util.find_spec("xlrd") is not None:
                    import xlrd
                    wb = xlrd.open_workbook(path)
                    rows = []
                    for sheet in wb.sheets():
                        for rx in range(sheet.nrows):
                            rows.append(" ".join(str(sheet.cell(rx, cx).value) for cx in range(sheet.ncols)))
                    text = "\n".join(rows)
                else:
                    self._on_log("Excel import requires 'openpyxl'. Install via pip.", "ERROR")
                    return
            emails = self._extract_emails_from_text(text)
            if emails:
                self.import_emails(emails)
                self._on_log(f"Excel import: found {len(emails)} email(s) in '{Path(path).name}'.", "SUCCESS")
            else:
                self._on_log(f"No email addresses found in '{Path(path).name}'.", "WARNING")
        except Exception as e:
            self._on_log(f"Excel import error: {e}", "ERROR")

    def _import_from_clipboard(self):
        """Extract email addresses from the current clipboard text."""
        from PySide6.QtGui import QGuiApplication
        text = QGuiApplication.clipboard().text()
        if not text.strip():
            self._on_log("Clipboard is empty.", "WARNING")
            return
        emails = self._extract_emails_from_text(text)
        if emails:
            self.import_emails(emails)
            self._on_log(f"Clipboard import: found {len(emails)} email(s).", "SUCCESS")
        else:
            self._on_log("No email addresses found in clipboard.", "WARNING")

    def _load_from_leads(self):
        from .load_leads_dialog import LoadLeadsDialog
        from .event_bridge import event_bus
        dialog = LoadLeadsDialog(self)
        if dialog.exec():
            emails = dialog.selected_emails
            if emails:
                self.import_emails(emails)
                event_bus.emit(
                    "toast.show",
                    title="Leads Loaded",
                    subtitle=f"Imported {len(emails)} emails into the broadcast queue.",
                    type="success"
                )

    def import_emails(self, emails: list[str]):
        """Public API for MainWindow to push leads here."""
        if not emails: return
        clean_new = [e.strip() for e in emails if e.strip()]
        current = self._get_recipients()
        combined = list(dict.fromkeys(current + clean_new))
        
        self._set_recipients(combined)
        self._on_log(f"Imported {len(clean_new)} lead(s). Total recipients: {len(combined)}", "SUCCESS")

    def _send_test(self):
        recs = self._get_recipients()
        if not recs: return self._on_log("No recipients in queue.", "ERROR")
        self._log(f"Executing test broadcast to {recs[0]}...")
        self._set_sending_state(True)
        threading.Thread(target=self._worker_send, args=([recs[0]],), daemon=True).start()

    def _send_all(self):
        recs = self._get_recipients()
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
        self._btn_continue.setEnabled(not sending)
        self._status_badge.setText("SENDING" if sending else "READY")

    def _log(self, text: str, level: str = "INFO"):
        self._signals.log.emit(text, level)

    def _worker_send(self, recipients: list[str]):
        self._error_vault.clear()
        sent = 0; failed = 0; total = len(recipients)
        try: 
            raw_val = int(self._interval_input.text().strip())
            interval = max(15, raw_val)
            if raw_val < 15:
                self._log(f"Enforcing minimum interval of 15 seconds (was {raw_val}s).", "WARNING")
        except: 
            interval = 30

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
            
            # ── Robust Sending Logic ──
            try:
                msg = self._build_message(rec)
                if self._stop_requested: break
                
                # Proactively ensure connection BEFORE sending
                try:
                    self._ensure_smtp_connection()
                except (smtplib.SMTPServerDisconnected, socket.error):
                    self._log(f"Connection lost. Reconnecting for {rec}...", "WARNING")
                    if self._active_server:
                        try: self._active_server.close()
                        except: pass
                    time.sleep(2) # Prevent rapid-fire reconnection
                    self._active_server = self._create_smtp_connection()
                    self._log("Reconnected successfully.", "SUCCESS")

                # Actual Transmission
                self._active_server.send_message(msg)
                sent += 1
                self._successful_emails.append(rec)
                self._log(f"Sent to {rec} ({i+1}/{total})", "INFO")

            except Exception as e:
                if self._stop_requested: break
                
                # If we fail here, the connection might be truly dead or the recipient is invalid
                failed += 1
                self._error_vault[rec] = str(e)
                err_short = str(e).splitlines()[0][:60] + "..." if len(str(e)) > 60 else str(e)
                
                # Check if it was a disconnection we couldn't recover from in time
                if "Server not connected" in err_short or "closed" in err_short.lower():
                    self._log(f"Connection error for {rec}: {err_short}. Re-initializing for next recipient.", "ERROR")
                    self._active_server = None # Force re-init on next loop
                else:
                    self._on_log(f"Error for {rec}: <a href='err:{rec}' style='color: #FF453A; text-decoration: underline;'>{err_short} (Details)</a>", "ERROR")
            
            self._signals.progress.emit(i+1, total)
            if i < total - 1 and not self._stop_requested:
                time.sleep(interval)

        try: 
            if self._active_server:
                self._active_server.quit()
        except: pass
        self._active_server = None
        self._signals.finished.emit(sent, failed, self._stop_requested)

    def _on_continue(self):
        if self._sending:
            self._on_log("Broadcast already in progress.", "WARNING")
            return
            
        all_recs = self._get_recipients()
        # Filter out those already successfully sent
        remaining = [e for e in all_recs if e not in self._successful_emails]
        
        if not remaining:
            self._on_log("No unsent emails remaining in queue.", "SUCCESS")
            return
            
        msg = f"Resuming broadcast. Skipping {len(all_recs) - len(remaining)} sent. {len(remaining)} pending."
        self._on_log(msg, "INFO")
        self._set_sending_state(True)
        threading.Thread(target=self._worker_send, args=(remaining,), daemon=True).start()

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
        if not host:
            raise ValueError("SMTP Host is required. Please check your settings.")
            
        port_txt = self._smtp_port.text().strip()
        try:
            port = int(port_txt)
        except ValueError:
            raise ValueError(f"Invalid SMTP Port: '{port_txt}'. Must be a number.")
            
        timeout = 60
        try:
            if self._ssl_switch.isChecked():
                self._signals.log.emit(f"Connecting via Implicit SSL to {host}:{port}...", "INFO")
                # Port 465 usually
                server = smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=timeout)
                server.ehlo()
            else:
                self._signals.log.emit(f"Connecting to {host}:{port}...", "INFO")
                server = smtplib.SMTP(host, port, timeout=timeout)
                server.ehlo()
                if self._tls_switch.isChecked():
                    self._signals.log.emit("Upgrading to STARTTLS...", "INFO")
                    # Port 587/25 usually
                    server.starttls(context=ssl.create_default_context())
                    server.ehlo()
                    
            if self._auth_switch.isChecked():
                user = self._smtp_user.text().strip()
                self._signals.log.emit(f"Authenticating as {user}...", "INFO")
                server.login(user, self._smtp_pass.text().strip())
                
            return server
            
        except socket.timeout:
            raise Exception("Connection timed out. Check your host/port and firewall settings.")
        except ssl.SSLError as e:
            raise Exception(f"SSL/TLS Handshake failed: {e}. Ensure you are using the correct port for the selected security protocol.")
        except ConnectionRefusedError:
            raise Exception(f"Connection refused. Ensure the SMTP server is reachable and the port is open.")
        except smtplib.SMTPConnectError as e:
            raise Exception(f"Failed to connect to SMTP server: {e}")
        except smtplib.SMTPAuthenticationError as e:
            raise Exception(f"Authentication failed: {e}")
        except Exception as e:
            # Fallback for other errors like 'Connection unexpectedly closed'
            err_msg = str(e)
            if not err_msg:
                err_msg = type(e).__name__
            raise Exception(f"{err_msg}")

    def _ensure_smtp_connection(self):
        """Verify the connection is still alive, otherwise raise SMTPServerDisconnected."""
        if not self._active_server:
            raise smtplib.SMTPServerDisconnected("No active connection")
        try:
            # noop() is the standard way to check if the session is still valid
            status = self._active_server.noop()
            if not (isinstance(status, tuple) and status[0] and 200 <= int(status[0]) < 400):
                raise smtplib.SMTPServerDisconnected(f"SMTP session invalid (status {status[0]})")
        except (smtplib.SMTPServerDisconnected, socket.error, ssl.SSLError) as e:
            # Explicitly catch socket and SSL errors as they imply a dead connection
            raise smtplib.SMTPServerDisconnected(str(e))
        except Exception as e:
            # Fallback for other potential issues
            raise smtplib.SMTPServerDisconnected(f"Session check failed: {e}")

    def _save_fields(self):
        if getattr(self, '_is_restoring', False):
            return
            
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
            email_recipients="\n".join(self._get_recipients())
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
        if s.email_recipients:
            self._set_recipients(s.email_recipients.split("\n"))
        else:
            self._on_recipients_changed()

    def _on_recipients_changed(self):
        """Updates the numeric badge and persists the updated list."""
        count = self._recipient_list.count()
        self._rec_count.setText(f"{count} EMAIL(S)")
        if count == 0:
            self._rec_stack.setCurrentWidget(self._rec_empty)
        else:
            self._rec_stack.setCurrentWidget(self._recipient_list)
        self._save_fields()


    # End of class
