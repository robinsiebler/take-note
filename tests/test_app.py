from __future__ import annotations

from datetime import datetime, timedelta, timezone
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


def test_trash_note_sets_deleted_at_hides_and_schedules_save():
    manager = Mock()
    note_window = Mock()
    note_window.note = Note()

    NoteManager.trash_note(manager, note_window)

    assert note_window.note.deleted_at is not None
    note_window.hide.assert_called_once()
    manager._schedule_save.assert_called_once()


def test_trash_note_does_not_touch_board_id():
    """The whole point of keeping board_id alone on trash (see
    Note.deleted_at's own docstring) — a board-attached note stays
    attached in the data model while trashed, so Restore puts it right
    back without needing to remember where it came from separately."""
    manager = Mock()
    note_window = Mock()
    note_window.note = Note(board_id="board-1")

    NoteManager.trash_note(manager, note_window)

    assert note_window.note.board_id == "board-1"


def test_restore_note_clears_deleted_at_shows_and_schedules_save():
    manager = Mock()
    note_window = Mock()
    note_window.note = Note(deleted_at="2026-01-01T00:00:00+00:00")

    NoteManager.restore_note(manager, note_window)

    assert note_window.note.deleted_at is None
    note_window.show.assert_called_once()
    manager._schedule_save.assert_called_once()


def test_bring_all_notes_to_front_raises_every_note():
    manager = _fake_manager([False, False])

    NoteManager.bring_all_notes_to_front(manager)

    for note_window in manager.notes.values():
        note_window.raise_.assert_called_once()


def test_check_reminders_fires_a_due_note():
    manager = _fake_manager([False])
    note_window = next(iter(manager.notes.values()))
    note_window.note.reminder_at = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    # _check_reminders() calls self._fire_reminder(...) internally — on a
    # bare Mock that would just hit an auto-generated stub instead of the
    # real method, so bind the real implementation through explicitly
    # (same pattern already used for _restart_notes_manager_hotkey_listener
    # above).
    manager._fire_reminder = lambda nw: NoteManager._fire_reminder(manager, nw)

    NoteManager._check_reminders(manager)

    assert note_window.note.reminder_at is None
    note_window.header.update_reminder_indicator.assert_called_once_with(None)
    note_window.set_rolled.assert_called_once_with(False)
    note_window.showNormal.assert_called_once()
    note_window.raise_.assert_called_once()
    note_window.activateWindow.assert_called_once()
    manager._schedule_save.assert_called_once()


def test_fire_reminder_flashes_above_when_not_always_on_top(qapp, monkeypatch):
    """Confirmed live: showNormal()/raise_()/activateWindow() alone are
    silently denied by KWin's focus-stealing prevention when triggered from
    this background timer rather than a direct user click, leaving a note
    that's actually hidden behind other windows invisible (notes always
    skip_taskbar, so there's no fallback either). Forcing the EWMH "above"
    state is a stacking-order change, not a focus/activation request, so it
    isn't subject to the same restriction — same mechanism the real
    Always-on-Top toggle already uses. Reverted after a flash so a note the
    user didn't mark Always-on-Top doesn't stay pinned above everything."""
    manager = _fake_manager([False])
    note_window = next(iter(manager.notes.values()))
    note_window.note.always_on_top = False
    note_window.winId.return_value = 4242
    stays_on_top_calls = []
    monkeypatch.setattr(
        app_module,
        "set_stays_on_top",
        lambda win_id, enabled: stays_on_top_calls.append((win_id, enabled)),
    )
    monkeypatch.setattr(app_module.QTimer, "singleShot", lambda ms, cb: cb())

    NoteManager._fire_reminder(manager, note_window)

    assert stays_on_top_calls == [(4242, True), (4242, False)]


def test_fire_reminder_does_not_flash_when_already_always_on_top():
    """Note() defaults to always_on_top=True — already above everything,
    nothing to force."""
    manager = _fake_manager([False])
    note_window = next(iter(manager.notes.values()))

    NoteManager._fire_reminder(manager, note_window)

    note_window.winId.assert_not_called()


def test_fire_reminder_does_not_flash_for_board_attached_note():
    """A board-attached note is a plain child widget with no top-level
    window/WM state of its own — its raise_() above already reorders it
    within the board canvas, no EWMH call needed or possible."""
    manager = _fake_manager([False])
    note_window = next(iter(manager.notes.values()))
    note_window.note.always_on_top = False
    note_window.note.board_id = "board-1"

    NoteManager._fire_reminder(manager, note_window)

    note_window.winId.assert_not_called()


def test_check_reminders_leaves_a_not_yet_due_note_alone():
    manager = _fake_manager([False])
    note_window = next(iter(manager.notes.values()))
    future_iso = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    note_window.note.reminder_at = future_iso

    NoteManager._check_reminders(manager)

    assert note_window.note.reminder_at == future_iso
    note_window.showNormal.assert_not_called()
    manager._schedule_save.assert_not_called()


def test_check_reminders_skips_a_trashed_note():
    """A trashed note stays hidden regardless — popping it up when its
    reminder comes due would be a surprising, implicit "un-trash". Not
    re-armed later just because the note gets restored either (the
    reminder is simply gone, not rescheduled)."""
    manager = _fake_manager([False])
    note_window = next(iter(manager.notes.values()))
    note_window.note.reminder_at = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    note_window.note.deleted_at = "2026-01-01T00:00:00+00:00"

    NoteManager._check_reminders(manager)

    assert note_window.note.reminder_at is not None
    note_window.showNormal.assert_not_called()
    manager._schedule_save.assert_not_called()



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
    """The Notes Manager stays live by listening for this signal — it
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


def test_create_note_uses_the_configured_default_size(qapp):
    settings = Settings(default_note_w=400, default_note_h=500)
    manager = _fake_manager_for_create_note(settings)

    note_window = NoteManager.create_note(manager)

    assert (note_window.note.w, note_window.note.h) == (400, 500)


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


def test_create_board_uses_the_configured_default_size(qapp):
    settings = Settings(default_notepad_w=800, default_notepad_h=600)
    manager = _fake_manager_for_create_note(settings)
    manager.boards = {}

    board_window = NoteManager.create_board(manager)

    assert (board_window.board.w, board_window.board.h) == (800, 600)


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


def test_load_from_disk_checks_reminders_once_after_loading(qapp, monkeypatch):
    """Must run after every NoteWindow is constructed and wired, not
    during __init__ (too early, no note windows exist yet) — catches a
    reminder that came due while the app was closed, per explicit user
    call. Reuses _check_reminders() rather than separate catch-up logic,
    so "missed while closed" and "came due while running" share one code
    path — asserted here as an orchestration/wiring check (same style as
    the cascade-offset test above), not a full end-to-end reminder fire,
    since this harness's Mock manager means _wire_note()/_check_reminders
    itself never really runs against manager.notes."""
    notes = [Note()]
    settings = Settings()
    monkeypatch.setattr(app_module.storage, "load_all", lambda: (notes, [], settings))
    manager = _fake_manager_for_create_note(settings)

    NoteManager.load_from_disk(manager)

    manager._check_reminders.assert_called_once()


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


class _FakeSettingsDialog:
    """Stands in for the real SettingsDialog — a real QDialog.exec() blocks
    on a modal event loop, which a plain unit test has no way to satisfy
    from the same thread. instances records every one constructed so a
    test can assert exactly one (or none) got created."""

    instances: list["_FakeSettingsDialog"] = []

    def __init__(self, settings):
        self.settings = settings
        self.applied = Mock()
        self.raise_ = Mock()
        self.activateWindow = Mock()
        self.exec_return = 0
        _FakeSettingsDialog.instances.append(self)

    def exec(self):
        return self.exec_return

    def result_settings(self):
        return self.settings


def test_open_settings_reuses_the_existing_dialog_if_already_open(monkeypatch):
    """Regression, reported live: the tray's own context menu (a separate
    top-level popup managed by the desktop shell, not this app's window
    stack) stays reachable even while a modal SettingsDialog is already
    blocked on its own exec() — clicking Settings… again spawned a second
    independent dialog instead of just refocusing the first."""
    monkeypatch.setattr(app_module.autostart, "is_enabled", lambda: False)
    _FakeSettingsDialog.instances = []
    monkeypatch.setattr(app_module, "SettingsDialog", _FakeSettingsDialog)
    manager = Mock()
    manager.settings = Settings()
    existing = Mock()
    manager._settings_dialog = existing

    NoteManager.open_settings(manager)

    existing.raise_.assert_called_once()
    existing.activateWindow.assert_called_once()
    assert _FakeSettingsDialog.instances == []


def test_open_settings_clears_the_tracked_dialog_once_closed(monkeypatch):
    monkeypatch.setattr(app_module.autostart, "is_enabled", lambda: False)
    _FakeSettingsDialog.instances = []
    monkeypatch.setattr(app_module, "SettingsDialog", _FakeSettingsDialog)
    manager = Mock()
    manager.settings = Settings()
    manager._settings_dialog = None

    NoteManager.open_settings(manager)

    assert len(_FakeSettingsDialog.instances) == 1
    assert manager._settings_dialog is None


class _FakeHotkeyListener:
    """Stands in for the real HotkeyListener (a QThread that opens a real
    X11 connection and would hang/crash under the offscreen QPA platform,
    same reasoning _fake_manager's docstring above gives for not
    constructing a real NoteManager). Records every instance created so
    tests can inspect what key/modifiers it was built with and fire its
    `triggered` callback manually."""

    instances: list["_FakeHotkeyListener"] = []

    def __init__(self, key, modifiers):
        self.key = key
        self.modifiers = modifiers
        self.triggered = Mock()
        self.grab_failed = Mock()
        self.started = False
        _FakeHotkeyListener.instances.append(self)

    def start(self):
        self.started = True


def test_start_hotkey_listener_skips_grabbing_when_cleared(monkeypatch):
    """Settings.hotkey is None once explicitly cleared via Settings'
    Clear button — no listener should be created or started at all,
    not a grab for some fallback/empty combo."""
    _FakeHotkeyListener.instances = []
    monkeypatch.setattr(app_module, "HotkeyListener", _FakeHotkeyListener)
    manager = Mock()
    manager.settings = Settings(hotkey=None)

    NoteManager._start_hotkey_listener(manager)

    assert _FakeHotkeyListener.instances == []
    assert manager.hotkey is None


def test_start_notes_manager_hotkey_listener_skips_grabbing_when_cleared(monkeypatch):
    _FakeHotkeyListener.instances = []
    monkeypatch.setattr(app_module, "HotkeyListener", _FakeHotkeyListener)
    manager = Mock()
    manager.settings = Settings(notes_browser_hotkey=None)

    NoteManager._start_notes_manager_hotkey_listener(manager)

    assert _FakeHotkeyListener.instances == []
    assert manager.notes_manager_hotkey is None


def test_start_notes_manager_hotkey_listener_uses_the_configured_combo(monkeypatch):
    _FakeHotkeyListener.instances = []
    monkeypatch.setattr(app_module, "HotkeyListener", _FakeHotkeyListener)
    manager = Mock()
    manager.settings = Settings(notes_browser_hotkey="Meta+Alt+B")

    NoteManager._start_notes_manager_hotkey_listener(manager)

    listener = _FakeHotkeyListener.instances[0]
    assert (listener.key, listener.modifiers) == ("B", ("meta", "mod1"))
    assert listener.started
    assert manager.notes_manager_hotkey is listener


def test_open_notes_manager_restores_an_already_open_window():
    """Regression, reported live: minimizing the Notes Manager left no way
    to get it back — show() is a no-op on a window that's already
    "visible" to Qt, which a minimized window still is. showNormal()
    actually clears the minimized state."""
    manager = Mock()
    existing = Mock()
    manager.notes_manager = existing

    NoteManager.open_notes_manager(manager)

    existing.showNormal.assert_called_once()
    existing.raise_.assert_called_once()
    existing.activateWindow.assert_called_once()


def test_notes_manager_hotkey_triggered_opens_the_notes_manager(monkeypatch):
    _FakeHotkeyListener.instances = []
    monkeypatch.setattr(app_module, "HotkeyListener", _FakeHotkeyListener)
    manager = Mock()
    manager.settings = Settings(notes_browser_hotkey="Meta+Alt+B")

    NoteManager._start_notes_manager_hotkey_listener(manager)

    triggered_callback = _FakeHotkeyListener.instances[0].triggered.connect.call_args[0][0]
    triggered_callback()

    manager.open_notes_manager.assert_called_once()


def test_restart_notes_manager_hotkey_listener_stops_the_old_one(monkeypatch):
    _FakeHotkeyListener.instances = []
    monkeypatch.setattr(app_module, "HotkeyListener", _FakeHotkeyListener)
    manager = Mock()
    manager.settings = Settings(notes_browser_hotkey="Meta+Alt+B")
    # _restart...() calls self._start_notes_manager_hotkey_listener()
    # internally — on a bare Mock that would just hit an auto-generated
    # stub instead of the real method, so bind the real implementation
    # through explicitly (same reasoning as _fake_manager's docstring
    # above for why a real NoteManager isn't constructed here).
    manager._start_notes_manager_hotkey_listener = (
        lambda: NoteManager._start_notes_manager_hotkey_listener(manager)
    )
    old_listener = Mock()
    manager.notes_manager_hotkey = old_listener

    NoteManager._restart_notes_manager_hotkey_listener(manager)

    old_listener.stop.assert_called_once()
    assert manager.notes_manager_hotkey is _FakeHotkeyListener.instances[0]


def test_apply_settings_restarts_only_the_new_note_hotkey_when_only_it_changed(monkeypatch):
    monkeypatch.setattr(app_module.autostart, "enable", Mock())
    monkeypatch.setattr(app_module.autostart, "disable", Mock())
    manager = _fake_manager_for_apply_settings(
        Settings(hotkey="Meta+Alt+N", notes_browser_hotkey="Meta+Alt+B")
    )

    NoteManager._apply_settings(
        manager, Settings(hotkey="Meta+Alt+X", notes_browser_hotkey="Meta+Alt+B")
    )

    manager._restart_hotkey_listener.assert_called_once()
    manager._restart_notes_manager_hotkey_listener.assert_not_called()


def test_apply_settings_restarts_only_the_notes_manager_hotkey_when_only_it_changed(monkeypatch):
    monkeypatch.setattr(app_module.autostart, "enable", Mock())
    monkeypatch.setattr(app_module.autostart, "disable", Mock())
    manager = _fake_manager_for_apply_settings(
        Settings(hotkey="Meta+Alt+N", notes_browser_hotkey="Meta+Alt+B")
    )

    NoteManager._apply_settings(
        manager, Settings(hotkey="Meta+Alt+N", notes_browser_hotkey="Meta+Alt+X")
    )

    manager._restart_hotkey_listener.assert_not_called()
    manager._restart_notes_manager_hotkey_listener.assert_called_once()


def test_on_about_to_quit_stops_all_five_hotkey_listeners():
    manager = Mock()
    manager.notes = {}

    NoteManager._on_about_to_quit(manager)

    manager.hotkey.stop.assert_called_once()
    manager.notes_manager_hotkey.stop.assert_called_once()
    manager.show_hide_all_notes_hotkey.stop.assert_called_once()
    manager.roll_all_notes_hotkey.stop.assert_called_once()
    manager.bring_all_notes_to_front_hotkey.stop.assert_called_once()


def test_start_show_hide_all_notes_hotkey_listener_uses_the_configured_combo(monkeypatch):
    _FakeHotkeyListener.instances = []
    monkeypatch.setattr(app_module, "HotkeyListener", _FakeHotkeyListener)
    manager = Mock()
    manager.settings = Settings(show_hide_all_notes_hotkey="Meta+Alt+H")

    NoteManager._start_show_hide_all_notes_hotkey_listener(manager)

    listener = _FakeHotkeyListener.instances[0]
    assert (listener.key, listener.modifiers) == ("H", ("meta", "mod1"))
    assert listener.started
    assert manager.show_hide_all_notes_hotkey is listener


def test_show_hide_all_notes_hotkey_triggered_calls_toggle_show_all_notes(monkeypatch):
    _FakeHotkeyListener.instances = []
    monkeypatch.setattr(app_module, "HotkeyListener", _FakeHotkeyListener)
    manager = Mock()
    manager.settings = Settings(show_hide_all_notes_hotkey="Meta+Alt+H")

    NoteManager._start_show_hide_all_notes_hotkey_listener(manager)

    triggered_callback = _FakeHotkeyListener.instances[0].triggered.connect.call_args[0][0]
    triggered_callback()

    manager.toggle_show_all_notes.assert_called_once()


def test_restart_show_hide_all_notes_hotkey_listener_stops_the_old_one(monkeypatch):
    _FakeHotkeyListener.instances = []
    monkeypatch.setattr(app_module, "HotkeyListener", _FakeHotkeyListener)
    manager = Mock()
    manager.settings = Settings(show_hide_all_notes_hotkey="Meta+Alt+H")
    manager._start_show_hide_all_notes_hotkey_listener = (
        lambda: NoteManager._start_show_hide_all_notes_hotkey_listener(manager)
    )
    old_listener = Mock()
    manager.show_hide_all_notes_hotkey = old_listener

    NoteManager._restart_show_hide_all_notes_hotkey_listener(manager)

    old_listener.stop.assert_called_once()
    assert manager.show_hide_all_notes_hotkey is _FakeHotkeyListener.instances[0]


def test_start_roll_all_notes_hotkey_listener_uses_the_configured_combo(monkeypatch):
    _FakeHotkeyListener.instances = []
    monkeypatch.setattr(app_module, "HotkeyListener", _FakeHotkeyListener)
    manager = Mock()
    manager.settings = Settings(roll_all_notes_hotkey="Meta+Alt+R")

    NoteManager._start_roll_all_notes_hotkey_listener(manager)

    listener = _FakeHotkeyListener.instances[0]
    assert (listener.key, listener.modifiers) == ("R", ("meta", "mod1"))
    assert listener.started
    assert manager.roll_all_notes_hotkey is listener


def test_roll_all_notes_hotkey_triggered_calls_toggle_roll_all_notes(monkeypatch):
    _FakeHotkeyListener.instances = []
    monkeypatch.setattr(app_module, "HotkeyListener", _FakeHotkeyListener)
    manager = Mock()
    manager.settings = Settings(roll_all_notes_hotkey="Meta+Alt+R")

    NoteManager._start_roll_all_notes_hotkey_listener(manager)

    triggered_callback = _FakeHotkeyListener.instances[0].triggered.connect.call_args[0][0]
    triggered_callback()

    manager.toggle_roll_all_notes.assert_called_once()


def test_restart_roll_all_notes_hotkey_listener_stops_the_old_one(monkeypatch):
    _FakeHotkeyListener.instances = []
    monkeypatch.setattr(app_module, "HotkeyListener", _FakeHotkeyListener)
    manager = Mock()
    manager.settings = Settings(roll_all_notes_hotkey="Meta+Alt+R")
    manager._start_roll_all_notes_hotkey_listener = (
        lambda: NoteManager._start_roll_all_notes_hotkey_listener(manager)
    )
    old_listener = Mock()
    manager.roll_all_notes_hotkey = old_listener

    NoteManager._restart_roll_all_notes_hotkey_listener(manager)

    old_listener.stop.assert_called_once()
    assert manager.roll_all_notes_hotkey is _FakeHotkeyListener.instances[0]


def test_start_bring_all_notes_to_front_hotkey_listener_uses_the_configured_combo(monkeypatch):
    _FakeHotkeyListener.instances = []
    monkeypatch.setattr(app_module, "HotkeyListener", _FakeHotkeyListener)
    manager = Mock()
    manager.settings = Settings(bring_all_notes_to_front_hotkey="Meta+Alt+T")

    NoteManager._start_bring_all_notes_to_front_hotkey_listener(manager)

    listener = _FakeHotkeyListener.instances[0]
    assert (listener.key, listener.modifiers) == ("T", ("meta", "mod1"))
    assert listener.started
    assert manager.bring_all_notes_to_front_hotkey is listener


def test_bring_all_notes_to_front_hotkey_triggered_calls_bring_all_notes_to_front(monkeypatch):
    _FakeHotkeyListener.instances = []
    monkeypatch.setattr(app_module, "HotkeyListener", _FakeHotkeyListener)
    manager = Mock()
    manager.settings = Settings(bring_all_notes_to_front_hotkey="Meta+Alt+T")

    NoteManager._start_bring_all_notes_to_front_hotkey_listener(manager)

    triggered_callback = _FakeHotkeyListener.instances[0].triggered.connect.call_args[0][0]
    triggered_callback()

    manager.bring_all_notes_to_front.assert_called_once()


def test_restart_bring_all_notes_to_front_hotkey_listener_stops_the_old_one(monkeypatch):
    _FakeHotkeyListener.instances = []
    monkeypatch.setattr(app_module, "HotkeyListener", _FakeHotkeyListener)
    manager = Mock()
    manager.settings = Settings(bring_all_notes_to_front_hotkey="Meta+Alt+T")
    manager._start_bring_all_notes_to_front_hotkey_listener = (
        lambda: NoteManager._start_bring_all_notes_to_front_hotkey_listener(manager)
    )
    old_listener = Mock()
    manager.bring_all_notes_to_front_hotkey = old_listener

    NoteManager._restart_bring_all_notes_to_front_hotkey_listener(manager)

    old_listener.stop.assert_called_once()
    assert manager.bring_all_notes_to_front_hotkey is _FakeHotkeyListener.instances[0]


def test_start_new_bulk_action_hotkey_listeners_skip_grabbing_when_cleared(monkeypatch):
    """All three default to None (see Settings.show_hide_all_notes_hotkey
    etc.'s own docstring — explicit user call, no default combo unlike
    the two hotkeys above), so a fresh install must never attempt a grab
    for any of them."""
    _FakeHotkeyListener.instances = []
    monkeypatch.setattr(app_module, "HotkeyListener", _FakeHotkeyListener)
    manager = Mock()
    manager.settings = Settings()

    NoteManager._start_show_hide_all_notes_hotkey_listener(manager)
    NoteManager._start_roll_all_notes_hotkey_listener(manager)
    NoteManager._start_bring_all_notes_to_front_hotkey_listener(manager)

    assert _FakeHotkeyListener.instances == []
    assert manager.show_hide_all_notes_hotkey is None
    assert manager.roll_all_notes_hotkey is None
    assert manager.bring_all_notes_to_front_hotkey is None


def test_apply_settings_restarts_only_the_changed_bulk_action_hotkey(monkeypatch):
    monkeypatch.setattr(app_module.autostart, "enable", Mock())
    monkeypatch.setattr(app_module.autostart, "disable", Mock())
    manager = _fake_manager_for_apply_settings(
        Settings(roll_all_notes_hotkey="Meta+Alt+R", bring_all_notes_to_front_hotkey="Meta+Alt+T")
    )

    NoteManager._apply_settings(
        manager,
        Settings(roll_all_notes_hotkey="Meta+Alt+X", bring_all_notes_to_front_hotkey="Meta+Alt+T"),
    )

    manager._restart_roll_all_notes_hotkey_listener.assert_called_once()
    manager._restart_show_hide_all_notes_hotkey_listener.assert_not_called()
    manager._restart_bring_all_notes_to_front_hotkey_listener.assert_not_called()
