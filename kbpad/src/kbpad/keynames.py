"""Conversion between evdev key codes and names (KEY_A) and short display labels (A)."""

from evdev import ecodes

_PRETTY = {
    "LEFTCTRL": "L-Ctrl", "RIGHTCTRL": "R-Ctrl", "LEFTSHIFT": "L-Shift",
    "RIGHTSHIFT": "R-Shift", "LEFTALT": "L-Alt", "RIGHTALT": "R-Alt",
    "LEFTMETA": "L-Super", "RIGHTMETA": "R-Super", "BACKSPACE": "Backspace",
    "ENTER": "Enter", "SPACE": "Space", "MINUS": "-", "EQUAL": "=",
    "LEFTBRACE": "[", "RIGHTBRACE": "]", "SEMICOLON": ";", "APOSTROPHE": "'",
    "GRAVE": "`", "BACKSLASH": "\\", "COMMA": ",", "DOT": ".", "SLASH": "/",
    "UP": "↑", "DOWN": "↓", "LEFT": "←", "RIGHT": "→", "ESC": "Esc",
    "TAB": "Tab", "CAPSLOCK": "CapsLock", "KPENTER": "Num Enter",
}


def code_to_name(code: int) -> str:
    """KEY_* name for a code; first alias when evdev lists several."""
    name = ecodes.KEY.get(code) or ecodes.BTN.get(code)
    if name is None:
        return f"KEY_{code}"
    if isinstance(name, (list, tuple)):
        keys = [n for n in name if n.startswith("KEY_")]
        name = keys[0] if keys else name[0]
    return name


def name_to_code(name: str) -> int | None:
    code = ecodes.ecodes.get(name)
    return code if isinstance(code, int) else None


def pretty(name: str | None) -> str:
    """'KEY_LEFTSHIFT' -> 'L-Shift', 'KEY_KP5' -> 'Num 5', '' -> '—'."""
    if not name:
        return "—"
    short = name.removeprefix("KEY_")
    if short in _PRETTY:
        return _PRETTY[short]
    if short.startswith("KP") and len(short) > 2:
        return "Num " + short[2:].capitalize()
    return short if len(short) <= 2 else short.capitalize()


_SHORT = {"Backspace": "Bksp", "L-Shift": "LShift", "R-Shift": "RShift", "L-Super": "LSuper", "R-Super": "RSuper", "CapsLock": "Caps", "Num Enter": "NEnt", "Enter": "Enter"}


def short(name: str | None) -> str:
    """Compact label for the controller picture (max ~5 characters)."""
    text = pretty(name)
    text = _SHORT.get(text, text)
    return text if len(text) <= 6 else text[:5] + "…"
