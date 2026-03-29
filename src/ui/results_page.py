"""
ZUGZWANG - Results Page
Modern 2030 Edition live results data grid with high-fidelity side panel.
"""

from __future__ import annotations

import queue
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QModelIndex, Qt, QSortFilterProxyModel, QTimer, Signal, QSize, QPoint
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut, QStandardItem, QStandardItemModel, QColor, QBrush, QFont, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QVBoxLayout, QWidget, QHeaderView, QFileDialog, QSplitter, QTableView, QFrame,
    QLabel, QPushButton, QStyledItemDelegate, QStyleOptionViewItem, QStyle, QGraphicsDropShadowEffect, QSizePolicy
)

from qfluentwidgets import (
    TableWidget, PushButton, PrimaryPushButton, TransparentPushButton,
    SearchLineEdit, ComboBox, ProgressBar, TitleLabel, SubtitleLabel, setThemeColor,
    BodyLabel, CaptionLabel, StrongBodyLabel, IconWidget, FluentIcon, SimpleCardWidget,
    ElevatedCardWidget, InfoBadge, RoundMenu, Action, MenuAnimationType, ScrollArea
)

from .icons import load_icon
from ..core.config import config_manager, get_exports_dir, get_projects_dir
from ..core.events import event_bus
from ..core.models import LeadRecord
from .theme import Theme
from ..services.export_service import ExportService


TABLE_COLUMNS = [
    ("company_name", "Company", 200),
    ("job_title", "Job / Category", 160),
    ("email", "Email", 190),
    ("phone", "Phone", 130),
    ("city", "City", 100),
    ("source_type", "Source", 90),
    ("linkedin", "LinkedIn", 120),
    ("status", "Status", 100),
]


class RowSelectionDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        opts = QStyleOptionViewItem(option)
        self.initStyleOption(opts, index)
        
        is_selected = option.state & QStyle.State_Selected
        is_hovered = option.state & QStyle.State_MouseOver
        
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        rect = opts.rect
        
        if is_selected:
            bg_color = QColor(10, 132, 255, 24) # #0A84FF18
            painter.fillRect(rect, bg_color)
            if index.column() == 0:
                painter.setBrush(QColor("#0A84FF"))
                painter.setPen(Qt.NoPen)
                painter.drawRect(rect.left(), rect.top(), 2, rect.height())
        elif is_hovered:
            painter.fillRect(rect, QColor("#2C2C2E"))

        # Manual Text Rendering
        text = str(index.data() or "")
        
        if index.column() == 2: # Email
            font = QFont("PT Root UI", 9)
            painter.setFont(font)
            if text and text != "—":
                painter.setPen(QColor("#0A84FF"))
            else:
                painter.setPen(QColor("#48484A"))
            fm = painter.fontMetrics()
            elided_text = fm.elidedText(text, Qt.ElideRight, rect.width() - 28)
            painter.drawText(rect.adjusted(14, 0, -14, 0), Qt.AlignVCenter | Qt.AlignLeft, elided_text)
            
        elif index.column() == 5: # Source
            if text and text != "—":
                font = QFont("PT Root UI", 9)
                font.setWeight(QFont.Bold)
                painter.setFont(font)
                fm = painter.fontMetrics()
                text_rect = fm.boundingRect(text)
                
                pill_rect = text_rect.adjusted(-6, -3, 6, 3)
                pill_rect.moveCenter(rect.center())
                pill_rect.moveLeft(rect.left() + 14)
                
                painter.setBrush(QColor("#2C2C2E"))
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(pill_rect, 6, 6)
                
                painter.setPen(QColor("#FFFFFF"))
                painter.drawText(pill_rect, Qt.AlignCenter, text)
            else:
                font = QFont("PT Root UI", 10)
                painter.setFont(font)
                painter.setPen(QColor("#48484A"))
                painter.drawText(rect.adjusted(14, 0, -14, 0), Qt.AlignVCenter | Qt.AlignLeft, "—")
        else:
            font = QFont("PT Root UI", 10)
            painter.setFont(font)
            if text == "—":
                painter.setPen(QColor("#48484A"))
            elif index.column() in (1, 4, 6): # Secondary columns
                painter.setPen(QColor("#8E8E93"))
            else:
                painter.setPen(QColor("#FFFFFF"))
                
            fm = painter.fontMetrics()
            elided_text = fm.elidedText(text, Qt.ElideRight, rect.width() - 28)
            painter.drawText(rect.adjusted(14, 0, -14, 0), Qt.AlignVCenter | Qt.AlignLeft, elided_text)

        painter.restore()

class ResultsTableModel(QStandardItemModel):
    def __init__(self):
        super().__init__(0, len(TABLE_COLUMNS))
        self.setHorizontalHeaderLabels([column[1] for column in TABLE_COLUMNS])
        self._records: list[LeadRecord] = []
        self._record_index_by_id: dict[str, int] = {}

    def add_record(self, record: LeadRecord) -> None:
        record.id = record.stable_id()
        existing_row = self._record_index_by_id.get(record.id)
        if existing_row is not None:
            merged = self._merge_records(self._records[existing_row], record)
            self._records[existing_row] = merged
            self._replace_row(existing_row, merged)
            return

        self._record_index_by_id[record.id] = len(self._records)
        self._records.append(record)
        self.appendRow(self._build_row_items(record))

    def get_record(self, row: int) -> Optional[LeadRecord]:
        return self._records[row] if 0 <= row < len(self._records) else None

    def get_all_records(self) -> list[LeadRecord]:
        return list(self._records)

    def clear_records(self) -> None:
        self._records.clear()
        self._record_index_by_id.clear()
        self.removeRows(0, self.rowCount())

    def _replace_row(self, row: int, record: LeadRecord) -> None:
        for col, item in enumerate(self._build_row_items(record)):
            self.setItem(row, col, item)

    def _merge_records(self, existing: LeadRecord, incoming: LeadRecord) -> LeadRecord:
        merged = existing.to_dict()
        for field, value in incoming.to_dict().items():
            if value not in (None, ""):
                merged[field] = value
        merged["id"] = existing.id or incoming.id
        return LeadRecord.from_dict(merged)

    def _build_row_items(self, record: LeadRecord) -> list[QStandardItem]:
        row_items: list[QStandardItem] = []
        for field, _, _ in TABLE_COLUMNS:
            try:
                if field == "source_type":
                    st = str(record.source_type).lower() if record.source_type else ""
                    if "maps" in st: value = "Maps"
                    elif "ausbildung" in st: value = "Ausbildung.de"
                    elif "aubiplus" in st: value = "Aubi-Plus"
                    else: value = "Jobsuche"
                elif field == "status":
                    if record.email:
                        value = "VERIFIED"
                    elif record.website:
                        value = "PARTIAL"
                    else:
                        value = "COLD"
                elif field == "job_title":
                    value = getattr(record, "job_title", "") or getattr(record, "category", "") or "—"
                else:
                    value = getattr(record, field, "") or "—"

                item = QStandardItem(str(value))
                item.setEditable(False)
                row_items.append(item)
            except Exception:
                row_items.append(QStandardItem("—"))
        return row_items

class FilterMenuItem(QWidget):
    """Custom menu item with right-aligned checkmark."""
    clicked = Signal(str, int) # text, index

    def __init__(self, text: str, index: int, is_selected: bool = False, parent=None):
        super().__init__(parent)
        self.text = text
        self.index = index
        self.is_selected = is_selected
        self.setFixedHeight(32)
        self.setCursor(Qt.PointingHandCursor)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(0)
        
        self.label = QLabel(text)
        weight = "600" if is_selected else "400"
        color = "#0A84FF" if is_selected else "#AEAEB2"
        self.label.setStyleSheet(f"color: {color}; font-family: 'PT Root UI'; font-size: 13px; font-weight: {weight}; background: transparent; border: none;")
        layout.addWidget(self.label)
        
        layout.addStretch()
        
        if is_selected:
            from .icons import load_icon
            check = IconWidget(FluentIcon.COMPLETED)
            check.setFixedSize(12, 12)
            check.setStyleSheet("color: #0A84FF; background: transparent; border: none;")
            layout.addWidget(check)

        self.setAttribute(Qt.WA_Hover)
        self._update_style(False)

    def _update_style(self, hovering: bool):
        bg = "#3A3A3C" if hovering else "transparent"
        text_color = "white" if hovering else ("#0A84FF" if self.is_selected else "#AEAEB2")
        self.label.setStyleSheet(self.label.styleSheet().replace("#AEAEB2", text_color).replace("#0A84FF", text_color).replace("white", text_color))
        self.setStyleSheet(f"background: {bg}; border: none;")

    def enterEvent(self, event):
        self._update_style(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._update_style(False)
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.text, self.index)
        super().mouseReleaseEvent(event)

class FilterMenu(QFrame):
    """Custom popup menu for filter chips."""
    itemSelected = Signal(str, int)
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setObjectName("FilterMenu")
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumWidth(180)
        
        self.container = QFrame(self)
        self.container.setObjectName("MenuContainer")
        self.container.setStyleSheet("""
            QFrame#MenuContainer {
                background: #2C2C2E;
                border: 1px solid #3A3A3C;
                border-radius: 10px;
            }
        """)
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.container)
        
        self.content_layout = QVBoxLayout(self.container)
        self.content_layout.setContentsMargins(0, 6, 0, 6)
        self.content_layout.setSpacing(0)
        
        # Shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, 12)
        self.container.setGraphicsEffect(shadow)

    def add_item(self, text: str, index: int, is_selected: bool = False):
        item = FilterMenuItem(text, index, is_selected, self)
        item.clicked.connect(self._on_item_clicked)
        self.content_layout.addWidget(item)

    def add_divider(self):
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background: #3A3A3C; margin: 4px 0;")
        self.content_layout.addWidget(line)

    def add_placeholder(self, text: str):
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("color: #48484A; font-family: 'PT Root UI'; font-size: 12px; padding: 12px; background: transparent;")
        self.content_layout.addWidget(lbl)

    def _on_item_clicked(self, text: str, index: int):
        self.itemSelected.emit(text, index)
        self.close()

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        super().keyPressEvent(event)

class FilterChip(QPushButton):
    """
    Premium macOS-style filter button with rotating chevron.
    """
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setFixedHeight(34)
        self.setCursor(Qt.PointingHandCursor)
        self._is_active = False
        self._is_open = False
        self._update_style()

    def set_open(self, is_open: bool):
        self._is_open = is_open
        self._update_style()

    def set_active(self, active: bool):
        self._is_active = active
        self._update_style()

    def _update_style(self):
        # Spec override: Open state takes priority
        is_blue = self._is_open or self._is_active
        color = "#0A84FF" if is_blue else "#FFFFFF"
        border_color = "#0A84FF" if is_blue else "#3A3A3C"
        chevron_color = "#0A84FF" if is_blue else "#8E8E93"
        
        self.setStyleSheet(f"""
            QPushButton {{
                background: #2C2C2E;
                border: 1px solid {border_color};
                border-radius: 8px;
                color: {color};
                font-family: 'PT Root UI', sans-serif;
                font-size: 12px;
                font-weight: 500;
                text-transform: uppercase;
                letter-spacing: 0.8px;
                padding: 0 12px;
                text-align: left;
                qproperty-iconSize: 10px 10px;
                spacing: 6px;
            }}
            QPushButton:hover {{
                background: #3A3A3C;
            }}
        """)
        
        from .icons import load_icon
        chevron = FluentIcon.CHEVRON_DOWN_MED.icon(color=chevron_color)
        self.setIcon(chevron)
        self.setIconSize(QSize(10, 10))
        self.setLayoutDirection(Qt.RightToLeft) 
        
        # Rotation logic (handled by QIcon in standard Qt, but we rotate the arrow manually if needed)
        # However, CHEVRON_DOWN_MED is already down. For rotation, we could use a custom painter
        # but the simplest is just to change icon if needed or use a transformation.
        # QFluentWidgets doesn't always support easy rotation in QSS.
        # We'll just stick to the correct icon for now.


class LeadFilterProxy(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._source_filter = 0
        self._status_filter = 0
        self._city_filter = "All Cities"
        self._date_filter = 0  
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.setFilterKeyColumn(-1)

    def set_source_filter(self, index: int):
        self._source_filter = index
        self.invalidateFilter()

    def set_status_filter(self, index: int):
        self._status_filter = index
        self.invalidateFilter()

    def set_city_filter(self, city: str):
        self._city_filter = city
        self.invalidateFilter()

    def set_date_filter(self, index: int):
        self._date_filter = index
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        if model is None:
            return True
        record = model.get_record(source_row)
        if record is None:
            return False

        filter_text = self.filterRegularExpression().pattern()
        if filter_text:
            searchable = " ".join(
                [
                    record.company_name or "",
                    record.job_title or "",
                    record.email or "",
                    record.website or "",
                    record.phone or "",
                    record.city or "",
                    record.country or "",
                    record.address or "",
                ]
            ).lower()
            if filter_text.lower() not in searchable:
                return False

        if self._source_filter != 0:
            source_val = (record.source_type or "").lower()
            if self._source_filter == 1 and "maps" not in source_val: return False
            if self._source_filter == 2 and "jobsuche" not in source_val: return False
            if self._source_filter == 3 and "ausbildung" not in source_val: return False
            if self._source_filter == 4 and "aubiplus" not in source_val: return False

        if self._status_filter != 0:
            has_email = bool(record.email)
            if self._status_filter == 1 and not has_email:
                return False
            if self._status_filter == 2 and has_email:
                return False

        if self._city_filter != "All Cities":
            if (record.city or "").lower() != self._city_filter.lower():
                return False

        if self._date_filter != 0:
            if not record.scraped_at:
                return False
            try:
                dt = record.scraped_at
                if isinstance(dt, str):
                    dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
                
                now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
                delta = (now - dt).total_seconds()
                
                # 0: All Time
                # 1: Last Minute
                # 2: Last Hour
                # 3: Last 3 Hours
                # 4: Last 6 Hours
                # 5: Last 12 Hours
                # 6: Today
                # 7: Yesterday
                # 8: Last 7 Days
                # 9: Last 30 Days

                if self._date_filter == 1: return delta <= 60
                if self._date_filter == 2: return delta <= 3600
                if self._date_filter == 3: return delta <= 10800
                if self._date_filter == 4: return delta <= 21600
                if self._date_filter == 5: return delta <= 43200
                
                if self._date_filter == 6: # Today
                    return dt.date() == now.date()
                
                if self._date_filter == 7: # Yesterday
                    from datetime import timedelta
                    return dt.date() == (now.date() - timedelta(days=1))
                
                if self._date_filter == 8: return delta <= 7 * 86400
                if self._date_filter == 9: return delta <= 30 * 86400
                
            except Exception:
                pass

        return True


class DetailPanel(QFrame):
    close_requested = Signal()

    # ── Font stacks used across elements ──
    _FONT_DISPLAY = "'PT Root UI', -apple-system, BlinkMacSystemFont, sans-serif"
    _FONT_TEXT    = "'PT Root UI', -apple-system, BlinkMacSystemFont, sans-serif"
    _TRANSITION   = "all 150ms cubic-bezier(0.4,0,0.2,1)"

    def __init__(self):
        super().__init__()
        self.setFixedWidth(300)
        self.setObjectName("DetailPanel")
        self.setStyleSheet("QFrame#DetailPanel { background: #1C1C1E; border: none; }")
        self._current_record: Optional[LeadRecord] = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── HERO SECTION ────────────────────────────────────────────────────
        self._hero_card = QFrame()
        self._hero_card.setObjectName("HeroCard")
        self._hero_card.setStyleSheet("""
            QFrame#HeroCard {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #242426,
                    stop:1 #1C1C1E);
                border: none;
                border-bottom: 1px solid rgba(255,255,255,0.06);
            }
        """)
        hero_l = QVBoxLayout(self._hero_card)
        hero_l.setContentsMargins(20, 0, 20, 24)
        hero_l.setSpacing(0)
        hero_l.setAlignment(Qt.AlignHCenter)

        # Top-right icon bar
        icon_bar = QHBoxLayout()
        icon_bar.setContentsMargins(0, 14, 0, 0)
        icon_bar.setSpacing(4)
        icon_bar.addStretch(1)

        _btn_css = (
            "QPushButton { border: none; background: transparent; color: #48484A; padding: 0; border-radius: 8px; }"
            "QPushButton:hover { color: #FFFFFF; background: rgba(255,255,255,0.07); }"
        )
        self._star_btn = QPushButton()
        self._star_btn.setIcon(FluentIcon.HEART.qicon())
        self._star_btn.setIconSize(QSize(16, 16))
        self._star_btn.setFixedSize(30, 30)
        self._star_btn.setStyleSheet(_btn_css)
        icon_bar.addWidget(self._star_btn)

        self._close_btn = QPushButton()
        self._close_btn.setIcon(FluentIcon.CLOSE.qicon())
        self._close_btn.setIconSize(QSize(16, 16))
        self._close_btn.setFixedSize(30, 30)
        self._close_btn.setStyleSheet(_btn_css)
        self._close_btn.clicked.connect(self.close_requested.emit)
        icon_bar.addWidget(self._close_btn)
        hero_l.addLayout(icon_bar)

        # Avatar — large circular with vivid gradient
        hero_l.addSpacing(10)
        self._avatar = QFrame()
        self._avatar.setFixedSize(76, 76)
        self._avatar.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0A84FF, stop:0.6 #3D7EFF, stop:1 #5E5CE6);
                border-radius: 38px;
                border: 2.5px solid rgba(255,255,255,0.12);
            }
        """)
        av_l = QVBoxLayout(self._avatar)
        av_l.setContentsMargins(0, 0, 0, 0)
        self._avatar_lbl = QLabel("?")
        self._avatar_lbl.setAlignment(Qt.AlignCenter)
        self._avatar_lbl.setStyleSheet(
            f"color: #FFFFFF; font-family: {self._FONT_DISPLAY}; font-size: 28px; font-weight: 700; "
            "background: transparent; border: none;"
        )
        av_l.addWidget(self._avatar_lbl)
        av_wrapper = QHBoxLayout()
        av_wrapper.setContentsMargins(0, 0, 0, 0)
        av_wrapper.addStretch(1)
        av_wrapper.addWidget(self._avatar)
        av_wrapper.addStretch(1)
        hero_l.addLayout(av_wrapper)

        hero_l.addSpacing(14)

        # Company name
        self._company = QLabel("Company Name")
        self._company.setAlignment(Qt.AlignCenter)
        self._company.setWordWrap(True)
        self._company.setStyleSheet(
            f"color: #FFFFFF; font-family: {self._FONT_DISPLAY}; font-size: 16px; font-weight: 700; "
            "line-height: 1.3; letter-spacing: -0.3px; background: transparent; border: none;"
        )
        hero_l.addWidget(self._company)

        hero_l.addSpacing(6)

        # Role subtitle
        self._job = QLabel("Role")
        self._job.setAlignment(Qt.AlignCenter)
        self._job.setWordWrap(True)
        self._job.setStyleSheet(
            f"color: #8E8E93; font-family: {self._FONT_TEXT}; font-size: 12px; font-weight: 500; "
            "background: transparent; border: none;"
        )
        hero_l.addWidget(self._job)

        hero_l.addSpacing(12)

        # Source badge — pill style
        self._source_badge = QLabel("JOBSUCHE")
        self._source_badge.setAlignment(Qt.AlignCenter)
        self._source_badge.setFixedHeight(22)
        self._source_badge.setStyleSheet(
            f"color: #0A84FF; background: rgba(10,132,255,0.12); border-radius: 11px; "
            f"padding: 2px 12px; font-family: {self._FONT_TEXT}; font-size: 9px; font-weight: 700; "
            "letter-spacing: 1.4px; border: none;"
        )
        badge_wrapper = QHBoxLayout()
        badge_wrapper.setContentsMargins(0, 0, 0, 0)
        badge_wrapper.addStretch(1)
        badge_wrapper.addWidget(self._source_badge)
        badge_wrapper.addStretch(1)
        hero_l.addLayout(badge_wrapper)

        layout.addWidget(self._hero_card)

        # ── ACTIONS ─────────────────────────────────────────────────────────
        self._action_strip = QWidget()
        self._action_strip.setStyleSheet("QWidget { background: #1C1C1E; border: none; }")
        act_l = QHBoxLayout(self._action_strip)
        act_l.setContentsMargins(16, 14, 16, 4)
        act_l.setSpacing(8)

        self._btn_site = QPushButton("  VISIT WEBSITE")
        self._btn_site.setIcon(FluentIcon.GLOBE.qicon())
        self._btn_site.setIconSize(QSize(13, 13))
        self._btn_site.setFixedHeight(38)
        self._btn_site.setCursor(Qt.PointingHandCursor)
        self._btn_site.setStyleSheet(f"""
            QPushButton {{
                background: #0A84FF;
                border: none;
                border-radius: 10px;
                color: #FFFFFF;
                font-family: {self._FONT_DISPLAY};
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 1.4px;
                text-transform: uppercase;
                padding: 0 16px;
            }}
            QPushButton:hover {{ background: #409CFF; }}
            QPushButton:pressed {{ background: #005CC8; }}
            QPushButton:disabled {{
                background: rgba(10,132,255,0.10);
                color: #3A3A3C;
            }}
        """)
        act_l.addWidget(self._btn_site)
        layout.addWidget(self._action_strip)

        # ── CONTACT ROWS ─────────────────────────────────────────────────────
        self._scroll = ScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: #1C1C1E; border: none;")
        sc_l = QVBoxLayout(scroll_content)
        sc_l.setContentsMargins(16, 12, 16, 24)
        sc_l.setSpacing(8)

        # Section label
        contacts_lbl = QLabel("CONTACT INFO")
        contacts_lbl.setStyleSheet(
            f"color: #48484A; font-family: {self._FONT_TEXT}; font-size: 9px; font-weight: 700; "
            "letter-spacing: 1.8px; background: transparent; border: none; padding: 4px 2px 6px 2px;"
        )
        sc_l.addWidget(contacts_lbl)

        # All 4 rows in one rounded container
        self._contacts_box = QFrame()
        self._contacts_box.setObjectName("ContactsBox")
        self._contacts_box.setStyleSheet("""
            QFrame#ContactsBox {
                background: #242426;
                border-radius: 12px;
                border: none;
            }
        """)
        self._contacts_layout = QVBoxLayout(self._contacts_box)
        self._contacts_layout.setContentsMargins(0, 0, 0, 0)
        self._contacts_layout.setSpacing(0)

        self.email_row    = self._create_row("EMAIL",   FluentIcon.MAIL,  is_last=False)
        self.phone_row    = self._create_row("PHONE",   FluentIcon.PHONE, is_last=False)
        self.website_row  = self._create_row("WEBSITE", FluentIcon.GLOBE, is_last=False)
        self.address_row  = self._create_row("ADDRESS", FluentIcon.HOME,  is_last=True)

        for row in [self.email_row, self.phone_row, self.website_row, self.address_row]:
            self._contacts_layout.addWidget(row)

        sc_l.addWidget(self._contacts_box)
        sc_l.addSpacing(10)

        # Social section label
        self._social_label = QLabel("SOCIAL")
        self._social_label.setStyleSheet(
            f"color: #48484A; font-family: {self._FONT_TEXT}; font-size: 9px; font-weight: 700; "
            "letter-spacing: 1.8px; background: transparent; border: none; padding: 4px 2px 6px 2px;"
        )
        self._social_label.hide()
        sc_l.addWidget(self._social_label)

        # Social rows
        self._social_box = QFrame()
        self._social_box.setObjectName("SocialBox")
        self._social_box.setStyleSheet("""
            QFrame#SocialBox {
                background: #242426;
                border-radius: 12px;
                border: none;
            }
        """)
        social_l = QVBoxLayout(self._social_box)
        social_l.setContentsMargins(0, 0, 0, 0)
        social_l.setSpacing(0)

        self.linkedin_row  = self._create_row("LINKEDIN",  FluentIcon.LINK, is_last=False)
        self.twitter_row   = self._create_row("TWITTER",   FluentIcon.LINK, is_last=False)
        self.instagram_row = self._create_row("INSTAGRAM", FluentIcon.LINK, is_last=True)
        for row in [self.linkedin_row, self.twitter_row, self.instagram_row]:
            social_l.addWidget(row)

        self._social_box.hide()
        sc_l.addWidget(self._social_box)
        sc_l.addStretch(1)

        self._scroll.setWidget(scroll_content)
        layout.addWidget(self._scroll, 1)

        # ── Placeholder ──────────────────────────────────────────────────────
        self._placeholder = QWidget()
        self._placeholder.setStyleSheet("QWidget { background: #1C1C1E; }")
        ph_l = QVBoxLayout(self._placeholder)
        ph_l.setAlignment(Qt.AlignCenter)
        ph_l.setSpacing(10)
        ph_icon = IconWidget(FluentIcon.PEOPLE)
        ph_icon.setFixedSize(40, 40)
        ph_icon.setStyleSheet("color: #2C2C2E;")
        ph_l.addWidget(ph_icon, 0, Qt.AlignCenter)
        ph_txt = QLabel("Select a lead")
        ph_txt.setStyleSheet(
            f"color: #48484A; font-family: {self._FONT_DISPLAY}; font-size: 13px; "
            "font-weight: 600; background: transparent; border: none;"
        )
        ph_l.addWidget(ph_txt, 0, Qt.AlignCenter)
        ph_sub = QLabel("Details will appear here")
        ph_sub.setStyleSheet(
            f"color: #3A3A3C; font-family: {self._FONT_TEXT}; font-size: 11px; "
            "font-weight: 400; background: transparent; border: none;"
        )
        ph_l.addWidget(ph_sub, 0, Qt.AlignCenter)
        layout.addWidget(self._placeholder)

    def _create_row(self, label_text: str, icon, is_last: bool = False):
        container = QFrame()
        divider_css = "" if is_last else "border-bottom: 1px solid rgba(255,255,255,0.04);"
        container.setStyleSheet(f"""
            QFrame {{
                background: transparent;
                border: none;
                {divider_css}
            }}
            QFrame:hover {{ background: rgba(255,255,255,0.03); }}
        """)
        row_l = QHBoxLayout(container)
        row_l.setContentsMargins(14, 10, 10, 10)
        row_l.setSpacing(12)

        # Icon
        icon_w = IconWidget(icon)
        icon_w.setFixedSize(16, 16)
        icon_w.setStyleSheet("color: #48484A; background: transparent; border: none;")
        row_l.addWidget(icon_w, 0, Qt.AlignTop)

        # Label + value stacked
        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        lbl = QLabel(label_text)
        lbl.setStyleSheet(
            f"color: #48484A; font-family: {self._FONT_TEXT}; font-size: 9px; "
            "font-weight: 700; letter-spacing: 1.2px; background: transparent; border: none;"
        )
        text_col.addWidget(lbl)

        val_label = QLabel("—")
        val_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        val_label.setWordWrap(True)
        val_label.setStyleSheet(
            f"color: #48484A; font-family: {self._FONT_TEXT}; font-size: 13px; "
            "font-weight: 400; background: transparent; border: none;"
        )
        text_col.addWidget(val_label)
        row_l.addLayout(text_col, 1)

        copy_btn = QPushButton()
        copy_btn.setIcon(FluentIcon.COPY.qicon())
        copy_btn.setIconSize(QSize(13, 13))
        copy_btn.setFixedSize(28, 28)
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.setStyleSheet("""
            QPushButton { border: none; background: transparent; color: #3A3A3C; border-radius: 6px; }
            QPushButton:hover { color: #0A84FF; background: rgba(10,132,255,0.10); }
        """)
        copy_btn.clicked.connect(lambda: self._copy_to_clipboard(val_label.text()))
        row_l.addWidget(copy_btn, 0, Qt.AlignVCenter)

        container.val_label = val_label
        container.copy_btn = copy_btn
        return container

    def _copy_to_clipboard(self, text: str):
        if text and text != "—":
            QGuiApplication.clipboard().setText(text)

    def show_placeholder(self):
        self._hero_card.hide()
        self._action_strip.hide()
        self._scroll.hide()
        self._placeholder.show()

    def show_record(self, record: LeadRecord):
        self._placeholder.hide()
        self._hero_card.show()
        self._action_strip.show()
        self._scroll.show()

        name = record.company_name or "Unknown Company"
        self._company.setText(name)
        self._avatar_lbl.setText(name[0].upper() if name else "?")

        job = record.job_title or record.category or "No description provided"
        self._job.setText(job)

        src = (record.source_type or "").lower()
        if "maps" in src:
            self._source_badge.setText("GOOGLE MAPS")
        elif "ausbildung" in src:
            self._source_badge.setText("AUSBILDUNG")
        elif "aubiplus" in src:
            self._source_badge.setText("AUBI-PLUS")
        else:
            self._source_badge.setText("JOBSUCHE")

        # Website button
        try: self._btn_site.clicked.disconnect()
        except: pass
        if record.website:
            self._btn_site.setEnabled(True)
            self._btn_site.clicked.connect(lambda: self._open_url(record.website or ""))
        else:
            self._btn_site.setEnabled(False)

        # Contact rows — white text for real values, #48484A for em-dash
        def _set(row, value):
            if value:
                row.val_label.setText(value)
                row.val_label.setStyleSheet(
                    f"color: #FFFFFF; font-family: {self._FONT_TEXT}; font-size: 13px; "
                    "font-weight: 400; background: transparent; border: none;"
                )
            else:
                row.val_label.setText("\u2014")
                row.val_label.setStyleSheet(
                    f"color: #48484A; font-family: {self._FONT_TEXT}; font-size: 13px; "
                    "font-weight: 400; background: transparent; border: none;"
                )

        _set(self.email_row,   record.email)
        _set(self.phone_row,   record.phone)
        _set(self.website_row, record.website)
        _set(self.address_row, record.address)

        # Social section — show only if any social data
        _set(self.linkedin_row,  record.linkedin)
        _set(self.twitter_row,   record.twitter)
        _set(self.instagram_row, record.instagram)
        has_social = any([record.linkedin, record.twitter, record.instagram])
        self._social_box.setVisible(has_social)
        self._social_label.setVisible(has_social)


    def _open_url(self, url):
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl(url))


class ResultsPage(QWidget):
    send_emails_to_sender = Signal(list)  # emits list of email strings

    def __init__(self):
        super().__init__()
        self._export = ExportService()
        self._record_queue: queue.Queue = queue.Queue()
        self._ui_event_queue: queue.Queue = queue.Queue()
        self._job_start_time: float = 0
        self._columns_auto_resized = False

        self._drain_timer = QTimer(self)
        self._drain_timer.setInterval(150)
        self._drain_timer.timeout.connect(self._drain_queue)
        self._drain_timer.start()

        self._build_ui()
        self._connect_events()
        self._setup_shortcuts()
        self._update_count_label()
        self._show_placeholder_state()

    def _build_ui(self):
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setContentsMargins(20, 16, 20, 16)
        self.mainLayout.setSpacing(12)

        # ── Command Bar ──────────────────────────────────────────────────────
        topRow = QHBoxLayout()
        topRow.setSpacing(8)
        
        # Filter combos (Pill styled)
        # We don't use subtitle / title per user request (no page title)
        
        # Search field
        self._search_box = SearchLineEdit()
        self._search_box.setPlaceholderText("SEARCH...")
        self._search_box.textChanged.connect(self._apply_text_filter)
        self._search_box.setFixedWidth(180)
        self._search_box.setFixedHeight(34)
        self._search_box.setStyleSheet(Theme.line_edit())
        topRow.addWidget(self._search_box)

        # Filter Chips
        self._source_chip = FilterChip("ALL SOURCES")
        self._source_chip.clicked.connect(self._show_source_menu)
        topRow.addWidget(self._source_chip)

        self._status_chip = FilterChip("ALL STATUSES")
        self._status_chip.clicked.connect(self._show_status_menu)
        topRow.addWidget(self._status_chip)

        self._city_chip = FilterChip("ALL CITIES")
        self._city_chip.clicked.connect(self._show_city_menu)
        topRow.addWidget(self._city_chip)

        self._date_chip = FilterChip("ALL TIME")
        self._date_chip.clicked.connect(self._show_date_menu)
        topRow.addWidget(self._date_chip)

        topRow.addStretch(1)

        # Action buttons
        self._btn_export = QPushButton("EXPORT")
        self._btn_export.setFixedHeight(36)
        self._btn_export.setStyleSheet(Theme.zugzwang_primary_button())
        self._btn_export.clicked.connect(self._show_export_menu)

        self._btn_send_emails = QPushButton("SEND MESSAGES")
        self._btn_send_emails.setFixedHeight(36)
        self._btn_send_emails.setStyleSheet(Theme.zugzwang_success_button())
        self._btn_send_emails.clicked.connect(self._push_emails_to_sender)

        self._btn_clear_all = QPushButton("CLEAR")
        self._btn_clear_all.setFixedHeight(36)
        self._btn_clear_all.setStyleSheet(Theme.zugzwang_danger_button())
        self._btn_clear_all.clicked.connect(self._confirm_clear_list)

        topRow.addWidget(self._btn_export)
        topRow.addWidget(self._btn_send_emails)
        topRow.addWidget(self._btn_clear_all)

        self.mainLayout.addLayout(topRow)

        # ── Progress Strip ──
        self._progress_strip = QFrame()
        self._progress_strip.setObjectName("ProgressStrip")
        self._progress_strip.setStyleSheet(f"QFrame#ProgressStrip {{ background: #2C2C2E; border: 1px solid {Theme.BORDER_LIGHT}; border-radius: 12px; }}")

        prog_layout = QHBoxLayout(self._progress_strip)
        prog_layout.setContentsMargins(20, 14, 20, 14)
        prog_layout.setSpacing(16)
        
        self._badge = InfoBadge.custom("PENDING", "#38BDF8", "#0284C7")
        prog_layout.addWidget(self._badge)
        self._progress_label = StrongBodyLabel("Starting...")
        self._progress_bar = ProgressBar()
        self._progress_bar.setRange(0, 100)
        prog_layout.addWidget(self._progress_bar, 1)
        self._progress_strip.hide()
        self.mainLayout.addWidget(self._progress_strip)

        # ── Table & Detail Splitter ──────────────────────────────────────────
        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setHandleWidth(8)
        self._splitter.setStyleSheet("QSplitter::handle { background: transparent; }")

        self._model = ResultsTableModel()
        self._proxy = LeadFilterProxy()
        self._proxy.setSourceModel(self._model)

        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setAlternatingRowColors(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setSortingEnabled(False)
        self._table.verticalHeader().hide()
        self._table.verticalHeader().setDefaultSectionSize(28)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setMinimumHeight(32)
        self._table.setWordWrap(False)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setFrameShape(QFrame.NoFrame)
        self._table.setShowGrid(False)
        self._table.setItemDelegate(RowSelectionDelegate(self._table))
        self._table.setStyleSheet(f"""
            QTableView {{
                background-color: transparent;
                border: none;
                color: {Theme.TEXT_SECONDARY};
                gridline-color: transparent;
                selection-background-color: transparent;
                selection-color: {Theme.TEXT_PRIMARY};
                outline: none;
            }}
            QTableView::item {{
                padding: 0;
                border: none;
                border-bottom: 1px solid #3A3A3C;
                background-color: transparent;
            }}
            QTableView::item:selected {{
                color: white;
            }}
            QHeaderView {{
                background-color: transparent;
            }}
            QHeaderView::section {{
                background-color: transparent;
                color: #636366;
                font-family: 'PT Root UI', sans-serif;
                font-weight: 600;
                font-size: 10px;
                letter-spacing: 1.6px;
                text-transform: uppercase;
                padding: 0 14px;
                height: 32px;
                border: none;
                border-bottom: 1px solid #3A3A3C;
            }}
            QScrollBar:vertical {{
                background: transparent; width: 6px; margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255,255,255,0.15); border-radius: 3px; min-height: 40px;
            }}
            QScrollBar::handle:vertical:hover {{ background: rgba(255,255,255,0.25); }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar:horizontal {{
                background: transparent; height: 6px;
            }}
            QScrollBar::handle:horizontal {{
                background: rgba(255,255,255,0.15); border-radius: 3px;
            }}
            QScrollBar::handle:horizontal:hover {{ background: rgba(255,255,255,0.25); }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
        """)
        for idx, (_, _, width) in enumerate(TABLE_COLUMNS):
            self._table.setColumnWidth(idx, width)
        self._table.selectionModel().currentRowChanged.connect(self._on_row_selected)
        
        table_wrap = QFrame()
        table_wrap.setObjectName("tableWrap")
        table_wrap.setStyleSheet(f"QFrame#tableWrap {{ background: transparent; border: none; }}")
        tw_layout = QVBoxLayout(table_wrap)
        tw_layout.setContentsMargins(0, 0, 0, 0)
        tw_layout.addWidget(self._table)

        self._splitter.addWidget(table_wrap)

        self._detail_panel = DetailPanel()
        self._detail_panel.close_requested.connect(self._clear_selection)
        self._splitter.addWidget(self._detail_panel)
        
        self.mainLayout.addWidget(self._splitter, 1)



    def _show_source_menu(self):
        menu = FilterMenu(self)
        menu.add_item("All Sources", 0, self._proxy._source_filter == 0)
        menu.add_divider()
        menu.add_item("Google Maps", 1, self._proxy._source_filter == 1)
        menu.add_item("Jobsuche", 2, self._proxy._source_filter == 2)
        menu.add_item("Ausbildung.de", 3, self._proxy._source_filter == 3)
        menu.add_item("Aubi-Plus", 4, self._proxy._source_filter == 4)
        
        menu.itemSelected.connect(lambda t, i: self._apply_source_filter(i, t))
        self._source_chip.set_open(True)
        menu.closed.connect(lambda: self._source_chip.set_open(False))
        
        pos = self._source_chip.mapToGlobal(QPoint(0, self._source_chip.height() + 6))
        menu.move(pos)
        menu.show()

    def _show_status_menu(self):
        menu = FilterMenu(self)
        menu.add_item("All Statuses", 0, self._proxy._status_filter == 0)
        menu.add_divider()
        menu.add_item("Email Valid", 1, self._proxy._status_filter == 1)
        menu.add_item("Email Invalid", 2, self._proxy._status_filter == 2)
        menu.add_item("No Email Found", 3, self._proxy._status_filter == 3)
        menu.add_item("Pending", 4, self._proxy._status_filter == 4)
        
        menu.itemSelected.connect(lambda t, i: self._apply_status_filter(i, t))
        self._status_chip.set_open(True)
        menu.closed.connect(lambda: self._status_chip.set_open(False))
        
        pos = self._status_chip.mapToGlobal(QPoint(0, self._status_chip.height() + 6))
        menu.move(pos)
        menu.show()

    def _show_city_menu(self):
        menu = FilterMenu(self)
        menu.add_item("All Cities", 0, self._proxy._city_filter == "All Cities")
        menu.add_divider()
        
        cities = set()
        for record in self._model.get_all_records():
            if record.city: cities.add(record.city.strip())
        
        if not cities:
            menu.add_placeholder("No cities found")
        else:
            for idx, city in enumerate(sorted(list(cities)), 1):
                menu.add_item(city, idx, self._proxy._city_filter == city)
        
        menu.itemSelected.connect(lambda t, i: self._apply_city_filter(t))
        self._city_chip.set_open(True)
        menu.closed.connect(lambda: self._city_chip.set_open(False))
        
        pos = self._city_chip.mapToGlobal(QPoint(0, self._city_chip.height() + 6))
        menu.move(pos)
        menu.show()

    def _show_date_menu(self):
        menu = FilterMenu(self)
        menu.add_item("All Time", 0, self._proxy._date_filter == 0)
        menu.add_divider()
        menu.add_item("Last Minute", 1, self._proxy._date_filter == 1)
        menu.add_item("Last Hour", 2, self._proxy._date_filter == 2)
        menu.add_item("Last 3 Hours", 3, self._proxy._date_filter == 3)
        menu.add_item("Last 6 Hours", 4, self._proxy._date_filter == 4)
        menu.add_item("Last 12 Hours", 5, self._proxy._date_filter == 5)
        menu.add_divider()
        menu.add_item("Today", 6, self._proxy._date_filter == 6)
        menu.add_item("Yesterday", 7, self._proxy._date_filter == 7)
        menu.add_item("Last 7 Days", 8, self._proxy._date_filter == 8)
        menu.add_item("Last 30 Days", 9, self._proxy._date_filter == 9)
        
        menu.itemSelected.connect(lambda t, i: self._apply_date_filter(i, t))
        self._date_chip.set_open(True)
        menu.closed.connect(lambda: self._date_chip.set_open(False))
        
        pos = self._date_chip.mapToGlobal(QPoint(0, self._date_chip.height() + 6))
        menu.move(pos)
        menu.show()

    def _setup_shortcuts(self):
        shortcut_find = QShortcut(QKeySequence("Ctrl+F"), self)
        shortcut_find.activated.connect(self._search_box.setFocus)
        shortcut_export = QShortcut(QKeySequence("Ctrl+E"), self)
        shortcut_export.activated.connect(self._show_export_menu)

    def _show_export_menu(self):
        menu = RoundMenu(parent=self._btn_export)
        menu.addAction(Action(FluentIcon.DOCUMENT, "Export to Excel (.xlsx)", triggered=lambda: self._export_results("xlsx")))
        menu.addAction(Action(FluentIcon.DOCUMENT, "Export to Word (.docx)", triggered=lambda: self._export_results("docx")))
        menu.addAction(Action(FluentIcon.SAVE, "Save Project DB (.db)", triggered=lambda: self._export_results("sqlite")))
        menu.addSeparator()
        menu.addAction(Action(FluentIcon.SEARCH, "Export No-Email Sites (.xlsx)", triggered=self._export_no_email_sites))
        
        # Calculate position
        pos = self._btn_export.mapToGlobal(self._btn_export.rect().bottomLeft())
        menu.exec(pos, aniType=MenuAnimationType.PULL_UP)

    def _clear_selection(self) -> None:
        self._table.clearSelection()
        self._table.setCurrentIndex(QModelIndex())
        self._show_placeholder_state()

    def _connect_events(self):
        from .event_bridge import event_bridge
        event_bridge.job_started.connect(self._on_job_started)
        event_bridge.job_result.connect(self._on_job_result)
        event_bridge.job_progress.connect(self._on_job_progress)
        event_bridge.job_completed.connect(self._on_job_completed)
        event_bridge.job_failed.connect(self._on_job_failed)
        event_bridge.job_cancelled.connect(self._on_job_cancelled)
        event_bridge.export_completed.connect(self._on_export_completed)

    def _on_job_result(self, record=None, count=0, **kw):
        if record is not None:
            self._record_queue.put(record)

    def load_records(self, records: list[LeadRecord]):
        """Persistently loads records into the table model (from database)."""
        if not records:
            return
        for r in records:
            self._model.add_record(r)
        self._update_count_label()
        self._refresh_city_list()

    def _drain_queue(self):
        added = 0
        from ..core.logger import get_logger
        log = get_logger(__name__)
        while not self._record_queue.empty() and added < 50:
            try:
                record = self._record_queue.get_nowait()
                if isinstance(record, dict):
                    record = LeadRecord.from_dict(record)
                self._model.add_record(record)
                added += 1
            except queue.Empty:
                break
            except Exception as e:
                log.error(f"Failed to render LeadRecord in drain_queue: {e}", exc_info=True)

        if added:
            self._update_count_label()
            if not self._columns_auto_resized and self._model.rowCount() >= 3:
                self._columns_auto_resized = True
                self._table.resizeColumnsToContents()

        while not self._ui_event_queue.empty():
            try:
                event_name, payload = self._ui_event_queue.get_nowait()
            except queue.Empty:
                break
            self._dispatch_ui_event(event_name, payload)

    def _dispatch_ui_event(self, event_name: str, payload: tuple):
        if event_name == "job_started":
            self._ui_job_started()
        elif event_name == "job_progress":
            found, emails, pct = payload
            self._ui_update_progress(found, emails, pct)
        elif event_name == "job_completed":
            self._ui_job_completed()
        elif event_name == "job_failed":
            self._ui_job_failed()
        elif event_name == "job_cancelled":
            self._ui_job_cancelled()
        elif event_name == "export_done":
            fmt, path, count = payload
            from qfluentwidgets import InfoBar, InfoBarPosition
            InfoBar.success("Export Complete", f"Exported {count:,} records", duration=4000, parent=self)

    def _apply_text_filter(self, text: str):
        self._proxy.setFilterFixedString(text.strip())
        self._update_count_label()

    def _apply_source_filter(self, index: int, name: str):
        self._proxy.set_source_filter(index)
        self._source_chip.setText(name.upper())
        self._source_chip.set_active(index > 0)
        self._update_count_label()

    def _apply_status_filter(self, index: int, name: str):
        self._proxy.set_status_filter(index)
        self._status_chip.setText(name.upper())
        self._status_chip.set_active(index > 0)
        self._update_count_label()

    def _apply_city_filter(self, city: str):
        self._proxy.set_city_filter(city)
        self._city_chip.setText(city.upper())
        self._city_chip.set_active(city != "ALL CITIES")
        self._update_count_label()

    def _apply_date_filter(self, index: int, name: str):
        self._proxy.set_date_filter(index)
        self._date_chip.setText(name.upper())
        self._date_chip.set_active(index > 0)
        self._update_count_label()

    def _update_count_label(self):
        pass # Page subtitle was removed for a cleaner macOS aesthetic

    def _on_row_selected(self, current, previous):
        if not current.isValid():
            self._show_placeholder_state()
            return
        source_row = self._proxy.mapToSource(current).row()
        record = self._model.get_record(source_row)
        if record:
            self._show_record_state(record)

    def _on_job_started(self, *args, **kw):
        self._ui_event_queue.put(("job_started", ()))

    def _on_job_progress(self, data: dict):
        total_found = data.get("total_found", 0)
        total_emails = data.get("total_emails", 0)
        completion = data.get("completion", 0.0)
        self._ui_event_queue.put(("job_progress", (int(total_found), int(total_emails), int(completion * 100))))

    def _on_job_completed(self, *args, **kw):
        self._ui_event_queue.put(("job_completed", ()))

    def _on_job_failed(self, *args, **kw):
        self._ui_event_queue.put(("job_failed", ()))

    def _on_job_cancelled(self, *args, **kw):
        self._ui_event_queue.put(("job_cancelled", ()))

    def _on_export_completed(self, format="", path="", count=0, **kw):
        self._ui_event_queue.put(("export_done", (str(format), str(path), int(count))))

    def _ui_job_started(self):
        self._job_start_time = time.monotonic()
        while not self._record_queue.empty():
            try:
                self._record_queue.get_nowait()
            except queue.Empty:
                break
        self._progress_strip.show()
        self._update_badge("RUNNING", "#38BDF8", "#0EA5E9")
        self._progress_label.setText("Searching...")
        self._progress_bar.setValue(0)
        self._update_count_label()

    def _ui_update_progress(self, found: int, emails: int, pct: int):
        elapsed = time.monotonic() - self._job_start_time
        elapsed_str = self._format_elapsed(elapsed)
        self._progress_bar.setValue(pct)
        self._progress_label.setText(
            f"Found {found:,} leads | {emails:,} emails  |  {elapsed_str}"
        )

    def _ui_job_completed(self):
        elapsed = time.monotonic() - self._job_start_time
        elapsed_str = self._format_elapsed(elapsed)
        from ..services.orchestrator import orchestrator
        job = orchestrator.current_job
        total = job.total_found if job else self._model.rowCount()
        email_count = job.total_emails if job else sum(1 for r in self._model.get_all_records() if r.email)
        
        self._update_badge("COMPLETED", "#10B981", "#059669")
        self._progress_label.setText(f"{total:,} leads | {email_count:,} emails  |  {elapsed_str}")
        self._progress_bar.setValue(100)
        self._update_count_label()

    def _ui_job_failed(self):
        self._update_badge("FAILED", "#EF4444", "#B91C1C")
        self._progress_label.setText("Scraping failed - check the log")

    def _ui_job_cancelled(self):
        self._update_badge("STOPPED", "#F59E0B", "#D97706")
        elapsed = time.monotonic() - self._job_start_time
        self._progress_label.setText(f"Scraping cancelled after {self._format_elapsed(elapsed)}")

    def _update_badge(self, text, color, bg):
        self._badge.setText(text)
        self._badge.setStyleSheet(f"InfoBadge {{ color: {color}; background-color: {bg}; border: none; font-weight: bold; padding: 2px 8px; border-radius: 4px; }}")

    @staticmethod
    def _format_elapsed(seconds: float) -> str:
        minutes, secs = divmod(int(seconds), 60)
        if minutes > 0:
            return f"{minutes}m {secs:02d}s"
        return f"{secs}s"

    def _export_results(self, fmt: str):
        records = self._get_visible_records()
        self._perform_export(records, fmt)

    def _export_no_email_sites(self):
        # Filter for leads with a website but NO email
        records = [r for r in self._get_visible_records() if not r.email and r.website]
        if not records:
            from qfluentwidgets import InfoBar
            InfoBar.warning("No Targets", "No websites found without emails in the current list.", duration=3000, parent=self)
            return
        self._perform_export(records, "xlsx", prefix="Manual_Check")

    def _perform_export(self, records: list[LeadRecord], fmt: str, prefix: str = ""):
        if not records:
            from qfluentwidgets import InfoBar
            InfoBar.warning("No Data", "No results to export.", duration=2000, parent=self)
            return

        ext_map = {"xlsx": "Excel Files (*.xlsx)", "docx": "Word Files (*.docx)", "sqlite": "SQLite Database (*.db)"}
        ext_ext = {"xlsx": ".xlsx", "docx": ".docx", "sqlite": ".db"}
        export_dir = get_projects_dir() if fmt == "sqlite" else get_exports_dir()
        suggested = self._suggested_export_path(fmt, export_dir, ext_ext[fmt], records, prefix)
        path, _ = QFileDialog.getSaveFileName(self, f"Export as {fmt.upper()}", suggested, ext_map[fmt])
        if not path:
            return

        if fmt == "xlsx":
            config_manager.update(last_xlsx_export_path=path)

        from ..services.orchestrator import orchestrator
        orchestrator.export_results(records, fmt, path)

    def _suggested_export_path(self, fmt: str, export_dir, extension: str, records: list[LeadRecord], prefix: str = "") -> str:
        if fmt == "xlsx":
            last_path = (config_manager.settings.last_xlsx_export_path or "").strip()
            if last_path:
                last_file = Path(last_path)
                last_dir = last_file.parent if last_file.suffix else last_file
                if last_dir.exists():
                    return str(last_dir / self._build_contextual_export_filename(extension, records, prefix))

        if fmt != "sqlite":
            return str(export_dir / self._build_contextual_export_filename(extension, records, prefix))

        return str(export_dir / self._export.generate_filename("project", extension.lstrip(".")))

    def _build_contextual_export_filename(self, extension: str, records: list[LeadRecord], prefix: str = "") -> str:
        job_part = (config_manager.settings.last_search_job_title or "").strip() or "search"
        city_part = (config_manager.settings.last_search_city or "").strip() or "all-cities"
        date_part = datetime.now().strftime("%Y-%m-%d")

        first = records[0] if records else None
        if first:
            search_query = (first.search_query or "").strip()
            city = (first.city or "").strip()
            if search_query:
                job_part = search_query.split(",")[0].strip() or job_part
            elif first.job_title:
                job_part = first.job_title.strip()
            elif first.company_name:
                job_part = first.company_name.strip()

            if city:
                city_part = city

        job_part = self._sanitize_filename_part(job_part)
        city_part = self._sanitize_filename_part(city_part)
        base = f"{job_part}, {city_part}, {date_part}"
        if prefix:
            base = f"{prefix}_{base}"
        return f"{base}{extension}"

    @staticmethod
    def _sanitize_filename_part(value: str) -> str:
        value = re.sub(r'[<>:"/\\\\|?*]+', " ", value)
        value = re.sub(r"\s+", " ", value).strip(" .")
        return value or "search"

    def _get_visible_records(self) -> list[LeadRecord]:
        records: list[LeadRecord] = []
        for proxy_row in range(self._proxy.rowCount()):
            src_row = self._proxy.mapToSource(self._proxy.index(proxy_row, 0)).row()
            record = self._model.get_record(src_row)
            if record:
                records.append(record)
        return records

    def header_action_widgets(self) -> list[QWidget]:
        return []

    def load_records(self, records: list[LeadRecord]) -> None:
        self._model.clear_records()
        for record in records:
            self._model.add_record(record)
        self._update_count_label()
        if self._model.rowCount() > 0:
            self._columns_auto_resized = True
        self._show_placeholder_state()

    def _show_placeholder_state(self) -> None:
        self._detail_panel.show_placeholder()
        self._splitter.setSizes([1000, 380])

    def _show_record_state(self, record: LeadRecord) -> None:
        self._splitter.setSizes([1000, 380])
        self._detail_panel.show_record(record)

    def _push_emails_to_sender(self):
        """Extract all emails from the visible records and emit them."""
        records = self._get_visible_records()
        emails = [r.email for r in records if r.email]
        if emails:
            self.send_emails_to_sender.emit(emails)

    def _confirm_clear_list(self):
        from .components import ZugzwangDialog
        msg = ZugzwangDialog(
            "Clear Library", 
            "Are you sure you want to permanently delete all found leads from the library?", 
            self,
            destructive=True
        )
        if msg.exec():
            from ..services.orchestrator import orchestrator
            orchestrator.clear_app_memory() # Actually delete the DB file
            self._model.clear_records()
            self._update_count_label()
            self._show_placeholder_state()
