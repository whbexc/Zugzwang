from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QWidget, QPushButton, QScrollBar, QSizePolicy,
)
from qfluentwidgets import LineEdit

from .components import FlowLayout
from ..core.locations import GERMAN_CITIES_BY_STATE, ALL_CITIES

# Single shared QSS driven by a dynamic "covered" property.
_CHIP_QSS = """
    QPushButton[covered="true"] {
        background: #0A84FF;
        border: 1px solid #0A84FF;
        border-radius: 12px;
        color: #FFFFFF;
        font-family: 'PT Root UI', sans-serif;
        font-size: 12px;
        font-weight: 600;
        padding: 4px 12px;
        outline: none;
    }
    QPushButton[covered="true"]:focus {
        border: 1px solid #0A84FF;
        outline: none;
    }
    QPushButton[covered="false"] {
        background: transparent;
        border: 1px solid #8E8E93;
        border-radius: 12px;
        color: #8E8E93;
        font-family: 'PT Root UI', sans-serif;
        font-size: 12px;
        padding: 4px 12px;
        outline: none;
    }
    QPushButton[covered="false"]:focus {
        border: 1px solid #8E8E93;
        outline: none;
    }
    QPushButton[covered="false"]:hover {
        border-color: #EBEBF5;
        color: #EBEBF5;
    }
"""

# Scroll height = 7 chip rows × 28px + 6 row-gaps × 8px + state-label 18px + label-gap 8px
_SCROLL_HEIGHT = 7 * 28 + 6 * 8 + 18 + 8  # = 274px


class CoverageTrackerPanel(QFrame):
    """
    Scrollable panel showing coverage of German settlements.
    Clicking a settlement emits city_clicked which auto-fills search parameters.

    Grid construction is deferred and batched so it never freezes the UI.
    The header shows a live "COVERAGE · <Bundesland>" indicator as the user scrolls.
    """
    city_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CoverageTrackerPanel")
        self.setStyleSheet(
            """
            QFrame#CoverageTrackerPanel {
                background: #1C1C1E;
                border: 2px solid #3A3A3C;
                border-radius: 12px;
            }
            """
            + _CHIP_QSS
        )

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 6, 16, 6)
        main_layout.setSpacing(8)

        # ── Header ───────────────────────────────────────────────────────────
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(0)

        self._title_label = QLabel("COVERAGE")
        self._title_label.setStyleSheet(
            "color: #8E8E93; font-family: 'PT Root UI', sans-serif; "
            "font-size: 11px; font-weight: 700; letter-spacing: 1px;"
        )

        # Muted secondary state indicator — hidden until build completes
        self._state_indicator = QLabel("")
        self._state_indicator.setStyleSheet(
            "color: #636366; font-family: 'PT Root UI', sans-serif; "
            "font-size: 11px; font-weight: 500; letter-spacing: 0.5px;"
        )
        self._state_indicator.setVisible(False)

        total = len(ALL_CITIES)
        self._summary_label = QLabel(f"0 / {total} settlements covered")
        self._summary_label.setStyleSheet(
            "color: #EBEBF5; font-family: 'PT Root UI', sans-serif; "
            "font-size: 13px; font-weight: 500;"
        )

        self._search_box = LineEdit()
        self._search_box.setPlaceholderText("Filter cities...")
        self._search_box.setFixedWidth(160)
        self._search_box.setFixedHeight(28)
        if hasattr(self._search_box, "setCustomFocusedBorderColor"):
            from PySide6.QtGui import QColor
            self._search_box.setCustomFocusedBorderColor(QColor(0,0,0,0), QColor(0,0,0,0))
        self._search_box.setStyleSheet("""
            LineEdit {
                background-color: #252528;
                border: 1px solid #2C2C2E;
                border-radius: 8px;
                color: #FFFFFF;
                padding-left: 10px;
                padding-top: 2px;
                padding-bottom: 2px;
                font-family: 'PT Root UI', sans-serif;
                font-size: 13px;
                font-weight: 500;
            }
            LineEdit:focus {
                border: 1px solid #0A84FF;
                background-color: #2C2C2E;
            }
            LineEdit:disabled {
                background-color: #1C1C1E;
                color: #636366;
            }
        """)
        self._search_box.textChanged.connect(self._on_search_changed)

        header.addWidget(self._title_label)
        header.addWidget(self._state_indicator)
        header.addStretch(1)
        header.addWidget(self._search_box)
        header.addSpacing(8)
        header.addWidget(self._summary_label)
        main_layout.addLayout(header)

        # ── City Scroll Area ─────────────────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setMinimumHeight(120)  # Allow shrinking if window is small
        self._scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        # Make the scroll area background transparent so the panel's own
        # #1C1C1E background shows through the bottom margin gap.
        self._scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollArea > QWidget { background: transparent; }"
        )

        # Direct placement — the main_layout's 10px bottom contentsMargin
        # creates the visible gap between the scroll area and the panel border.
        main_layout.addWidget(self._scroll)

        self._content = QWidget()
        self._scroll.setWidget(self._content)
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 24)
        self._content_layout.setSpacing(16)
        self._content_layout.setAlignment(Qt.AlignTop)

        # Connect scroll position → live Bundesland indicator
        self._scroll.verticalScrollBar().valueChanged.connect(self._on_scroll)

        # State tracking
        self._chip_buttons: dict[str, QPushButton] = {}
        # (state_name, state_container_widget, [chip_buttons])
        self._state_containers: list[tuple[str, QWidget, list[QPushButton]]] = []
        self._chip_normalized: dict[str, str] = {}
        self._pending_covered: set[str] | None = None

        # Deferred build — one Bundesland per timer tick keeps UI responsive.
        self._build_queue = sorted(GERMAN_CITIES_BY_STATE.items())
        self._build_index = 0
        self._build_timer = QTimer(self)
        self._build_timer.setInterval(0)
        self._build_timer.timeout.connect(self._build_next_state)
        self._build_timer.start()

    def reload_full_coverage(self, preview_mode=False):
        """Rebuilds the entire coverage panel with full data (or redacted preview data)."""
        self._is_preview_mode = preview_mode
        
        # Stop existing build
        self._build_timer.stop()
        self._chip_buttons.clear()
        self._state_containers.clear()
        self._chip_normalized.clear()
        
        # Clear content layout
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        # Restart build queue
        self._build_queue = sorted(GERMAN_CITIES_BY_STATE.items())
        self._build_index = 0
        self._build_timer.start(0)

    # ── Deferred grid construction ───────────────────────────────────────────

    def _build_next_state(self):
        """Build one Bundesland worth of chips per timer tick."""
        if self._build_index >= len(self._build_queue):
            self._build_timer.stop()
            if self._pending_covered is not None:
                self.set_covered_cities(self._pending_covered)
                self._pending_covered = None
            # Show initial state label once the first section is visible
            self._on_scroll(self._scroll.verticalScrollBar().value())
            return

        state, cities = self._build_queue[self._build_index]
        self._build_index += 1

        # In preview mode, stop early so the widget remains small enough for QGraphicsBlurEffect to render
        if getattr(self, '_is_preview_mode', False) and self._build_index >= 2:
            self._build_queue = [] # Force stop on next tick

        state_container = QWidget()
        state_layout = QVBoxLayout(state_container)
        # 10px bottom margin ensures the last chip row of every state group
        # always has visible breathing room before the viewport edge — works at
        # every scroll position, not just the absolute bottom of all content.
        state_layout.setContentsMargins(0, 0, 0, 10)
        state_layout.setSpacing(8)

        state_lbl = QLabel(state.upper())
        state_lbl.setStyleSheet(
            "color: #8E8E93; font-family: 'PT Root UI', sans-serif; "
            "font-size: 10px; font-weight: 600; letter-spacing: 0.5px;"
        )
        state_layout.addWidget(state_lbl)

        flow_container = QWidget()
        flow_layout = FlowLayout(flow_container, margin=0, hSpacing=8, vSpacing=8)

        state_chips: list[QPushButton] = []
        is_preview = getattr(self, '_is_preview_mode', False)
        for city in sorted(cities):
            display_text = city if not is_preview else "•••••••••"
            btn = QPushButton(display_text)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setProperty("covered", "false")
            btn.clicked.connect(lambda _, c=city: self.city_clicked.emit(c))
            flow_layout.addWidget(btn)

            self._chip_buttons[city] = btn
            self._chip_normalized[city] = self._normalize(city)
            state_chips.append(btn)

        state_layout.addWidget(flow_container)
        self._content_layout.addWidget(state_container)
        self._state_containers.append((state, state_container, state_chips))

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _normalize(s: str) -> str:
        return (
            s.lower()
            .replace("ä", "a")
            .replace("ö", "o")
            .replace("ü", "u")
            .replace("ß", "ss")
        )

    # ── Slots ────────────────────────────────────────────────────────────────

    def _on_scroll(self, scroll_y: int):
        """
        Update the state indicator in the header to whichever Bundesland group
        is at/just above the visible viewport top. Cheap O(n_states) check
        against cached widget positions — no layout re-queries needed.
        """
        viewport_top = scroll_y  # scroll value == content-y of the viewport top

        # Walk states in reverse order so we find the last one whose top is
        # still at-or-above the viewport top.
        current_state = None
        for state, container, _ in self._state_containers:
            if not container.isVisible():
                continue
            container_y = container.pos().y()
            if container_y <= viewport_top:
                current_state = state

        if current_state:
            self._state_indicator.setText(f" · {current_state.upper()}")
            self._state_indicator.setVisible(True)
        else:
            self._state_indicator.setVisible(False)

    def _on_search_changed(self, text: str):
        query = self._normalize(text)
        for state, state_container, chips in self._state_containers:
            state_match = not query or query in self._normalize(state)
            visible = 0
            
            # Prevent O(N^2) layout calculations while batch-updating visibility
            layout = state_container.layout()
            if layout:
                layout.setEnabled(False)
                
            for btn in chips:
                show = state_match or query in self._chip_normalized.get(
                    btn.text(), btn.text().lower()
                )
                if btn.isVisible() != show:
                    btn.setVisible(show)
                if show:
                    visible += 1
                    
            if layout:
                layout.setEnabled(True)
                
            if state_container.isVisible() != (visible > 0):
                state_container.setVisible(visible > 0)

        # Reset indicator to top-most visible state after filter changes
        self._on_scroll(self._scroll.verticalScrollBar().value())

    def set_covered_cities(self, covered_cities: set[str]):
        """
        Update chip appearance. If the grid isn't fully built yet, the call is
        queued and replayed automatically once construction finishes.
        """
        if self._build_index < len(self._build_queue):
            self._pending_covered = covered_cities
            return

        total = len(ALL_CITIES)
        covered_count = 0
        style = self.style()

        for city, btn in self._chip_buttons.items():
            is_covered = self._normalize(city) in covered_cities
            if is_covered:
                covered_count += 1
            new_val = "true" if is_covered else "false"
            if btn.property("covered") != new_val:
                btn.setProperty("covered", new_val)
                style.unpolish(btn)
                style.polish(btn)

        self._summary_label.setText(
            f"{covered_count} / {total} settlements covered"
        )
