"""Main window: header, keyboards on the left; players / PCSX2 / key test / checks / log / settings tabs."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QDesktopServices, QFont, QGuiApplication
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout,
                               QFrame, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QInputDialog, QLabel,
                               QLineEdit, QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea,
                               QSpinBox, QSplitter, QSystemTrayIcon, QTableWidget, QTableWidgetItem, QTabWidget,
                               QVBoxLayout, QWidget)

from .. import config, doctor, logsetup, pcsx2, profiles
from .. import engine as eng
from ..constants import LOG_DIR, LOG_FILE, MAX_PLAYERS
from ..keynames import code_to_name, pretty
from ..pad import SOCD_MODES
from ..profiles import CONTROLS, Profile
from . import theme
from .widgets import Banner, CaptureDialog, KeyboardCard, PadView, app_icon, dot_icon

log = logging.getLogger(__name__)


class EngineBridge(QObject):
    """Engine callbacks arrive on reader threads; Qt signals carry them to the GUI thread."""
    changed = Signal()
    message = Signal(str, str)
    grab = Signal(str, bool, str)

    def notify(self, kind: str, **kw) -> None:
        if kind == "changed":
            self.changed.emit()
        elif kind == "message":
            self.message.emit(kw.get("level", "info"), kw.get("text", ""))
        elif kind == "grab":
            self.grab.emit(kw.get("name", ""), bool(kw.get("grabbed")), kw.get("source", ""))


def _panel(title: str | None = None) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("panel")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(16, 14, 16, 14)
    if title:
        t = QLabel(title)
        t.setObjectName("panelTitle")
        lay.addWidget(t)
    return frame, lay


def _hint(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("hint")
    lbl.setWordWrap(True)
    lbl.setTextFormat(Qt.RichText)
    return lbl


# ---------------------------------------------------------------------------

class PlayerTab(QWidget):
    """Controller diagram + key table for one player. Edits save immediately."""

    def __init__(self, win: "MainWindow", player: int):
        super().__init__()
        self.win = win
        self.player = player
        self.profile: Profile = win.player_profiles[player]

        self.preset = QComboBox()
        self.preset.setMinimumWidth(200)
        load = QPushButton("Load preset")
        load.clicked.connect(self._load_preset)
        save_as = QPushButton("Save as preset…")
        save_as.clicked.connect(self._save_as)
        delete = QPushButton("Delete preset")
        delete.clicked.connect(self._delete_preset)
        imp = QPushButton("Import kb2xbox config…")
        imp.clicked.connect(self._import_kb2xbox)

        self.labels = QComboBox()
        self.labels.addItem("PlayStation names", "ps2")
        self.labels.addItem("Xbox names", "xbox")
        self.labels.activated.connect(self._labels_changed)
        self.socd = QComboBox()
        for mode, text in SOCD_MODES.items():
            self.socd.addItem(text, mode)
        self.socd.setToolTip("What the controller does when you hold two opposite directions at once.\n"
                             "Fighting games often play best with 'Last pressed wins'.")
        self.socd.activated.connect(self._socd_changed)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Preset"))
        row1.addWidget(self.preset)
        row1.addWidget(load)
        row1.addWidget(save_as)
        row1.addWidget(delete)
        row1.addStretch(1)
        row1.addWidget(imp)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Button names"))
        row2.addWidget(self.labels)
        row2.addSpacing(16)
        row2.addWidget(QLabel("Opposite directions held"))
        row2.addWidget(self.socd)
        row2.addStretch(1)

        self.keyboards = QLabel()
        self.keyboards.setWordWrap(True)
        self.keyboards.setTextFormat(Qt.RichText)

        self.pad = PadView(player)
        self.pad.control_clicked.connect(lambda cid: self.change_key(cid, "main"))

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Group", "Controller button", "Key", "Second key", ""])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.Fixed)
        self.table.setColumnWidth(4, 214)
        self.table.cellDoubleClicked.connect(
            lambda row, col: self.change_key(CONTROLS[row].id, "alt" if col == 3 else "main"))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 10)
        lay.addLayout(row1)
        lay.addLayout(row2)
        lay.addWidget(self.keyboards)
        split = QSplitter(Qt.Vertical)
        split.addWidget(self.pad)
        split.addWidget(self.table)
        split.setSizes([310, 390])
        lay.addWidget(split, 1)
        lay.addWidget(_hint("Click a button on the picture, double-click a row, or press <b>Key</b> / "
                            "<b>2nd</b>, then press the new key. A second key does the same as the first. "
                            "Changes save immediately."))
        self.refresh_presets()
        self.refresh()

    # --- presets -----------------------------------------------------------

    def refresh_presets(self) -> None:
        current = self.preset.currentData() or self.win.settings.presets.get(self.player) \
            or profiles.default_preset_for(self.player)
        self.preset.clear()
        for pid, prof in sorted(self.win.presets().items(), key=lambda kv: (not kv[1].builtin, kv[1].name.lower())):
            self.preset.addItem(prof.name + ("" if prof.builtin else "  (yours)"), pid)
        self.preset.setCurrentIndex(max(0, self.preset.findData(current)))

    def _apply_layout(self, source: Profile, preset_id: str | None) -> None:
        self.profile.keys = dict(source.keys)
        self.profile.alt = dict(source.alt)
        self.profile.label_set = source.label_set
        if preset_id:
            self.win.settings.presets[self.player] = preset_id
        self.win.save_player(self.player)
        self.win.save_settings()
        self.refresh()

    def _load_preset(self) -> None:
        pid = self.preset.currentData()
        preset = self.win.presets().get(pid)
        if not preset:
            return
        if QMessageBox.question(self, "Load preset",
                                f"Replace Player {self.player}'s keys with “{preset.name}”?") != QMessageBox.Yes:
            return
        self._apply_layout(preset, pid)

    def _save_as(self) -> None:
        name, ok = QInputDialog.getText(self, "Save as preset", "Preset name:", text=f"My layout P{self.player}")
        if not ok or not name.strip():
            return
        pid = profiles.slug(name)
        if pid.startswith("player") or pid in profiles.builtin_profiles():
            QMessageBox.warning(self, "Save as preset", "That name is reserved. Choose another one.")
            return
        profiles.save_user_profile(self.profile.copy(id=pid, name=name.strip(), builtin=False))
        self.win.settings.presets[self.player] = pid
        self.win.save_settings()
        self.win.refresh_all_presets()
        self.preset.setCurrentIndex(self.preset.findData(pid))
        self.win.status(f"Saved preset “{name.strip()}”")

    def _delete_preset(self) -> None:
        pid = self.preset.currentData()
        preset = self.win.presets().get(pid)
        if not preset:
            return
        if preset.builtin:
            QMessageBox.information(self, "Delete preset", "Built-in presets cannot be deleted.")
            return
        if QMessageBox.question(self, "Delete preset", f"Delete “{preset.name}”?") == QMessageBox.Yes:
            profiles.delete_user_profile(pid)
            self.win.refresh_all_presets()

    def _import_kb2xbox(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import kb2xbox config", str(Path.home() / "kb2xbox"),
                                              "kb2xbox config (*.cfg *.conf *.txt);;All files (*)")
        if not path:
            return
        try:
            text = Path(path).read_text(errors="replace")
        except OSError as err:
            QMessageBox.critical(self, "Import", f"Cannot read the file:\n{err}")
            return
        name = Path(path).stem
        imported, notes = profiles.import_kb2xbox(text, profiles.slug("kb2xbox-" + name), f"kb2xbox {name}")
        bound = sum(1 for k in imported.keys.values() if k)
        if not bound:
            QMessageBox.warning(self, "Import", "No usable key lines were found in that file.")
            return
        details = "\n".join(notes) if notes else "Everything was imported."
        answer = QMessageBox.question(
            self, "Import kb2xbox config",
            f"Found {bound} buttons in {Path(path).name}.\n\n{details}\n\n"
            f"Use it for Player {self.player} now? (It is also saved as a preset.)")
        try:
            profiles.save_user_profile(imported.copy(builtin=False))
        except OSError as err:
            log.error("cannot save imported preset: %s", err)
        self.win.refresh_all_presets()
        log.info("imported kb2xbox config (%d buttons, %d notes)", bound, len(notes))
        if answer == QMessageBox.Yes:
            self._apply_layout(imported, imported.id)
            self.win.status(f"Player {self.player} now uses {Path(path).name}")

    def _labels_changed(self) -> None:
        self.profile.label_set = self.labels.currentData()
        self.win.save_player(self.player)
        self.refresh()

    def _socd_changed(self) -> None:
        mode = self.socd.currentData()
        self.win.settings.socd[self.player] = mode
        self.win.engine.set_socd(self.player, mode)
        self.win.save_settings()
        self.win.status(f"Player {self.player}: opposite directions → {SOCD_MODES[mode]}")

    # --- keys --------------------------------------------------------------

    def change_key(self, control_id: str, slot: str = "main") -> None:
        names = {v.key: v.name for v in self.win.engine.views()}
        label = self.profile.label(control_id)
        dlg = CaptureDialog(self, self.win.engine, f"Player {self.player} · {label}" + (" · second key" if slot == "alt" else ""),
                            "Press the key you want on the keyboard.\nAny key works, including Esc and Enter. "
                            "Use the mouse to cancel.", names)
        if not dlg.exec() or dlg.result_key is None:
            return
        key = dlg.result_key
        if key and dlg.result_code in (self.win.engine.toggle_chord.key, self.win.engine.panic_chord.key):
            QMessageBox.information(self, "Hotkey key",
                                    f"{pretty(key)} is part of a kbpad hotkey "
                                    f"({self.win.engine.toggle_chord.text()} / {self.win.engine.panic_chord.text()}). "
                                    "Pressed together with the hotkey's modifiers it grabs/releases instead.")
        moved = self.profile.bind(control_id, key, slot)
        self.win.save_player(self.player)
        self.refresh()
        if moved:
            self.win.status(f"{pretty(key)} moved from {self.profile.label(moved)} to {label}")
        elif key:
            self.win.status(f"Player {self.player}: {label} = {pretty(key)}"
                            + (f" (pressed on {dlg.result_from})" if dlg.result_from else ""))
        else:
            self.win.status(f"Player {self.player}: {label} cleared")

    def _clear_key(self, control_id: str) -> None:
        self.profile.keys[control_id] = ""
        self.profile.alt[control_id] = ""
        self.win.save_player(self.player)
        self.refresh()

    def refresh(self) -> None:
        self.labels.setCurrentIndex(self.labels.findData(self.profile.label_set))
        self.socd.setCurrentIndex(max(0, self.socd.findData(self.win.settings.socd.get(self.player, "neutral"))))
        self.pad.set_profile(self.profile)
        self.table.setRowCount(len(CONTROLS))
        bold = QFont(self.font()); bold.setBold(True)
        for row, c in enumerate(CONTROLS):
            g = QTableWidgetItem(c.group)
            g.setForeground(QGuiApplication.palette().placeholderText())
            self.table.setItem(row, 0, g)
            self.table.setItem(row, 1, QTableWidgetItem(self.profile.label(c.id)))
            for col, key in ((2, self.profile.key_for(c.id)), (3, self.profile.alt_for(c.id))):
                item = QTableWidgetItem(pretty(key) if key else ("— not set —" if col == 2 else ""))
                item.setToolTip(key)
                if key:
                    item.setFont(bold)
                self.table.setItem(row, col, item)
            cell = QWidget()
            h = QHBoxLayout(cell)
            h.setContentsMargins(2, 1, 2, 1)
            h.setSpacing(4)
            for text, slot in (("Key", "main"), ("2nd", "alt")):
                b = QPushButton(text)
                b.setObjectName("small")
                b.setMinimumWidth(56)
                b.clicked.connect(lambda _=False, cid=c.id, s=slot: self.change_key(cid, s))
                h.addWidget(b)
            clear = QPushButton("Clear")
            clear.setObjectName("small")
            clear.setMinimumWidth(60)
            clear.setEnabled(bool(self.profile.key_for(c.id) or self.profile.alt_for(c.id)))
            clear.clicked.connect(lambda _=False, cid=c.id: self._clear_key(cid))
            h.addWidget(clear)
            self.table.setCellWidget(row, 4, cell)
        self.table.resizeRowsToContents()
        self.refresh_keyboards()

    def refresh_keyboards(self) -> None:
        kbs = [v for v in self.win.engine.views() if v.player == self.player]
        color = theme.player_color(self.player)
        if not kbs:
            self.keyboards.setText(f"<span style='color:{theme.WARNING}'>No keyboard is set to Player {self.player} "
                                   "yet. Choose it in the Keyboards list on the left.</span>")
        else:
            parts = [f"<b>{v.name}</b> <span style='color:gray'>({eng_state_text(v.state)})</span>" for v in kbs]
            self.keyboards.setText(f"<span style='color:{color}'>●</span> Keyboard: " + ", ".join(parts))

    def tick(self) -> None:
        self.pad.set_pressed(self.win.engine.pressed(self.player))


def eng_state_text(state: str) -> str:
    return {eng.GRABBED: "grabbed", eng.FREE: "not grabbed", eng.WAITING: "grabbing…",
            eng.DISCONNECTED: "disconnected", eng.ERROR: "error"}.get(state, state)


# ---------------------------------------------------------------------------

class KeyTestTab(QWidget):
    """Ghosting test: shows which keys a keyboard reports as held, and the most at once."""

    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        self.kb = QComboBox()
        self.kb.setMinimumWidth(260)
        reset = QPushButton("Reset")
        reset.clicked.connect(lambda: self.kb.currentData() and self.win.engine.reset_max_held(self.kb.currentData()))
        top = QHBoxLayout()
        top.addWidget(QLabel("Keyboard"))
        top.addWidget(self.kb)
        top.addWidget(reset)
        top.addStretch(1)

        self.held = QLabel()
        self.held.setTextFormat(Qt.RichText)
        self.held.setWordWrap(True)
        self.held.setMinimumHeight(110)
        self.held.setAlignment(Qt.AlignCenter)
        self.max = QLabel("0")
        self.max.setObjectName("bigNumber")
        self.max.setAlignment(Qt.AlignCenter)

        held_panel, hl = _panel("Keys held right now")
        hl.addWidget(self.held, 1)
        max_panel, ml = _panel("Most keys at once")
        ml.addWidget(self.max, 1)
        grid = QHBoxLayout()
        grid.addWidget(held_panel, 3)
        grid.addWidget(max_panel, 1)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.addLayout(top)
        lay.addLayout(grid, 1)
        lay.addWidget(_hint(
            "Hold the keys you press together in a game (for example ↓ → plus two attack keys). "
            "If a key you are holding does <b>not</b> appear, this keyboard cannot register that combination "
            "(called ghosting). Pick other keys for those buttons, or use another keyboard. "
            "Cheap keyboards often manage only 2–3 keys in some areas. Nothing here is saved or logged."))

    def refresh_list(self) -> None:
        current = self.kb.currentData()
        self.kb.clear()
        for v in self.win.engine.views():
            if v.present and not v.hidden:
                self.kb.addItem(dot_icon(theme.player_color(v.player)), v.name, v.key)
        if self.kb.count():
            self.kb.setCurrentIndex(max(0, self.kb.findData(current)))

    def tick(self) -> None:
        key = self.kb.currentData()
        if not key:
            self.held.setText("<i>No keyboard</i>")
            return
        keys, most = self.win.engine.held_keys(key)
        if keys:
            chips = " ".join(f"<span style='background:{theme.ACCENT}; color:white; border-radius:8px;'>"
                             f"&nbsp;{pretty(k)}&nbsp;</span>" for k in keys)
            self.held.setText(f"<span style='font-size:20pt; font-weight:700'>{chips}</span>")
        else:
            self.held.setText(f"<span style='color:gray'>Press and hold keys on this keyboard…</span>")
        self.max.setText(str(most))


# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self, engine: eng.Engine, bridge: EngineBridge, settings: config.Settings,
                 player_profiles: dict[int, Profile]):
        super().__init__()
        self.engine = engine
        self.bridge = bridge
        self.settings = settings
        self.player_profiles = player_profiles
        self.cards: dict[str, KeyboardCard] = {}
        self.player_tabs: dict[int, PlayerTab] = {}
        self._quitting = False
        self._tray_hint_shown = False
        self.tray = None
        self.tray_release = None

        self.setWindowTitle("kbpad — keyboards as controllers")
        self.setWindowIcon(app_icon())
        self.resize(1320, 860)

        central = QWidget()
        lay = QVBoxLayout(central)
        lay.setContentsMargins(14, 10, 14, 6)
        lay.setSpacing(10)
        lay.addWidget(self._build_header())
        self.banner = Banner()
        lay.addWidget(self.banner)

        split = QSplitter(Qt.Horizontal)
        split.addWidget(self._build_keyboards_panel())
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(False)
        for n in range(1, self.settings.players + 1):
            self._add_player_tab(n)
        self.tabs.addTab(self._build_pcsx2_tab(), "PCSX2")
        self.key_test = KeyTestTab(self)
        self.tabs.addTab(self.key_test, "Key test")
        self.tabs.addTab(self._build_checks_tab(), "System check")
        self.tabs.addTab(self._build_log_tab(), "Log")
        self.tabs.addTab(self._build_settings_tab(), "Settings")
        self.tabs.currentChanged.connect(self._tab_changed)
        split.addWidget(self.tabs)
        split.setSizes([440, 880])
        split.setHandleWidth(10)
        lay.addWidget(split, 1)
        self.setCentralWidget(central)

        self._build_menu()
        self._build_tray()

        bridge.changed.connect(self.refresh_cards)
        bridge.message.connect(self._on_message)
        bridge.grab.connect(self._on_grab)

        self.scan_timer = QTimer(self)
        self.scan_timer.timeout.connect(lambda: self.engine.rescan())
        self.scan_timer.start(1500)
        self.live_timer = QTimer(self)
        self.live_timer.timeout.connect(self._tick)
        self.live_timer.start(33)
        self.card_timer = QTimer(self)
        self.card_timer.timeout.connect(self.refresh_cards)
        self.card_timer.start(250)
        self.pcsx2_running = pcsx2.is_running()
        self.pcsx2_timer = QTimer(self)
        self.pcsx2_timer.timeout.connect(self._watch_pcsx2)
        self.pcsx2_timer.start(2000)

        self.engine.rescan(force=True)
        self.refresh_cards()
        self.run_checks()
        self.refresh_pcsx2()
        self.update_header()
        if self.pcsx2_running and not self.engine.pad_error:
            self.banner.show_message("<b>PCSX2 was already running when kbpad started.</b> It only looks for "
                                     "controllers when it starts: restart PCSX2 so it sees them. (W020)", "warning")

    # --- header and keyboards panel ---------------------------------------

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("header")
        icon = QLabel()
        icon.setPixmap(app_icon().pixmap(46, 46))
        title = QLabel("kbpad")
        title.setObjectName("appTitle")
        subtitle = QLabel("Keyboards → controllers")
        subtitle.setObjectName("appSubtitle")
        tcol = QVBoxLayout()
        tcol.setSpacing(0)
        tcol.addWidget(title)
        tcol.addWidget(subtitle)
        self.pad_status = QLabel()
        self.pad_status.setTextFormat(Qt.RichText)
        self.pcsx2_chip = QLabel()
        self.release_all_btn = QPushButton("Release all keyboards")
        self.release_all_btn.clicked.connect(lambda: self.engine.release_all("gui"))
        self.launch_btn = QPushButton("▶  Start PCSX2")
        self.launch_btn.setObjectName("launch")
        self.launch_btn.clicked.connect(self.launch_pcsx2)
        h = QHBoxLayout(header)
        h.setContentsMargins(16, 10, 16, 10)
        h.setSpacing(14)
        h.addWidget(icon)
        h.addLayout(tcol)
        h.addSpacing(18)
        h.addWidget(self.pad_status, 1)
        h.addWidget(self.pcsx2_chip)
        h.addWidget(self.release_all_btn)
        h.addWidget(self.launch_btn)
        return header

    def _build_keyboards_panel(self) -> QFrame:
        panel, lay = _panel("Keyboards")
        self.hotkey_hint = _hint("")
        lay.addWidget(self.hotkey_hint)
        self.kb_list = QVBoxLayout()
        self.kb_list.setSpacing(10)
        self.kb_list.addStretch(1)
        holder = QWidget()
        holder.setLayout(self.kb_list)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(holder)
        lay.addWidget(scroll, 1)
        self.show_hidden = QCheckBox("Show mice and virtual devices")
        self.show_hidden.toggled.connect(self.refresh_cards)
        lay.addWidget(self.show_hidden)
        self._update_hotkey_hint()
        return panel

    def _update_hotkey_hint(self) -> None:
        self.hotkey_hint.setText(
            "Press any key on a keyboard: its card lights up.<br>"
            f"<b>{self.engine.toggle_chord.text()}</b> on a keyboard grabs or releases that keyboard.<br>"
            f"<b>{self.engine.panic_chord.text()}</b> releases every keyboard.")

    # --- helpers -----------------------------------------------------------

    def status(self, text: str) -> None:
        self.statusBar().showMessage(text, 8000)

    def presets(self) -> dict[str, Profile]:
        return {pid: p for pid, p in profiles.all_profiles().items() if not pid.startswith("player")}

    def refresh_all_presets(self) -> None:
        for tab in self.player_tabs.values():
            tab.refresh_presets()

    def save_player(self, player: int) -> None:
        try:
            profiles.save_user_profile(self.player_profiles[player])
        except OSError as err:
            log.error("cannot save profile: %s", err)
            QMessageBox.critical(self, "Save failed", f"Could not save Player {player}'s keys:\n{err}")
        self.engine.set_profile(player, self.player_profiles[player])

    def save_settings(self) -> None:
        names = {v.key: v.name for v in self.engine.views()}
        self.settings.assignments = [config.Assignment(key=k, player=p, name=names.get(k, ""))
                                     for k, p in self.engine.assignments.items()]
        try:
            config.save(self.settings)
        except OSError as err:
            log.error("cannot save config: %s", err)
            self.status(f"Could not save settings: {err}")

    def _add_player_tab(self, n: int) -> None:
        tab = PlayerTab(self, n)
        self.player_tabs[n] = tab
        self.tabs.insertTab(n - 1, tab, dot_icon(theme.player_color(n)), f"Player {n}")

    def _tab_changed(self, _index: int) -> None:
        w = self.tabs.currentWidget()
        if w is getattr(self, "checks_tab", None):
            self._refresh_awake()
        elif w is self.key_test:
            self.key_test.refresh_list()
        elif w is getattr(self, "log_tab", None):
            self.refresh_log()

    # --- keyboards ---------------------------------------------------------

    def refresh_cards(self) -> None:
        views = self.engine.views()
        visible = [v for v in views if self.show_hidden.isChecked() or not v.hidden]
        keys = [v.key for v in visible]
        models: dict[tuple, int] = {}
        for v in visible:
            models[(v.usb_id, v.name)] = models.get((v.usb_id, v.name), 0) + 1
        for key in [k for k in self.cards if k not in keys]:
            card = self.cards.pop(key)
            self.kb_list.removeWidget(card)
            card.deleteLater()
        for i, v in enumerate(visible):
            card = self.cards.get(v.key)
            if card is None:
                card = KeyboardCard(v.key, self.settings.players)
                card.player_changed.connect(self._assign)
                card.grab_clicked.connect(lambda key: self.engine.toggle_grab(key, "gui"))
                self.cards[v.key] = card
                self.kb_list.insertWidget(i, card)
            card.update_view(v, show_port=models[(v.usb_id, v.name)] > 1)
        if not visible:
            if not hasattr(self, "_empty"):
                self._empty = _hint("No keyboards found. Check the System check tab.")
                self._empty.setAlignment(Qt.AlignCenter)
                self.kb_list.insertWidget(0, self._empty)
            self._empty.show()
        elif hasattr(self, "_empty"):
            self._empty.hide()
        for tab in self.player_tabs.values():
            tab.refresh_keyboards()
        self.update_header()

    def _assign(self, key: str, player) -> None:
        self.engine.assign(key, player)
        self.save_settings()
        self.refresh_cards()
        self._refresh_awake()
        if player:
            self.status(f"Keyboard set to Player {player}. Press {self.engine.toggle_chord.text()} on it "
                        "(or Grab) so the desktop ignores it.")

    def update_header(self) -> None:
        if self.engine.pad_error:
            self.pad_status.setText(f"<b>Controllers not created</b><br>{self.engine.pad_error}")
        else:
            views = self.engine.views()
            parts = []
            for n in sorted(self.engine.pads):
                kbs = [v for v in views if v.player == n and v.present]
                grabbed = any(v.state == eng.GRABBED for v in kbs)
                state = "grabbed" if grabbed else ("ready" if kbs else "no keyboard")
                dot = theme.player_color(n)
                parts.append(f"<span style='color:{dot}; font-size:14pt'>●</span>"
                             f"<b> P{n}</b> <span style='color:rgba(255,255,255,0.75)'>{state}</span>")
            self.pad_status.setText("&nbsp;&nbsp;&nbsp;".join(parts))
        any_grabbed = self.engine.any_grabbed()
        if self.release_all_btn.objectName() != ("danger" if any_grabbed else ""):
            self.release_all_btn.setObjectName("danger" if any_grabbed else "")
            self.release_all_btn.style().unpolish(self.release_all_btn)
            self.release_all_btn.style().polish(self.release_all_btn)
        if self.tray_release:
            self.tray_release.setEnabled(any_grabbed)
        if self.pcsx2_running:
            self.pcsx2_chip.setText("PCSX2 running")
            self.pcsx2_chip.setStyleSheet(theme.chip("rgba(34,197,94,0.9)"))
        else:
            self.pcsx2_chip.setText("")
            self.pcsx2_chip.setStyleSheet("")

    def _tick(self) -> None:
        tab = self.tabs.currentWidget()
        if isinstance(tab, (PlayerTab, KeyTestTab)):
            tab.tick()

    def _on_message(self, level: str, text: str) -> None:
        self.status(text)
        if level == "error":
            self.banner.show_message(text, "error")

    def _on_grab(self, name: str, grabbed: bool, source: str) -> None:
        if source in ("hotkey", "panic", "pcsx2") and self.tray and self.tray.isVisible():
            msg = f"{name} grabbed — {self.engine.toggle_chord.text()} on it to release" if grabbed \
                else f"{name} released"
            self.tray.showMessage("kbpad", msg, QSystemTrayIcon.Information, 1500)
        self.refresh_cards()

    # --- PCSX2 -------------------------------------------------------------

    def _build_pcsx2_tab(self) -> QWidget:
        w = QWidget()
        self.pcsx2_found = QLabel()
        self.pcsx2_found.setWordWrap(True)
        self.pcsx2_found.setTextFormat(Qt.RichText)
        self.pcsx2_mode = QComboBox()
        for label, data in (("Automatic", "auto"), ("Flatpak", "flatpak"), ("Installed package", "native"),
                            ("Custom command / AppImage", "custom")):
            self.pcsx2_mode.addItem(label, data)
        self.pcsx2_mode.setCurrentIndex(self.pcsx2_mode.findData(self.settings.pcsx2_mode))
        self.pcsx2_mode.activated.connect(self._pcsx2_settings_changed)
        self.pcsx2_cmd = QLineEdit(self.settings.pcsx2_command)
        self.pcsx2_cmd.setPlaceholderText("/path/to/pcsx2-qt.AppImage")
        self.pcsx2_cmd.editingFinished.connect(self._pcsx2_settings_changed)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_pcsx2)
        cmd_row = QHBoxLayout()
        cmd_row.addWidget(self.pcsx2_cmd, 1)
        cmd_row.addWidget(browse)
        self.hidapi = QCheckBox("Start with SDL_JOYSTICK_HIDAPI=0 (try this if PCSX2 does not list the controllers)")
        self.hidapi.setChecked(self.settings.sdl_hidapi_off)
        self.hidapi.toggled.connect(self._pcsx2_settings_changed)
        self.flatpak_status = QLabel()
        self.flatpak_status.setTextFormat(Qt.RichText)
        self.flatpak_btn = QPushButton("Allow PCSX2 Flatpak to see controllers")
        self.flatpak_btn.clicked.connect(self._grant_flatpak)

        start_panel, sl = _panel("Start")
        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(8)
        form.addRow("Found", self.pcsx2_found)
        form.addRow("Start using", self.pcsx2_mode)
        form.addRow("Custom command", cmd_row)
        form.addRow("", self.hidapi)
        form.addRow("Flatpak access", self.flatpak_status)
        form.addRow("", self.flatpak_btn)
        sl.addLayout(form)
        launch = QPushButton("▶  Start PCSX2")
        launch.setObjectName("primary")
        launch.setMinimumHeight(38)
        launch.clicked.connect(self.launch_pcsx2)
        sl.addWidget(launch)

        setup_panel, ul = _panel("Controller setup inside PCSX2")
        self.ini_status = _hint("")
        ul.addWidget(self.ini_status)
        setup_btn = QPushButton("Set up PCSX2 controllers automatically")
        setup_btn.clicked.connect(self._write_pcsx2_setup)
        ul.addWidget(setup_btn)
        ul.addWidget(_hint(
            "Sets Port 1 = DualShock 2 on <b>SDL-0</b> (XBOX Controller P1), Port 2 = <b>SDL-1</b> (P2), …, "
            "the same as <i>Automatic Mapping</i> in PCSX2. A backup of PCSX2.ini is kept first. "
            "PCSX2 must be closed. If you have another real gamepad plugged in, SDL numbers can shift: "
            "then pick the controllers by name in PCSX2 instead."))

        steps = _hint(
            "<b>Order that always works</b><ol>"
            "<li>Set each keyboard to a player (left side).</li>"
            "<li>Start PCSX2 from here: the controllers already exist, so PCSX2 sees them.</li>"
            "<li>Start the game, then press the grab hotkey on each keyboard (or click Grab).</li>"
            "<li>Close PCSX2 and every keyboard is released automatically (Settings).</li></ol>")

        lay = QVBoxLayout(w)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.addWidget(start_panel)
        lay.addWidget(setup_panel)
        lay.addWidget(steps)
        lay.addStretch(1)
        return w

    def _browse_pcsx2(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose PCSX2", str(Path.home()))
        if path:
            self.pcsx2_cmd.setText(path)
            self.pcsx2_mode.setCurrentIndex(self.pcsx2_mode.findData("custom"))
            self._pcsx2_settings_changed()

    def _pcsx2_settings_changed(self, *_):
        self.settings.pcsx2_mode = self.pcsx2_mode.currentData()
        self.settings.pcsx2_command = self.pcsx2_cmd.text().strip()
        self.settings.sdl_hidapi_off = self.hidapi.isChecked()
        self.save_settings()
        self.refresh_pcsx2()

    def refresh_pcsx2(self) -> None:
        inst = pcsx2.detect(self.settings.pcsx2_mode, self.settings.pcsx2_command)
        self.pcsx2_install = inst
        if inst.kind == "none":
            self.pcsx2_found.setText(f"<span style='color:{theme.DANGER}'>{inst.detail}</span>")
        else:
            self.pcsx2_found.setText(f"<b>{inst.kind}</b> · {inst.detail}")
        self.pcsx2_cmd.setEnabled(self.settings.pcsx2_mode == "custom")
        if inst.kind == "flatpak":
            access = pcsx2.flatpak_has_device_access()
            if access:
                self.flatpak_status.setText(f"<span style='color:{theme.SUCCESS}'>✔ allowed</span>")
                self.flatpak_btn.hide()
            else:
                self.flatpak_status.setText(f"<span style='color:{theme.DANGER}'>✘ not allowed: PCSX2 will not see "
                                            "the controllers (E031)</span>")
                self.flatpak_btn.show()
        else:
            self.flatpak_status.setText("not needed")
            self.flatpak_btn.hide()
        ini = pcsx2.find_ini(inst.kind)
        self.ini_status.setText(f"Settings file: <code>{ini}</code>" if ini else
                                "PCSX2.ini not found yet: start PCSX2 once and finish its first-run setup.")
        self.launch_btn.setEnabled(inst.kind != "none")
        self.launch_btn.setToolTip(inst.detail)

    def _grant_flatpak(self) -> None:
        ok, out = pcsx2.grant_flatpak_device_access()
        if not ok:
            QMessageBox.warning(self, "Flatpak", f"Could not change the permission:\n{out}")
        self.refresh_pcsx2()

    def _write_pcsx2_setup(self) -> None:
        ini = pcsx2.find_ini(self.pcsx2_install.kind)
        if not ini:
            QMessageBox.information(self, "PCSX2", "PCSX2.ini was not found. Start PCSX2 once, finish its setup "
                                    "wizard, close it, then try again.")
            return
        n = len(self.engine.pads) or self.settings.players
        if QMessageBox.question(self, "PCSX2 controller setup",
                                f"Set {n} PCSX2 controller port(s) to the kbpad controllers?\n\n{ini}\n\n"
                                "A backup is saved first.") != QMessageBox.Yes:
            return
        try:
            backup, style = pcsx2.write_controller_setup(ini, n)
        except pcsx2.IniError as err:
            QMessageBox.warning(self, "PCSX2 controller setup", str(err))
            return
        except OSError as err:
            QMessageBox.critical(self, "PCSX2 controller setup", f"Could not write the file:\n{err}")
            return
        QMessageBox.information(self, "PCSX2 controller setup",
                                f"Done ({'new' if style == 'new' else 'older'} PCSX2 naming).\n"
                                f"Backup: {backup}\n\nStart PCSX2 and check Settings → Controllers once.")

    def launch_pcsx2(self) -> None:
        self.refresh_pcsx2()
        inst = self.pcsx2_install
        if inst.kind == "none":
            self.tabs.setCurrentIndex(self.settings.players)        # PCSX2 tab follows the player tabs
            QMessageBox.warning(self, "PCSX2", inst.detail)
            return
        if self.engine.pad_error:
            QMessageBox.critical(self, "PCSX2", "The virtual controllers do not exist, so PCSX2 would not see them.\n\n"
                                 + self.engine.pad_error + "\n\nSee the System check tab.")
            return
        if self.pcsx2_running:
            QMessageBox.information(self, "PCSX2", "PCSX2 is already running.")
            return
        if not any(v.present for v in self.engine.views() if v.player):
            if QMessageBox.question(self, "PCSX2", "No keyboard is set to a player yet. Start PCSX2 anyway?") \
                    != QMessageBox.Yes:
                return
        if inst.kind == "flatpak" and pcsx2.flatpak_has_device_access() is False:
            if QMessageBox.question(self, "PCSX2", "The PCSX2 Flatpak is not allowed to see controllers. "
                                    "Allow it now?") == QMessageBox.Yes:
                self._grant_flatpak()
        try:
            pcsx2.launch(inst, self.settings.sdl_hidapi_off)
            self.status(f"PCSX2 started. In the game, press {self.engine.toggle_chord.text()} on each keyboard.")
        except OSError as err:
            log.error("E030 PCSX2 start failed: %s", err)
            QMessageBox.critical(self, "PCSX2", f"Could not start PCSX2 (E030):\n{err}")

    def _watch_pcsx2(self) -> None:
        running = pcsx2.is_running()
        if running == self.pcsx2_running:
            return
        self.pcsx2_running = running
        log.info("PCSX2 %s", "started" if running else "closed")
        if not running and self.settings.release_on_pcsx2_exit and self.engine.any_grabbed():
            self.engine.release_all("pcsx2")
            self.status("PCSX2 closed: all keyboards released.")
        if running and self.banner.isVisible() and "W020" in self.banner.label.text():
            self.banner.hide()
        self.update_header()

    # --- checks ------------------------------------------------------------

    def _build_checks_tab(self) -> QWidget:
        w = QWidget()
        self.checks_tab = w
        self.checks_table = QTableWidget(0, 3)
        self.checks_table.setHorizontalHeaderLabels(["", "Check", "Result / fix"])
        self.checks_table.verticalHeader().setVisible(False)
        self.checks_table.setShowGrid(False)
        self.checks_table.setAlternatingRowColors(True)
        self.checks_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.checks_table.setWordWrap(True)
        rerun = QPushButton("Run checks again")
        rerun.clicked.connect(self.run_checks)
        copy = QPushButton("Copy fix commands")
        copy.clicked.connect(self._copy_fixes)
        row = QHBoxLayout()
        row.addWidget(rerun)
        row.addWidget(copy)
        row.addStretch(1)

        awake, al = _panel("Keyboards dropping out?")
        al.addWidget(_hint("USB power saving (autosuspend) can make a keyboard stop responding for a moment. "
                           "This keeps every keyboard that is set to a player always awake, now and after replugging. "
                           "Asks for your password once."))
        self.awake_status = QLabel()
        self.awake_status.setTextFormat(Qt.RichText)
        self.awake_status.setWordWrap(True)
        al.addWidget(self.awake_status)
        awake_btn = QPushButton("Keep game keyboards awake")
        awake_btn.setObjectName("primary")
        awake_btn.clicked.connect(self._fix_autosuspend)
        al.addWidget(awake_btn, 0, Qt.AlignLeft)

        lay = QVBoxLayout(w)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.addWidget(self.checks_table, 1)
        lay.addLayout(row)
        lay.addWidget(_hint("Fix commands need a terminal and your password. Run them, then restart kbpad."))
        lay.addWidget(awake)
        return w

    def _game_keyboards(self):
        return [self.engine.keyboards[k] for k in self.engine.assignments if k in self.engine.keyboards]

    def run_checks(self) -> None:
        self.checks = doctor.run_checks()
        self.checks_table.setRowCount(len(self.checks))
        for i, c in enumerate(self.checks):
            mark = QTableWidgetItem("✔" if c.ok else "✘")
            mark.setForeground(QBrush(QColor(theme.SUCCESS if c.ok else theme.DANGER)))
            self.checks_table.setItem(i, 0, mark)
            self.checks_table.setItem(i, 1, QTableWidgetItem(c.name))
            text = c.detail + ("" if c.ok or not c.fix else f"\nFix: {c.fix}")
            self.checks_table.setItem(i, 2, QTableWidgetItem(text))
        self.checks_table.resizeColumnsToContents()
        self.checks_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.checks_table.resizeRowsToContents()
        self._refresh_awake()
        failed = [c for c in self.checks if not c.ok]
        if failed or self.engine.pad_error:
            items = "".join(f"<li>{c.name}: {c.detail}</li>" for c in failed)
            if self.engine.pad_error:
                items = f"<li>{self.engine.pad_error}</li>" + items
            self.banner.show_message(f"<b>Setup problem</b><ul>{items}</ul>Open the <b>System check</b> tab "
                                     "for the fix.", "error")

    def _refresh_awake(self) -> None:
        kbs = self._game_keyboards()
        if not kbs:
            self.awake_status.setText("<i>No keyboard is set to a player yet.</i>")
            return
        rows = []
        for name, usb, state in doctor.autosuspend_status(kbs):
            if state == "on":
                mark = f"<span style='color:{theme.SUCCESS}'>✔ always awake</span>"
            elif state == "auto":
                mark = f"<span style='color:{theme.WARNING}'>⚠ may sleep</span>"
            else:
                mark = "<span style='color:gray'>? not a USB keyboard (nothing to do)</span>"
            rows.append(f"{mark} — {name} ({usb})")
        self.awake_status.setText("<br>".join(rows))

    def _fix_autosuspend(self) -> None:
        kbs = self._game_keyboards()
        ok, msg = doctor.apply_autosuspend_fix(kbs)
        if ok:
            QMessageBox.information(self, "Keep keyboards awake", msg)
        else:
            if "sudo sh -c" in msg:
                QGuiApplication.clipboard().setText(msg.split("instead:\n", 1)[-1])
                msg += "\n\n(The command was copied to the clipboard.)"
            QMessageBox.warning(self, "Keep keyboards awake", msg)
        self._refresh_awake()

    def _copy_fixes(self) -> None:
        fixes = [c.fix for c in getattr(self, "checks", []) if not c.ok and c.fix]
        QGuiApplication.clipboard().setText("\n".join(fixes) if fixes else "# nothing to fix")
        self.status("Fix commands copied" if fixes else "Nothing to fix")

    # --- log ---------------------------------------------------------------

    def _build_log_tab(self) -> QWidget:
        w = QWidget()
        self.log_tab = w
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("monospace", 9))
        self.log_view.setMaximumBlockCount(3000)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh_log)
        folder = QPushButton("Open log folder")
        folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(LOG_DIR))))
        export = QPushButton("Export diagnostics…")
        export.setObjectName("primary")
        export.clicked.connect(self.export_diagnostics)
        row = QHBoxLayout()
        for b in (refresh, folder, export):
            row.addWidget(b)
        row.addStretch(1)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.addWidget(self.log_view, 1)
        lay.addLayout(row)
        lay.addWidget(_hint("The log never records which keys you type. Diagnostics stay on this PC until you "
                            "send the zip yourself; your username is masked."))
        return w

    def refresh_log(self) -> None:
        try:
            lines = LOG_FILE.read_text(errors="replace").splitlines()[-1500:]
        except OSError:
            lines = ["(no log yet)"]
        self.log_view.setPlainText("\n".join(lines))
        self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())

    def export_diagnostics(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Save diagnostics to", str(Path.home()))
        if not folder:
            return
        try:
            path = logsetup.export_bundle(Path(folder))
            QMessageBox.information(self, "Diagnostics", f"Saved:\n{path}")
        except OSError as err:
            QMessageBox.critical(self, "Diagnostics", f"Could not write the zip:\n{err}")

    # --- settings ----------------------------------------------------------

    def _build_settings_tab(self) -> QWidget:
        w = QWidget()
        look, ll = _panel("Look")
        self.theme_box = QComboBox()
        for label, data in (("Dark", "dark"), ("Light", "light"), ("Follow system", "system")):
            self.theme_box.addItem(label, data)
        self.theme_box.setCurrentIndex(max(0, self.theme_box.findData(self.settings.theme)))
        self.theme_box.activated.connect(self._theme_changed)
        self.theme_box.setFixedWidth(220)
        lf = QFormLayout()
        lf.addRow("Theme", self.theme_box)
        ll.addLayout(lf)

        hk, hl = _panel("Hotkeys")
        self.toggle_label = QLabel()
        self.panic_label = QLabel()
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        for row, (title, lbl, which) in enumerate((("Grab / release this keyboard", self.toggle_label, "toggle"),
                                                    ("Release every keyboard", self.panic_label, "panic"))):
            grid.addWidget(QLabel(title), row, 0)
            lbl.setStyleSheet(f"font-weight:700; color:{theme.ACCENT};")
            grid.addWidget(lbl, row, 1)
            change = QPushButton("Change…")
            change.clicked.connect(lambda _=False, wh=which: self._change_hotkey(wh))
            grid.addWidget(change, row, 2)
        reset = QPushButton("Reset to defaults")
        reset.clicked.connect(self._reset_hotkeys)
        grid.addWidget(reset, 2, 2)
        grid.setColumnStretch(3, 1)
        hl.addLayout(grid)
        hl.addWidget(_hint("Hotkeys work from any keyboard set to a player, grabbed or not, with no terminal. "
                           "A grab waits until you let go of all keys, so modifiers never stick. "
                           "KDE uses Ctrl+F1 for “switch to desktop 1”: if that bothers you, pick "
                           "<b>Pause</b> or <b>Scroll Lock</b>, or turn the KDE shortcut off."))
        self._update_hotkey_labels()

        beh, bl = _panel("Behaviour")
        self.players_spin = QSpinBox()
        self.players_spin.setRange(1, MAX_PLAYERS)
        self.players_spin.setValue(self.settings.players)
        apply_players = QPushButton("Apply")
        apply_players.clicked.connect(self._apply_players)
        prow = QHBoxLayout()
        prow.addWidget(QLabel("Players (controllers)"))
        prow.addWidget(self.players_spin)
        prow.addWidget(apply_players)
        prow.addStretch(1)
        bl.addLayout(prow)
        for text, attr, handler in (
                ("Send keys to the controller only while the keyboard is grabbed (how kb2xbox worked)",
                 "map_only_when_grabbed", self._only_grabbed),
                ("Release every keyboard when PCSX2 closes", "release_on_pcsx2_exit", None),
                ("Closing the window keeps kbpad running in the tray (controllers stay alive)",
                 "close_to_tray", None)):
            box = QCheckBox(text)
            box.setChecked(getattr(self.settings, attr))
            box.toggled.connect(handler or (lambda on, a=attr: self._set_flag(a, on)))
            bl.addWidget(box)

        lay = QVBoxLayout(w)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(12)
        lay.addWidget(look)
        lay.addWidget(hk)
        lay.addWidget(beh)
        lay.addStretch(1)
        return w

    def _theme_changed(self) -> None:
        self.settings.theme = self.theme_box.currentData()
        theme.apply(QApplication.instance(), self.settings.theme)
        self.save_settings()
        for card in self.cards.values():
            card._player = card._state = None          # force restyle
        self.refresh_cards()
        for tab in self.player_tabs.values():
            tab.refresh()
        self._update_hotkey_labels()

    def _update_hotkey_labels(self) -> None:
        self.toggle_label.setText(self.engine.toggle_chord.text())
        self.panic_label.setText(self.engine.panic_chord.text())
        for lbl in (self.toggle_label, self.panic_label):
            lbl.setStyleSheet(f"font-weight:700; color:{theme.ACCENT};")
        if hasattr(self, "hotkey_hint"):
            self._update_hotkey_hint()

    def _change_hotkey(self, which: str) -> None:
        names = {v.key: v.name for v in self.engine.views()}
        title = "Grab / release hotkey" if which == "toggle" else "Release-all hotkey"
        dlg = CaptureDialog(self, self.engine, title,
                            "Hold the modifier keys you want (Ctrl, Shift, Alt…), then press the main key.\n"
                            "Single keys like Pause or Scroll Lock also work.", names, chord=True, allow_clear=False)
        if not dlg.exec() or dlg.result_code is None:
            return
        chord = eng.Chord.from_capture(dlg.result_code, set(dlg.result_held))
        other = self.engine.panic_chord if which == "toggle" else self.engine.toggle_chord
        if chord.tokens == other.tokens:
            QMessageBox.warning(self, title, "That is already the other hotkey.")
            return
        used = [f"Player {n}: {self.player_profiles[n].label(c)}" for n in self.player_profiles
                for k, c in self.player_profiles[n].all_bindings() if k == code_to_name(chord.key)]
        if not chord.mods:
            msg = (f"{chord.text()} without Ctrl/Shift/Alt means that key will always grab/release and never "
                   "type or play while kbpad runs.")
            if used:
                msg += "\n\nIt is also bound to: " + ", ".join(used)
            if QMessageBox.question(self, title, msg + "\n\nUse it anyway?") != QMessageBox.Yes:
                return
        elif used:
            QMessageBox.information(self, title, f"Note: {chord.text().split(' + ')[-1]} is also a controller key "
                                    f"({', '.join(used)}). With the modifiers held it grabs instead.")
        toggle = chord.tokens if which == "toggle" else self.settings.hotkey_toggle
        panic = chord.tokens if which == "panic" else self.settings.hotkey_panic
        self._set_hotkeys(toggle, panic)

    def _reset_hotkeys(self) -> None:
        self._set_hotkeys(list(eng.DEFAULT_TOGGLE), list(eng.DEFAULT_PANIC))

    def _set_hotkeys(self, toggle: list[str], panic: list[str]) -> None:
        try:
            self.engine.set_hotkeys(toggle, panic)
        except ValueError as err:
            QMessageBox.warning(self, "Hotkeys", str(err))
            return
        self.settings.hotkey_toggle, self.settings.hotkey_panic = list(toggle), list(panic)
        self.save_settings()
        self._update_hotkey_labels()
        self.status(f"Hotkeys: {self.engine.toggle_chord.text()} / {self.engine.panic_chord.text()}")

    def _apply_players(self) -> None:
        n = self.players_spin.value()
        if n == self.settings.players:
            return
        warn = "\n\nPCSX2 is running: restart it afterwards so it sees the new controllers." if self.pcsx2_running \
            else ""
        if QMessageBox.question(self, "Players", f"Change to {n} controllers?{warn}") != QMessageBox.Yes:
            self.players_spin.setValue(self.settings.players)
            return
        for kb_key, p in list(self.engine.assignments.items()):
            if p > n:
                self.engine.assign(kb_key, None)
        for p in [p for p in self.player_tabs if p > n]:
            tab = self.player_tabs.pop(p)
            self.tabs.removeTab(self.tabs.indexOf(tab))
            tab.deleteLater()
        self.settings.players = n
        for p in range(1, n + 1):
            if p not in self.player_profiles:
                self.player_profiles[p] = load_player_profile(p, self.settings)
                self.engine.set_profile(p, self.player_profiles[p])
            if p not in self.player_tabs:
                self._add_player_tab(p)
        self.engine.create_pads(n)
        for card in self.cards.values():
            card.set_player_count(n)
        self.save_settings()
        self.refresh_cards()
        if self.pcsx2_running:
            self.banner.show_message("<b>Restart PCSX2</b>: the number of controllers changed while it was "
                                     "running. (W020)", "warning")

    def _only_grabbed(self, on: bool) -> None:
        self.settings.map_only_when_grabbed = on
        self.engine.map_only_when_grabbed = on
        self.save_settings()

    def _set_flag(self, attr: str, on: bool) -> None:
        setattr(self.settings, attr, on)
        self.save_settings()

    # --- menu, tray, closing ----------------------------------------------

    def _build_menu(self) -> None:
        m = self.menuBar().addMenu("&File")
        for text, slot, shortcut in (("Release all keyboards", lambda: self.engine.release_all("gui"), None),
                                     ("Export diagnostics…", self.export_diagnostics, None),
                                     (None, None, None),
                                     ("Quit kbpad", self.quit_app, "Ctrl+Q")):
            if text is None:
                m.addSeparator()
                continue
            a = QAction(text, self)
            a.triggered.connect(slot)
            if shortcut:
                a.setShortcut(shortcut)
            m.addAction(a)

    def _build_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip("kbpad")
        menu = QMenu()
        menu.addAction("Show window", self.show_window)
        self.tray_release = menu.addAction("Release all keyboards", lambda: self.engine.release_all("gui"))
        menu.addAction("Start PCSX2", self.launch_pcsx2)
        menu.addSeparator()
        menu.addAction("Quit kbpad", self.quit_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.show_window()
                                    if reason == QSystemTrayIcon.Trigger else None)
        self.tray.show()

    def show_window(self) -> None:
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.raise_()
        self.activateWindow()

    def closeEvent(self, ev) -> None:
        if not self._quitting and self.settings.close_to_tray and self.tray and self.tray.isVisible():
            ev.ignore()
            self.hide()
            if not self._tray_hint_shown:
                self.tray.showMessage("kbpad is still running",
                                      "Controllers stay alive for PCSX2. Quit from the tray icon.",
                                      QSystemTrayIcon.Information, 3000)
                self._tray_hint_shown = True
            return
        self._quitting = True
        ev.accept()
        QApplication.instance().quit()

    def quit_app(self) -> None:
        self._quitting = True
        self.save_settings()
        QApplication.instance().quit()


def load_player_profile(player: int, settings: config.Settings) -> Profile:
    """Player N's live keys: saved copy if present, else a copy of the player's preset."""
    pid = profiles.player_profile_id(player)
    existing = profiles.user_profiles().get(pid)
    if existing:
        return existing
    presets = profiles.builtin_profiles()
    preset_id = settings.presets.get(player) or profiles.default_preset_for(player)
    base = profiles.all_profiles().get(preset_id) or presets.get(profiles.default_preset_for(player)) \
        or Profile(id=pid, name=pid)
    live = base.copy(id=pid, name=f"Player {player} (current keys)", builtin=False)
    settings.presets[player] = base.id
    try:
        profiles.save_user_profile(live)
    except OSError as err:
        log.error("cannot save player profile: %s", err)
    return live
