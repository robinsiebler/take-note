from __future__ import annotations

from unittest.mock import Mock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QTableWidget, QTableWidgetItem

from take_note.models import Board, Note, Settings
from take_note.notes_manager import (
    ALL_NOTES,
    UNFILED,
    NotesManagerWindow,
    _DateTableWidgetItem,
    _format_modified,
)


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


def _tree_labels(browser: NotesManagerWindow) -> list[str]:
    return [browser.tree.topLevelItem(i).text(0) for i in range(browser.tree.topLevelItemCount())]


def test_notes_manager_skips_the_taskbar(qapp, monkeypatch):
    """The one Take Note! window that used to be visible in the taskbar —
    notes/boards already skip it — which is what a real KDE Task Manager
    bug (confirmed unrelated to this app, filed upstream) mislabeled with
    an unrelated app's icon. With a dedicated hotkey to reopen it, there's
    no remaining need for taskbar/Alt-Tab reachability."""
    calls = []
    monkeypatch.setattr(
        "take_note.notes_manager.set_skip_taskbar", lambda win_id, enabled: calls.append((win_id, enabled))
    )

    NotesManagerWindow(_fake_manager())

    assert calls == [(calls[0][0], True)]


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

    browser = NotesManagerWindow(manager)

    assert _tree_labels(browser) == ["All Notes", "Unfiled", "Work", "Personal", "Trash"]


def test_all_notes_selected_by_default_shows_every_note(qapp):
    n1 = _note_window(title="Groceries")
    n2 = _note_window(title="Taxes", board_id="board-1")
    manager = _fake_manager(notes={n1.note.id: n1, n2.note.id: n2})

    browser = NotesManagerWindow(manager)

    assert browser.table.rowCount() == 2


def test_search_filters_table_by_title_substring(qapp):
    n1 = _note_window(title="Groceries")
    n2 = _note_window(title="Taxes")
    manager = _fake_manager(notes={n1.note.id: n1, n2.note.id: n2})
    browser = NotesManagerWindow(manager)

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
    browser = NotesManagerWindow(manager)

    browser.search_edit.setText("poem")

    assert browser.table.rowCount() == 1
    assert browser.table.item(0, 0).data(Qt.UserRole) == n1.note.id


def test_preview_column_shows_body_snippet_for_untitled_notes(qapp):
    """Regression: an untitled note showed as bare "(untitled)" with
    nothing else to distinguish it from any other untitled note."""
    n1 = _note_window(title="", body_text="Check out my songs, stories and poems!")
    manager = _fake_manager(notes={n1.note.id: n1})
    browser = NotesManagerWindow(manager)

    assert browser.table.item(0, 1).text() == "Check out my songs, stories and poems!"


def test_preview_column_collapses_whitespace_and_truncates(qapp):
    long_body = "word " * 30
    n1 = _note_window(title="", body_text=long_body)
    manager = _fake_manager(notes={n1.note.id: n1})
    browser = NotesManagerWindow(manager)

    preview = browser.table.item(0, 1).text()
    assert "\n" not in preview
    assert len(preview) <= 61  # 60 chars + the ellipsis character
    assert preview.endswith("…")


def test_notepad_column_shows_board_name_when_attached(qapp):
    work = _board_window(name="Work")
    n1 = _note_window(title="Report", board_id=work.board.id)
    manager = _fake_manager(notes={n1.note.id: n1}, boards={work.board.id: work})
    browser = NotesManagerWindow(manager)

    assert browser.table.item(0, 2).text() == "Work"


def test_notepad_column_blank_when_unfiled(qapp):
    n1 = _note_window(title="Groceries")
    manager = _fake_manager(notes={n1.note.id: n1})
    browser = NotesManagerWindow(manager)

    assert browser.table.item(0, 2).text() == ""


def test_tags_column_shows_joined_tags(qapp):
    n1 = _note_window(title="Report", tags=["work", "urgent"])
    manager = _fake_manager(notes={n1.note.id: n1})
    browser = NotesManagerWindow(manager)

    assert browser.table.item(0, 4).text() == "work, urgent"


def test_tags_column_blank_when_untagged(qapp):
    n1 = _note_window(title="Groceries")
    manager = _fake_manager(notes={n1.note.id: n1})
    browser = NotesManagerWindow(manager)

    assert browser.table.item(0, 4).text() == ""


def test_reminder_column_shows_formatted_time_when_set(qapp):
    n1 = _note_window(title="Report", reminder_at="2026-08-01T15:30:00+00:00")
    manager = _fake_manager(notes={n1.note.id: n1})
    browser = NotesManagerWindow(manager)

    assert browser.table.item(0, 5).text() == _format_modified("2026-08-01T15:30:00+00:00")


def test_reminder_column_blank_when_not_set(qapp):
    n1 = _note_window(title="Groceries")
    manager = _fake_manager(notes={n1.note.id: n1})
    browser = NotesManagerWindow(manager)

    assert browser.table.item(0, 5).text() == ""


def test_sorting_a_column_mixing_date_and_plain_items_does_not_recurse(qapp):
    """Regression: confirmed live — sorting the Reminder column (the
    first column to ever mix _DateTableWidgetItem, when a reminder is
    set, with a plain QTableWidgetItem(""), when it isn't) crashed with
    a RecursionError inside __lt__. Date Modified never mixed types
    (modified_at is never null), so this was dead code until now."""
    # Confirmed directly: too few rows doesn't reliably trigger the
    # recursive comparison within pytest's own stack depth (unlike a
    # bare script, which crashed even at 2 rows) — 8 rows reliably hits
    # it, matching the real live crash.
    table = QTableWidget(8, 1)
    for row in range(8):
        if row % 2 == 0:
            table.setItem(row, 0, _DateTableWidgetItem(f"2026-08-0{row + 1}T00:00:00+00:00"))
        else:
            table.setItem(row, 0, QTableWidgetItem(""))

    table.sortItems(0)


def test_tree_has_no_tags_section_when_no_notes_are_tagged(qapp):
    n1 = _note_window(title="Groceries")
    manager = _fake_manager(notes={n1.note.id: n1})

    browser = NotesManagerWindow(manager)

    assert "Tags" not in _tree_labels(browser)


def test_tree_tags_section_lists_unique_tags_in_use(qapp):
    n1 = _note_window(title="Report", tags=["work", "urgent"])
    n2 = _note_window(title="Groceries", tags=["urgent", "home"])
    manager = _fake_manager(notes={n1.note.id: n1, n2.note.id: n2})

    browser = NotesManagerWindow(manager)

    tags_item = browser.tree.topLevelItem(_tree_labels(browser).index("Tags"))
    child_labels = [tags_item.child(i).text(0) for i in range(tags_item.childCount())]
    assert child_labels == ["home", "urgent", "work"]


def test_selecting_tag_filters_table_to_notes_with_that_tag(qapp):
    n_work = _note_window(title="Report", tags=["work"])
    n_other = _note_window(title="Groceries", tags=["home"])
    manager = _fake_manager(notes={n_work.note.id: n_work, n_other.note.id: n_other})
    browser = NotesManagerWindow(manager)
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
    browser = NotesManagerWindow(manager)

    tags_item = browser.tree.topLevelItem(_tree_labels(browser).index("Tags"))

    assert not bool(tags_item.flags() & Qt.ItemIsSelectable)


def test_orphaned_tag_disappears_after_refresh(qapp):
    """Fully free-form vocabulary: a tag exists implicitly as long as at
    least one note uses it, computed fresh from live note data every
    refresh rather than a separate registry."""
    n1 = _note_window(title="Report", tags=["work"])
    manager = _fake_manager(notes={n1.note.id: n1})
    browser = NotesManagerWindow(manager)
    assert "Tags" in _tree_labels(browser)

    n1.note.tags = []
    browser._refresh()

    assert "Tags" not in _tree_labels(browser)


def test_search_field_has_a_clear_button(qapp):
    """Regression: there was previously no way to clear the search box
    short of manually deleting the typed text."""
    manager = _fake_manager()
    browser = NotesManagerWindow(manager)

    assert browser.search_edit.isClearButtonEnabled()


def test_selecting_board_narrows_table_to_that_boards_notes(qapp):
    work = _board_window(name="Work")
    n_work = _note_window(title="Report", board_id=work.board.id)
    n_other = _note_window(title="Groceries")
    manager = _fake_manager(
        notes={n_work.note.id: n_work, n_other.note.id: n_other},
        boards={work.board.id: work},
    )
    browser = NotesManagerWindow(manager)
    board_item = browser.tree.topLevelItem(2)
    assert board_item.text(0) == "Work"

    browser.tree.setCurrentItem(board_item)

    assert browser.table.rowCount() == 1
    assert browser.table.item(0, 0).text() == "Report"


def test_selecting_unfiled_shows_only_notes_without_a_board(qapp):
    n_filed = _note_window(title="Report", board_id="board-1")
    n_unfiled = _note_window(title="Groceries")
    manager = _fake_manager(notes={n_filed.note.id: n_filed, n_unfiled.note.id: n_unfiled})
    browser = NotesManagerWindow(manager)
    unfiled_item = browser.tree.topLevelItem(1)
    assert unfiled_item.data(0, Qt.UserRole) == UNFILED

    browser.tree.setCurrentItem(unfiled_item)

    assert browser.table.rowCount() == 1
    assert browser.table.item(0, 0).text() == "Groceries"


def test_delete_selected_note_confirms_then_calls_manager_trash_note(qapp, monkeypatch):
    """Delete now means Move to Trash everywhere except the Trash view
    itself (see test_delete_selected_note_in_trash_view_deletes_permanently
    below) — manager.delete_note() (permanent) is no longer reachable
    from a normal note selection."""
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
    n1 = _note_window(title="Groceries")
    manager = _fake_manager(notes={n1.note.id: n1})
    browser = NotesManagerWindow(manager)
    browser.table.selectRow(0)

    browser._delete_selected_notes()

    manager.trash_note.assert_called_once_with(n1)
    manager.delete_note.assert_not_called()


def test_delete_selected_note_does_nothing_when_declined(qapp, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.No))
    n1 = _note_window(title="Groceries")
    manager = _fake_manager(notes={n1.note.id: n1})
    browser = NotesManagerWindow(manager)
    browser.table.selectRow(0)

    browser._delete_selected_notes()

    manager.trash_note.assert_not_called()


def test_multi_select_delete_asks_once_and_trashes_every_selected_note(qapp, monkeypatch):
    """Regression coverage for extending selection beyond a single row:
    one confirmation dialog, not one per note, and every selected note
    gets trashed."""
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
    n1 = _note_window(title="Groceries")
    n2 = _note_window(title="Taxes")
    manager = _fake_manager(notes={n1.note.id: n1, n2.note.id: n2})
    browser = NotesManagerWindow(manager)
    browser.table.selectAll()

    browser._delete_selected_notes()

    assert manager.trash_note.call_count == 2
    manager.trash_note.assert_any_call(n1)
    manager.trash_note.assert_any_call(n2)


def test_switching_tree_filter_clears_the_table_selection(qapp):
    """Regression, reported live: selecting N notes while viewing All
    Notes, then clicking Trash in the tree, left N notes looking selected
    there too — same root cause as the delete-selection fix below (row/
    column index-based selection surviving a table repopulation with
    completely different content at those same indices), just triggered
    by switching filters instead of a delete."""
    n1 = _note_window(title="Groceries")
    n2 = _note_window(title="Taxes")
    manager = _fake_manager(notes={n1.note.id: n1, n2.note.id: n2})
    browser = NotesManagerWindow(manager)
    browser.table.selectAll()
    assert len(browser.table.selectionModel().selectedRows()) == 2

    _select_tree_item(browser, "Trash")

    assert browser.table.selectionModel().selectedRows() == []


def test_deleting_selected_notes_clears_the_table_selection(qapp, monkeypatch):
    """Regression, reported live: deleting several selected notes left
    whatever notes now occupied those same row indices looking selected,
    even though the user never touched them — QTableWidget's selection
    model tracks selection by row/column index, not by which
    QTableWidgetItem object occupies it, and a live refresh after the
    delete only ever replaces items at each surviving index, never clears
    which indices were marked selected."""
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
    n1 = _note_window(title="Groceries")
    n2 = _note_window(title="Taxes")
    manager = _fake_manager(notes={n1.note.id: n1, n2.note.id: n2})
    browser = NotesManagerWindow(manager)
    browser.table.selectAll()

    browser._delete_selected_notes()

    assert browser.table.selectionModel().selectedRows() == []


def _select_tree_item(browser: NotesManagerWindow, label: str):
    for i in range(browser.tree.topLevelItemCount()):
        item = browser.tree.topLevelItem(i)
        if item.text(0) == label:
            browser.tree.setCurrentItem(item)
            return
    raise AssertionError(f"no top-level tree item named {label!r}")


def test_delete_selected_note_in_trash_view_deletes_permanently(qapp, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
    n1 = _note_window(title="Groceries", deleted_at="2026-01-01T00:00:00+00:00")
    manager = _fake_manager(notes={n1.note.id: n1})
    browser = NotesManagerWindow(manager)
    _select_tree_item(browser, "Trash")
    browser.table.selectRow(0)

    browser._delete_selected_notes()

    manager.delete_note.assert_called_once_with(n1)
    manager.trash_note.assert_not_called()


def test_deleting_permanently_also_clears_the_table_selection(qapp, monkeypatch):
    """Same fix as test_deleting_selected_notes_clears_the_table_selection,
    covering the Trash view's separate _confirm_and_delete_permanently
    code path."""
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
    n1 = _note_window(title="Groceries", deleted_at="2026-01-01T00:00:00+00:00")
    manager = _fake_manager(notes={n1.note.id: n1})
    browser = NotesManagerWindow(manager)
    _select_tree_item(browser, "Trash")
    browser.table.selectRow(0)

    browser._delete_selected_notes()

    assert browser.table.selectionModel().selectedRows() == []


def test_restore_selected_notes_calls_manager_restore_note(qapp):
    n1 = _note_window(title="Groceries", deleted_at="2026-01-01T00:00:00+00:00")
    manager = _fake_manager(notes={n1.note.id: n1})
    browser = NotesManagerWindow(manager)
    _select_tree_item(browser, "Trash")
    browser.table.selectRow(0)

    browser._restore_selected_notes()

    manager.restore_note.assert_called_once_with(n1)


def test_trashed_notes_excluded_from_all_notes(qapp):
    active = _note_window(title="Groceries")
    trashed = _note_window(title="Old note", deleted_at="2026-01-01T00:00:00+00:00")
    manager = _fake_manager(notes={active.note.id: active, trashed.note.id: trashed})

    browser = NotesManagerWindow(manager)

    assert browser.table.rowCount() == 1
    assert browser.table.item(0, 0).text() == "Groceries"


def test_trash_view_shows_only_trashed_notes(qapp):
    active = _note_window(title="Groceries")
    trashed = _note_window(title="Old note", deleted_at="2026-01-01T00:00:00+00:00")
    manager = _fake_manager(notes={active.note.id: active, trashed.note.id: trashed})
    browser = NotesManagerWindow(manager)

    _select_tree_item(browser, "Trash")

    assert browser.table.rowCount() == 1
    assert browser.table.item(0, 0).text() == "Old note"


def test_toolbar_shows_restore_and_relabels_delete_only_in_trash_view(qapp):
    manager = _fake_manager()
    browser = NotesManagerWindow(manager)

    assert not browser.restore_btn.isVisible()
    assert browser.delete_btn.text() == "Delete"

    _select_tree_item(browser, "Trash")

    assert browser.restore_btn.isVisible()
    assert browser.delete_btn.text() == "Delete Permanently"


def test_double_clicking_a_trashed_note_does_not_show_it(qapp):
    trashed = _note_window(title="Old note", deleted_at="2026-01-01T00:00:00+00:00")
    manager = _fake_manager(notes={trashed.note.id: trashed})
    browser = NotesManagerWindow(manager)
    _select_tree_item(browser, "Trash")
    browser.table.selectRow(0)

    browser._open_selected_note()

    trashed.show.assert_not_called()


def test_double_clicking_a_note_restores_it_if_minimized(qapp):
    """Regression, reported live: minimizing a note reopened from here left
    no way to get it back the same way the Notes Manager itself did — see
    NoteManager.open_notes_manager's own regression test/comment."""
    note_window = _note_window(title="Some note")
    manager = _fake_manager(notes={note_window.note.id: note_window})
    browser = NotesManagerWindow(manager)
    browser.table.selectRow(0)

    browser._open_selected_note()

    note_window.showNormal.assert_called_once()
    note_window.raise_.assert_called_once()
    note_window.activateWindow.assert_called_once()


def test_double_clicking_a_board_in_the_tree_restores_it_if_minimized(qapp):
    """show_board() (not raw showNormal()/raise_()/activateWindow()) —
    also persists board.hidden = False, so reopening a closed board from
    the tree is remembered across a restart too."""
    board_window = _board_window(name="Work")
    manager = _fake_manager(boards={board_window.board.id: board_window})
    browser = NotesManagerWindow(manager)
    item = browser.tree.findItems("Work", Qt.MatchExactly)[0]

    browser._open_board_from_tree(item, 0)

    board_window.show_board.assert_called_once()


def test_table_allows_extended_selection(qapp):
    from PySide6.QtWidgets import QAbstractItemView

    manager = _fake_manager()
    browser = NotesManagerWindow(manager)

    assert browser.table.selectionMode() == QAbstractItemView.ExtendedSelection


def test_restores_saved_window_geometry(qapp):
    settings = Settings(notes_browser_x=50, notes_browser_y=60, notes_browser_w=800, notes_browser_h=500)
    manager = _fake_manager(settings=settings)

    browser = NotesManagerWindow(manager)

    assert browser.size().width() == 800
    assert browser.size().height() == 500
    assert browser.pos().x() == 50
    assert browser.pos().y() == 60


def test_resizing_persists_geometry_and_schedules_save(qapp):
    manager = _fake_manager()
    browser = NotesManagerWindow(manager)

    browser.resize(600, 400)

    assert manager.settings.notes_browser_w == 600
    assert manager.settings.notes_browser_h == 400
    manager._schedule_save.assert_called()


def test_new_note_on_all_notes_creates_unattached_note(qapp):
    manager = _fake_manager()
    browser = NotesManagerWindow(manager)
    assert browser._current_tree_filter() == ALL_NOTES

    browser._create_note()

    manager.create_note.assert_called_once_with()


def test_new_note_with_board_selected_attaches_to_that_board(qapp):
    work = _board_window(name="Work")
    manager = _fake_manager(boards={work.board.id: work})
    browser = NotesManagerWindow(manager)
    board_item = browser.tree.topLevelItem(2)
    browser.tree.setCurrentItem(board_item)

    browser._create_note()

    manager.create_note.assert_called_once_with(board=work)


def test_window_title_does_not_duplicate_app_name(qapp):
    """Regression, found via a live screenshot (test case 8.8): the
    window rendered as "Take Note! — Notes Manager — Take Note!" — the
    OS/WM already appends " — Take Note!" automatically (same behavior
    already confirmed for dialog titles), so this window's own hardcoded
    "Take Note! —" prefix was a redundant duplicate. Every other window
    in the app already just sets its own plain descriptive title."""
    manager = _fake_manager()
    browser = NotesManagerWindow(manager)

    assert browser.windowTitle() == "Notes Manager"


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
    browser = NotesManagerWindow(manager)
    header = browser.table.horizontalHeader()

    assert header.minimumSectionSize() == header.sectionSizeHint(1)
