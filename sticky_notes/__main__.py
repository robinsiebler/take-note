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
    manager = NoteManager(app)
    manager.load_from_disk()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
