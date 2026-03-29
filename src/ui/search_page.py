"""
ZUGZWANG - Search Page
Target Generation workflow using Obsidian Core design language.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QPropertyAnimation, Property, QEasingCurve
from PySide6.QtGui import QDoubleValidator, QIntValidator, QColor
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget, QGraphicsDropShadowEffect

from qfluentwidgets import (
    ComboBox,
    EditableComboBox,
    FluentIcon,
    IconWidget,
    LineEdit,
    PrimaryPushButton,
    PushButton,
)
from .components import StatCard, SectionCard, MacSwitch

from ..core.config import config_manager
from ..core.models import SearchConfig, SourceType
from .theme import Theme


class SearchSourceCard(QFrame):
    activated = Signal(str)

    def __init__(self, key: str, icon_name: FluentIcon, title: str, body: str, parent=None):
        super().__init__(parent)
        self._key = key
        self._active = False
        self._hover_opacity = 0.0
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(220, 124)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(6)

        header = QHBoxLayout()
        self._icon = IconWidget(icon_name)
        self._icon.setFixedSize(20, 20)
        self._icon.setStyleSheet(f"color: #8E8E93;")
        header.addWidget(self._icon)
        header.addStretch(1)
        
        # Pill Status Badge 
        self._status_badge = QFrame()
        self._status_badge.setObjectName("StatusBadge")
        self._status_badge.setFixedHeight(18)
        self._status_badge.setStyleSheet("QFrame#StatusBadge { border: 1.2px solid #0A84FF; border-radius: 9px; background: transparent; }")
        badge_layout = QHBoxLayout(self._status_badge)
        badge_layout.setContentsMargins(8, 0, 8, 0)
        badge_layout.setSpacing(0)
        self._status_label = QLabel("SELECTED")
        self._status_label.setStyleSheet("color: #0A84FF; font-family: 'SF Mono', 'Menlo', monospace; font-size: 9px; font-weight: 700; background: transparent; border: none;")
        self._status_label.setAlignment(Qt.AlignCenter)
        badge_layout.addWidget(self._status_label)
        self._status_badge.setVisible(False)
        header.addWidget(self._status_badge)
        
        layout.addLayout(header)
        layout.addStretch(1)

        self._title = QLabel(title)
        self._title.setStyleSheet(f"color: #FFFFFF; font-family: 'PT Root UI', sans-serif; font-size: 18px; font-weight: 700; background: transparent; border: none;")
        layout.addWidget(self._title)

        self._body = QLabel(body)
        self._body.setWordWrap(True)
        self._body.setStyleSheet(f"color: #8E8E93; font-family: 'SF Mono', 'Menlo', monospace; font-size: 10px; font-weight: 600; letter-spacing: 0.5px; background: transparent; border: none;")
        layout.addWidget(self._body)

        # ZUGZWANG Elevation Effect
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(12)
        self._shadow.setXOffset(0)
        self._shadow.setYOffset(2)
        self._shadow.setColor(QColor(0, 0, 0, 102))
        self.setGraphicsEffect(self._shadow)

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

    def enterEvent(self, event):
        self._anim = QPropertyAnimation(self._shadow, b"yOffset")
        self._anim.setDuration(120)
        self._anim.setEndValue(6)
        self._anim_blur = QPropertyAnimation(self._shadow, b"blurRadius")
        self._anim_blur.setDuration(120)
        self._anim_blur.setEndValue(16)
        self._anim.start()
        self._anim_blur.start()
        self._apply_style(hovered=True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._anim = QPropertyAnimation(self._shadow, b"yOffset")
        self._anim.setDuration(120)
        self._anim.setEndValue(2)
        self._anim_blur = QPropertyAnimation(self._shadow, b"blurRadius")
        self._anim_blur.setDuration(120)
        self._anim_blur.setEndValue(12)
        self._anim.start()
        self._anim_blur.start()
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

    def __init__(self):
        super().__init__()
        self._source = "maps"
        self._interactive_widgets: list[QWidget] = []
        self._build_ui()
        self._load_last_search()

    def header_action_widgets(self) -> list[QWidget]:
        return []

    def _build_ui(self) -> None:
        self.setObjectName("searchPage")
        self.setStyleSheet(f"QWidget#searchPage {{ background: {Theme.BG_OBSIDIAN}; }}")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        host = QWidget()
        root.addWidget(host)

        body = QVBoxLayout(host)
        body.setContentsMargins(32, 20, 32, 20)
        body.setSpacing(14)

        header = QHBoxLayout()
        self._page_title = QLabel("Target Generation")
        self._page_title.setStyleSheet("color: #FFFFFF; font-family: 'PT Root UI', sans-serif; font-size: 28px; font-weight: 600; background: transparent; border: none;")
        header.addWidget(self._page_title)
        header.addStretch(1)

        self._clear_btn = PushButton("CLEAR")
        self._clear_btn.setFixedSize(80, 40)
        self._clear_btn.setStyleSheet(Theme.danger_button())
        self._clear_btn.clicked.connect(self._clear_form)
        self._interactive_widgets.append(self._clear_btn)
        header.addWidget(self._clear_btn)
        body.addLayout(header)

        # Step 1: Intelligence Source
        body.addWidget(self._step_card("1", "Intelligence Source", self._build_source_section(), compact=True))

        # Main Area: Parameters and Advanced Controls side-by-side
        main_layout = QHBoxLayout()
        main_layout.setSpacing(24)
        
        self._target_card = self._step_card("2", "Target Blueprint", self._build_target_section())
        self._advanced_card = self._step_card("3", "Advanced Controls", self._build_advanced_section())
        
        main_layout.addWidget(self._target_card, 55)
        main_layout.addWidget(self._advanced_card, 45)
        body.addLayout(main_layout, 1)

        # Launch Button
        from PySide6.QtWidgets import QPushButton as _QPB
        self._launch_btn = _QPB("START SCRAPING JOB")
        self._launch_btn.setFixedSize(320, 42)
        self._launch_btn.setCursor(Qt.PointingHandCursor)
        self._launch_btn.setStyleSheet(Theme.zugzwang_primary_button())
        self._launch_btn.clicked.connect(self._launch)
        self._interactive_widgets.append(self._launch_btn)
        
        # Pulse Animation
        from PySide6.QtWidgets import QGraphicsOpacityEffect
        self._btn_op_effect = QGraphicsOpacityEffect(self._launch_btn)
        self._btn_op_effect.setOpacity(0.85)
        self._launch_btn.setGraphicsEffect(self._btn_op_effect)
        self._pulse_anim = QPropertyAnimation(self._btn_op_effect, b"opacity", self)
        self._pulse_anim.setDuration(2000)
        self._pulse_anim.setStartValue(0.85)
        self._pulse_anim.setEndValue(1.0)
        self._pulse_anim.setLoopCount(-1)
        self._pulse_anim.setEasingCurve(QEasingCurve.InOutSine)
        self._pulse_anim.start()
        
        body.addWidget(self._launch_btn, 0, Qt.AlignHCenter)

    def _step_card(self, num: str, title: str, content: QWidget, compact: bool = False) -> QFrame:
        card = QFrame()
        card.setObjectName(f"StepCard{num}")
        card.setStyleSheet(f"QFrame#StepCard{num} {{ background: transparent; border: none; }}")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(16)

        header = QHBoxLayout()
        header.setSpacing(12)
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
        if not compact:
            layout.addStretch(1)
        return card

    def _build_source_section(self) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addStretch(1)

        self._card_maps = SearchSourceCard(
            "maps",
            FluentIcon.GLOBE,
            "Google Maps",
            "Extract business details, contact info, and ratings worldwide.",
        )
        self._card_jobsuche = SearchSourceCard(
            "jobsuche",
            FluentIcon.SEARCH,
            "Jobsuche (BA)",
            "Monitor federal job listings and corporate hiring signals.",
        )
        self._card_ausbildung = SearchSourceCard(
            "ausbildung",
            FluentIcon.EDUCATION,
            "Ausbildung.de",
            "Hunt for apprenticeship and training positions.",
        )
        self._card_aubiplus = SearchSourceCard(
            "aubiplus",
            FluentIcon.CERTIFICATE,
            "Aubi-Plus",
            "Premium apprenticeships and dual study programs.",
        )
        self._card_maps.activated.connect(self._select_source)
        self._card_jobsuche.activated.connect(self._select_source)
        self._card_ausbildung.activated.connect(self._select_source)
        self._card_aubiplus.activated.connect(self._select_source)
        self._interactive_widgets.extend([self._card_maps, self._card_jobsuche, self._card_ausbildung, self._card_aubiplus])

        layout.addWidget(self._card_maps)
        layout.addWidget(self._card_jobsuche)
        layout.addWidget(self._card_ausbildung)
        layout.addWidget(self._card_aubiplus)
        layout.addStretch(1)
        return container

    def _build_target_section(self) -> QWidget:
        container = QWidget()
        container.setStyleSheet("QWidget { background: transparent; border: none; }")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        # Job Title
        self._job_title = LineEdit()
        self._job_title.setFixedHeight(40)
        self._job_title.setPlaceholderText("e.g. Software Engineer, Pflegefachmann")
        self._job_title.textChanged.connect(self._clear_validation_error)
        self._style_input(self._job_title)

        self._title_error = QLabel("This field is required")
        self._title_error.setStyleSheet(f"color: {Theme.DANGER}; font-size: 11px; font-weight: 700; background: transparent; border: none;")
        self._title_error.setVisible(False)

        layout.addLayout(self._make_field("Industry or Job Title", self._job_title, self._title_error))

        # Location Row
        loc_row = QHBoxLayout()
        loc_row.setSpacing(12)

        self._country = EditableComboBox()
        self._country.setFixedHeight(40)
        self._country.addItems(["Germany", "United States", "United Kingdom", "France", "Netherlands", "Switzerland", "Austria"])
        self._style_combo(self._country)
        loc_row.addLayout(self._make_field("Target Country", self._country), 1)

        self._city = LineEdit()
        self._city.setFixedHeight(40)
        self._city.setPlaceholderText("e.g. Berlin")
        self._style_input(self._city)
        loc_row.addLayout(self._make_field("City / Region", self._city), 1)
        
        layout.addLayout(loc_row)

        # Offer Type (Specific for Jobsuche)
        self._offer_type_container = QWidget()
        self._offer_type_container.setStyleSheet("QWidget { background: transparent; border: none; }")
        offer_vbox = QVBoxLayout(self._offer_type_container)
        offer_vbox.setContentsMargins(0, 0, 0, 0)
        offer_vbox.setSpacing(6)
        
        self._offer_type = ComboBox()
        self._offer_type.setFixedHeight(40)
        self._offer_type.addItems([
            "Arbeit", "Ausbildung/Duales Studium",
            "Praktikum/Trainee/Werkstudent", "Selbstständigkeit"
        ])
        self._style_combo(self._offer_type)
        offer_vbox.addLayout(self._make_field("Offer Type (Jobsuche specific)", self._offer_type))
        
        layout.addWidget(self._offer_type_container)
        return container

    def _make_field(self, label: str, widget: QWidget, error: QWidget = None) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(8)
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
        layout.setSpacing(16)

        # Limits Row
        limits_row = QHBoxLayout()
        limits_row.setSpacing(12)

        max_col = QVBoxLayout()
        max_col.setSpacing(6)
        max_col.addWidget(self._field_label("Max Depth Limit"))
        self._max_results_input = LineEdit()
        self._max_results_input.setValidator(QIntValidator(10, 10000, self))
        self._max_results_input.setText("100")
        self._max_results_input.setFixedSize(130, 40)
        self._style_input(self._max_results_input)
        max_col.addWidget(self._max_results_input)
        limits_row.addLayout(max_col)

        delay_validator = QDoubleValidator(0.5, 60.0, 1, self)
        delay_validator.setNotation(QDoubleValidator.StandardNotation)

        min_col = QVBoxLayout()
        min_col.setSpacing(6)
        min_col.addWidget(self._field_label("Min Delay (s)"))
        self._delay_min = LineEdit()
        self._delay_min.setValidator(delay_validator)
        self._delay_min.setText("0.5")
        self._delay_min.setFixedSize(100, 40)
        self._style_input(self._delay_min)
        min_col.addWidget(self._delay_min)
        limits_row.addLayout(min_col)

        max_delay_col = QVBoxLayout()
        max_delay_col.setSpacing(6)
        max_delay_col.addWidget(self._field_label("Max Delay (s)"))
        self._delay_max = LineEdit()
        self._delay_max.setValidator(delay_validator)
        self._delay_max.setText("0.5")
        self._delay_max.setFixedSize(100, 40)
        self._style_input(self._delay_max)
        max_delay_col.addWidget(self._delay_max)
        limits_row.addLayout(max_delay_col)
        limits_row.addStretch(1)
        
        layout.addLayout(limits_row)

        divider = QFrame()
        divider.setObjectName("AdvDivider")
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"QFrame#AdvDivider {{ background: {Theme.BORDER_LIGHT}; border: none; }}")
        layout.addWidget(divider)

        # Toggles Grid
        toggles = QGridLayout()
        toggles.setSpacing(14)
        
        self._chk_emails = MacSwitch()
        self._chk_headless = MacSwitch()
        self._chk_latest = MacSwitch()
        self._chk_robots = MacSwitch()
        self._chk_refresh = MacSwitch()
        self._chk_social = MacSwitch()
        
        for switch in [self._chk_emails, self._chk_headless, self._chk_latest, self._chk_robots, self._chk_refresh, self._chk_social]:
            self._interactive_widgets.append(switch)

        toggles.addWidget(SearchToggleTile("Engage Email Resolution", self._chk_emails), 0, 0)
        toggles.addWidget(SearchToggleTile("Execute Headless", self._chk_headless), 0, 1)
        toggles.addWidget(SearchToggleTile("Latest Offers Only", self._chk_latest), 1, 0)
        toggles.addWidget(SearchToggleTile("Honor Robots Protocol", self._chk_robots), 1, 1)
        toggles.addWidget(SearchToggleTile("Bypass Local Cache", self._chk_refresh), 2, 0)
        toggles.addWidget(SearchToggleTile("Extract Social Profiles", self._chk_social), 2, 1)
        
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
        combo.setStyleSheet(Theme.combo_box())

    def _style_input(self, widget: QWidget) -> None:
        widget.setStyleSheet(Theme.line_edit())

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

        settings = config_manager.settings
        self._offer_type_container.setEnabled(not is_maps)
        self._chk_latest.setEnabled(not is_maps)
        if is_maps:
            self._chk_latest.setChecked(False)
        elif not preserve_values:
            self._chk_headless.setChecked(settings.default_headless)

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
            
            # Enforce strict 20-scrap limit for trial users
            if max_results > 20:
                from .components import ZugzwangDialog
                res = ZugzwangDialog(
                    "Trial Limit", 
                    "Free trial search is limited to 20 records per session to keep the server stable. "
                    "Would you like to activate the full version for unlimited depth?", 
                    self
                ).exec()
                if res:
                    if not self.window().show_activation_dialog():
                        return
                # Force to 20 if they skip activation
                max_results = 20
                self._max_results_input.setText("20")
        
        job_title = self._job_title.text().strip()
        if not job_title:
            self._title_error.setVisible(True)
            self._job_title.setFocus()
            return

        source_map = {
            "maps": SourceType.GOOGLE_MAPS,
            "jobsuche": SourceType.JOBSUCHE,
            "ausbildung": SourceType.AUSBILDUNG_DE,
            "aubiplus": SourceType.AUBIPLUS_DE,
        }

        config = SearchConfig(
            job_title=job_title,
            country=self._country.text().strip() or "Germany",
            city=self._city.text().strip(),
            source_type=source_map.get(self._source, SourceType.GOOGLE_MAPS),
            offer_type=self._offer_type.currentText(),
            max_results=self._int_value(self._max_results_input, 100),
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
        self.job_requested.emit(config)

    def _clear_form(self) -> None:
        settings = config_manager.settings
        self._job_title.clear()
        self._city.clear()
        self._country.setText("Germany")
        self._offer_type.setCurrentIndex(0)
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
        self._select_source(self._source, preserve_values=True)

    def _load_last_search(self) -> None:
        settings = config_manager.settings
        self._job_title.setText(settings.last_search_job_title or "")
        self._city.setText(settings.last_search_city or "")
        self._clear_validation_error()

        self._country.setText(settings.last_search_country or "Germany")

        offer_index = self._offer_type.findText(settings.last_search_offer_type or "Arbeit")
        self._offer_type.setCurrentIndex(max(offer_index, 0))

        from ..core.security import LicenseManager
        is_free = not LicenseManager.is_active()
        last_max = settings.last_search_max_results or settings.default_max_results
        if is_free:
            last_max = min(20, last_max)

        self._max_results_input.setText(str(max(10, min(10000, last_max))))
        self._delay_min.setText(f"{(settings.last_search_delay_min or settings.default_delay_min):.1f}")
        self._delay_max.setText(f"{(settings.last_search_delay_max or settings.default_delay_max):.1f}")
        self._chk_emails.setChecked(bool(settings.last_search_scrape_emails))
        self._chk_headless.setChecked(bool(settings.last_search_headless))
        self._chk_latest.setChecked(bool(settings.last_search_latest_offers_only))
        self._chk_refresh.setChecked(bool(settings.last_search_bypass_cache))
        self._chk_social.setChecked(bool(settings.last_search_social_profiles))
        self._chk_robots.setChecked(bool(settings.last_search_respect_robots))

        source = settings.last_search_source if settings.last_search_source in ("maps", "jobsuche", "ausbildung", "aubiplus") else "maps"
        self._select_source(source, preserve_values=True)

    def _save_last_search(self) -> None:
        config_manager.update(
            last_search_job_title=self._job_title.text().strip(),
            last_search_country=self._country.text().strip() or "Germany",
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
        )

    def lock(self) -> None:
        for widget in self._interactive_widgets:
            widget.setEnabled(False)
        self._launch_btn.setText("Booting Protocol...")

    def unlock(self) -> None:
        for widget in self._interactive_widgets:
            widget.setEnabled(True)
        self._launch_btn.setText("Start Scraping Job")
        self._select_source(self._source, preserve_values=True)
