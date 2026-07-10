import logging
import os
import sys

# Must happen before PySide6 is imported anywhere: Wayland's core protocol
# doesn't let a client position its own top-level window, which breaks
# "remember each note's position" and complicates always-on-top. Forcing
# XWayland gives real X11 window semantics, which KWin honors reliably.
if sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")


def main():
    logging.basicConfig(level=logging.INFO)

    from PySide6.QtWidgets import QApplication

    from .app import NoteManager

    app = QApplication(sys.argv)
    # Explicit, unique applicationName drives WM_CLASS — important since a
    # generic name is what caused KWin's task switcher to confuse our icon
    # with an unrelated, similarly-named "Sticky Notes" Flatpak app.
    app.setApplicationName("take-note")
    app.setApplicationDisplayName("Take Note!")
    manager = NoteManager(app)
    manager.load_from_disk()

    exit_code = app.exec()
    # Python 3.14's own interpreter teardown (GC/type finalization) SIGSEGVs
    # against this Shiboken/PySide6 build on quit — confirmed via
    # coredumpctl (SIGSEGV in python3.14 itself, right at quit, no crash
    # during actual use). Same root cause already found and worked around
    # for the test suite in tests/conftest.py; os._exit() skips that
    # teardown entirely. Safe to skip here too: all real cleanup (saving
    # notes.json, stopping the X11 hotkey listener thread) already
    # happened synchronously in NoteManager._on_about_to_quit(), wired to
    # QApplication.aboutToQuit, before app.exec() returned.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)


if __name__ == "__main__":
    main()
