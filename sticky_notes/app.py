from __future__ import annotations

import logging

from PySide6.QtCore import QObject, QPoint, QTimer
from PySide6.QtWidgets import QApplication

from . import storage
from .board_window import MemoboardWindow
from .hotkey import HotkeyListener
from .models import Board, Note
from .note_window import NoteWindow
from .tray import TrayIcon

logger = logging.getLogger(__name__)

SAVE_DEBOUNCE_MS = 800
CASCADE_OFFSET = 24


class NoteManager(QObject):
    """Owns every open Note/Memoboard window, the tray icon, the global
    hotkey, and the single debounced save timer that writes all of them to
    disk as one JSON file."""

    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app
        self.notes: dict[str, NoteWindow] = {}
        self.boards: dict[str, MemoboardWindow] = {}

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(SAVE_DEBOUNCE_MS)
        self._save_timer.timeout.connect(self._save_now)

        self.tray = TrayIcon(self)
        self.tray.show()

        self.hotkey = HotkeyListener()
        self.hotkey.triggered.connect(lambda: self.create_note())
        self.hotkey.grab_failed.connect(self._on_hotkey_failed)
        self.hotkey.start()

        self.app.setQuitOnLastWindowClosed(False)
        self.app.aboutToQuit.connect(self._on_about_to_quit)

    # -- startup -------------------------------------------------------

    def load_from_disk(self):
        notes, boards = storage.load_all()

        # Boards first so each note's board canvas already exists by the
        # time a note with a board_id needs to be parented into it.
        for board in boards:
            board_window = MemoboardWindow(board, self)
            self._wire_board(board_window)

        for note in notes:
            parent_board = self.boards.get(note.board_id) if note.board_id else None
            note_window = NoteWindow(note, self, parent_board=parent_board)
            self._wire_note(note_window)

        if not notes and not boards:
            self.create_note()

    def _wire_note(self, note_window: NoteWindow):
        self.notes[note_window.note.id] = note_window
        note_window.changed.connect(self._schedule_save)

    def _wire_board(self, board_window: MemoboardWindow):
        self.boards[board_window.board.id] = board_window
        board_window.changed.connect(self._schedule_save)

    # -- notes -----------------------------------------------------------

    def create_note(self, board: MemoboardWindow | None = None, pos: QPoint | None = None) -> NoteWindow:
        note = Note()
        if board is not None:
            note.board_id = board.board.id
            note.x, note.y = (pos.x(), pos.y()) if pos is not None else (20, 20)

        note_window = NoteWindow(note, self, parent_board=board)
        self._wire_note(note_window)
        self._schedule_save()
        return note_window

    def delete_note(self, note_window: NoteWindow):
        self.notes.pop(note_window.note.id, None)
        note_window.setParent(None)
        note_window.deleteLater()
        self._schedule_save()

    # -- boards ----------------------------------------------------------

    def create_board(self, name: str = "Memoboard") -> MemoboardWindow:
        board = Board(name=name)
        board_window = MemoboardWindow(board, self)
        self._wire_board(board_window)
        self._schedule_save()
        return board_window

    def create_board_and_attach(self, note_window: NoteWindow):
        board_window = self.create_board()
        self.attach_note_to_board(note_window, board_window)

    def attach_note_to_board(self, note_window: NoteWindow, board_window: MemoboardWindow):
        note_window.attach_to_board(board_window, pos=QPoint(20, 20))
        self._schedule_save()

    def detach_note_from_board(self, note_window: NoteWindow):
        board_window = self.boards.get(note_window.note.board_id)
        pos = board_window.pos() + QPoint(30, 30) if board_window is not None else None
        note_window.attach_to_board(None, pos=pos)
        self._schedule_save()

    def delete_board(self, board_window: MemoboardWindow):
        board_id = board_window.board.id
        offset = 0
        for note_window in list(self.notes.values()):
            if note_window.note.board_id == board_id:
                pos = board_window.pos() + QPoint(20 + offset, 20 + offset)
                note_window.attach_to_board(None, pos=pos)
                offset += CASCADE_OFFSET
        self.boards.pop(board_id, None)
        board_window.deleteLater()
        self._schedule_save()

    # -- persistence -------------------------------------------------------

    def _schedule_save(self):
        self._save_timer.start()

    def _save_now(self):
        notes = [nw.sync_model() for nw in self.notes.values()]
        boards = [bw.sync_model() for bw in self.boards.values()]
        storage.save_all(notes, boards)

    # -- lifecycle ---------------------------------------------------------

    def _on_hotkey_failed(self):
        logger.warning("Global hotkey could not be registered (combo may already be in use)")

    def _on_about_to_quit(self):
        self.hotkey.stop()
        self._save_timer.stop()
        self._save_now()

    def quit(self):
        self.app.quit()
