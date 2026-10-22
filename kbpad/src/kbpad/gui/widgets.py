"""Reusable widgets: keyboard card, controller diagram, key capture dialog, banner, icons."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QIcon, QKeyEvent, QLinearGradient, QPainter, QPainterPath, QPen,
                           QPixmap, QRadialGradient)
from PySide6.QtWidgets import (QComboBox, QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
                               QVBoxLayout, QWidget)

from .. import engine as eng
from ..keynames import code_to_name, pretty, short
from ..profiles import Profile
from . import theme

STATE_TEXT = {
    eng.FREE: ("Not grabbed", "#64748b"),
    eng.WAITING: ("Let go of all keys…", theme.WARNING),
    eng.GRABBED: ("● GRABBED", theme.SUCCESS),
    eng.DISCONNECTED: ("Disconnected", "#475569"),
    eng.ERROR: ("Error", theme.DANGER),
}


def app_icon() -> QIcon:
    pm = QPixmap(128, 128)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    grad = QLinearGradient(0, 0, 128, 128)
    grad.setColorAt(0, QColor(theme.ACCENT_2))
    grad.setColorAt(1, QColor(theme.ACCENT))
    p.setBrush(grad)
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(QRectF(4, 4, 120, 120), 28, 28)
    body = QPainterPath()
    body.addRoundedRect(QRectF(16, 40, 96, 52), 26, 26)
    p.setBrush(QColor("white"))
    p.drawPath(body)
    p.setBrush(QColor(theme.ACCENT_2))
    p.drawRoundedRect(QRectF(30, 62, 24, 8), 3, 3)
    p.drawRoundedRect(QRectF(38, 54, 8, 24), 3, 3)
    for (x, y), col in (((84, 58), theme.PLAYER_COLORS[3]), ((96, 66), theme.PLAYER_COLORS[2]),
                        ((72, 66), theme.PLAYER_COLORS[1]), ((84, 74), theme.PLAYER_COLORS[4])):
        p.setBrush(QColor(col))
        p.drawEllipse(QPointF(x, y), 5.5, 5.5)
    p.end()
    return QIcon(pm)


def dot_icon(color: str, size: int = 12) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.NoPen)
    p.drawEllipse(QRectF(1, 1, size - 2, size - 2))
    p.end()
    return QIcon(pm)


class Banner(QFrame):
    """Dismissable message strip (info / warning / error)."""

    def __init__(self):
        super().__init__()
        self.setObjectName("banner")
        self.label = QLabel()
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.RichText)
        self.label.setOpenExternalLinks(False)
        close = QPushButton("✕")
        close.setObjectName("small")
        close.setFixedWidth(34)
        close.clicked.connect(self.hide)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 6, 6, 6)
        lay.addWidget(self.label, 1)
        lay.addWidget(close, 0, Qt.AlignTop)
        self.hide()

    def show_message(self, html: str, level: str = "warning") -> None:
        self.setProperty("level", level)
        self.style().unpolish(self)
        self.style().polish(self)
        self.label.setText(html)
        self.show()


class KeyboardCard(QFrame):
    """One physical keyboard: name, live key flash, state, player choice, grab button."""
    player_changed = Signal(str, object)     # keyboard key, player or None
    grab_clicked = Signal(str)

    def __init__(self, key: str, players: int):
        super().__init__()
        self.key = key
        self.setObjectName("card")
        self._player = None
        self._state = None

        self.name = QLabel()
        self.name.setObjectName("cardName")
        self.detail = QLabel()
        self.detail.setObjectName("muted")
        self.detail.setWordWrap(True)
        self.state = QLabel()
        self.state.setAlignment(Qt.AlignCenter)
        self.lastkey = QLabel()
        self.lastkey.setAlignment(Qt.AlignCenter)
        self.lastkey.setMinimumWidth(56)

        self.player = QComboBox()
        self.player.setMinimumWidth(130)
        self.set_player_count(players)
        self.player.activated.connect(lambda _i: self.player_changed.emit(self.key, self.player.currentData()))

        self.grab = QPushButton("Grab")
        self.grab.setMinimumWidth(110)
        self.grab.clicked.connect(lambda: self.grab_clicked.emit(self.key))

        top = QHBoxLayout()
        top.addWidget(self.name, 1)
        top.addWidget(self.lastkey)
        top.addWidget(self.state)
        bottom = QHBoxLayout()
        bottom.addWidget(self.player)
        bottom.addStretch(1)
        bottom.addWidget(self.grab)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 14, 12)
        lay.setSpacing(6)
        lay.addLayout(top)
        lay.addWidget(self.detail)
        lay.addLayout(bottom)

    def set_player_count(self, players: int) -> None:
        current = self.player.currentData()
        self.player.clear()
        self.player.addItem(dot_icon("#64748b"), "Not used", None)
        for n in range(1, players + 1):
            self.player.addItem(dot_icon(theme.player_color(n)), f"Player {n}", n)
        self.player.setCurrentIndex(max(0, self.player.findData(current)))

    def update_view(self, v: eng.KeyboardView, show_port: bool) -> None:
        self.name.setText(("🖱  " if v.is_mouse else "⌨  ") + v.name)
        if v.present:
            parts = [f"USB {v.usb_id}"]
            if show_port and v.port:
                parts.append(v.port)
            self.detail.setText(" · ".join(parts) + (f"\n⚠ {v.error}" if v.error else ""))
        else:
            self.detail.setText("Plug this keyboard back in. Its controller stays ready." +
                                (f"\n⚠ {v.error}" if v.error else ""))
        text, color = STATE_TEXT.get(v.state, (v.state, "#64748b"))
        self.state.setText(text)
        self.state.setStyleSheet(theme.chip(color))
        if self.player.currentData() != v.player:
            self.player.setCurrentIndex(max(0, self.player.findData(v.player)))
        grabbed = v.state in (eng.GRABBED, eng.WAITING)
        self.grab.setText("Release" if grabbed else "Grab")
        self.grab.setObjectName("danger" if grabbed else "primary")
        self.grab.setEnabled(v.present and (grabbed or v.player is not None))
        self.grab.setToolTip("" if v.player is not None or grabbed else "Choose a player first")
        flash = v.last_key_age < 0.6
        if v.last_key and v.last_key_age < 5:
            self.lastkey.setText(pretty(v.last_key))
            self.lastkey.setStyleSheet(theme.chip(theme.ACCENT) if flash else
                                       theme.chip("transparent", theme.colors()["muted"]))
        else:
            self.lastkey.setText("")
            self.lastkey.setStyleSheet("")
        if (v.player, v.state) != (self._player, self._state):
            self._player, self._state = v.player, v.state
            c = theme.colors()
            border = theme.SUCCESS if v.state == eng.GRABBED else c["border"]
            stripe = theme.player_color(v.player) if v.player else c["border"]
            self.setStyleSheet(f"#card {{ border: 1px solid {border}; border-left: 5px solid {stripe}; }}")
            self.grab.style().unpolish(self.grab)
            self.grab.style().polish(self.grab)


# ---------------------------------------------------------------------------
# Controller diagram

_LAYOUT = {
    "ABS_Z": ("rect", (40, 8, 96, 28)), "BTN_TL": ("rect", (40, 40, 96, 28)),
    "ABS_RZ": ("rect", (324, 8, 96, 28)), "BTN_TR": ("rect", (324, 40, 96, 28)),
    "DPAD_UP": ("rect", (90, 100, 38, 34)), "DPAD_DOWN": ("rect", (90, 170, 38, 34)),
    "DPAD_LEFT": ("rect", (52, 135, 38, 34)), "DPAD_RIGHT": ("rect", (128, 135, 38, 34)),
    "BTN_NORTH": ("circle", (331, 96, 40, 40)), "BTN_SOUTH": ("circle", (331, 168, 40, 40)),
    "BTN_WEST": ("circle", (294, 132, 40, 40)), "BTN_EAST": ("circle", (368, 132, 40, 40)),
    "BTN_SELECT": ("rect", (178, 100, 46, 24)), "BTN_START": ("rect", (236, 100, 46, 24)),
    "BTN_MODE": ("circle", (213, 132, 34, 34)),
}
_STICKS = {"L": ((170, 222), "LS", "BTN_THUMBL"), "R": ((290, 222), "RS", "BTN_THUMBR")}
# Face button colours: PlayStation (△ green, ○ red, ✕ blue, □ pink) and Xbox (Y yellow, B red, A green, X blue)
_FACE_COLORS = {
    "ps2": {"BTN_NORTH": "#22c55e", "BTN_EAST": "#ef4444", "BTN_SOUTH": "#3b82f6", "BTN_WEST": "#ec4899"},
    "xbox": {"BTN_NORTH": "#eab308", "BTN_EAST": "#ef4444", "BTN_SOUTH": "#22c55e", "BTN_WEST": "#3b82f6"},
}


class PadView(QWidget):
    """Draws the controller with each button's key; pressed controls light up."""
    control_clicked = Signal(str)

    def __init__(self, player: int = 1):
        super().__init__()
        self.player = player
        self.profile: Profile | None = None
        self.pressed: set[str] = set()
        self.setMinimumSize(400, 240)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._hit: list[tuple[QRectF, str]] = []
        self.setToolTip("Click a button to change its key")
        self.setCursor(Qt.PointingHandCursor)

    def sizeHint(self):
        return QSize(480, 290)

    def set_profile(self, profile: Profile) -> None:
        self.profile = profile
        self.update()

    def set_pressed(self, pressed: set[str]) -> None:
        if pressed != self.pressed:
            self.pressed = pressed
            self.update()

    def mousePressEvent(self, ev):
        for rect, cid in self._hit:
            if rect.contains(ev.position()):
                self.control_clicked.emit(cid)
                return

    def paintEvent(self, _ev):
        if not self.profile:
            return
        c = theme.colors()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        scale = min(self.width() / 460, self.height() / 275)
        ox = (self.width() - 460 * scale) / 2
        oy = (self.height() - 275 * scale) / 2
        p.translate(ox, oy)
        p.scale(scale, scale)
        accent = QColor(theme.player_color(self.player))
        fg = QColor(c["text"])
        muted = QColor(c["muted"])
        edge = QColor(c["border"])
        self._hit = []

        def to_widget(r: QRectF) -> QRectF:
            return QRectF(r.x() * scale + ox, r.y() * scale + oy, r.width() * scale, r.height() * scale)

        # body with soft gradient and a player-colour glow line
        body = QPainterPath()
        body.addRoundedRect(QRectF(20, 74, 420, 192), 76, 76)
        grad = QLinearGradient(0, 74, 0, 266)
        grad.setColorAt(0, QColor(c["surface3"]))
        grad.setColorAt(1, QColor(c["surface2"]))
        p.setBrush(grad)
        p.setPen(QPen(edge, 1.5))
        p.drawPath(body)
        p.setPen(QPen(accent, 3))
        p.drawLine(QPointF(196, 84), QPointF(264, 84))

        small = QFont(self.font()); small.setPointSizeF(7.5); small.setBold(True)
        bold = QFont(self.font()); bold.setBold(True); bold.setPointSizeF(9)
        face = _FACE_COLORS[self.profile.label_set]

        for cid, (shape, (x, y, w, h)) in _LAYOUT.items():
            r = QRectF(x, y, w, h)
            on = cid in self.pressed
            tint = QColor(face.get(cid, accent.name()))
            if on:
                glow = QRadialGradient(r.center(), max(w, h))
                glow.setColorAt(0, QColor(tint.red(), tint.green(), tint.blue(), 140))
                glow.setColorAt(1, QColor(tint.red(), tint.green(), tint.blue(), 0))
                p.setPen(Qt.NoPen)
                p.setBrush(glow)
                p.drawEllipse(r.center(), w, h)
            p.setPen(QPen(tint if (on or cid in face) else edge, 2 if cid in face else 1.5))
            p.setBrush(tint if on else QColor(c["base"]))
            if shape == "circle":
                p.drawEllipse(r)
            else:
                p.drawRoundedRect(r, 7, 7)
            label = self.profile.label(cid)
            if cid.startswith("DPAD_"):
                label = ""
            elif cid == "BTN_MODE":
                label = "PS" if self.profile.label_set == "ps2" else "Guide"
            elif self.profile.label_set == "ps2" and cid in face:
                label = label.split(" ")[-1]
            key = self.profile.key_for(cid)
            text = short(key) if key else "·"
            if label:
                p.setFont(small)
                p.setPen(QColor("white") if on else (tint if cid in face else muted))
                p.drawText(QRectF(r.x(), r.y() + 1, r.width(), r.height() / 2), Qt.AlignHCenter | Qt.AlignBottom, label)
                p.setFont(bold)
                p.setPen(QColor("white") if on else fg)
                p.drawText(QRectF(r.x() - 6, r.y() + r.height() / 2, r.width() + 12, r.height() / 2),
                           Qt.AlignHCenter | Qt.AlignTop, text)
            else:
                p.setFont(bold)
                p.setPen(QColor("white") if on else fg)
                p.drawText(r, Qt.AlignCenter, text)
            self._hit.append((to_widget(r), cid))

        for (cx, cy), prefix, click in _STICKS.values():
            on_click = click in self.pressed
            p.setPen(QPen(accent if on_click else edge, 2))
            p.setBrush(QColor(c["base"]))
            p.drawEllipse(QPointF(cx, cy), 27, 27)
            dx = (prefix + "_RIGHT" in self.pressed) - (prefix + "_LEFT" in self.pressed)
            dy = (prefix + "_DOWN" in self.pressed) - (prefix + "_UP" in self.pressed)
            moving = bool(dx or dy or on_click)
            p.setBrush(accent if moving else QColor(c["surface3"]))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(cx + dx * 13, cy + dy * 13), 11, 11)
            p.setFont(bold)
            for d, (tx, ty) in {"UP": (0, -37), "DOWN": (0, 37), "LEFT": (-42, 0), "RIGHT": (42, 0)}.items():
                cid = f"{prefix}_{d}"
                key = self.profile.key_for(cid)
                tr = QRectF(cx + tx - 22, cy + ty - 9, 44, 18)
                p.setPen(accent if cid in self.pressed else (fg if key else muted))
                p.drawText(tr, Qt.AlignCenter, short(key) if key else "·")
                self._hit.append((to_widget(tr), cid))
            self._hit.append((to_widget(QRectF(cx - 27, cy - 27, 54, 54)), click))
        p.end()


# ---------------------------------------------------------------------------

class CaptureDialog(QDialog):
    """Waits for one key press on any keyboard, read through evdev (works while grabbed).
    chord=True captures a hotkey: hold modifiers, then press the key."""

    def __init__(self, parent, engine, title: str, subtitle: str, keyboard_names: dict[str, str],
                 chord: bool = False, allow_clear: bool = True):
        super().__init__(parent)
        self.engine = engine
        self.names = keyboard_names
        self.chord = chord
        self.result_key: str | None = None
        self.result_code: int | None = None
        self.result_held: frozenset = frozenset()
        self.result_from = ""
        self.setWindowTitle("Set hotkey" if chord else "Change key")
        self.setModal(True)
        head = QLabel(title)
        head.setObjectName("panelTitle")
        head.setAlignment(Qt.AlignCenter)
        msg = QLabel(subtitle)
        msg.setObjectName("hint")
        msg.setAlignment(Qt.AlignCenter)
        msg.setWordWrap(True)
        self.big = QLabel("…")
        self.big.setObjectName("bigNumber")
        self.big.setAlignment(Qt.AlignCenter)
        self.big.setMinimumHeight(90)
        row = QHBoxLayout()
        if allow_clear:
            clear = QPushButton("Unbind")
            clear.setAutoDefault(False)
            clear.clicked.connect(self._clear)
            row.addWidget(clear)
        row.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setAutoDefault(False)
        cancel.clicked.connect(self.reject)
        row.addWidget(cancel)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 16)
        lay.addWidget(head)
        lay.addWidget(msg)
        lay.addWidget(self.big)
        lay.addLayout(row)
        self.setMinimumWidth(400)
        engine.begin_capture(chord=chord)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll)
        self.timer.start(25)

    def _poll(self):
        got = self.engine.poll_capture()
        if got:
            kb_key, code, held = got
            self.result_code = code
            self.result_held = held
            self.result_key = code_to_name(code)
            self.result_from = self.names.get(kb_key, "")
            if self.chord:
                self.big.setText(eng.Chord.from_capture(code, set(held)).text())
            else:
                self.big.setText(pretty(self.result_key))
            self.timer.stop()
            QTimer.singleShot(300, self.accept)

    def _clear(self):
        self.result_key = ""
        self.accept()

    def keyPressEvent(self, ev: QKeyEvent):
        ev.accept()             # keys come through evdev; never let Esc/Enter close the dialog

    def done(self, r):
        self.timer.stop()
        self.engine.cancel_capture()
        super().done(r)
