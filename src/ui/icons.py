from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer


_ASSETS_DIR = Path(__file__).resolve().parent / "assets"


def icon_path(name: str) -> str:
    return str((_ASSETS_DIR / name).resolve())


def stylesheet_icon_url(name: str) -> str:
    return icon_path(name).replace("\\", "/")


def load_icon(name: str) -> QIcon:
    return QIcon(icon_path(name))


def _render_tinted_icon(name: str, size: int, color: str) -> QIcon:
    svg_bytes = Path(icon_path(name)).read_bytes()
    data = svg_bytes.decode("utf-8")
    for source in ["#EEEEEE", "#eeeeee", "#FFFFFF", "#ffffff", "#F8FAFC", "#f8fafc"]:
        data = data.replace(source, color)

    renderer = QSvgRenderer(QByteArray(data.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


def _default_button_icon_color(button) -> str:
    name = button.objectName()
    if name in {"PrimaryBtn", "SidebarPrimaryBtn", "SettingsPrimaryBtn", "ResultsHeaderPrimaryBtn", "ResultsMinorActionBtn"}:
        return "#FBFCFD"
    if name == "NavBtn":
        return "#FBFCFD" if str(button.property("active")).lower() == "true" else "#CED3DE"
    if name in {"ToolbarIconBtn", "TopBarIconBtn", "TopBarAvatarBtn", "ResultsRoundIconBtn", "ResultsIconGhost"}:
        return "#E6EBF5"
    if name in {"SecondaryBtn", "GhostBtn", "DashboardGhostBtn", "MonitorGhostBtn", "MonitorControlBtn", "LogsGhostBtn"}:
        return "#B8C2D6"
    return "#8F99AD"


def apply_button_icon(button, name: str, size: int = 16, color: str | None = None) -> None:
    button.setProperty("icon_name", name)
    button.setProperty("icon_size", size)
    icon_color = color or _default_button_icon_color(button)
    button.setIcon(_render_tinted_icon(name, size, icon_color))
    button.setIconSize(QSize(size, size))
