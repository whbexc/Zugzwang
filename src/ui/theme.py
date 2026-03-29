"""
ZUGZWANG - Design System (Theme)
"Obsidian Core" Aesthetic - Premium, highly-polished, modern design language.
"""

from PySide6.QtGui import QColor

class Theme:
    # ── Colors (Apple/macOS Dark Mode Inspired) ─────────────────────────────────
    # Neutral / Backgrounds
    BG_OBSIDIAN    = "#1C1C1E" # Base background (macOS dark window)
    BG_ZINC        = "#2C2C2E" # Elevated surfaces (Cards, Panels) — iOS dark secondary
    BG_GLASS       = "rgba(44, 44, 46, 0.90)" # Translucent cards
    BG_HOVER       = "rgba(255, 255, 255, 0.12)"
    BG_HOVER_LIGHT = "rgba(255, 255, 255, 0.06)"
    
    # Border / Separators
    BORDER_LIGHT   = "rgba(255, 255, 255, 0.14)"
    BORDER_SUBTLE  = "rgba(255, 255, 255, 0.08)"    
    # Accents
    ACCENT_PRIMARY   = "#0A84FF" # macOS vibrant blue
    ACCENT_HOVER     = "#007AFF"
    ACCENT_SECONDARY = "rgba(255, 255, 255, 0.1)"
    
    # Status
    SUCCESS        = "#30D158"
    DANGER         = "#FF453A"
    WARNING        = "#FF9F0A"
    INFO           = "#0A84FF"
    
    # Typography
    TEXT_PRIMARY   = "#FFFFFF"
    TEXT_SECONDARY = "#8E8E93"
    TEXT_TERTIARY  = "#636366"
    
    # ── Legacy Aliases (For gradual rollout) ───────────────────────────────────
    BG_DARK = BG_OBSIDIAN
    BG_ELEVATED = BG_ZINC
    ACCENT_BLUE = ACCENT_PRIMARY
    ACCENT_BLUE_HOVER = ACCENT_HOVER
    TEXT_SUBTLE = TEXT_TERTIARY
    BORDER_ULTRA_LIGHT = BORDER_SUBTLE
    
    # ── Design Tokens ────────────────────────────────────────────────────────
    RADIUS_MODAL   = 16
    RADIUS_CARD    = 14
    RADIUS_BUTTON  = 10
    ANIMATION_FAST = 200
    ANIMATION_SLOW = 450
    
    # ── Utilities ────────────────────────────────────────────────────────
    @staticmethod
    def elevated_card(radius: int = None) -> str:
        r = radius if radius is not None else Theme.RADIUS_CARD
        return f"""
            background: {Theme.BG_ZINC};
            border: 1px solid {Theme.BORDER_LIGHT};
            border-radius: {r}px;
        """
        
    @staticmethod
    def borderless_card() -> str:
        return f"""
            background: {Theme.BG_ZINC};
            border: none;
            border-radius: {Theme.RADIUS_CARD}px;
        """

    @staticmethod
    def glass_card(radius: int = 12) -> str:
        # 5.0: Added top-down linear gradient to simulate glass reflection
        return f"""
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                                      stop:0 rgba(60, 60, 64, 0.95), 
                                      stop:1 rgba(44, 44, 46, 0.90));
            border: 1px solid {Theme.BORDER_LIGHT};
            border-top: 1px solid rgba(255, 255, 255, 0.18);
            border-radius: {radius}px;
        """

    @staticmethod
    def vibrant_glow(color: str = "#0A84FF", opacity: float = 0.3) -> str:
        # Helper for QGraphicsDropShadowEffect settings
        return f"rgba({QColor(color).red()}, {QColor(color).green()}, {QColor(color).blue()}, {opacity})"

    # ── ZUGZWANG Button System (v2) ─────────────────────────────────────────────
    # Canonical button spec: #2A2A2A bg, #3A3A3C border, 6px radius,
    # 12px/700/1.8px-tracking uppercase text. One exception for primary CTA.

    @staticmethod
    def zugzwang_button() -> str:
        """Canonical ZUGZWANG button (Secondary/Reset) — borderless, 10px radius."""
        return f"""
            QPushButton {{
                background: #2C2C2E;
                border: none;
                border-radius: {Theme.RADIUS_BUTTON}px;
                color: #FFFFFF;
                font-family: "PT Root UI", "-apple-system", sans-serif;
                font-weight: 600;
                font-size: 12px;
                letter-spacing: 1.6px;
                text-transform: uppercase;
                padding: 0 18px;
            }}
            QPushButton:hover {{
                background: #3A3A3C;
            }}
            QPushButton:pressed {{ background: #252525; }}
            QPushButton:disabled {{ color: #444444; background: #252525; }}
        """

    @staticmethod
    def zugzwang_primary_button() -> str:
        """ZUGZWANG primary CTA button (#0A84FF)."""
        return f"""
            QPushButton {{
                background: #0A84FF;
                border: none;
                border-radius: {Theme.RADIUS_BUTTON}px;
                color: #FFFFFF;
                font-family: "PT Root UI", "-apple-system", sans-serif;
                font-weight: 600;
                font-size: 12px;
                letter-spacing: 1.6px;
                text-transform: uppercase;
                padding: 0 18px;
            }}
            QPushButton:hover {{ background: #409CFF; }}
            QPushButton:pressed {{ background: #005CC8; }}
            QPushButton:disabled {{ background: #1C3D6B; color: #636366; }}
        """

    @staticmethod
    def primary_button() -> str:
        """Alias → zugzwang_primary_button() for backwards compatibility."""
        return Theme.zugzwang_primary_button()

    @staticmethod
    def secondary_button() -> str:
        """Alias → zugzwang_button() for backwards compatibility."""
        return Theme.zugzwang_button()

    @staticmethod
    def zugzwang_danger_button() -> str:
        """Danger button — dark red-tinted bg, vivid red text, no border (CLEAN style)."""
        return f"""
            QPushButton {{
                background-color: #3C1A1A;
                border: none;
                border-radius: 10px;
                color: #FF453A;
                font-family: "PT Root UI", "-apple-system", sans-serif;
                font-weight: 700;
                font-size: 12px;
                letter-spacing: 1.8px;
                text-transform: uppercase;
                padding: 0 18px;
            }}
            QPushButton:hover {{ background-color: #4A2020; color: #FF6259; }}
            QPushButton:pressed {{ background-color: #5A1F1F; }}
            QPushButton:disabled {{ color: #5A3030; background-color: #2A1212; }}
        """

    @staticmethod
    def danger_button() -> str:
        """Alias → zugzwang_danger_button() for backwards compatibility."""
        return Theme.zugzwang_danger_button()

    @staticmethod
    def zugzwang_success_button() -> str:
        """Success button — dark green-tinted bg, vivid green text, no border (matches danger style)."""
        return """
            QPushButton {
                background-color: #1A3C22;
                border: none;
                border-radius: 10px;
                color: #30D158;
                font-family: "PT Root UI", "-apple-system", sans-serif;
                font-weight: 700;
                font-size: 12px;
                letter-spacing: 1.8px;
                text-transform: uppercase;
                padding: 0 20px;
            }
            QPushButton:hover { background-color: #20492A; color: #5EE27A; }
            QPushButton:pressed { background-color: #275A33; }
            QPushButton:disabled { color: #305040; background: #1A2A1E; }
        """

    @staticmethod
    def success_button() -> str:
        """Alias → zugzwang_success_button() for backwards compatibility."""
        return Theme.zugzwang_success_button()

    @staticmethod
    def line_edit() -> str:
        return f"""
            LineEdit {{
                background: #1C1C1E;
                border: 1px solid #3A3A3C;
                border-radius: 8px;
                color: #FFFFFF;
                padding: 4px 12px;
                font-family: "PT Root UI", "-apple-system", sans-serif;
                font-size: 14px;
            }}
            LineEdit:focus {{
                border: 1px solid {Theme.ACCENT_PRIMARY};
                background: #1C1C1E;
            }}
        """

    @staticmethod
    def combo_box() -> str:
        return f"""
            ComboBox, EditableComboBox {{
                background: #1C1C1E;
                border: 1px solid #3A3A3C;
                border-radius: 8px;
                color: #FFFFFF;
                padding: 4px 12px;
                font-family: "PT Root UI", "-apple-system", sans-serif;
                font-size: 14px;
            }}
            ComboBox:hover, EditableComboBox:hover {{
                background: #2C2C2E;
            }}
            ComboBox:focus, EditableComboBox:focus {{
                border: 1px solid {Theme.ACCENT_PRIMARY};
            }}
        """

    @staticmethod
    def text_edit() -> str:
        return f"""
            TextEdit, PlainTextEdit {{
                background: {Theme.BG_ZINC};
                border: 1px solid {Theme.BORDER_LIGHT};
                border-bottom: 1px solid {Theme.BORDER_LIGHT};
                border-radius: 8px;
                padding: 10px;
                color: #FFFFFF;
                font-size: 13px;
            }}
            TextEdit:focus, PlainTextEdit:focus {{
                border: 1px solid {Theme.ACCENT_PRIMARY};
                border-bottom: 1px solid {Theme.ACCENT_PRIMARY};
                background: #323234;
            }}
        """
