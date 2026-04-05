"""
ZUGZWANG - Load Leads Dialog (Improvement 8)
Allows the user to query the lead database with optional filters and
populate the email recipient queue in the Email Sender page.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel,
    QPushButton, QVBoxLayout, QWidget,
)
from qfluentwidgets import ComboBox, LineEdit


class LoadLeadsDialog(QDialog):
    """
    Queries app_memory.db for leads with optional source/city filters
    and returns a list of email addresses.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(460)
        self._drag_pos = None
        self.selected_emails: list[str] = []

        container = QFrame(self)
        container.setObjectName("LoadLeadsContainer")
        container.setStyleSheet("""
            QFrame#LoadLeadsContainer {
                background: #1C1C1E;
                border: 1px solid #3A3A3C;
                border-radius: 16px;
            }
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 28, 28, 24)
        layout.setSpacing(16)

        # Header
        title = QLabel("Load From Leads")
        title.setStyleSheet(
            "color: #FFFFFF; font-family: 'PT Root UI', sans-serif; "
            "font-size: 20px; font-weight: 700; background: transparent; border: none;"
        )
        layout.addWidget(title)

        sub = QLabel("Filter your lead database to select recipient emails.")
        sub.setStyleSheet(
            "color: #8E8E93; font-family: 'PT Root UI', sans-serif; "
            "font-size: 12px; background: transparent; border: none;"
        )
        sub.setWordWrap(True)
        layout.addWidget(sub)

        divider1 = QFrame()
        divider1.setFixedHeight(1)
        divider1.setStyleSheet("background: #3A3A3C; border: none;")
        layout.addWidget(divider1)

        # Source filter
        src_lbl = self._field_label("SOURCE")
        layout.addWidget(src_lbl)
        self._source_combo = ComboBox()
        self._source_combo.addItems(["All Sources", "Google Maps", "Jobsuche", "Ausbildung.de", "Aubi-Plus"])
        self._source_combo.setStyleSheet(self._combo_style())
        self._source_combo.setFixedHeight(38)
        layout.addWidget(self._source_combo)
        self._source_combo.currentIndexChanged.connect(self._update_count)

        # City filter
        city_lbl = self._field_label("CITY (optional)")
        layout.addWidget(city_lbl)
        self._city_input = LineEdit()
        self._city_input.setPlaceholderText("e.g. Berlin, München…")
        self._city_input.setFixedHeight(38)
        self._city_input.setStyleSheet("""
            QLineEdit {
                background: #2C2C2E; border: 1px solid #3A3A3C;
                border-radius: 8px; color: #FFFFFF;
                font-family: 'PT Root UI', sans-serif; font-size: 13px;
                padding: 0 12px;
            }
            QLineEdit:focus { border-color: #0A84FF; }
        """)
        layout.addWidget(self._city_input)
        self._city_input.textChanged.connect(lambda _: QTimer.singleShot(300, self._update_count))

        # Email-only toggle
        self._email_only_row = QHBoxLayout()
        self._email_only_row.setContentsMargins(0, 0, 0, 0)
        from src.ui.components import MacSwitch
        self._email_switch = MacSwitch()
        self._email_switch.setChecked(True)
        self._email_switch.toggled.connect(self._update_count)
        self._email_only_row.addWidget(self._email_switch)
        email_lbl = QLabel("Leads with email only")
        email_lbl.setStyleSheet("color: #AEAEB2; font-family: 'PT Root UI', sans-serif; font-size: 13px; background: transparent; border: none;")
        self._email_only_row.addWidget(email_lbl)
        self._email_only_row.addStretch(1)
        layout.addLayout(self._email_only_row)

        # Count preview
        self._count_lbl = QLabel("Counting…")
        self._count_lbl.setStyleSheet(
            "color: #0A84FF; font-family: 'PT Root UI', sans-serif; "
            "font-size: 12px; font-weight: 600; background: transparent; border: none;"
        )
        layout.addWidget(self._count_lbl)

        divider2 = QFrame()
        divider2.setFixedHeight(1)
        divider2.setStyleSheet("background: #3A3A3C; border: none;")
        layout.addWidget(divider2)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        cancel_btn = QPushButton("CANCEL")
        cancel_btn.setFixedHeight(38)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: #2C2C2E; border: 1px solid #3A3A3C; border-radius: 8px;
                color: #AEAEB2; font-family: 'PT Root UI', sans-serif;
                font-size: 12px; font-weight: 600; letter-spacing: 1.2px;
            }
            QPushButton:hover { background: #3A3A3C; color: #FFFFFF; }
        """)
        cancel_btn.clicked.connect(self.reject)

        self._load_btn = QPushButton("LOAD LEADS")
        self._load_btn.setFixedHeight(38)
        self._load_btn.setCursor(Qt.PointingHandCursor)
        self._load_btn.setStyleSheet("""
            QPushButton {
                background: #0A84FF; border: none; border-radius: 8px;
                color: #FFFFFF; font-family: 'PT Root UI', sans-serif;
                font-size: 12px; font-weight: 700; letter-spacing: 1.2px;
            }
            QPushButton:hover { background: #409CFF; }
            QPushButton:disabled { background: #2C2C2E; color: #636366; }
        """)
        self._load_btn.clicked.connect(self._on_load)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._load_btn)
        layout.addLayout(btn_row)

        self.adjustSize()
        if parent:
            center = parent.geometry().center()
            self.move(center.x() - self.width() // 2, center.y() - self.height() // 2)

        QTimer.singleShot(100, self._update_count)

    def _field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "color: #636366; font-family: 'PT Root UI', sans-serif; "
            "font-size: 10px; font-weight: 600; letter-spacing: 1px; "
            "background: transparent; border: none;"
        )
        return lbl

    def _combo_style(self) -> str:
        return """
            QComboBox {
                background: #2C2C2E; border: 1px solid #3A3A3C;
                border-radius: 8px; color: #FFFFFF;
                font-family: 'PT Root UI', sans-serif; font-size: 13px;
                padding: 0 12px;
            }
            QComboBox::drop-down { border: none; width: 24px; }
            QComboBox:focus { border-color: #0A84FF; }
        """

    def _update_count(self) -> None:
        """Query the DB with current filters and update count label."""
        try:
            emails, total = self._query_emails(count_only=True)
            if total == 0:
                self._count_lbl.setText("No matching leads found")
                self._count_lbl.setStyleSheet(
                    "color: #FF453A; font-family: 'PT Root UI', sans-serif; "
                    "font-size: 12px; font-weight: 600; background: transparent; border: none;"
                )
                self._load_btn.setEnabled(False)
            else:
                self._count_lbl.setText(f"{total} lead{'' if total == 1 else 's'} will be loaded")
                self._count_lbl.setStyleSheet(
                    "color: #30D158; font-family: 'PT Root UI', sans-serif; "
                    "font-size: 12px; font-weight: 600; background: transparent; border: none;"
                )
                self._load_btn.setEnabled(True)
        except Exception as e:
            self._count_lbl.setText(f"DB error: {e}")
            self._load_btn.setEnabled(False)

    def _query_emails(self, count_only: bool = False):
        """Query leads from the DB applying current filters. Returns (email_list, total)."""
        import sqlite3
        from src.core.config import get_memory_db_path
        
        source_map = {
            "All Sources": None,
            "Google Maps": "maps",
            "Jobsuche": "jobsuche",
            "Ausbildung.de": "ausbildung",
            "Aubi-Plus": "aubiplus",
        }
        source_filter = source_map.get(self._source_combo.currentText())
        city_filter = self._city_input.text().strip()
        email_only = self._email_switch.isChecked()

        db_path = str(get_memory_db_path())
        conn = sqlite3.connect(db_path)
        try:
            query = "SELECT email FROM leads WHERE 1=1"
            params = []
            if email_only:
                query += " AND email IS NOT NULL AND email != ''"
            if source_filter:
                legacy_map = {
                    "maps": "google_maps",
                    "ausbildung": "ausbildung_de",
                    "aubiplus": "aubiplus_de"
                }
                if source_filter in legacy_map:
                    query += " AND (source_type = ? OR source_type = ?)"
                    params.extend([source_filter, legacy_map[source_filter]])
                else:
                    query += " AND source_type = ?"
                    params.append(source_filter)
            if city_filter:
                query += " AND city LIKE ?"
                params.append(f"%{city_filter}%")
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            emails = [r[0] for r in rows if r[0]]
            return emails, len(emails)
        finally:
            conn.close()

    def _on_load(self) -> None:
        try:
            self.selected_emails, _ = self._query_emails()
            self.accept()
        except Exception as e:
            self._count_lbl.setText(f"Error: {e}")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()
