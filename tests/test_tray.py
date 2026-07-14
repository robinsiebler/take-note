from __future__ import annotations

from unittest.mock import Mock

from take_note.models import Board
from take_note.tray import TrayIcon


def _fake_manager(boards=None) -> Mock:
    manager = Mock()
    manager.boards = boards or {}
    return manager


def _fake_board_window(name: str, visible: bool = True) -> Mock:
    board_window = Mock()
    board_window.board = Board(name=name)
    board_window.isVisible.return_value = visible
    return board_window


def test_notepads_menu_disabled_when_no_boards(qapp):
    tray = TrayIcon(_fake_manager())

    tray._populate_notepads_menu()

    assert not tray.notepads_menu.isEnabled()
    assert tray.notepads_menu.actions() == []


def test_notepads_menu_lists_each_board_by_name(qapp):
    work = _fake_board_window("Work")
    personal = _fake_board_window("Personal")
    manager = _fake_manager({work.board.id: work, personal.board.id: personal})
    tray = TrayIcon(manager)

    tray._populate_notepads_menu()

    assert tray.notepads_menu.isEnabled()
    assert [a.text() for a in tray.notepads_menu.actions()] == ["Work", "Personal"]


def test_notepads_menu_checkmark_reflects_board_visibility(qapp):
    shown = _fake_board_window("Work", visible=True)
    hidden = _fake_board_window("Personal", visible=False)
    manager = _fake_manager({shown.board.id: shown, hidden.board.id: hidden})
    tray = TrayIcon(manager)

    tray._populate_notepads_menu()

    actions = {a.text(): a for a in tray.notepads_menu.actions()}
    assert actions["Work"].isChecked()
    assert not actions["Personal"].isChecked()


def test_notepads_menu_rebuilds_on_every_open(qapp):
    """Regression-guard: a board created mid-session must show up next
    time the tray menu opens, not just at TrayIcon construction time."""
    manager = _fake_manager()
    tray = TrayIcon(manager)
    tray._populate_notepads_menu()
    assert tray.notepads_menu.actions() == []

    new_board = _fake_board_window("Errands")
    manager.boards[new_board.board.id] = new_board
    tray.menu.aboutToShow.emit()

    assert [a.text() for a in tray.notepads_menu.actions()] == ["Errands"]


def test_checking_a_hidden_board_shows_and_raises_it(qapp):
    board_window = _fake_board_window("Work", visible=False)
    manager = _fake_manager({board_window.board.id: board_window})
    tray = TrayIcon(manager)
    tray._populate_notepads_menu()
    action = tray.notepads_menu.actions()[0]

    action.setChecked(True)

    board_window.showNormal.assert_called_once()
    board_window.raise_.assert_called_once()
    board_window.activateWindow.assert_called_once()
    board_window.hide.assert_not_called()


def test_unchecking_a_visible_board_hides_it(qapp):
    board_window = _fake_board_window("Work", visible=True)
    manager = _fake_manager({board_window.board.id: board_window})
    tray = TrayIcon(manager)
    tray._populate_notepads_menu()
    action = tray.notepads_menu.actions()[0]

    action.setChecked(False)

    board_window.hide.assert_called_once()
    board_window.showNormal.assert_not_called()
