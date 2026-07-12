from __future__ import annotations

from unittest.mock import Mock

from take_note import app as app_module
from take_note.app import NoteManager
from take_note.models import SWATCHES, Note, Settings


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


def test_toggle_show_all_notes_hides_when_all_visible():
    """Regression: a bulk toggle must converge every note to one
    consistent end state, matching toggle_roll_all_notes's pattern —
    replaces two always-visible tray items (Show All/Hide All Notes)
    with one toggling item. toggle_show_all_notes delegates to the
    existing show_all_notes/hide_all_notes (each already covered by its
    own test above), so this only needs to check which one gets called —
    it can't call the *real* show_all_notes/hide_all_notes through a bare
    Mock `self`, since those are themselves mocked-away attributes here."""
    manager = _fake_manager([False, False])
    for note_window in manager.notes.values():
        note_window.isVisible.return_value = True

    NoteManager.toggle_show_all_notes(manager)

    manager.hide_all_notes.assert_called_once()
    manager.show_all_notes.assert_not_called()


def test_toggle_show_all_notes_shows_when_any_hidden():
    manager = _fake_manager([False, False])
    visibilities = [True, False]
    for note_window, visible in zip(manager.notes.values(), visibilities):
        note_window.isVisible.return_value = visible

    NoteManager.toggle_show_all_notes(manager)

    manager.show_all_notes.assert_called_once()
    manager.hide_all_notes.assert_not_called()


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


def test_schedule_save_emits_notes_changed():
    """The Notes Browser stays live by listening for this signal — it
    must fire on every existing _schedule_save() call site (create/delete
    note or board, attach/detach, any note/board's own `changed` signal)
    without those call sites needing to know about it individually."""
    manager = Mock()
    manager._save_timer = Mock()
    manager.notes_changed = Mock()

    NoteManager._schedule_save(manager)

    manager._save_timer.start.assert_called_once()
    manager.notes_changed.emit.assert_called_once()


def _fake_manager_for_create_note(settings) -> Mock:
    manager = Mock()
    manager.notes = {}
    manager.boards = {}
    manager.settings = settings
    manager._new_note_cascade_offset = 0
    return manager


def test_create_note_uses_default_color_when_not_randomizing(qapp):
    settings = Settings(default_color="#a5d6a7", randomize_new_note_color=False)
    manager = _fake_manager_for_create_note(settings)

    note_window = NoteManager.create_note(manager)

    assert note_window.note.color == "#a5d6a7"


def test_create_note_uses_random_color_when_randomizing(qapp, monkeypatch):
    monkeypatch.setattr(app_module.random, "choice", lambda seq: seq[3])
    settings = Settings(default_color="#a5d6a7", randomize_new_note_color=True)
    manager = _fake_manager_for_create_note(settings)

    note_window = NoteManager.create_note(manager)

    assert note_window.note.color == SWATCHES[3]
    assert note_window.note.color != "#a5d6a7"


def test_create_note_staggers_each_standalone_note_from_the_last(qapp):
    """Regression: every new standalone note used to appear at the exact
    same fixed default position, giving no visible sign a new note was
    even created."""
    manager = _fake_manager_for_create_note(Settings())
    default_x, default_y = Note().x, Note().y

    first = NoteManager.create_note(manager)
    second = NoteManager.create_note(manager)
    third = NoteManager.create_note(manager)

    assert (first.note.x, first.note.y) == (default_x, default_y)
    assert (second.note.x, second.note.y) == (default_x + 24, default_y + 24)
    assert (third.note.x, third.note.y) == (default_x + 48, default_y + 48)


def test_create_note_cascade_wraps_around_instead_of_drifting_forever(qapp):
    manager = _fake_manager_for_create_note(Settings())
    manager._new_note_cascade_offset = app_module.CASCADE_OFFSET * 9

    NoteManager.create_note(manager)

    assert manager._new_note_cascade_offset == 0


def test_create_note_on_a_board_does_not_apply_the_cascade_offset(qapp):
    """A board-attached note already gets a real position (the actual
    right-click point or a fixed (20, 20) default) via a separate code
    path — the cascade is only for the standalone-desktop-note case."""
    from take_note.board_window import NotepadWindow
    from take_note.models import Board

    manager = _fake_manager_for_create_note(Settings())
    manager._new_note_cascade_offset = 24
    board_window = NotepadWindow(Board(), manager)

    note_window = NoteManager.create_note(manager, board=board_window)

    assert (note_window.note.x, note_window.note.y) == (20, 20)
    assert manager._new_note_cascade_offset == 24  # unchanged


def test_load_from_disk_seeds_cascade_offset_from_standalone_note_count(qapp, monkeypatch):
    """Regression, reported live: the cascade offset always started at 0
    on every launch, so the very first standalone note created right
    after a relaunch landed at the exact same fixed default position
    (100, 100) as whatever old note was already sitting there -- reading
    as "staggering doesn't work" even though it works fine for notes
    created within the same session. Seeding from how many standalone
    notes are already on disk means a relaunch picks the cascade back up
    roughly where it left off, board-attached notes excluded since they
    don't use this offset at all (see
    test_create_note_on_a_board_does_not_apply_the_cascade_offset)."""
    from take_note.models import Board

    notes = [Note(), Note(), Note(board_id="b1")]
    boards = [Board(id="b1")]
    settings = Settings()
    monkeypatch.setattr(app_module.storage, "load_all", lambda: (notes, boards, settings))
    manager = _fake_manager_for_create_note(settings)

    NoteManager.load_from_disk(manager)

    assert manager._new_note_cascade_offset == app_module.CASCADE_OFFSET * 2


def _fake_manager_for_apply_settings(settings) -> Mock:
    manager = Mock()
    manager.settings = settings
    manager.notes = {"1": Mock()}
    return manager


def test_apply_settings_attaches_spell_highlighter_when_turned_on(monkeypatch):
    monkeypatch.setattr(app_module.autostart, "enable", Mock())
    monkeypatch.setattr(app_module.autostart, "disable", Mock())
    manager = _fake_manager_for_apply_settings(Settings(spell_check_enabled=False))
    note_window = manager.notes["1"]

    NoteManager._apply_settings(manager, Settings(spell_check_enabled=True))

    note_window._attach_spell_highlighter.assert_called_once()
    note_window._detach_spell_highlighter.assert_not_called()


def test_apply_settings_detaches_spell_highlighter_when_turned_off(monkeypatch):
    monkeypatch.setattr(app_module.autostart, "enable", Mock())
    monkeypatch.setattr(app_module.autostart, "disable", Mock())
    manager = _fake_manager_for_apply_settings(Settings(spell_check_enabled=True))
    note_window = manager.notes["1"]

    NoteManager._apply_settings(manager, Settings(spell_check_enabled=False))

    note_window._detach_spell_highlighter.assert_called_once()
    note_window._attach_spell_highlighter.assert_not_called()


def test_apply_settings_leaves_highlighters_alone_when_unchanged(monkeypatch):
    monkeypatch.setattr(app_module.autostart, "enable", Mock())
    monkeypatch.setattr(app_module.autostart, "disable", Mock())
    manager = _fake_manager_for_apply_settings(Settings(spell_check_enabled=True))
    note_window = manager.notes["1"]

    NoteManager._apply_settings(manager, Settings(spell_check_enabled=True))

    note_window._attach_spell_highlighter.assert_not_called()
    note_window._detach_spell_highlighter.assert_not_called()
