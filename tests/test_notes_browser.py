from __future__ import annotations

from unittest.mock import Mock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from take_note.models import Board, Note, Settings
from take_note.notes_browser import ALL_NOTES, UNFILED, NotesBrowserWindow, _format_modified


def _note_window(body_text: str = "", **kwargs) -> Mock:
    note_window = Mock()
    note_window.note = Note(**kwargs)
    note_window.body.toPlainText.return_value = body_text
    return note_window


def _board_window(**kwargs) -> Mock:
    board_window = Mock()
    board_window.board = Board(**kwargs)
    return board_window


def _fake_manager(notes=None, boards=None, settings=None) -> Mock:
    manager = Mock()
    manager.notes = notes or {}
    manager.boards = boards or {}
    manager.notes_changed = Mock()
    manager.settings = settings or Settings()
    return manager


def _tree_labels(browser: NotesBrowserWindow) -> list[str]:
    return [browser.tree.topLevelItem(i).text(0) for i in range(browser.tree.topLevelItemCount())]


def test_format_modified_converts_utc_to_local_time():
    """Regression, reported live: displayed "07:11 PM" when the actual
    local wall-clock time was 12:33 PM — datetime.fromisoformat() on a
    UTC-offset string produces a timezone-aware datetime still set to
    UTC, and strftime() alone doesn't convert it. Deliberately doesn't
    hardcode an expected local time (would be fragile to whatever
    timezone the test happens to run in) — instead checks against the
    exact same astimezone() conversion the fix itself performs, so
    what's actually being verified is that the conversion happens at
    all, not a guessed specific local time."""
    from datetime import datetime

    utc_iso = "2026-07-11T19:32:19.041089+00:00"
    expected_local = datetime.fromisoformat(utc_iso).astimezone().strftime("%B %d, %Y %I:%M %p")

    assert _format_modified(utc_iso) == expected_local


def test_format_modified_returns_raw_string_for_unparseable_input():
    assert _format_modified("not a real timestamp") == "not a real timestamp"


def test_tree_has_all_notes_and_unfiled_plus_one_item_per_board(qapp):
    work = _board_window(name="Work")
    personal = _board_window(name="Personal")
    manager = _fake_manager(boards={work.board.id: work, personal.board.id: personal})

    browser = NotesBrowserWindow(manager)

    assert _tree_labels(browser) == ["All Notes", "Unfiled", "Work", "Personal"]


def test_all_notes_selected_by_default_shows_every_note(qapp):
    n1 = _note_window(title="Groceries")
    n2 = _note_window(title="Taxes", board_id="board-1")
    manager = _fake_manager(notes={n1.note.id: n1, n2.note.id: n2})

    browser = NotesBrowserWindow(manager)

    assert browser.table.rowCount() == 2


def test_search_filters_table_by_title_substring(qapp):
    n1 = _note_window(title="Groceries")
    n2 = _note_window(title="Taxes")
    manager = _fake_manager(notes={n1.note.id: n1, n2.note.id: n2})
    browser = NotesBrowserWindow(manager)

    browser.search_edit.setText("tax")

    assert browser.table.rowCount() == 1
    assert browser.table.item(0, 0).data(Qt.UserRole) == n2.note.id


def test_search_also_matches_note_body_not_just_title(qapp):
    """Regression: a search for a word only in the note's body (not its
    title) previously found nothing, since filtering only checked
    note.title."""
    n1 = _note_window(title="", body_text="Check out my songs, stories and poems!")
    n2 = _note_window(title="", body_text="Grocery list")
    manager = _fake_manager(notes={n1.note.id: n1, n2.note.id: n2})
    browser = NotesBrowserWindow(manager)

    browser.search_edit.setText("poem")

    assert browser.table.rowCount() == 1
    assert browser.table.item(0, 0).data(Qt.UserRole) == n1.note.id


def test_preview_column_shows_body_snippet_for_untitled_notes(qapp):
    """Regression: an untitled note showed as bare "(untitled)" with
    nothing else to distinguish it from any other untitled note."""
    n1 = _note_window(title="", body_text="Check out my songs, stories and poems!")
    manager = _fake_manager(notes={n1.note.id: n1})
    browser = NotesBrowserWindow(manager)

    assert browser.table.item(0, 1).text() == "Check out my songs, stories and poems!"


def test_preview_column_collapses_whitespace_and_truncates(qapp):
    long_body = "word " * 30
    n1 = _note_window(title="", body_text=long_body)
    manager = _fake_manager(notes={n1.note.id: n1})
    browser = NotesBrowserWindow(manager)

    preview = browser.table.item(0, 1).text()
    assert "\n" not in preview
    assert len(preview) <= 61  # 60 chars + the ellipsis character
    assert preview.endswith("…")


def test_notepad_column_shows_board_name_when_attached(qapp):
    work = _board_window(name="Work")
    n1 = _note_window(title="Report", board_id=work.board.id)
    manager = _fake_manager(notes={n1.note.id: n1}, boards={work.board.id: work})
    browser = NotesBrowserWindow(manager)

    assert browser.table.item(0, 2).text() == "Work"


def test_notepad_column_blank_when_unfiled(qapp):
    n1 = _note_window(title="Groceries")
    manager = _fake_manager(notes={n1.note.id: n1})
    browser = NotesBrowserWindow(manager)

    assert browser.table.item(0, 2).text() == ""


def test_tags_column_shows_joined_tags(qapp):
    n1 = _note_window(title="Report", tags=["work", "urgent"])
    manager = _fake_manager(notes={n1.note.id: n1})
    browser = NotesBrowserWindow(manager)

    assert browser.table.item(0, 4).text() == "work, urgent"


def test_tags_column_blank_when_untagged(qapp):
    n1 = _note_window(title="Groceries")
    manager = _fake_manager(notes={n1.note.id: n1})
    browser = NotesBrowserWindow(manager)

    assert browser.table.item(0, 4).text() == ""


def test_tree_has_no_tags_section_when_no_notes_are_tagged(qapp):
    n1 = _note_window(title="Groceries")
    manager = _fake_manager(notes={n1.note.id: n1})

    browser = NotesBrowserWindow(manager)

    assert "Tags" not in _tree_labels(browser)


def test_tree_tags_section_lists_unique_tags_in_use(qapp):
    n1 = _note_window(title="Report", tags=["work", "urgent"])
    n2 = _note_window(title="Groceries", tags=["urgent", "home"])
    manager = _fake_manager(notes={n1.note.id: n1, n2.note.id: n2})

    browser = NotesBrowserWindow(manager)

    tags_item = browser.tree.topLevelItem(_tree_labels(browser).index("Tags"))
    child_labels = [tags_item.child(i).text(0) for i in range(tags_item.childCount())]
    assert child_labels == ["home", "urgent", "work"]


def test_selecting_tag_filters_table_to_notes_with_that_tag(qapp):
    n_work = _note_window(title="Report", tags=["work"])
    n_other = _note_window(title="Groceries", tags=["home"])
    manager = _fake_manager(notes={n_work.note.id: n_work, n_other.note.id: n_other})
    browser = NotesBrowserWindow(manager)
    tags_item = browser.tree.topLevelItem(_tree_labels(browser).index("Tags"))
    work_item = next(
        tags_item.child(i) for i in range(tags_item.childCount()) if tags_item.child(i).text(0) == "work"
    )

    browser.tree.setCurrentItem(work_item)

    assert browser.table.rowCount() == 1
    assert browser.table.item(0, 0).text() == "Report"


def test_tags_parent_item_is_not_selectable(qapp):
    """The "Tags" parent has no natural "show notes with any tag"
    filtering meaning of its own — only its children do."""
    n1 = _note_window(title="Report", tags=["work"])
    manager = _fake_manager(notes={n1.note.id: n1})
    browser = NotesBrowserWindow(manager)

    tags_item = browser.tree.topLevelItem(_tree_labels(browser).index("Tags"))

    assert not bool(tags_item.flags() & Qt.ItemIsSelectable)


def test_orphaned_tag_disappears_after_refresh(qapp):
    """Fully free-form vocabulary: a tag exists implicitly as long as at
    least one note uses it, computed fresh from live note data every
    refresh rather than a separate registry."""
    n1 = _note_window(title="Report", tags=["work"])
    manager = _fake_manager(notes={n1.note.id: n1})
    browser = NotesBrowserWindow(manager)
    assert "Tags" in _tree_labels(browser)

    n1.note.tags = []
    browser._refresh()

    assert "Tags" not in _tree_labels(browser)


def test_search_field_has_a_clear_button(qapp):
    """Regression: there was previously no way to clear the search box
    short of manually deleting the typed text."""
    manager = _fake_manager()
    browser = NotesBrowserWindow(manager)

    assert browser.search_edit.isClearButtonEnabled()


def test_selecting_board_narrows_table_to_that_boards_notes(qapp):
    work = _board_window(name="Work")
    n_work = _note_window(title="Report", board_id=work.board.id)
    n_other = _note_window(title="Groceries")
    manager = _fake_manager(
        notes={n_work.note.id: n_work, n_other.note.id: n_other},
        boards={work.board.id: work},
    )
    browser = NotesBrowserWindow(manager)
    board_item = browser.tree.topLevelItem(2)
    assert board_item.text(0) == "Work"

    browser.tree.setCurrentItem(board_item)

    assert browser.table.rowCount() == 1
    assert browser.table.item(0, 0).text() == "Report"


def test_selecting_unfiled_shows_only_notes_without_a_board(qapp):
    n_filed = _note_window(title="Report", board_id="board-1")
    n_unfiled = _note_window(title="Groceries")
    manager = _fake_manager(notes={n_filed.note.id: n_filed, n_unfiled.note.id: n_unfiled})
    browser = NotesBrowserWindow(manager)
    unfiled_item = browser.tree.topLevelItem(1)
    assert unfiled_item.data(0, Qt.UserRole) == UNFILED

    browser.tree.setCurrentItem(unfiled_item)

    assert browser.table.rowCount() == 1
    assert browser.table.item(0, 0).text() == "Groceries"


def test_delete_selected_note_confirms_then_calls_manager_delete_note(qapp, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
    n1 = _note_window(title="Groceries")
    manager = _fake_manager(notes={n1.note.id: n1})
    browser = NotesBrowserWindow(manager)
    browser.table.selectRow(0)

    browser._delete_selected_notes()

    manager.delete_note.assert_called_once_with(n1)


def test_delete_selected_note_does_nothing_when_declined(qapp, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.No))
    n1 = _note_window(title="Groceries")
    manager = _fake_manager(notes={n1.note.id: n1})
    browser = NotesBrowserWindow(manager)
    browser.table.selectRow(0)

    browser._delete_selected_notes()

    manager.delete_note.assert_not_called()


def test_multi_select_delete_asks_once_and_deletes_every_selected_note(qapp, monkeypatch):
    """Regression coverage for extending selection beyond a single row:
    one confirmation dialog, not one per note, and every selected note
    gets deleted."""
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
    n1 = _note_window(title="Groceries")
    n2 = _note_window(title="Taxes")
    manager = _fake_manager(notes={n1.note.id: n1, n2.note.id: n2})
    browser = NotesBrowserWindow(manager)
    browser.table.selectAll()

    browser._delete_selected_notes()

    assert manager.delete_note.call_count == 2
    manager.delete_note.assert_any_call(n1)
    manager.delete_note.assert_any_call(n2)


def test_table_allows_extended_selection(qapp):
    from PySide6.QtWidgets import QAbstractItemView

    manager = _fake_manager()
    browser = NotesBrowserWindow(manager)

    assert browser.table.selectionMode() == QAbstractItemView.ExtendedSelection


def test_restores_saved_window_geometry(qapp):
    settings = Settings(notes_browser_x=50, notes_browser_y=60, notes_browser_w=800, notes_browser_h=500)
    manager = _fake_manager(settings=settings)

    browser = NotesBrowserWindow(manager)

    assert browser.size().width() == 800
    assert browser.size().height() == 500
    assert browser.pos().x() == 50
    assert browser.pos().y() == 60


def test_resizing_persists_geometry_and_schedules_save(qapp):
    manager = _fake_manager()
    browser = NotesBrowserWindow(manager)

    browser.resize(600, 400)

    assert manager.settings.notes_browser_w == 600
    assert manager.settings.notes_browser_h == 400
    manager._schedule_save.assert_called()


def test_new_note_on_all_notes_creates_unattached_note(qapp):
    manager = _fake_manager()
    browser = NotesBrowserWindow(manager)
    assert browser._current_tree_filter() == ALL_NOTES

    browser._create_note()

    manager.create_note.assert_called_once_with()


def test_new_note_with_board_selected_attaches_to_that_board(qapp):
    work = _board_window(name="Work")
    manager = _fake_manager(boards={work.board.id: work})
    browser = NotesBrowserWindow(manager)
    board_item = browser.tree.topLevelItem(2)
    browser.tree.setCurrentItem(board_item)

    browser._create_note()

    manager.create_note.assert_called_once_with(board=work)


def test_window_title_does_not_duplicate_app_name(qapp):
    """Regression, found via a live screenshot (test case 8.8): the
    window rendered as "Take Note! — Notes Browser — Take Note!" — the
    OS/WM already appends " — Take Note!" automatically (same behavior
    already confirmed for dialog titles), so this window's own hardcoded
    "Take Note! —" prefix was a redundant duplicate. Every other window
    in the app already just sets its own plain descriptive title."""
    manager = _fake_manager()
    browser = NotesBrowserWindow(manager)

    assert browser.windowTitle() == "Notes Browser"


def test_preview_column_has_a_minimum_width(qapp):
    """Regression, reproduced live: sorting by Date Modified and Notepad a
    few times each, then sorting by Preview, clipped its header to
    "review" (leading "P" cut off). Preview is a Stretch column next to
    Title, which is Interactive (user-draggable) — without a floor, Title
    could claim enough width to squeeze Preview below what its own header
    text plus the sort-indicator arrow need to render.

    Not a hardcoded pixel floor: an earlier fix hardcoded 90px, which
    matched the offscreen test platform's narrower fallback font but
    undershot the real desktop font (122px under real xcb/Noto Sans) —
    this test would have stayed green while the app clipped live. Assert
    against the header's own real requirement instead, which is exactly
    what the fix itself now does."""
    manager = _fake_manager()
    browser = NotesBrowserWindow(manager)
    header = browser.table.horizontalHeader()

    assert header.minimumSectionSize() == header.sectionSizeHint(1)
