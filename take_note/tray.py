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

        new_board_action = self.menu.addAction("New Notepad")
        new_board_action.triggered.connect(lambda: manager.create_board())

        # Rebuilt fresh every time the tray menu is about to open (not
        # built once in __init__) — boards get created/deleted/shown/
        # hidden throughout a session, and this is the simplest way to
        # keep the list and each checkmark's visible/hidden state
        # current without a separate change-signal wired to it. Mocked
        # up 3 options as real rendered menus first (flat inline items,
        # a plain submenu, a checkable submenu) — user picked a checkable
        # submenu, toggling a board's own show/hide from its checkmark.
        self.notepads_menu = self.menu.addMenu("Notepads")
        self.menu.aboutToShow.connect(self._populate_notepads_menu)

        notes_manager_action = self.menu.addAction("Notes Manager…")
        notes_manager_action.triggered.connect(manager.open_notes_manager)

        self.menu.addSeparator()
        bring_to_front_action = self.menu.addAction("Bring Notes on Top")
        bring_to_front_action.triggered.connect(manager.bring_all_notes_to_front)

        show_hide_all_action = self.menu.addAction("Show/Hide All Notes")
        show_hide_all_action.triggered.connect(manager.toggle_show_all_notes)

        roll_all_action = self.menu.addAction("Roll Up/Down Notes")
        roll_all_action.triggered.connect(manager.toggle_roll_all_notes)

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

    def _populate_notepads_menu(self):
        self.notepads_menu.clear()
        boards = list(self.manager.boards.values())
        # Disables the "Notepads" item itself (greyed out, unopenable) in
        # the main menu when there are no boards yet, rather than letting
        # it open onto an empty submenu with nothing to show.
        self.notepads_menu.setEnabled(bool(boards))
        for board_window in boards:
            action = self.notepads_menu.addAction(board_window.board.name)
            action.setCheckable(True)
            action.setChecked(board_window.isVisible())
            # Connected after setChecked() above, not before — setChecked()
            # only emits toggled() on an actual state change, but connecting
            # first would still risk firing on the very first board whose
            # real state happens to differ from a fresh QAction's own
            # default (unchecked).
            action.toggled.connect(lambda checked, bw=board_window: self._toggle_board(bw, checked))

    def _toggle_board(self, board_window, checked: bool):
        # show_board()/hide_board() (not raw showNormal()/hide()) — also
        # persists board.hidden, so toggling a board here is remembered
        # across a restart, same as toggling it via the board's own ×.
        if checked:
            board_window.show_board()
        else:
            board_window.hide_board()
