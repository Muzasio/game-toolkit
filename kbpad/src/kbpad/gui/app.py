"""Entry point: single instance, logging, engine, window, tray."""

from __future__ import annotations

import argparse
import fcntl
import logging
import os
import signal
import sys

from .. import __version__, config, doctor, logsetup, profiles
from ..constants import LOCK_FILE
from ..engine import Engine

log = logging.getLogger("kbpad")


def _single_instance():
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    fh = open(LOCK_FILE, "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    fh.write(str(os.getpid()))
    fh.flush()
    return fh


def _cli_list() -> int:
    from .. import devices
    for kb in devices.scan():
        flags = " (mouse)" if kb.is_mouse else " (virtual)" if kb.is_virtual else ""
        print(f"{kb.name}{flags}\n  usb {kb.usb_id}  key {kb.key}\n  nodes {' '.join(kb.all_nodes)}")
    return 0


def _cli_check() -> int:
    bad = 0
    for c in doctor.run_checks():
        print(("OK   " if c.ok else "FAIL ") + f"{c.name}: {c.detail}")
        if not c.ok:
            bad += 1
            if c.fix:
                print(f"     fix: {c.fix}")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kbpad", description="Use keyboards as game controllers.")
    ap.add_argument("--list", action="store_true", help="list detected keyboards and exit")
    ap.add_argument("--check", action="store_true", help="run the system checks and exit")
    ap.add_argument("--hidden", action="store_true", help="start minimised to the tray")
    ap.add_argument("--debug", action="store_true", help="verbose log (still never logs typed keys)")
    ap.add_argument("--version", action="version", version=f"kbpad {__version__}")
    args = ap.parse_args(argv)

    if args.list:
        return _cli_list()
    if args.check:
        return _cli_check()

    logsetup.setup(debug=args.debug)

    from PySide6.QtCore import QTimer
    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    from PySide6.QtWidgets import QApplication, QMessageBox

    app = QApplication(sys.argv[:1])
    app.setApplicationName("kbpad")
    app.setDesktopFileName("kbpad")
    app.setQuitOnLastWindowClosed(False)
    server_name = f"kbpad-{os.getuid()}"

    lock = _single_instance()
    if lock is None:
        # Already running: ask that instance to show its window, then leave.
        sock = QLocalSocket()
        sock.connectToServer(server_name)
        if sock.waitForConnected(1000):
            sock.write(b"show\n")
            sock.waitForBytesWritten(1000)
            sock.disconnectFromServer()
            return 0
        QMessageBox.information(None, "kbpad", "kbpad is already running.\nLook for its icon in the system tray.")
        return 0

    from . import theme
    from .main_window import EngineBridge, MainWindow, load_player_profile

    settings = config.load()
    theme.apply(app, settings.theme)
    bridge = EngineBridge()
    engine = Engine(notify=bridge.notify)
    engine.map_only_when_grabbed = settings.map_only_when_grabbed
    try:
        engine.set_hotkeys(settings.hotkey_toggle, settings.hotkey_panic)
    except ValueError as err:
        log.error("bad hotkey in config (%s); using defaults", err)
    for player, mode in settings.socd.items():
        engine.set_socd(player, mode)

    player_profiles = {}
    for n in range(1, settings.players + 1):
        player_profiles[n] = load_player_profile(n, settings)
        engine.set_profile(n, player_profiles[n])
    for a in settings.assignments:
        if a.player <= settings.players:
            engine.assignments[a.key] = a.player
            engine.known_names[a.key] = a.name or a.key
    engine.create_pads(settings.players)
    try:
        config.save(settings)
    except OSError as err:
        log.error("cannot save config: %s", err)

    win = MainWindow(engine, bridge, settings, player_profiles)

    QLocalServer.removeServer(server_name)          # stale socket from a crash
    server = QLocalServer()
    server.setSocketOptions(QLocalServer.UserAccessOption)

    def on_connection():
        conn = server.nextPendingConnection()
        if conn:
            conn.readyRead.connect(lambda: (conn.readAll(), win.show_window()))
            conn.disconnected.connect(conn.deleteLater)
    server.newConnection.connect(on_connection)
    if not server.listen(server_name):
        log.warning("single-instance server not available: %s", server.errorString())

    def crash_dialog(text, path):
        QTimer.singleShot(0, lambda: QMessageBox.critical(
            win, "kbpad error", "Something went wrong, but your keyboards are safe.\n\n"
            + text.strip().splitlines()[-1] + (f"\n\nReport saved: {path}" if path else "")))
    logsetup.on_crash(crash_dialog)

    def shutdown():
        log.info("shutting down")
        engine.stop()
        lock.close()
    app.aboutToQuit.connect(shutdown)

    # Ctrl+C / SIGTERM in a terminal: quit cleanly (releases every keyboard).
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    signal.signal(signal.SIGTERM, lambda *_: app.quit())
    pump = QTimer()
    pump.timeout.connect(lambda: None)      # lets Python run signal handlers
    pump.start(300)

    if not (args.hidden and win.tray):
        win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
