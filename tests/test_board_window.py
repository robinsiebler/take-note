from __future__ import annotations

from PySide6.QtCore import QPoint

from take_note.board_window import NotepadWindow
from take_note.models import Board, Note, Settings
from take_note.note_window import NoteWindow


class FakeManager:
    boards = {}
    settings = Settings()


def test_empty_board_canvas_matches_viewport_not_a_fixed_minimum(qapp):
    """Regression: the canvas used to have a flat setMinimumSize(600, 600)
    — bigger than the board's own default window size (400x300) — which
    forced a scrollbar with zero content anywhere near an edge."""
    board = NotepadWindow(Board(), FakeManager())

    assert not board.scroll.horizontalScrollBar().isVisible()
    assert not board.scroll.verticalScrollBar().isVisible()


def test_board_with_one_small_note_shows_no_scrollbar(qapp):
    board = NotepadWindow(Board(), FakeManager())
    note = NoteWindow(Note(color="#80deea"), FakeManager())
    note.show()
    note.attach_to_board(board, pos=QPoint(20, 20))

    assert not board.scroll.horizontalScrollBar().isVisible()
    assert not board.scroll.verticalScrollBar().isVisible()


def test_canvas_grows_when_note_dragged_beyond_viewport(qapp):
    board = NotepadWindow(Board(), FakeManager())
    note = NoteWindow(Note(color="#80deea"), FakeManager())
    note.show()
    note.attach_to_board(board, pos=QPoint(20, 20))
    before = board.canvas.size()

    note.move(700, 500)

    after = board.canvas.size()
    assert after.width() > before.width()
    assert after.height() > before.height()
    assert after.width() >= 700 + note.width()
    assert after.height() >= 500 + note.height()


def test_canvas_shrinks_back_after_note_moved_back(qapp):
    board = NotepadWindow(Board(), FakeManager())
    note = NoteWindow(Note(color="#80deea"), FakeManager())
    note.show()
    note.attach_to_board(board, pos=QPoint(20, 20))
    note.move(700, 500)
    grown = board.canvas.size()

    note.move(20, 20)

    shrunk = board.canvas.size()
    assert shrunk.width() < grown.width()
    assert shrunk.height() < grown.height()
    assert not board.scroll.horizontalScrollBar().isVisible()
    assert not board.scroll.verticalScrollBar().isVisible()


def test_canvas_recomputes_when_board_window_resized(qapp):
    board = NotepadWindow(Board(), FakeManager())

    board.resize(900, 700)

    viewport = board.scroll.viewport().size()
    assert board.canvas.width() >= viewport.width()
    assert board.canvas.height() >= viewport.height()


def test_detached_note_move_does_not_touch_any_canvas(qapp):
    """A standalone note's moveEvent must not blow up just because it has
    no board — _notify_board_canvas() should be a no-op for it."""
    note = NoteWindow(Note(color="#80deea"), FakeManager())
    note.show()

    note.move(300, 300)  # must not raise

    assert note.note.board_id is None
