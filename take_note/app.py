from __future__ import annotations

import logging
import random
from datetime import datetime, timezone

from PySide6.QtCore import QObject, QPoint, QTimer, Signal
from PySide6.QtWidgets import QApplication

from . import autostart, storage
from .board_window import NotepadWindow
from .hotkey import HotkeyListener, parse_shortcut
from .models import SWATCHES, Board, Note, Settings
from .note_window import NoteWindow
from .notes_manager import NotesManagerWindow
from .settings_dialog import SettingsDialog
from .tray import TrayIcon

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

SAVE_DEBOUNCE_MS = 800
CASCADE_OFFSET = 24


class NoteManager(QObject):
    """Owns every open Note/Notepad window, the tray icon, the global
    hotkey, and the single debounced save timer that writes all of them to
    disk as one JSON file."""

    # Piggybacks on every existing _schedule_save() call site (create/delete
    # note or board, attach/detach, and any note/board's own `changed`
    # signal) so the Notes Manager can stay live without new call sites.
    notes_changed = Signal()

    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app
        self.notes: dict[str, NoteWindow] = {}
        self.boards: dict[str, NotepadWindow] = {}
        self.notes_manager: "NotesManagerWindow | None" = None
        # Cascades each new standalone note CASCADE_OFFSET further from the
        # last, so creating several in a row doesn't stack them exactly on
        # top of each other (confusing — no visible sign a new note even
        # appeared). Wraps back to 0 after a few steps rather than
        # drifting the notes off-screen forever. Not persisted to disk —
        # load_from_disk() (below) reseeds it from the loaded note count
        # instead, cheap enough to redo on every launch and avoids the
        # very first post-relaunch note landing exactly on top of an old
        # one sitting at the fixed (100, 100) default (confirmed live).
        self._new_note_cascade_offset = 0

        # Settings must be known before the hotkey listener is created, so
        # read them here; load_from_disk() re-reads (along with notes/boards)
        # shortly after, keeping self.settings as the single source of truth.
        _, _, self.settings = storage.load_all()

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(SAVE_DEBOUNCE_MS)
        self._save_timer.timeout.connect(self._save_now)

        self.tray = TrayIcon(self)
        self.tray.show()

        self.hotkey: HotkeyListener | None = None
        self._start_hotkey_listener()
        self.notes_manager_hotkey: HotkeyListener | None = None
        self._start_notes_manager_hotkey_listener()
        self.show_hide_all_notes_hotkey: HotkeyListener | None = None
        self._start_show_hide_all_notes_hotkey_listener()
        self.roll_all_notes_hotkey: HotkeyListener | None = None
        self._start_roll_all_notes_hotkey_listener()
        self.bring_all_notes_to_front_hotkey: HotkeyListener | None = None
        self._start_bring_all_notes_to_front_hotkey_listener()

        self.app.setQuitOnLastWindowClosed(False)
        self.app.aboutToQuit.connect(self._on_about_to_quit)

    # -- startup -------------------------------------------------------

    def load_from_disk(self):
        notes, boards, settings = storage.load_all()
        self.settings = settings

        # Boards first so each note's board canvas already exists by the
        # time a note with a board_id needs to be parented into it.
        for board in boards:
            board_window = NotepadWindow(board, self)
            self._wire_board(board_window)

        for note in notes:
            parent_board = self.boards.get(note.board_id) if note.board_id else None
            note_window = NoteWindow(note, self, parent_board=parent_board)
            self._wire_note(note_window)

        if not notes and not boards:
            self.create_note()
        else:
            # Reported live: relaunching the app resets the cascade
            # counter to 0, so the very first standalone note created
            # after a relaunch lands at the exact same fixed (100, 100)
            # default as the very first note of any session — landing
            # right on top of whatever old note is already sitting there,
            # reading as "not staggered" even though the mechanism itself
            # works fine within a session. Seeding from how many
            # standalone notes are already loaded means a relaunch
            # continues roughly where the cascade left off instead of
            # restarting from scratch.
            standalone_count = sum(1 for note in notes if note.board_id is None)
            self._new_note_cascade_offset = (standalone_count * CASCADE_OFFSET) % (
                CASCADE_OFFSET * 10
            )

    def _wire_note(self, note_window: NoteWindow):
        self.notes[note_window.note.id] = note_window
        note_window.changed.connect(self._schedule_save)

    def _wire_board(self, board_window: NotepadWindow):
        self.boards[board_window.board.id] = board_window
        board_window.changed.connect(self._schedule_save)

    # -- notes -----------------------------------------------------------

    def create_note(self, board: NotepadWindow | None = None, pos: QPoint | None = None) -> NoteWindow:
        color = (
            random.choice(SWATCHES)
            if self.settings.randomize_new_note_color
            else self.settings.default_color
        )
        note = Note(
            color=color,
            always_on_top=self.settings.default_always_on_top,
            w=self.settings.default_note_w,
            h=self.settings.default_note_h,
        )
        if board is not None:
            note.board_id = board.board.id
            note.x, note.y = (pos.x(), pos.y()) if pos is not None else (20, 20)
        else:
            # A board-attached note already gets a real position above (the
            # actual right-click point, or a fixed (20, 20) default) — this
            # only staggers the standalone-desktop-note path, which
            # otherwise always used the same fixed default position.
            note.x += self._new_note_cascade_offset
            note.y += self._new_note_cascade_offset
            self._new_note_cascade_offset = (self._new_note_cascade_offset + CASCADE_OFFSET) % (
                CASCADE_OFFSET * 10
            )

        note_window = NoteWindow(note, self, parent_board=board)
        self._wire_note(note_window)
        self._schedule_save()
        return note_window

    def delete_note(self, note_window: NoteWindow):
        note_window._clear_window_watcher()
        self.notes.pop(note_window.note.id, None)
        note_window.setParent(None)
        note_window.deleteLater()
        self._schedule_save()

    def trash_note(self, note_window: NoteWindow):
        """Soft delete — the note stays in self.notes/notes.json (so
        Restore and the Notes Manager's Trash view both work without a
        separate data path) but hidden, same mechanism as the existing
        session-only "Hide Note" except deleted_at makes it persist
        across restarts. Deliberately doesn't touch board_id, unlike
        permanent delete_note() (which doesn't need to, since the whole
        Note is gone either way) — see Note.deleted_at's own docstring
        for why that's what makes Restore board-aware."""
        note_window.note.deleted_at = _now_iso()
        note_window.hide()
        self._schedule_save()

    def restore_note(self, note_window: NoteWindow):
        note_window.note.deleted_at = None
        note_window.show()
        self._schedule_save()

    # -- bulk note actions (tray menu) ------------------------------------

    def show_all_notes(self):
        for note_window in self.notes.values():
            note_window.show()

    def hide_all_notes(self):
        # Deliberately not persisted (no Note field for it) — this is a
        # quick, session-only declutter, not a state a note should still
        # be in unexpectedly after the next restart.
        for note_window in self.notes.values():
            note_window.hide()

    def toggle_show_all_notes(self):
        """Shows every note if any are currently hidden, otherwise hides
        them all — one consistent end state for the whole batch, same
        convergent-toggle pattern as toggle_roll_all_notes, so the tray
        only needs one menu item instead of two always-visible ones."""
        if any(not nw.isVisible() for nw in self.notes.values()):
            self.show_all_notes()
        else:
            self.hide_all_notes()

    def bring_all_notes_to_front(self):
        for note_window in self.notes.values():
            note_window.raise_()

    def toggle_roll_all_notes(self):
        """Rolls every note up if any are currently expanded, otherwise
        expands them all — one consistent end state for the whole batch,
        rather than flipping each note's own individual state independently
        (which would leave them just as mixed as before, only swapped)."""
        any_expanded = any(not nw.note.rolled_up for nw in self.notes.values())
        for note_window in self.notes.values():
            note_window.set_rolled(any_expanded)

    # -- boards ----------------------------------------------------------

    def create_board(self, name: str = "Notepad") -> NotepadWindow:
        board = Board(name=name, w=self.settings.default_notepad_w, h=self.settings.default_notepad_h)
        board_window = NotepadWindow(board, self)
        self._wire_board(board_window)
        self._schedule_save()
        return board_window

    def create_board_and_attach(self, note_window: NoteWindow):
        board_window = self.create_board()
        self.attach_note_to_board(note_window, board_window)

    def attach_note_to_board(self, note_window: NoteWindow, board_window: NotepadWindow):
        note_window.attach_to_board(board_window, pos=QPoint(20, 20))
        self._schedule_save()

    def detach_note_from_board(self, note_window: NoteWindow):
        board_window = self.boards.get(note_window.note.board_id)
        pos = board_window.pos() + QPoint(30, 30) if board_window is not None else None
        note_window.attach_to_board(None, pos=pos)
        self._schedule_save()

    def delete_board(self, board_window: NotepadWindow):
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

    # -- notes manager -----------------------------------------------------

    def open_notes_manager(self):
        if self.notes_manager is None:
            self.notes_manager = NotesManagerWindow(self)
        else:
            self.notes_manager.show()
            self.notes_manager.raise_()
            self.notes_manager.activateWindow()

    # -- settings ------------------------------------------------------

    def open_settings(self):
        # Reflect the real filesystem state rather than trusting a
        # persisted flag that could drift if the autostart file was added
        # or removed outside the app.
        self.settings.launch_at_login = autostart.is_enabled()

        dialog = SettingsDialog(self.settings)
        # Apply live-applies without closing the dialog; OK still goes
        # through the same _apply_settings() after exec() returns, so
        # clicking Apply once and then OK just re-applies identically
        # unchanged settings rather than double-applying anything.
        dialog.applied.connect(self._apply_settings)
        if dialog.exec():
            self._apply_settings(dialog.result_settings())
        else:
            # Cancelled — no setting change to apply, but the dialog's
            # own moveEvent/resizeEvent already wrote its latest geometry
            # directly into self.settings (same object, passed by
            # reference), so it still needs a save to actually reach
            # disk, matching the fact that window position isn't a
            # "setting" the user is choosing to discard by cancelling.
            self._schedule_save()

    def _apply_settings(self, new_settings: Settings):
        hotkey_changed = new_settings.hotkey != self.settings.hotkey
        notes_manager_hotkey_changed = (
            new_settings.notes_browser_hotkey != self.settings.notes_browser_hotkey
        )
        show_hide_all_notes_hotkey_changed = (
            new_settings.show_hide_all_notes_hotkey != self.settings.show_hide_all_notes_hotkey
        )
        roll_all_notes_hotkey_changed = (
            new_settings.roll_all_notes_hotkey != self.settings.roll_all_notes_hotkey
        )
        bring_all_notes_to_front_hotkey_changed = (
            new_settings.bring_all_notes_to_front_hotkey
            != self.settings.bring_all_notes_to_front_hotkey
        )
        spell_check_changed = new_settings.spell_check_enabled != self.settings.spell_check_enabled
        self.settings = new_settings

        if new_settings.launch_at_login:
            autostart.enable()
        else:
            autostart.disable()

        if hotkey_changed:
            self._restart_hotkey_listener()

        if notes_manager_hotkey_changed:
            self._restart_notes_manager_hotkey_listener()

        if show_hide_all_notes_hotkey_changed:
            self._restart_show_hide_all_notes_hotkey_listener()

        if roll_all_notes_hotkey_changed:
            self._restart_roll_all_notes_hotkey_listener()

        if bring_all_notes_to_front_hotkey_changed:
            self._restart_bring_all_notes_to_front_hotkey_listener()

        if spell_check_changed:
            for note_window in self.notes.values():
                if new_settings.spell_check_enabled:
                    note_window._attach_spell_highlighter()
                else:
                    note_window._detach_spell_highlighter()

        self._schedule_save()

    def _start_hotkey_listener(self):
        # Settings.hotkey is None once a user explicitly clears it via
        # the Clear button in Settings — leave self.hotkey None too
        # rather than grabbing a combo nobody asked for.
        if not self.settings.hotkey:
            self.hotkey = None
            return
        key, modifiers = parse_shortcut(self.settings.hotkey)
        self.hotkey = HotkeyListener(key, modifiers)
        self.hotkey.triggered.connect(lambda: self.create_note())
        self.hotkey.grab_failed.connect(lambda: self._on_hotkey_failed("new-note"))
        self.hotkey.start()

    def _restart_hotkey_listener(self):
        if self.hotkey is not None:
            self.hotkey.stop()
        self._start_hotkey_listener()

    def _start_notes_manager_hotkey_listener(self):
        if not self.settings.notes_browser_hotkey:
            self.notes_manager_hotkey = None
            return
        key, modifiers = parse_shortcut(self.settings.notes_browser_hotkey)
        self.notes_manager_hotkey = HotkeyListener(key, modifiers)
        self.notes_manager_hotkey.triggered.connect(lambda: self.open_notes_manager())
        self.notes_manager_hotkey.grab_failed.connect(lambda: self._on_hotkey_failed("Notes Manager"))
        self.notes_manager_hotkey.start()

    def _restart_notes_manager_hotkey_listener(self):
        if self.notes_manager_hotkey is not None:
            self.notes_manager_hotkey.stop()
        self._start_notes_manager_hotkey_listener()

    def _start_show_hide_all_notes_hotkey_listener(self):
        if not self.settings.show_hide_all_notes_hotkey:
            self.show_hide_all_notes_hotkey = None
            return
        key, modifiers = parse_shortcut(self.settings.show_hide_all_notes_hotkey)
        self.show_hide_all_notes_hotkey = HotkeyListener(key, modifiers)
        self.show_hide_all_notes_hotkey.triggered.connect(lambda: self.toggle_show_all_notes())
        self.show_hide_all_notes_hotkey.grab_failed.connect(
            lambda: self._on_hotkey_failed("Show/Hide All Notes")
        )
        self.show_hide_all_notes_hotkey.start()

    def _restart_show_hide_all_notes_hotkey_listener(self):
        if self.show_hide_all_notes_hotkey is not None:
            self.show_hide_all_notes_hotkey.stop()
        self._start_show_hide_all_notes_hotkey_listener()

    def _start_roll_all_notes_hotkey_listener(self):
        if not self.settings.roll_all_notes_hotkey:
            self.roll_all_notes_hotkey = None
            return
        key, modifiers = parse_shortcut(self.settings.roll_all_notes_hotkey)
        self.roll_all_notes_hotkey = HotkeyListener(key, modifiers)
        self.roll_all_notes_hotkey.triggered.connect(lambda: self.toggle_roll_all_notes())
        self.roll_all_notes_hotkey.grab_failed.connect(
            lambda: self._on_hotkey_failed("Roll Up/Down Notes")
        )
        self.roll_all_notes_hotkey.start()

    def _restart_roll_all_notes_hotkey_listener(self):
        if self.roll_all_notes_hotkey is not None:
            self.roll_all_notes_hotkey.stop()
        self._start_roll_all_notes_hotkey_listener()

    def _start_bring_all_notes_to_front_hotkey_listener(self):
        if not self.settings.bring_all_notes_to_front_hotkey:
            self.bring_all_notes_to_front_hotkey = None
            return
        key, modifiers = parse_shortcut(self.settings.bring_all_notes_to_front_hotkey)
        self.bring_all_notes_to_front_hotkey = HotkeyListener(key, modifiers)
        self.bring_all_notes_to_front_hotkey.triggered.connect(
            lambda: self.bring_all_notes_to_front()
        )
        self.bring_all_notes_to_front_hotkey.grab_failed.connect(
            lambda: self._on_hotkey_failed("Bring Notes on Top")
        )
        self.bring_all_notes_to_front_hotkey.start()

    def _restart_bring_all_notes_to_front_hotkey_listener(self):
        if self.bring_all_notes_to_front_hotkey is not None:
            self.bring_all_notes_to_front_hotkey.stop()
        self._start_bring_all_notes_to_front_hotkey_listener()

    # -- persistence -------------------------------------------------------

    def _schedule_save(self):
        self._save_timer.start()
        self.notes_changed.emit()

    def _save_now(self):
        notes = [nw.sync_model() for nw in self.notes.values()]
        boards = [bw.sync_model() for bw in self.boards.values()]
        storage.save_all(notes, boards, self.settings)

    # -- lifecycle ---------------------------------------------------------

    def _on_hotkey_failed(self, name: str):
        logger.warning("%s hotkey could not be registered (combo may already be in use)", name)

    def _on_about_to_quit(self):
        if self.hotkey is not None:
            self.hotkey.stop()
        if self.notes_manager_hotkey is not None:
            self.notes_manager_hotkey.stop()
        if self.show_hide_all_notes_hotkey is not None:
            self.show_hide_all_notes_hotkey.stop()
        if self.roll_all_notes_hotkey is not None:
            self.roll_all_notes_hotkey.stop()
        if self.bring_all_notes_to_front_hotkey is not None:
            self.bring_all_notes_to_front_hotkey.stop()
        for note_window in self.notes.values():
            note_window._clear_window_watcher()
        self._save_timer.stop()
        self._save_now()

    def quit(self):
        self.app.quit()
