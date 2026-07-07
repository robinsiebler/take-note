from __future__ import annotations

from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from .note_window import get_menu_qss


def _build_icon() -> QIcon:
    """A small generated icon so the app doesn't need a bundled asset file."""
    pixmap = QPixmap(32, 32)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setBrush(QColor("#fff59d"))
    painter.setPen(QColor(0, 0, 0, 60))
    painter.drawRoundedRect(2, 2, 28, 28, 5, 5)
    painter.end()
    return QIcon(pixmap)


class TrayIcon(QSystemTrayIcon):
    def __init__(self, manager):
        super().__init__(_build_icon())
        self.manager = manager
        self.setToolTip("Take Note!")

        # setContextMenu() does NOT take ownership of the menu (per Qt docs),
        # so it must be kept alive via a Python-side reference (self.menu) —
        # otherwise it (and its connected actions) get garbage collected
        # right after __init__ returns, and every item silently stops working.
        self.menu = QMenu()
        self.menu.setStyleSheet(get_menu_qss())
        new_note_action = self.menu.addAction("New Note")
        new_note_action.triggered.connect(lambda: manager.create_note())

        new_board_action = self.menu.addAction("New Memoboard")
        new_board_action.triggered.connect(lambda: manager.create_board())

        self.menu.addSeparator()
        settings_action = self.menu.addAction("Settings…")
        settings_action.triggered.connect(manager.open_settings)

        self.menu.addSeparator()
        quit_action = self.menu.addAction("Quit")
        quit_action.triggered.connect(manager.quit)

        self.setContextMenu(self.menu)
        self.activated.connect(self._on_activated)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.manager.create_note()
