from __future__ import annotations

from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtGui import QKeyEvent, QTextCursor, QTextListFormat
from PySide6.QtWidgets import QMenu, QMessageBox, QToolButton

from take_note.models import Note
from take_note.note_window import NoteWindow


class FakeManager:
    boards = {}


def make_note_window(text=""):
    win = NoteWindow(Note(), manager=FakeManager())
    if text:
        win.body.setPlainText(text)
    return win


def goto_block(win, index):
    cursor = win.body.textCursor()
    cursor.movePosition(QTextCursor.Start)
    for _ in range(index):
        cursor.movePosition(QTextCursor.NextBlock)
    win.body.setTextCursor(cursor)


def select_all(win):
    cursor = win.body.textCursor()
    cursor.select(QTextCursor.Document)
    win.body.setTextCursor(cursor)


def test_set_list_style_creates_list(qapp):
    win = make_note_window("Item one")
    select_all(win)
    win._set_list_style(QTextListFormat.ListDecimal)

    block = win.body.document().findBlockByNumber(0)
    assert block.textList() is not None
    assert block.textList().format().style() == QTextListFormat.ListDecimal


def test_set_list_style_none_removes_list(qapp):
    win = make_note_window("Item one")
    select_all(win)
    win._set_list_style(QTextListFormat.ListDecimal)
    select_all(win)
    win._set_list_style(None)

    block = win.body.document().findBlockByNumber(0)
    assert block.textList() is None


def test_set_list_style_applies_across_multiblock_selection(qapp):
    """Regression: converting a multi-item list's style used to read only
    cursor.currentList() (a single position), silently skipping every list
    the selection touched besides the one at the cursor's active end —
    reported as "only the 1st bullet converted" when items were at
    different nesting depths (each depth is its own QTextList)."""
    win = make_note_window("Fix Dinner\nGrate Cheese\nGet Cheese")
    select_all(win)
    win._set_list_style(QTextListFormat.ListDisc)

    goto_block(win, 1)
    win._increase_indent()
    goto_block(win, 2)
    win._increase_indent()
    win._increase_indent()

    select_all(win)
    win._set_list_style(QTextListFormat.ListUpperRoman)

    doc = win.body.document()
    for i in range(3):
        block = doc.findBlockByNumber(i)
        assert block.textList().format().style() == QTextListFormat.ListUpperRoman


def test_increase_indent_creates_nested_list(qapp):
    win = make_note_window("Alpha\nBeta")
    select_all(win)
    win._set_list_style(QTextListFormat.ListDecimal)

    goto_block(win, 1)
    win._increase_indent()

    doc = win.body.document()
    alpha_list = doc.findBlockByNumber(0).textList()
    beta_list = doc.findBlockByNumber(1).textList()
    assert beta_list is not alpha_list
    assert beta_list.format().indent() == alpha_list.format().indent() + 1


def test_increase_indent_joins_adjacent_sibling_list(qapp):
    win = make_note_window("Alpha\nBeta\nGamma")
    select_all(win)
    win._set_list_style(QTextListFormat.ListDecimal)

    goto_block(win, 1)
    win._increase_indent()
    goto_block(win, 2)
    win._increase_indent()

    doc = win.body.document()
    beta_list = doc.findBlockByNumber(1).textList()
    gamma_list = doc.findBlockByNumber(2).textList()
    assert beta_list is gamma_list


def test_decrease_indent_rejoins_parent_list_and_resyncs_block_indent(qapp):
    """Regression: rejoining an existing list via QTextList.add() left the
    block's own (separate) indent level stale, visually narrowing/wrapping
    the line even though the list-nesting data itself was correct."""
    win = make_note_window("Alpha\nBeta\nGamma")
    select_all(win)
    win._set_list_style(QTextListFormat.ListDecimal)

    goto_block(win, 1)
    win._increase_indent()
    goto_block(win, 2)
    win._increase_indent()

    goto_block(win, 2)
    win._decrease_indent()

    doc = win.body.document()
    alpha_block = doc.findBlockByNumber(0)
    gamma_block = doc.findBlockByNumber(2)
    assert gamma_block.textList() is alpha_block.textList()
    assert gamma_block.blockFormat().indent() == alpha_block.blockFormat().indent()


def test_decrease_indent_below_top_level_removes_list(qapp):
    win = make_note_window("Item one")
    select_all(win)
    win._set_list_style(QTextListFormat.ListDecimal)

    win._decrease_indent()

    block = win.body.document().findBlockByNumber(0)
    assert block.textList() is None
    assert block.blockFormat().indent() == 0


def test_set_text_color_recolors_list_marker_without_corrupting_layout(qapp):
    """Regression: mergeBlockCharFormat on a selection ending exactly at
    EndOfBlock (not crossing into the next block) corrupted that list
    item's cached layout rect in Qt, collapsing it to zero size so the
    line stopped painting entirely instead of just staying the old color."""
    win = make_note_window("Fix Dinner")
    select_all(win)
    win._set_list_style(QTextListFormat.ListDecimal)

    win.body.moveCursor(QTextCursor.End)
    win.body.insertPlainText("\n")

    cursor = win.body.textCursor()
    cursor.movePosition(QTextCursor.Start)
    cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
    win.body.setTextCursor(cursor)

    win._set_text_color("#c62828")
    qapp.processEvents()

    doc = win.body.document()
    layout = doc.documentLayout()
    block0 = doc.findBlockByNumber(0)
    rect = layout.blockBoundingRect(block0)
    assert rect.width() > 0
    assert rect.height() > 0
    assert block0.charFormat().foreground().color().name() == "#c62828"


def test_indent_width_smaller_than_qt_default(qapp):
    win = make_note_window()
    assert win.body.document().indentWidth() < 40.0


def test_indent_width_fits_widest_common_list_marker(qapp):
    """Regression: Qt renders a list marker glyph ending flush at the
    indent boundary — a marker wider than indentWidth overflows past the
    note's own left edge rather than just sitting close to it (reported:
    "a." nearly clipped off the left edge after cycling bullet styles)."""
    from PySide6.QtGui import QFontMetrics

    win = make_note_window()
    fm = QFontMetrics(win.body.font())
    widest_marker = max(
        fm.horizontalAdvance(marker)
        for marker in ["1.", "a.", "A.", "i.", "ii.", "iii.", "iv.", "v.", "vi.", "vii.", "viii."]
    )
    assert win.body.document().indentWidth() >= widest_marker


def test_delete_confirmation_dialog_forces_stays_on_top(qapp, monkeypatch):
    """Regression: a plain child QMessageBox didn't reliably outrank this
    note's own raw EWMH always-on-top state in KWin's stacking layers,
    so the delete confirmation could end up hidden behind the note."""
    win = make_note_window()

    captured = {}

    def fake_exec(self):
        captured["stays_on_top"] = bool(self.windowFlags() & Qt.WindowStaysOnTopHint)
        return QMessageBox.No

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    win.confirm_delete()

    assert captured["stays_on_top"] is True


def test_bullets_menu_checks_none_for_plain_note(qapp):
    win = make_note_window("Just plain text")
    menu = QMenu()
    win.populate_text_menu(menu)

    checked = [action.text() for style, action in win.list_style_actions if action.isChecked()]
    assert checked == ["None"]


def test_bullets_menu_checks_current_style(qapp):
    win = make_note_window("Item one")
    select_all(win)
    win._set_list_style(QTextListFormat.ListDecimal)

    menu = QMenu()
    win.populate_text_menu(menu)

    checked = [action.text() for style, action in win.list_style_actions if action.isChecked()]
    assert checked == ["1, 2, 3"]


def test_text_menu_excludes_whole_note_actions(qapp):
    """Regression: right-clicking selected text used to show whole-note
    actions (Change Color, Transparency, Always on Top, Memoboard,
    Delete) alongside text formatting, which doesn't make sense mid-
    selection — those now live only in the note-actions menu."""
    win = make_note_window("Some text")
    menu = QMenu()
    win.populate_text_menu(menu)

    titles = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert titles == [
        "Font Style",
        "Font Color…",
        "Bullets && Numbering",
        "Increase Indent",
        "Decrease Indent",
    ]


def test_note_actions_menu_excludes_text_formatting(qapp):
    win = make_note_window("Some text")
    menu = QMenu()
    win.populate_note_actions_menu(menu)

    titles = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert titles == [
        "Change Note Color…",
        "Note Transparency",
        "Always on Top",
        "Add to Memoboard",
        "Delete Note",
    ]


def test_opacity_action_checked_matches_note_opacity_at_construction(qapp):
    win = NoteWindow(Note(opacity=0.55), manager=FakeManager())

    checked = [a.text() for a in win.opacity_actions if a.isChecked()]
    assert checked == ["High"]


def test_set_opacity_updates_note_and_exclusive_checked_state(qapp):
    win = make_note_window()
    full_action = next(a for a in win.opacity_actions if a.text() == "Full")

    full_action.trigger()

    assert win.note.opacity == 0.40
    assert win.windowOpacity() == 0.40
    checked = [a.text() for a in win.opacity_actions if a.isChecked()]
    assert checked == ["Full"]


def test_tab_key_indents_within_list(qapp):
    win = make_note_window("Item one")
    select_all(win)
    win._set_list_style(QTextListFormat.ListDecimal)

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_Tab, Qt.NoModifier)
    qapp.sendEvent(win.body, event)

    block = win.body.document().findBlockByNumber(0)
    assert block.textList().format().indent() == 2


def test_shift_tab_key_dedents_within_list(qapp):
    win = make_note_window("Item one")
    select_all(win)
    win._set_list_style(QTextListFormat.ListDecimal)

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_Backtab, Qt.ShiftModifier)
    qapp.sendEvent(win.body, event)

    block = win.body.document().findBlockByNumber(0)
    assert block.textList() is None


def test_tab_key_outside_list_does_not_create_one(qapp):
    """Outside a list, Tab must not be intercepted into an indent step —
    it should fall through to QTextEdit's own default handling instead."""
    win = make_note_window("plain text")
    cursor = win.body.textCursor()
    cursor.movePosition(QTextCursor.Start)
    win.body.setTextCursor(cursor)

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_Tab, Qt.NoModifier)
    qapp.sendEvent(win.body, event)

    assert win.body.document().findBlockByNumber(0).textList() is None


def test_set_text_color_on_plain_text(qapp):
    win = make_note_window("Hello World")
    select_all(win)

    win._set_text_color("#c62828")

    assert win.body.textColor().name() == "#c62828"


def test_show_font_color_menu_uses_font_swatches_and_applies_pick(qapp):
    """QMenu.exec() runs its own nested event loop that a plain Python
    monkeypatch of QMenu.exec can't intercept (Shiboken-wrapped methods
    aren't overridden by simple attribute assignment — confirmed this
    silently falls through to the real, blocking exec()). Scheduling the
    swatch click via a QTimer fired *during* that nested loop is the
    reliable way to drive a modal popup in a test."""
    from take_note.models import FONT_SWATCHES

    win = make_note_window("Hello World")
    select_all(win)

    captured = {}

    def click_first_swatch():
        popup = qapp.activePopupWidget()
        assert popup is not None
        buttons = popup.findChildren(QToolButton)
        captured["swatch_count"] = len(buttons)
        buttons[0].click()  # first FONT_SWATCHES entry ("#000000", black)

    QTimer.singleShot(50, click_first_swatch)
    win.show_font_color_menu(win.body)  # blocks until the swatch click closes it

    assert captured["swatch_count"] == len(FONT_SWATCHES)
    assert win.body.textColor().name() == "#000000"


def test_set_always_on_top_updates_note_flag(qapp):
    win = make_note_window()
    assert win.note.always_on_top is True

    win.set_always_on_top(False)
    assert win.note.always_on_top is False

    win.set_always_on_top(True)
    assert win.note.always_on_top is True


def test_toggle_rolled_collapses_and_expands(qapp):
    win = make_note_window()
    assert win.note.rolled_up is False

    win.toggle_rolled()
    assert win.note.rolled_up is True
    assert win.body.isHidden()

    win.toggle_rolled()
    assert win.note.rolled_up is False
    assert not win.body.isHidden()
