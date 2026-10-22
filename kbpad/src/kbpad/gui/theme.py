"""Colour themes (dark / light / system) applied as a Fusion palette plus one stylesheet."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPalette, QPixmap, QPolygonF
from PySide6.QtWidgets import QApplication, QStyleFactory

PLAYER_COLORS = {1: "#3b82f6", 2: "#ef4444", 3: "#22c55e", 4: "#ec4899"}
ACCENT = "#8b5cf6"
ACCENT_2 = "#6366f1"
SUCCESS = "#22c55e"
WARNING = "#f59e0b"
DANGER = "#ef4444"

THEMES = {
    "dark": {
        "bg": "#0e1016", "surface": "#161922", "surface2": "#1e2230", "surface3": "#262b3b",
        "border": "#2b3142", "text": "#e7e9f0", "muted": "#8a90a3", "base": "#11131b",
    },
    "light": {
        "bg": "#f3f4f8", "surface": "#ffffff", "surface2": "#eef0f6", "surface3": "#e3e6ef",
        "border": "#d9dde7", "text": "#1a1d26", "muted": "#6b7180", "base": "#ffffff",
    },
}

_current: dict[str, str] = dict(THEMES["dark"])
_default_style: str | None = None


def colors() -> dict[str, str]:
    """Current theme colours; widgets that paint themselves read this."""
    return _current


def player_color(player: int | None) -> str:
    return PLAYER_COLORS.get(player or 0, "#64748b")


def apply(app: QApplication, name: str) -> None:
    global _current, _default_style
    if _default_style is None:
        _default_style = app.style().name()
    if name == "system":
        app.setStyle(QStyleFactory.create(_default_style) or app.style())
        pal = app.style().standardPalette()
        app.setPalette(pal)
        dark = pal.color(QPalette.Window).lightness() < 128
        base = dict(THEMES["dark" if dark else "light"])
        base.update(bg=pal.color(QPalette.Window).name(), surface=pal.color(QPalette.Base).name(),
                    text=pal.color(QPalette.WindowText).name(), base=pal.color(QPalette.Base).name())
        _current = base
    else:
        _current = dict(THEMES.get(name, THEMES["dark"]))
        app.setStyle(QStyleFactory.create("Fusion"))
        app.setPalette(_palette(_current))
    app.setStyleSheet(_stylesheet(_current))


def _arrow_image(color: str, up: bool = False) -> str:
    """Small triangle PNG for combo/spin arrows (style sheets cannot draw one). Returns its path."""
    cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "kbpad"
    path = cache / f"arrow-{'up' if up else 'down'}-{color.lstrip('#')}.png"
    if not path.exists():
        cache.mkdir(parents=True, exist_ok=True)
        pm = QPixmap(20, 20)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(color))
        pts = [QPointF(4, 13), QPointF(16, 13), QPointF(10, 6)] if up else \
              [QPointF(4, 7), QPointF(16, 7), QPointF(10, 14)]
        p.drawPolygon(QPolygonF(pts))
        p.end()
        pm.save(str(path))
    return path.as_posix()


def _palette(c: dict[str, str]) -> QPalette:
    p = QPalette()
    role = QPalette.ColorRole
    p.setColor(role.Window, QColor(c["bg"]))
    p.setColor(role.WindowText, QColor(c["text"]))
    p.setColor(role.Base, QColor(c["base"]))
    p.setColor(role.AlternateBase, QColor(c["surface2"]))
    p.setColor(role.Text, QColor(c["text"]))
    p.setColor(role.Button, QColor(c["surface2"]))
    p.setColor(role.ButtonText, QColor(c["text"]))
    p.setColor(role.Highlight, QColor(ACCENT))
    p.setColor(role.HighlightedText, QColor("#ffffff"))
    p.setColor(role.ToolTipBase, QColor(c["surface3"]))
    p.setColor(role.ToolTipText, QColor(c["text"]))
    p.setColor(role.PlaceholderText, QColor(c["muted"]))
    p.setColor(role.Mid, QColor(c["border"]))
    p.setColor(role.Link, QColor(ACCENT))
    for r in (role.WindowText, role.Text, role.ButtonText):
        p.setColor(QPalette.Disabled, r, QColor(c["muted"]))
    return p


def _stylesheet(c: dict[str, str]) -> str:
    return f"""
QWidget {{ font-size: 10pt; }}
QMainWindow, QDialog {{ background: {c['bg']}; }}
QToolTip {{ background: {c['surface3']}; color: {c['text']}; border: 1px solid {c['border']};
           border-radius: 6px; padding: 5px 8px; }}

#header {{ border-radius: 14px;
          background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {ACCENT_2}, stop:1 {ACCENT}); }}
#header QLabel {{ color: white; background: transparent; }}
#appTitle {{ font-size: 19pt; font-weight: 800; letter-spacing: 1px; }}
#appSubtitle {{ font-size: 9pt; color: rgba(255,255,255,0.80); }}
#header QPushButton {{ background: rgba(255,255,255,0.16); color: white; border: 1px solid rgba(255,255,255,0.35);
                       border-radius: 10px; padding: 8px 16px; font-weight: 600; }}
#header QPushButton:hover {{ background: rgba(255,255,255,0.26); }}
#header QPushButton:disabled {{ color: rgba(255,255,255,0.45); border-color: rgba(255,255,255,0.18); }}
#header QPushButton#launch {{ background: white; color: {ACCENT_2}; border: none; }}
#header QPushButton#launch:hover {{ background: #f1edff; }}
#header QPushButton#launch:disabled {{ background: rgba(255,255,255,0.35); color: rgba(255,255,255,0.75); }}
#header QPushButton#danger {{ background: {DANGER}; border: none; color: white; }}

#panel {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 14px; }}
#panelTitle {{ font-size: 12pt; font-weight: 700; }}
#hint, #muted {{ color: {c['muted']}; }}

#card {{ background: {c['surface2']}; border: 1px solid {c['border']}; border-radius: 12px; }}
#cardName {{ font-size: 11pt; font-weight: 700; }}

QPushButton {{ background: {c['surface3']}; color: {c['text']}; border: 1px solid {c['border']};
              border-radius: 8px; padding: 6px 14px; }}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:pressed {{ background: {c['surface2']}; }}
QPushButton:disabled {{ color: {c['muted']}; background: {c['surface2']}; border-color: {c['surface3']}; }}
QPushButton#primary {{ background: {ACCENT}; color: white; border: none; font-weight: 600; }}
QPushButton#primary:hover {{ background: {ACCENT_2}; }}
QPushButton#primary:disabled {{ background: {c['surface3']}; color: {c['muted']}; }}
QPushButton#danger {{ background: {DANGER}; color: white; border: none; font-weight: 600; }}
QPushButton#small {{ padding: 3px 10px; border-radius: 6px; }}

QComboBox, QLineEdit, QSpinBox {{ background: {c['base']}; color: {c['text']}; border: 1px solid {c['border']};
                                  border-radius: 8px; padding: 5px 9px; }}
QComboBox:hover, QLineEdit:focus, QSpinBox:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 24px; background: transparent; }}
QComboBox::down-arrow {{ image: url({_arrow_image(c['muted'])}); width: 12px; height: 12px; }}
QSpinBox::up-arrow {{ image: url({_arrow_image(c['muted'], up=True)}); width: 10px; height: 10px; }}
QSpinBox::down-arrow {{ image: url({_arrow_image(c['muted'])}); width: 10px; height: 10px; }}
QSpinBox::up-button, QSpinBox::down-button {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{ background: {c['surface']}; border: 1px solid {c['border']};
                               selection-background-color: {ACCENT}; selection-color: white; outline: 0; }}

QTabWidget::pane {{ border: 1px solid {c['border']}; border-radius: 14px; background: {c['surface']}; top: -1px; }}
QTabBar::tab {{ background: transparent; color: {c['muted']}; padding: 8px 16px; margin-right: 4px;
                border-top-left-radius: 10px; border-top-right-radius: 10px; font-weight: 600; }}
QTabBar::tab:selected {{ background: {c['surface']}; color: {c['text']};
                         border: 1px solid {c['border']}; border-bottom: 3px solid {ACCENT}; }}
QTabBar::tab:hover:!selected {{ color: {c['text']}; }}

QTableWidget {{ background: {c['base']}; alternate-background-color: {c['surface2']}; color: {c['text']};
               border: 1px solid {c['border']}; border-radius: 10px; gridline-color: transparent;
               selection-background-color: {ACCENT}; selection-color: white; }}
QTableWidget::item {{ padding: 4px; }}
QHeaderView::section {{ background: {c['surface2']}; color: {c['muted']}; border: none;
                        border-bottom: 1px solid {c['border']}; padding: 6px; font-weight: 700; }}

QPlainTextEdit {{ background: {c['base']}; color: {c['text']}; border: 1px solid {c['border']};
                 border-radius: 10px; padding: 6px; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {c['surface3']}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {ACCENT}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {c['surface3']}; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 5px; border: 1px solid {c['border']};
                        background: {c['base']}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QGroupBox {{ border: 1px solid {c['border']}; border-radius: 12px; margin-top: 14px; padding: 12px 10px 10px 10px;
             font-weight: 700; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; color: {c['text']}; }}
QSplitter::handle {{ background: transparent; }}
QStatusBar {{ color: {c['muted']}; }}
QMenu {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 4px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: {ACCENT}; color: white; }}
QMenuBar {{ background: transparent; }}
QMenuBar::item:selected {{ background: {c['surface3']}; border-radius: 6px; }}

#banner {{ border-radius: 10px; padding: 2px; }}
#banner[level="warning"] {{ background: rgba(245,158,11,0.16); border: 1px solid {WARNING}; }}
#banner[level="error"] {{ background: rgba(239,68,68,0.16); border: 1px solid {DANGER}; }}
#banner[level="info"] {{ background: rgba(139,92,246,0.16); border: 1px solid {ACCENT}; }}
#bigNumber {{ font-size: 40pt; font-weight: 800; color: {ACCENT}; }}
"""


def chip(bg: str, fg: str = "white") -> str:
    """Stylesheet for a rounded label 'chip'."""
    return (f"QLabel {{ background: {bg}; color: {fg}; border-radius: 10px; padding: 3px 11px;"
            f" font-weight: 700; font-size: 9pt; }}")
