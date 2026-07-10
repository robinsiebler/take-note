from __future__ import annotations

from unittest.mock import Mock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from take_note.models import Board, Note
from take_note.notes_browser import ALL_NOTES, UNFILED, NotesBrowserWindow


def _note_window(body_text: str = "", **kwargs) -> Mock:
    note_window = Mock()
    note_window.note = Note(**kwargs)
    note_window.body.toPlainText.return_value = body_text
    return note_window


def _board_window(**kwargs) -> Mock:
    board_window = Mock()
    board_window.board = Board(**kwargs)
    return board_window


def _fake_manager(notes=None, boards=None) -> Mock:
    manager = Mock()
    manager.notes = notes or {}
    manager.boards = boards or {}
    manager.notes_changed = Mock()
    return manager


def _tree_labels(browser: NotesBrowserWindow) -> list[str]:
    return [browser.tree.topLevelItem(i).text(0) for i in range(browser.tree.topLevelItemCount())]


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

    browser._delete_selected_note()

    manager.delete_note.assert_called_once_with(n1)


def test_delete_selected_note_does_nothing_when_declined(qapp, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.No))
    n1 = _note_window(title="Groceries")
    manager = _fake_manager(notes={n1.note.id: n1})
    browser = NotesBrowserWindow(manager)
    browser.table.selectRow(0)

    browser._delete_selected_note()

    manager.delete_note.assert_not_called()


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
