from __future__ import annotations

from PySide6.QtGui import QTextCursor, QTextListFormat

from take_note.list_markers import marker_gutter_rect, marker_text, to_alpha, to_roman
from take_note.models import Note, Settings
from take_note.note_window import NoteWindow


class FakeManager:
    boards = {}
    settings = Settings()


def make_note_window(text=""):
    win = NoteWindow(Note(), manager=FakeManager())
    if text:
        win.body.setPlainText(text)
    return win


def select_all(win):
    cursor = win.body.textCursor()
    cursor.select(QTextCursor.Document)
    win.body.setTextCursor(cursor)


def test_to_alpha_wraps_past_z_as_bijective_base26():
    assert to_alpha(1) == "a"
    assert to_alpha(26) == "z"
    assert to_alpha(27) == "aa"
    assert to_alpha(28) == "ab"


def test_to_roman_standard_subtractive_notation():
    assert to_roman(1) == "I"
    assert to_roman(4) == "IV"
    assert to_roman(9) == "IX"
    assert to_roman(40) == "XL"
    assert to_roman(1994) == "MCMXCIV"


def test_marker_text_disc_has_no_text_marker():
    assert marker_text(QTextListFormat.ListDisc, 1) is None
    assert marker_text(QTextListFormat.ListCircle, 1) is None
    assert marker_text(QTextListFormat.ListSquare, 1) is None


def test_marker_text_checklist_has_no_text_marker():
    assert marker_text(QTextListFormat.ListStyleUndefined, 1) is None


def test_marker_text_numbered_styles_end_with_a_period():
    """Confirmed against Qt's own native rendering of each style — every
    numbered marker ends with a literal period, no other punctuation."""
    assert marker_text(QTextListFormat.ListDecimal, 3) == "3."
    assert marker_text(QTextListFormat.ListLowerAlpha, 27) == "aa."
    assert marker_text(QTextListFormat.ListUpperAlpha, 27) == "AA."
    assert marker_text(QTextListFormat.ListLowerRoman, 40) == "xl."
    assert marker_text(QTextListFormat.ListUpperRoman, 40) == "XL."


def test_marker_gutter_rect_matches_indent_width_and_cursor_position(qapp):
    win = make_note_window("Item one")
    select_all(win)
    win._set_list_style(QTextListFormat.ListDecimal)

    block = win.body.document().findBlockByNumber(0)
    gutter = marker_gutter_rect(win.body, block)
    row_left = win.body.cursorRect(QTextCursor(block)).left()

    assert gutter.right() == row_left
    assert gutter.width() == win.body.document().indentWidth()


def test_painting_list_markers_never_triggers_a_document_change(qapp):
    """Regression guard for a rejected approach: an earlier prototype
    suppressed Qt's native marker glyph by swapping QTextListFormat.style()
    for the duration of one paintEvent, then restoring it — but even a
    synchronous restore fires contentsChanged/modificationChanged/
    textChanged, which in the real app schedules a disk save via
    NoteManager._schedule_save() on every repaint (cursor blink, scroll,
    resize). The actual fix never touches QTextList/QTextListFormat data
    at all, so repainting a list-containing note must never fire
    textChanged."""
    win = make_note_window("First\nSecond\nThird\nFourth")
    select_all(win)
    win._set_list_style(QTextListFormat.ListDisc)

    changed = {"count": 0}
    win.body.textChanged.connect(lambda: changed.__setitem__("count", changed["count"] + 1))

    for _ in range(5):
        win.body.repaint()

    assert changed["count"] == 0


def test_painting_checklist_markers_never_triggers_a_document_change(qapp):
    win = make_note_window("Buy milk\nWalk the dog")
    select_all(win)
    win._set_list_style(QTextListFormat.ListStyleUndefined)
    win._toggle_checklist_item(win.body.document().findBlockByNumber(0))

    changed = {"count": 0}
    win.body.textChanged.connect(lambda: changed.__setitem__("count", changed["count"] + 1))

    for _ in range(5):
        win.body.repaint()

    assert changed["count"] == 0
