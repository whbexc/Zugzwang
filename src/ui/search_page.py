"""
ZUGZWANG - Search Page
Target Generation workflow using Obsidian Core design language.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QPropertyAnimation, Property, QEasingCurve, QEvent, QTimer
from PySide6.QtGui import QDoubleValidator, QIntValidator, QColor
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget, QGraphicsDropShadowEffect, QSizePolicy, QScrollArea, QLineEdit, QStackedLayout

from qfluentwidgets import (
    ComboBox,
    FluentIcon,
    IconWidget,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    InfoBar,
    TextEdit,
    Action,
    ToolTipFilter,
    ToolTipPosition
)
from .components import StatCard, SectionCard, MacSwitch, FlowLayout, MacComboBox, MacEditableComboBox
from .coverage_panel import CoverageTrackerPanel

from ..core.config import config_manager
from ..core.i18n import get_language, tr
from ..core.models import SearchConfig, SourceType
from .theme import Theme


class SearchSourceCard(QFrame):
    activated = Signal(str)

    def __init__(self, key: str, icon_name: FluentIcon, title: str, body: str, selected_label: str, parent=None):
        super().__init__(parent)
        self._key = key
        self._active = False
        self._hover_opacity = 0.0
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(124)
        self.setMinimumWidth(120)
        self.setMaximumWidth(240)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(6)

        header = QHBoxLayout()
        self._icon = IconWidget(icon_name)
        self._icon.setFixedSize(20, 20)
        self._icon.setStyleSheet(f"color: #8E8E93;")
        header.addWidget(self._icon)
        header.addStretch(1)
        
        # Checkmark Status Badge 
        self._status_badge = QFrame()
        self._status_badge.setObjectName("StatusBadge")
        self._status_badge.setFixedSize(18, 18)
        self._status_badge.setStyleSheet("QFrame#StatusBadge { background: #0A84FF; border-radius: 9px; border: none; }")
        badge_layout = QVBoxLayout(self._status_badge)
        badge_layout.setContentsMargins(0, 0, 0, 0)
        badge_layout.setSpacing(0)
        badge_layout.setAlignment(Qt.AlignCenter)
        
        self._status_icon = IconWidget(FluentIcon.ACCEPT)
        self._status_icon.setFixedSize(10, 10)
        self._status_icon.setStyleSheet("color: white; background: transparent; border: none;")
        badge_layout.addWidget(self._status_icon, 0, Qt.AlignCenter)
        self._status_badge.setVisible(False)
        header.addWidget(self._status_badge)
        
        layout.addLayout(header)
        layout.addStretch(1)

        self._title = QLabel(title)
        self._title.setStyleSheet(f"color: #FFFFFF; font-family: 'PT Root UI', sans-serif; font-size: 18px; font-weight: 700; background: transparent; border: none;")
        layout.addWidget(self._title)

        self._body = QLabel(body)
        self._body.setWordWrap(True)
        self._body.setStyleSheet(f"color: #8E8E93; font-family: 'Menlo', 'Menlo', monospace; font-size: 10px; font-weight: 600; letter-spacing: 0.5px; background: transparent; border: none;")
        layout.addWidget(self._body)

        # Shadow removed based on user feedback

        self._apply_style()

    def set_active(self, active: bool) -> None:
        self._active = active
        self._apply_style()

    def _apply_style(self, hovered: bool = False) -> None:
        if self._active:
            self.setObjectName("GlassCardActive")
            border = f"1.5px solid #0A84FF"
            bg = f"rgba(10, 132, 255, 0.06)"
            self._icon.setStyleSheet(f"color: #0A84FF;")
            self._status_badge.setVisible(True)
        else:
            self.setObjectName("GlassCard")
            bg = "#3A3A3C" if hovered else "#2C2C2E"
            border = "none"
            self._icon.setStyleSheet(f"color: #8E8E93;")
            self._status_badge.setVisible(False)

        self.setStyleSheet(f"""
            QFrame#GlassCard, QFrame#GlassCardActive {{
                background: {bg};
                border: {border};
                border-radius: 12px;
            }}
        """)
        
        # Add tooltips for better UX
        tooltips = {
            "maps": "Search businesses and services globally via Google Maps",
            "jobsuche": "Search official German Federal Employment Agency listings",
            "ausbildung": "Find apprenticeship positions across Germany",
            "aubiplus": "High-quality vocational training and study positions",
            "dasoertliche": "Search German business directory Das Örtliche",
            "azubiyo": "Sophisticated matching for apprenticeships (Coming Soon)"
        }
        self.setToolTip(tooltips.get(self._key, ""))

    def enterEvent(self, event):
        if not self.isEnabled():
            super().enterEvent(event)
            return
        self._apply_style(hovered=True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self.isEnabled():
            super().leaveEvent(event)
            return
        self._apply_style(hovered=False)
        super().leaveEvent(event)

    def _select(self) -> None:
        self._active = True
        self._apply_style()
        self.activated.emit(self._key)

    def _deselect(self) -> None:
        self._active = False
        self._apply_style()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._select()
        super().mousePressEvent(event)





class SearchHistoryDropdown(QFrame):
    """Floating history dropdown anchored to the job title input."""
    item_selected = Signal(dict)  # dict with job_title, city, source, offer_type
    closed = Signal()

    # Internal key strings for source cards
    _SOURCE_KEYS = ("maps", "jobsuche", "ausbildung", "aubiplus", "dasoertliche") #, "azubiyo" - Staged for v1.1.0

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus)
        self.setObjectName("HistoryDropdown")
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("QFrame#HistoryDropdown { background: transparent; border: none; }")
        self._entries: list = []  # (id, job_title, city, source, offer_type, is_saved)
        self._anchor_widget = None

        from PySide6.QtCore import QCoreApplication
        QCoreApplication.instance().installEventFilter(self)

        # Container to hold styles and shadow
        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        self.container = QFrame(self)
        self.container.setObjectName("HistoryContainer")
        self.container.setStyleSheet("""
            QFrame#HistoryContainer {
                background: #1C1C1E;
                border: 1px solid #3A3A3C;
                border-radius: 10px;
            }
        """)
        # Main layout holds container
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.container)

        # Content layout inside container
        self.content_layout = QVBoxLayout(self.container)
        self.content_layout.setContentsMargins(0, 6, 0, 6)
        self.content_layout.setSpacing(0)

        self._list_layout = QVBoxLayout()
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(0)
        self.content_layout.addLayout(self._list_layout)

        # Divider + Clear button
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet("background: #3A3A3C; border: none;")
        self.content_layout.addWidget(div)

        self._clear_btn = QPushButton("CLEAR HISTORY")
        self._clear_btn.setFixedHeight(36)
        self._clear_btn.setCursor(Qt.PointingHandCursor)
        self._clear_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: none;
                color: #FF453A; font-family: 'PT Root UI', sans-serif;
                font-size: 12px; font-weight: 600; letter-spacing: 1.0px;
                text-align: center;
            }
            QPushButton:hover { color: #FF5C52; }
            QPushButton:pressed { color: #FF2D21; }
        """)
        self._clear_btn.clicked.connect(self._clear_history)
        self.content_layout.addWidget(self._clear_btn)

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent, QRect
        from PySide6.QtGui import QMouseEvent
        if event.type() == QEvent.MouseButtonPress and self.isVisible():
            if isinstance(event, QMouseEvent):
                try:
                    pos = event.globalPosition().toPoint() if hasattr(event, 'globalPosition') else event.globalPos()
                except AttributeError:
                    return super().eventFilter(obj, event)
                
                if not self.geometry().contains(pos):
                    if getattr(self, '_anchor_widget', None):
                        top_left = self._anchor_widget.mapToGlobal(self._anchor_widget.rect().topLeft())
                        bottom_right = self._anchor_widget.mapToGlobal(self._anchor_widget.rect().bottomRight())
                        if QRect(top_left, bottom_right).contains(pos):
                            return super().eventFilter(obj, event)
                    self.hide()
        return super().eventFilter(obj, event)

    def refresh(self) -> None:
        """Reload from DB and rebuild rows if changed."""
        new_entries = config_manager.get_search_history()
        # Optimization: Avoid rebuilding if data is identical and list is already populated
        if new_entries == self._entries and self._list_layout.count() > 0:
            return
            
        self._entries = new_entries
        # clear old rows
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._entries:
            no_lbl = QLabel("  No recent searches")
            no_lbl.setFixedHeight(32)
            no_lbl.setStyleSheet("color: #636366; font-size: 12px; font-family: 'PT Root UI', sans-serif; background: transparent; border: none;")
            self._list_layout.addWidget(no_lbl)
            self._clear_btn.hide()
            return

        self._clear_btn.show()
        for row in self._entries:
            self._list_layout.addWidget(self._make_row(row))

    def _make_row(self, row) -> QWidget:
        """Build a single history row widget."""
        rid, job_title, city, source, offer_type, radius, is_saved = row
        item = QFrame()
        item.setFixedHeight(36)
        item.setStyleSheet("QFrame { background: transparent; border: none; }")
        item.setCursor(Qt.PointingHandCursor)
        hl = QHBoxLayout(item)
        hl.setContentsMargins(14, 0, 10, 0)
        hl.setSpacing(8)

        # Star button
        star = QPushButton("★" if is_saved else "☆")
        star.setFixedSize(20, 20)
        star.setCursor(Qt.PointingHandCursor)
        star_color = "#FF9F0A" if is_saved else "#636366"
        star.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: {star_color}; font-size: 14px;
            }}
            QPushButton:hover {{ color: #FF9F0A; }}
        """)
        star.setProperty("_hid", rid)
        star.setProperty("_saved", bool(is_saved))
        star.clicked.connect(lambda _, s=star, r=row: self._toggle_star(s, r))
        hl.addWidget(star, 0, Qt.AlignVCenter)

        # Label
        label_text = job_title or ""
        if city:
            label_text += f"  ·  {city}"
        if source:
            label_text += f"  ·  {source}"
        lbl = QLabel(label_text)
        lbl.setStyleSheet("color: #AEAEB2; font-family: 'PT Root UI', sans-serif; font-size: 13px; background: transparent; border: none;")
        lbl.setToolTip(f"Re-apply this search configuration:\nRole: {job_title or 'Any'}\nCity: {city or 'Any'}\nSource: {source or 'Maps'}")
        hl.addWidget(lbl, 1)

        # Hover effect (event filter)
        item.mousePressEvent = lambda e, r=row: self._on_select(r)
        
        def on_enter(e, l=lbl):
            l.setStyleSheet("color: #FFFFFF; font-family: 'PT Root UI', sans-serif; font-size: 13px; background: transparent; border: none;")
            
        def on_leave(e, l=lbl):
            l.setStyleSheet("color: #AEAEB2; font-family: 'PT Root UI', sans-serif; font-size: 13px; background: transparent; border: none;")
            
        item.enterEvent = on_enter
        item.leaveEvent = on_leave
        return item

    def _toggle_star(self, star_btn: QPushButton, row) -> None:
        rid = row[0]
        new_saved = config_manager.toggle_saved(rid)
        star_btn.setText("★" if new_saved else "☆")
        color = "#FF9F0A" if new_saved else "#636366"
        star_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: {color}; font-size: 14px;
            }}
            QPushButton:hover {{ color: #FF9F0A; }}
        """)

    def _on_select(self, row) -> None:
        _, job_title, city, source, offer_type, radius, _ = row
        self.item_selected.emit({
            "job_title": job_title or "",
            "city": city or "",
            "source": source or "maps",
            "offer_type": offer_type or "",
            "radius": radius or 25,
        })
        self.hide()
        self.closed.emit()

    def _clear_history(self) -> None:
        config_manager.clear_unsaved_history()
        self.refresh()

    def show_below(self, anchor_widget: QWidget) -> None:
        """Position the dropdown below anchor_widget and show."""
        self._anchor_widget = anchor_widget
        self.refresh()
        pos = anchor_widget.mapToGlobal(anchor_widget.rect().bottomLeft())
        self.setFixedWidth(max(anchor_widget.width(), 360))
        self.adjustSize()
        self.move(pos)
        self.show()
        self.raise_()


from PySide6.QtWidgets import QPushButton as QPushButton


class SearchToggleTile(QWidget):
    def __init__(self, title: str, switch: MacSwitch):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(switch, 0, Qt.AlignVCenter)

        label = QLabel(title)
        label.setStyleSheet(f"color: #FFFFFF; font-family: 'PT Root UI', sans-serif; font-size: 13px; font-weight: 500; background: transparent; border: none;")
        layout.addWidget(label, 0, Qt.AlignVCenter)
        layout.addStretch(1)


class SearchPage(QWidget):
    job_requested = Signal(object)

    def eventFilter(self, obj, event: QEvent):
        if obj == self._job_title:
            if event.type() in [QEvent.FocusIn, QEvent.MouseButtonPress]:
                # Snappy 20ms delay instead of 100ms
                QTimer.singleShot(20, lambda: self._history_dropdown.show_below(self._job_title))
            elif event.type() == QEvent.FocusOut:
                # Hide dropdown when field loses focus
                self._history_dropdown.hide()
        return super().eventFilter(obj, event)

    def __init__(self):
        super().__init__()
        self._language = get_language(config_manager.settings.app_language)
        self._source = "maps"
        self._interactive_widgets: list[QWidget] = []
        self._build_ui()
        self._load_last_search()
        self._load_covered_cities()

        from .event_bridge import event_bridge
        event_bridge.job_completed.connect(lambda j, f, e: self._load_covered_cities())

    def header_action_widgets(self) -> list[QWidget]:
        return []

    def _show_pro_warning(self, event):
        # Show the actual Pro activation dialog (the main window handles state refreshing automatically if activated)
        self.window().show_activation_dialog()

    def _build_ui(self) -> None:
        self.setObjectName("searchPage")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.ClickFocus)
        self.setStyleSheet(f"QWidget#searchPage {{ background: {Theme.BG_OBSIDIAN}; }}")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        body = QVBoxLayout()
        body.setContentsMargins(32, 20, 32, 20)
        body.setSpacing(14)
        root.addLayout(body)

        self._clear_btn = PushButton(tr("search.clear", self._language))
        self._clear_btn.setFixedSize(120, 44)
        self._clear_btn.setStyleSheet(Theme.danger_button())
        self._clear_btn.setCursor(Qt.PointingHandCursor)
        self._clear_btn.clicked.connect(self._clear_form)
        self._interactive_widgets.append(self._clear_btn)
        # Step 1: Intelligence Source
        body.addWidget(self._step_card("1", tr("search.step.source", self._language), self._build_source_section(), compact=True))

        # Main Area: Parameters and Advanced Controls side-by-side
        main_layout = QHBoxLayout()
        main_layout.setSpacing(24)
        
        self._target_card = self._step_card("2", tr("search.step.target", self._language), self._build_target_section())
        self._advanced_card = self._step_card("3", tr("search.step.advanced", self._language), self._build_advanced_section())
        
        main_layout.addWidget(self._target_card, 55, Qt.AlignTop)
        main_layout.addWidget(self._advanced_card, 45, Qt.AlignTop)
        body.addLayout(main_layout)

        # Coverage Tracker Panel Container
        self._coverage_container = QWidget()
        coverage_layout = QStackedLayout(self._coverage_container)
        coverage_layout.setStackingMode(QStackedLayout.StackAll)

        self._coverage_panel = CoverageTrackerPanel()
        self._coverage_panel.city_clicked.connect(self._on_coverage_city_clicked)
        coverage_layout.addWidget(self._coverage_panel)
        
        # Pro Overlay
        self._pro_overlay = QFrame()
        self._pro_overlay.setObjectName("ProOverlay")
        self._pro_overlay.setStyleSheet("QFrame#ProOverlay { background: rgba(28, 28, 30, 0.65); border-radius: 12px; }")
        self._pro_overlay.setCursor(Qt.PointingHandCursor)
        
        overlay_vbox = QVBoxLayout(self._pro_overlay)
        overlay_vbox.setAlignment(Qt.AlignCenter)
        overlay_vbox.setSpacing(8)
        
        lock_icon = IconWidget(FluentIcon.CERTIFICATE)
        lock_icon.setFixedSize(32, 32)
        # Using a distinct color for the icon, or leaving default
        overlay_vbox.addWidget(lock_icon, 0, Qt.AlignHCenter)
        
        pro_label = QLabel("Pro Feature")
        pro_label.setStyleSheet("color: #FFFFFF; font-family: 'PT Root UI', sans-serif; font-size: 16px; font-weight: 700; background: transparent; border: none;")
        overlay_vbox.addWidget(pro_label, 0, Qt.AlignHCenter)
        
        pro_desc = QLabel("Unlock the Coverage Tracker to see comprehensive scraping zones.")
        pro_desc.setStyleSheet("color: #8E8E93; font-family: 'PT Root UI', sans-serif; font-size: 13px; font-weight: 500; background: transparent; border: none;")
        overlay_vbox.addWidget(pro_desc, 0, Qt.AlignHCenter)
        
        coverage_layout.addWidget(self._pro_overlay)
        
        # Check pro status
        from ..core.security import LicenseManager
        is_pro = LicenseManager.is_active()
        
        if not is_pro:
            self._coverage_panel._is_preview_mode = True
            self._coverage_panel.setEnabled(False)
            self._pro_overlay.mousePressEvent = self._show_pro_warning
            coverage_layout.setCurrentIndex(1)
        else:
            self._pro_overlay.setVisible(False)

        body.addWidget(self._coverage_container)

        # Launch Button
        from PySide6.QtWidgets import QPushButton as _QPB
        self._launch_btn = _QPB(tr("search.launch", self._language))
        self._launch_btn.setObjectName("SearchLaunchBtn")
        self._launch_btn.setMinimumSize(320, 44)
        self._launch_btn.setCursor(Qt.PointingHandCursor)
        self._launch_btn.setStyleSheet(Theme.zugzwang_primary_button())
        self._launch_btn.setToolTip("Initiate the scraping job with the configured parameters")
        self._launch_btn.clicked.connect(self._launch)
        self._interactive_widgets.append(self._launch_btn)
        

        
        action_layout = QHBoxLayout()
        action_layout.setSpacing(16)
        action_layout.addStretch()
        action_layout.addWidget(self._clear_btn)
        action_layout.addWidget(self._launch_btn)
        action_layout.addStretch()
        body.addLayout(action_layout)

    def _step_card(self, num: str, title: str, content: QWidget, compact: bool = False) -> QFrame:
        card = QFrame()
        card.setObjectName(f"StepCard{num}")
        card.setStyleSheet(f"QFrame#StepCard{num} {{ background: transparent; border: none; }}")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(8)
        badge = QFrame()
        badge.setObjectName(f"StepBadge{num}")
        badge.setFixedSize(24, 24)
        badge.setStyleSheet(f"QFrame#StepBadge{num} {{ background: #0A84FF; border-radius: 12px; border: none; }}")
        badge_layout = QHBoxLayout(badge)
        badge_layout.setContentsMargins(0, 0, 0, 0)
        badge_label = QLabel(num)
        badge_label.setAlignment(Qt.AlignCenter)
        badge_label.setStyleSheet("color: #FFFFFF; font-family: 'PT Root UI', sans-serif; font-size: 12px; font-weight: 800; background: transparent; border: none;")
        badge_layout.addWidget(badge_label)
        header.addWidget(badge)

        title_label = QLabel(title.upper())
        title_label.setStyleSheet(
            f"color: #8E8E93; font-family: 'PT Root UI', sans-serif; font-size: 11px; font-weight: 600; letter-spacing: 1.8px; "
            "background: transparent; border: none;"
        )
        header.addWidget(title_label)
        header.addStretch(1)
        layout.addLayout(header)

        if not compact:
            divider = QFrame()
            divider.setObjectName(f"StepDivider{num}")
            divider.setFixedHeight(1)
            divider.setStyleSheet(f"QFrame#StepDivider{num} {{ background: {Theme.BORDER_LIGHT}; border: none; }}")
            layout.addWidget(divider)

        layout.addWidget(content)
        return card

    def _build_source_section(self) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self._card_maps = SearchSourceCard(
            "maps",
            FluentIcon.GLOBE,
            tr("search.source.maps.title", self._language),
            tr("search.source.maps.body", self._language),
            tr("search.selected", self._language),
        )
        self._card_jobsuche = SearchSourceCard(
            "jobsuche",
            FluentIcon.SEARCH,
            tr("search.source.jobsuche.title", self._language),
            tr("search.source.jobsuche.body", self._language),
            tr("search.selected", self._language),
        )
        self._card_ausbildung = SearchSourceCard(
            "ausbildung",
            FluentIcon.EDUCATION,
            tr("search.source.ausbildung.title", self._language),
            tr("search.source.ausbildung.body", self._language),
            tr("search.selected", self._language),
        )
        self._card_aubiplus = SearchSourceCard(
            "aubiplus",
            FluentIcon.CERTIFICATE,
            tr("search.source.aubiplus.title", self._language),
            tr("search.source.aubiplus.body", self._language),
            tr("search.selected", self._language),
        )
        self._card_dasoertliche = SearchSourceCard(
            "dasoertliche",
            FluentIcon.DICTIONARY,
            "Das Örtliche",
            "Scrape German business directory",
            tr("search.selected", self._language),
        )
        # Azubiyo visible as disabled sneak-peek
        self._card_azubiyo = SearchSourceCard(
            "azubiyo",
            FluentIcon.PEOPLE,
            "AZUBIYO.DE",
            "Coming in v1.1.0",
            tr("search.selected", self._language),
        )
        self._card_azubiyo.setEnabled(False)
        from PySide6.QtWidgets import QGraphicsOpacityEffect
        op = QGraphicsOpacityEffect(self._card_azubiyo)
        op.setOpacity(0.5)
        self._card_azubiyo.setGraphicsEffect(op)

        self._card_maps.activated.connect(self._select_source)
        self._card_jobsuche.activated.connect(self._select_source)
        self._card_ausbildung.activated.connect(self._select_source)
        self._card_aubiplus.activated.connect(self._select_source)
        self._card_dasoertliche.activated.connect(self._select_source)
        
        self._interactive_widgets.extend([self._card_maps, self._card_jobsuche, self._card_ausbildung, self._card_aubiplus, self._card_dasoertliche])

        layout.addWidget(self._card_maps, 1)
        layout.addWidget(self._card_jobsuche, 1)
        layout.addWidget(self._card_ausbildung, 1)
        layout.addWidget(self._card_aubiplus, 1)
        layout.addWidget(self._card_dasoertliche, 1)
        layout.addWidget(self._card_azubiyo, 1)
        return container

    def _build_target_section(self) -> QWidget:
        container = QWidget()
        container.setStyleSheet("QWidget { background: transparent; border: none; }")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Job Title
        self._job_title = LineEdit()
        self._job_title.setFixedHeight(34)
        self._job_title.setPlaceholderText(tr("search.placeholder.job", self._language))
        self._job_title.addAction(Action(FluentIcon.SEARCH, "Search"), QLineEdit.LeadingPosition)
        self._job_title.textChanged.connect(self._clear_validation_error)
        self._style_input(self._job_title)
        self._job_title.setToolTip("Enter the job title or role to search for (e.g. 'Software Engineer', 'Pflegefachmann')")

        self._title_error = QLabel(tr("search.error.required", self._language))
        self._title_error.setStyleSheet(f"color: {Theme.DANGER}; font-size: 11px; font-weight: 700; background: transparent; border: none;")
        self._title_error.setVisible(False)

        layout.addLayout(self._make_field(tr("search.field.job_title", self._language), self._job_title, self._title_error))

        # ── Search History Dropdown ───────────────────────────────────────────
        self._history_dropdown = SearchHistoryDropdown(self)
        self._history_dropdown.item_selected.connect(self._apply_history)

        self._job_title.installEventFilter(self)

        # Location Row
        loc_row = QHBoxLayout()
        loc_row.setContentsMargins(0, 0, 0, 0)
        loc_row.setSpacing(12)

        self._country = MacComboBox()
        self._country.setFixedHeight(34)
        self._country.addItems(["Germany", "United States", "United Kingdom", "France", "Netherlands", "Switzerland", "Austria"])
        self._style_combo(self._country)
        self._country.setToolTip("Select the country where you want to search for leads")
        loc_row.addLayout(self._make_field(tr("search.field.country", self._language), self._country), 1)

        self._city = LineEdit()
        self._city.setFixedHeight(34)
        self._city.setPlaceholderText(tr("search.placeholder.city", self._language))
        self._city.addAction(Action(FluentIcon.SEARCH, "Search"), QLineEdit.LeadingPosition)
        self._style_input(self._city)
        self._city.setToolTip("Target a specific city or region (e.g. 'Berlin', 'New York')")
        loc_row.addLayout(self._make_field(tr("search.field.city", self._language), self._city), 1)
        
        self._radius = MacComboBox()
        self._radius.setFixedHeight(34)
        self._radius.addItems(["0 km", "10 km", "20 km", "25 km", "50 km", "100 km", "200 km"])
        self._radius.setCurrentText("25 km")
        self._style_combo(self._radius)
        self._radius.setToolTip("Search radius around the target city (Jobsuche/Ausbildung)")
        loc_row.addLayout(self._make_field(tr("search.field.radius", self._language), self._radius), 1)

        layout.addLayout(loc_row)

        # Offer Type (Specific for Jobsuche)
        self._offer_type_container = QWidget()
        self._offer_type_container.setStyleSheet("QWidget { background: transparent; border: none; }")
        offer_vbox = QVBoxLayout(self._offer_type_container)
        offer_vbox.setContentsMargins(0, 0, 0, 0)
        offer_vbox.setSpacing(6)
        
        self._offer_type = MacComboBox()
        self._offer_type.setFixedHeight(34)
        self._offer_type.addItems([
            tr("search.offer.arbeit", self._language),
            tr("search.offer.ausbildung", self._language),
            tr("search.offer.praktikum", self._language),
            tr("search.offer.selbststaendigkeit", self._language)
        ])
        self._style_combo(self._offer_type)
        self._offer_type.setToolTip("Filter by the type of job offer (Apprenticeship, Full-time, etc.)")
        offer_vbox.addLayout(self._make_field(tr("search.field.offer_type", self._language), self._offer_type))
        
        layout.addWidget(self._offer_type_container)
        return container

    def _make_field(self, label: str, widget: QWidget, error: QWidget = None) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(4)
        col.addWidget(self._field_label(label))
        col.addWidget(widget)
        if error:
            col.addWidget(error)
        return col

    def _build_advanced_section(self) -> QWidget:
        container = QWidget()
        container.setStyleSheet("QWidget { background: transparent; border: none; }")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Limits Row
        limits_row = QHBoxLayout()
        limits_row.setContentsMargins(0, 0, 0, 0)
        limits_row.setSpacing(12)

        self._max_results_input = LineEdit()
        self._max_results_input.setValidator(QIntValidator(10, 10000, self))
        self._max_results_input.setText("100")
        self._max_results_input.setFixedSize(130, 34)
        self._style_input(self._max_results_input)
        self._max_results_input.setToolTip("Maximum number of leads to extract in this session")
        limits_row.addLayout(self._make_field(tr("search.field.max_depth", self._language), self._max_results_input))

        delay_validator = QDoubleValidator(0.5, 60.0, 1, self)
        delay_validator.setNotation(QDoubleValidator.StandardNotation)

        self._delay_min = LineEdit()
        self._delay_min.setValidator(delay_validator)
        self._delay_min.setText("0.5")
        self._delay_min.setFixedSize(100, 34)
        self._style_input(self._delay_min)
        self._delay_min.setToolTip("Minimum seconds to wait between actions (prevents bans)")
        limits_row.addLayout(self._make_field(tr("search.field.min_delay", self._language), self._delay_min))

        self._delay_max = LineEdit()
        self._delay_max.setValidator(delay_validator)
        self._delay_max.setText("0.5")
        self._delay_max.setFixedSize(100, 34)
        self._style_input(self._delay_max)
        self._delay_max.setToolTip("Maximum seconds to wait (randomized for human-like behavior)")
        limits_row.addLayout(self._make_field(tr("search.field.max_delay", self._language), self._delay_max))
        
        limits_row.addStretch(1)
        
        layout.addLayout(limits_row)

        divider = QFrame()
        divider.setObjectName("AdvDivider")
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"QFrame#AdvDivider {{ background: {Theme.BORDER_LIGHT}; border: none; }}")
        layout.addWidget(divider)

        # Toggles Grid
        toggles = QGridLayout()
        toggles.setSpacing(10)
        
        self._chk_emails = MacSwitch()
        self._chk_headless = MacSwitch()
        self._chk_latest = MacSwitch()
        self._chk_robots = MacSwitch()
        self._chk_refresh = MacSwitch()
        self._chk_social = MacSwitch()
        
        for switch in [self._chk_emails, self._chk_headless, self._chk_latest, self._chk_robots, self._chk_refresh, self._chk_social]:
            self._interactive_widgets.append(switch)
        
        self._chk_emails.setToolTip("Extract email addresses from the websites found")
        self._chk_headless.setToolTip("Run the browser invisibly (Faster)")
        self._chk_latest.setToolTip("Only scrape the most recently posted offers")
        self._chk_robots.setToolTip("Respect robots.txt and website policies")
        self._chk_refresh.setToolTip("Ignore cached data and fetch everything fresh")
        self._chk_social.setToolTip("Search for Instagram, LinkedIn, and Facebook profiles")

        toggles.addWidget(SearchToggleTile(tr("search.toggle.emails", self._language), self._chk_emails), 0, 0)
        toggles.addWidget(SearchToggleTile(tr("search.toggle.headless", self._language), self._chk_headless), 0, 1)
        toggles.addWidget(SearchToggleTile(tr("search.toggle.latest", self._language), self._chk_latest), 1, 0)
        toggles.addWidget(SearchToggleTile(tr("search.toggle.robots", self._language), self._chk_robots), 1, 1)
        toggles.addWidget(SearchToggleTile(tr("search.toggle.refresh", self._language), self._chk_refresh), 2, 0)
        toggles.addWidget(SearchToggleTile(tr("search.toggle.social", self._language), self._chk_social), 2, 1)
        
        layout.addLayout(toggles)
        return container

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text.upper())
        label.setStyleSheet(
            f"color: {Theme.TEXT_TERTIARY}; font-size: 10px; font-weight: 600; "
            "letter-spacing: 0.6px; background: transparent; border: none;"
        )
        return label

    def _style_combo(self, combo: QWidget) -> None:
        if hasattr(combo, "lineEdit") and hasattr(combo.lineEdit(), "setCustomFocusedBorderColor"):
            from PySide6.QtGui import QColor
            combo.lineEdit().setCustomFocusedBorderColor(QColor(0,0,0,0), QColor(0,0,0,0))
        elif hasattr(combo, "setCustomFocusedBorderColor"):
            from PySide6.QtGui import QColor
            combo.setCustomFocusedBorderColor(QColor(0,0,0,0), QColor(0,0,0,0))
            
        combo.setStyleSheet("""
            QComboBox {
                background-color: #252528;
                border: 1px solid #2C2C2E;
                border-radius: 8px;
                color: #FFFFFF;
                padding-left: 10px;
                padding-top: 4px;
                padding-bottom: 4px;
                font-family: 'PT Root UI', sans-serif;
                font-size: 13px;
                font-weight: 500;
            }
            QComboBox:hover, QComboBox:focus {
                background-color: #2C2C2E;
                border: 1px solid #3A3A3C;
            }
            QComboBox:disabled {
                background-color: #1C1C1E;
                border: 1px solid #2C2C2E;
                color: #48484A;
            }
        """)

    def _style_input(self, widget: QWidget) -> None:
        if hasattr(widget, "setCustomFocusedBorderColor"):
            from PySide6.QtGui import QColor
            widget.setCustomFocusedBorderColor(QColor(0,0,0,0), QColor(0,0,0,0))
        widget.setStyleSheet("""
            LineEdit {
                background-color: #252528;
                border: 1px solid #2C2C2E;
                border-radius: 8px;
                color: #FFFFFF;
                padding-left: 10px;
                padding-top: 4px;
                padding-bottom: 4px;
                font-family: 'PT Root UI', sans-serif;
                font-size: 13px;
                font-weight: 500;
            }
            SearchLineEdit {
                padding-left: 32px;
            }
            LineEdit:hover, LineEdit:focus {
                background-color: #2C2C2E;
                border: 1px solid #3A3A3C;
            }
        """)

    def _clear_validation_error(self) -> None:
        self._title_error.setVisible(False)

    def _int_value(self, widget: LineEdit, fallback: int) -> int:
        try:
            return int(widget.text().strip() or str(fallback))
        except ValueError:
            return fallback

    def _delay_value(self, widget: LineEdit, fallback: float) -> float:
        text = (widget.text() or "").strip().replace(",", ".")
        try:
            value = float(text)
        except ValueError:
            return fallback
        return max(0.1, value)

    def _select_source(self, source: str, preserve_values: bool = False) -> None:
        self._source = source
        is_maps = source == "maps"
        self._card_maps.set_active(source == "maps")
        self._card_jobsuche.set_active(source == "jobsuche")
        self._card_ausbildung.set_active(source == "ausbildung")
        self._card_aubiplus.set_active(source == "aubiplus")
        self._card_dasoertliche.set_active(source == "dasoertliche")

        settings = config_manager.settings
        self._offer_type_container.setEnabled(source not in ("maps", "dasoertliche"))
        self._offer_type.setEnabled(source not in ("maps", "dasoertliche"))
        self._chk_latest.setEnabled(source not in ("maps", "dasoertliche"))
        
        if not preserve_values and source not in ("maps", "dasoertliche"):
            ausbildung_text = tr("search.offer.ausbildung", self._language)
            idx = self._offer_type.findText(ausbildung_text)
            self._offer_type.setCurrentIndex(max(idx, 0))
        # Radius is now available for Maps too
        self._radius.setEnabled(True)
        
        # Reload the covered cities for the newly selected source
        self._load_covered_cities()
        
        # Dynamically adjust radius options based on source
        current_radius = self._radius.currentText()
        self._radius.clear()
        
        base_radii = ["0 km", "10 km", "20 km", "25 km", "50 km", "100 km", "200 km"]
        if source == "ausbildung":
            self._radius.addItems(base_radii + ["500 km", "1000 km"])
        else:
            self._radius.addItems(base_radii)
            
        # Restore pre-existing radius or fallback safely to max available without crashing
        if current_radius in [self._radius.itemText(i) for i in range(self._radius.count())]:
            self._radius.setCurrentText(current_radius)
        elif source != "ausbildung" and current_radius in ["500 km", "1000 km"]:
            self._radius.setCurrentText("200 km")
        else:
            self._radius.setCurrentText("25 km")

        if is_maps:
            self._chk_latest.setChecked(False)
        elif not preserve_values:
            self._chk_headless.setChecked(settings.default_headless)

    from src.diagnostics import monitor_slot
    @monitor_slot
    def _launch(self) -> None:
        # Check for License Activation (Trial logic)
        from ..core.security import LicenseManager
        is_active = LicenseManager.is_active()
        
        # Get and validate max_results early for trial users
        max_results = self._int_value(self._max_results_input, 100)
        
        if not is_active:
            status = LicenseManager.get_trial_status()
            if status["remaining"] <= 0:
                if not self.window().show_activation_dialog():
                    return
            
            # Enforce strict 20-scrap limit for trial users silently
            if max_results > 20:
                max_results = 20
                self._max_results_input.setText("20")
                from qfluentwidgets import InfoBar
                InfoBar.warning(
                    tr("search.dialog.trial.title", self._language),
                    "Trial limit enforced. Max limits capped at 20.",
                    duration=3000,
                    parent=self.window()
                )
        
        job_title = self._job_title.text().strip()
        if not job_title:
            self._title_error.setVisible(True)
            self._job_title.setFocus()
            return

        # Offer type mapping for backend (Jobsuche BA expects specific German strings)
        offer_map = {
            tr("search.offer.arbeit", self._language): "Arbeit",
            tr("search.offer.ausbildung", self._language): "Ausbildung/Duales Studium",
            tr("search.offer.praktikum", self._language): "Praktikum/Trainee/Werkstudent",
            tr("search.offer.selbststaendigkeit", self._language): "Selbstständigkeit",
        }
        selected_offer = self._offer_type.currentText()
        backend_offer = offer_map.get(selected_offer, "Arbeit")

        config = SearchConfig(
            job_title=job_title,
            country=self._country.currentText().strip(),
            city=self._city.text().strip(),
            radius=int(self._radius.currentText().split()[0]),
            source_type=SourceType(self._source),
            offer_type=backend_offer,
            max_results=max_results,
            scrape_emails=self._chk_emails.isChecked(),
            latest_offers_only=self._chk_latest.isChecked(),
            headless=self._chk_headless.isChecked(),
            delay_min=self._delay_value(self._delay_min, 0.5),
            delay_max=self._delay_value(self._delay_max, 0.5),
            respect_robots=self._chk_robots.isChecked(),
            bypass_cache=self._chk_refresh.isChecked(),
            extract_social_profiles=self._chk_social.isChecked(),
        )
        self._save_last_search()
        # Also save to search history db
        config_manager.save_search(
            job_title=self._job_title.text().strip(),
            city=self._city.text().strip(),
            source=self._source,
            offer_type=backend_offer,
            radius=int(self._radius.currentText().split()[0]),
        )
        self.job_requested.emit(config)

    def _clear_form(self) -> None:
        from .components import ZugzwangDialog
        msg = ZugzwangDialog(
            "Clear Search Data",
            "Are you sure you want to clear the search inputs and reset the city coverage history?",
            self.window(),
            destructive=True
        )
        if not msg.exec():
            return

        settings = config_manager.settings
        self._job_title.clear()
        self._city.clear()
        self._country.setCurrentText("Germany")
        self._offer_type.setCurrentIndex(1)
        self._clear_validation_error()

        from ..core.security import LicenseManager
        is_free = not LicenseManager.is_active()
        default_max = 20 if is_free else settings.default_max_results

        self._max_results_input.setText(str(max(10, min(10000, default_max))))
        self._delay_min.setText(f"{settings.default_delay_min:.1f}")
        self._delay_max.setText(f"{settings.default_delay_max:.1f}")
        self._chk_emails.setChecked(settings.default_scrape_emails)
        self._chk_headless.setChecked(settings.default_headless)
        self._chk_robots.setChecked(settings.default_respect_robots)
        self._chk_latest.setChecked(False)
        self._chk_refresh.setChecked(settings.default_bypass_cache)
        self._chk_social.setChecked(settings.default_extract_social_profiles)
        self._radius.setCurrentText(f"{settings.last_search_radius} km")
        self._select_source(self._source, preserve_values=True)
        
        # Clear city coverage history
        from ..core.config import get_memory_db_path
        import sqlite3
        try:
            db_path = str(get_memory_db_path())
            with sqlite3.connect(db_path, timeout=2.0) as conn:
                conn.execute("DELETE FROM jobs")
            self._load_covered_cities()
            
            from qfluentwidgets import InfoBar, InfoBarPosition
            InfoBar.success(
                title="Cleared",
                content="Search fields and city coverage history have been reset.",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
        except Exception as e:
            from ..core.logger import get_logger
            get_logger(__name__).warning(f"Failed to clear coverage history: {e}")

    def refresh_license_state(self) -> None:
        from ..core.security import LicenseManager

        settings = config_manager.settings
        is_free = not LicenseManager.is_active()
        current_max = self._int_value(self._max_results_input, settings.default_max_results)

        if is_free:
            current_max = min(20, current_max)
        elif current_max <= 20 and (settings.last_search_max_results or 0) <= 20:
            current_max = settings.default_max_results

        self._max_results_input.setText(str(max(10, min(10000, current_max))))
        
        # Sync Coverage Tracker Panel state
        if is_free:
            self._pro_overlay.setVisible(True)
            self._coverage_panel.setEnabled(False)
            if not getattr(self._coverage_panel, '_is_preview_mode', False):
                self._coverage_panel.reload_full_coverage(preview_mode=True)
        else:
            self._pro_overlay.setVisible(False)
            self._coverage_panel.setEnabled(True)
            if getattr(self._coverage_panel, '_is_preview_mode', False):
                self._coverage_panel.reload_full_coverage(preview_mode=False)
                self._load_covered_cities()

    def _load_last_search(self) -> None:
        settings = config_manager.settings
        self._job_title.setText(settings.last_search_job_title or "")
        self._city.setText(settings.last_search_city or "")
        self._clear_validation_error()

        self._country.setCurrentText(settings.last_search_country or "Germany")

        # Map back from backend value to localized index
        backend_val = settings.last_search_offer_type or "Ausbildung"
        rev_map = {
            "Arbeit": tr("search.offer.arbeit", self._language),
            "Ausbildung/Duales Studium": tr("search.offer.ausbildung", self._language),
            "Praktikum/Trainee/Werkstudent": tr("search.offer.praktikum", self._language),
            "Selbstständigkeit": tr("search.offer.selbststaendigkeit", self._language),
        }
        localized_val = rev_map.get(backend_val, tr("search.offer.ausbildung", self._language))
        offer_index = self._offer_type.findText(localized_val)
        self._offer_type.setCurrentIndex(max(offer_index, 0))

        from ..core.security import LicenseManager
        is_free = not LicenseManager.is_active()
        last_max = settings.last_search_max_results or settings.default_max_results
        if is_free:
            last_max = min(20, last_max)
        elif last_max <= 20:
            last_max = settings.default_max_results

        self._max_results_input.setText(str(max(10, min(10000, last_max))))
        self._delay_min.setText(f"{(settings.last_search_delay_min or settings.default_delay_min):.1f}")
        self._delay_max.setText(f"{(settings.last_search_delay_max or settings.default_delay_max):.1f}")
        self._chk_emails.setChecked(bool(settings.last_search_scrape_emails))
        self._chk_headless.setChecked(bool(settings.last_search_headless))
        self._chk_latest.setChecked(bool(settings.last_search_latest_offers_only))
        self._chk_refresh.setChecked(bool(settings.last_search_bypass_cache))
        self._chk_social.setChecked(bool(settings.last_search_social_profiles))
        self._chk_robots.setChecked(bool(settings.last_search_respect_robots))
        self._chk_latest.setChecked(bool(settings.last_search_latest_offers_only))
        self._radius.setCurrentText(f"{settings.last_search_radius} km")

        source = settings.last_search_source if settings.last_search_source in ("maps", "jobsuche", "ausbildung", "aubiplus") else "maps"
        self._select_source(source, preserve_values=True)

    def _save_last_search(self) -> None:
        config_manager.update(
            last_search_job_title=self._job_title.text().strip(),
            last_search_country=self._country.currentText().strip() or "Germany",
            last_search_city=self._city.text().strip(),
            last_search_source=self._source,
            last_search_offer_type=self._offer_type.currentText(),
            last_search_max_results=self._int_value(self._max_results_input, 100),
            last_search_delay_min=self._delay_value(self._delay_min, config_manager.settings.default_delay_min),
            last_search_delay_max=self._delay_value(self._delay_max, config_manager.settings.default_delay_max),
            last_search_scrape_emails=self._chk_emails.isChecked(),
            last_search_headless=self._chk_headless.isChecked(),
            last_search_latest_offers_only=self._chk_latest.isChecked(),
            last_search_respect_robots=self._chk_robots.isChecked(),
            last_search_bypass_cache=self._chk_refresh.isChecked(),
            last_search_social_profiles=self._chk_social.isChecked(),
            last_search_radius=int(self._radius.currentText().split()[0]),
        )

    def _apply_history(self, item: dict) -> None:
        """Populate all form fields from a history item dict."""
        self._job_title.setText(item.get("job_title", ""))
        self._city.setText(item.get("city", ""))
        source = item.get("source", "maps")
        if source in ("maps", "jobsuche", "ausbildung", "aubiplus"):
            self._select_source(source, preserve_values=True)
        # Try to find the offer_type in localized combo
        offer = item.get("offer_type", "")
        if offer:
            idx = self._offer_type.findText(offer)
            if idx >= 0:
                self._offer_type.setCurrentIndex(idx)
            else:
                # Try localized reverse mapping
                rev_map = {
                    "Arbeit": tr("search.offer.arbeit", self._language),
                    "Ausbildung/Duales Studium": tr("search.offer.ausbildung", self._language),
                    "Praktikum/Trainee/Werkstudent": tr("search.offer.praktikum", self._language),
                    "Selbstständigkeit": tr("search.offer.selbststaendigkeit", self._language),
                }
                localized = rev_map.get(offer, "")
                if localized:
                    idx2 = self._offer_type.findText(localized)
                    if idx2 >= 0:
                        self._offer_type.setCurrentIndex(idx2)
        
        radius = item.get("radius", 25)
        self._radius.setCurrentText(f"{radius} km")
        
        self._clear_validation_error()

    def mousePressEvent(self, event) -> None:
        if hasattr(self, '_job_title'):
            self._job_title.clearFocus()
        if hasattr(self, '_history_dropdown'):
            self._history_dropdown.hide()
        super().mousePressEvent(event)

    def lock(self) -> None:
        for widget in self._interactive_widgets:
            widget.setEnabled(False)
        self._launch_btn.setText(tr("search.launch.loading", self._language))

    def unlock(self) -> None:
        for widget in self._interactive_widgets:
            widget.setEnabled(True)
        self._launch_btn.setText(tr("search.launch", self._language))
        self._select_source(self._source, preserve_values=True)

    def _on_coverage_city_clicked(self, city: str) -> None:
        """Fills the city field when a coverage chip is clicked."""
        self._city.setText(city)

    def _load_covered_cities(self) -> None:
        """Fetch completed jobs from app_memory.db asynchronously to determine coverage."""
        from ..core.config import get_memory_db_path
        from ..utils.db_worker import run_in_thread
        import sqlite3
        import os
        import json
        
        current_source = self._source

        def _normalize(s: str) -> str:
            """Umlaut-safe lower-case — matches the normalization in CoverageTrackerPanel."""
            return (
                s.lower()
                .replace("ä", "a").replace("ö", "o").replace("ü", "u").replace("ß", "ss")
                .strip()
            )

        def _fetch_cities():
            db_path = str(get_memory_db_path())
            if not os.path.exists(db_path):
                return set()

            covered = set()
            conn = sqlite3.connect(db_path, timeout=5.0)
            try:
                conn.execute("PRAGMA journal_mode=WAL")
                rows = conn.execute(
                    "SELECT config_json FROM jobs WHERE status = 'completed'"
                ).fetchall()
                for row in rows:
                    if not row[0]:
                        continue
                    try:
                        config_data = json.loads(row[0])
                        # Only mark as covered if the job was run for the currently selected source
                        # Enums are serialized as their value string, e.g. "maps", "jobsuche"
                        job_source = config_data.get("source_type")
                        if job_source != current_source:
                            continue
                            
                        # 'city' is the canonical field written by SearchConfig.__dict__
                        city = (config_data.get("city") or "").strip()
                        if city:
                            covered.add(_normalize(city))
                    except Exception:
                        pass
                return covered
            except Exception:
                return set()
            finally:
                conn.close()

        def _on_cities_fetched(covered_set: set[str]):
            if hasattr(self, '_coverage_panel') and self._coverage_panel:
                self._coverage_panel.set_covered_cities(covered_set)

        run_in_thread(_fetch_cities, on_result=_on_cities_fetched)


# 1.1.0 Beta5
