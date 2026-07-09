from __future__ import annotations

from unittest.mock import Mock

from take_note.app import NoteManager
from take_note.models import Note


def _fake_manager(rolled_states):
    """A bare stand-in for NoteManager's `notes` dict, not the real class —
    constructing a real NoteManager crashes under the offscreen QPA
    platform (its TrayIcon/HotkeyListener setup assumes a real display), so
    these bulk-action methods are called directly (unbound) against a
    lightweight double instead."""
    manager = Mock()
    manager.notes = {}
    for i, rolled in enumerate(rolled_states):
        note_window = Mock()
        note_window.note = Note(rolled_up=rolled)
        manager.notes[str(i)] = note_window
    return manager


def test_show_all_notes_shows_every_note():
    manager = _fake_manager([False, False])

    NoteManager.show_all_notes(manager)

    for note_window in manager.notes.values():
        note_window.show.assert_called_once()


def test_hide_all_notes_hides_every_note():
    manager = _fake_manager([False, False])

    NoteManager.hide_all_notes(manager)

    for note_window in manager.notes.values():
        note_window.hide.assert_called_once()


def test_bring_all_notes_to_front_raises_every_note():
    manager = _fake_manager([False, False])

    NoteManager.bring_all_notes_to_front(manager)

    for note_window in manager.notes.values():
        note_window.raise_.assert_called_once()


def test_toggle_roll_all_notes_rolls_up_when_any_expanded():
    """Regression: a bulk toggle must converge every note to one consistent
    end state, not flip each note's own individual state independently
    (which would leave a mixed batch just as mixed, only swapped)."""
    manager = _fake_manager([True, False])

    NoteManager.toggle_roll_all_notes(manager)

    for note_window in manager.notes.values():
        note_window.set_rolled.assert_called_once_with(True)


def test_toggle_roll_all_notes_expands_when_all_already_rolled():
    manager = _fake_manager([True, True])

    NoteManager.toggle_roll_all_notes(manager)

    for note_window in manager.notes.values():
        note_window.set_rolled.assert_called_once_with(False)


def test_toggle_roll_all_notes_rolls_up_when_all_expanded():
    manager = _fake_manager([False, False])

    NoteManager.toggle_roll_all_notes(manager)

    for note_window in manager.notes.values():
        note_window.set_rolled.assert_called_once_with(True)


def test_delete_note_clears_its_window_watcher():
    """A note stuck to another window (see window_watch.WindowWatcher)
    must have that watcher thread stopped on delete, or it leaks."""
    manager = _fake_manager([False])
    note_window = next(iter(manager.notes.values()))

    NoteManager.delete_note(manager, note_window)

    note_window._clear_window_watcher.assert_called_once()


def test_on_about_to_quit_clears_every_notes_window_watcher():
    manager = _fake_manager([False, True])
    manager.hotkey = None

    NoteManager._on_about_to_quit(manager)

    for note_window in manager.notes.values():
        note_window._clear_window_watcher.assert_called_once()
