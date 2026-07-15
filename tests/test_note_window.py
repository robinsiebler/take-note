from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QDateTime, QEvent, QObject, QPointF, QTimer, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextListFormat,
)
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFontDialog,
    QInputDialog,
    QLineEdit,
    QMenu,
    QMessageBox,
    QToolButton,
    QWidget,
)

from take_note.models import Board, Note, Settings
from take_note import spellcheck
from take_note.note_window import NoteWindow, _detect_url_span, _ReminderDialog, find_bar_tint
from take_note.reminders import local_datetime_to_utc_iso


class FakeManager:
    boards = {}
    settings = Settings()


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


def test_set_list_style_on_multiline_selection_creates_one_shared_list(qapp):
    """Regression: creating a list from a multi-line selection called
    createList() separately per block, producing N independent
    single-item lists instead of one shared list — each one started
    counting from 1, so every item in a numbered list showed "1."
    instead of incrementing 1, 2, 3, 4. Reported live after converting a
    4-item bulleted list to numbers and seeing every line read "1."."""
    win = make_note_window("carrots\ncelery\nbacon\nbread")
    select_all(win)

    win._set_list_style(QTextListFormat.ListDecimal)

    doc = win.body.document()
    lists = [doc.findBlockByNumber(i).textList() for i in range(4)]
    assert len({id(lst) for lst in lists}) == 1, "expected one shared list, got several"
    for i in range(4):
        block = doc.findBlockByNumber(i)
        assert block.textList().itemNumber(block) == i


def test_set_list_style_none_removes_list(qapp):
    win = make_note_window("Item one")
    select_all(win)
    win._set_list_style(QTextListFormat.ListDecimal)
    select_all(win)
    win._set_list_style(None)

    block = win.body.document().findBlockByNumber(0)
    assert block.textList() is None


def test_set_list_style_none_over_nested_selection_resets_block_indent(qapp):
    """Regression, reported live via a screenshot: selecting a multi-level
    nested list and choosing "None" removed every bullet, but each line
    stayed staggered at its old nesting depth as plain paragraph indent
    instead of resetting flush — QTextList.remove() transfers the list's
    old nesting indent onto the block's own blockFormat().indent() rather
    than snapping it back to 0."""
    win = make_note_window("Item 1\nItem 1 a\nItem 2")
    select_all(win)
    win._set_list_style(QTextListFormat.ListDisc)
    goto_block(win, 1)
    win._increase_indent()

    select_all(win)
    win._set_list_style(None)

    doc = win.body.document()
    for i in range(3):
        block = doc.findBlockByNumber(i)
        assert block.textList() is None
        assert block.blockFormat().indent() == 0


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


def _checklist_gutter_center(win, index):
    from take_note.list_markers import marker_gutter_rect

    block = win.body.document().findBlockByNumber(index)
    return marker_gutter_rect(win.body, block).center()


def test_set_list_style_checklist_defaults_new_items_unchecked(qapp):
    win = make_note_window("Buy milk\nWalk the dog")
    select_all(win)
    win._set_list_style(QTextListFormat.ListStyleUndefined)

    doc = win.body.document()
    for i in range(2):
        block = doc.findBlockByNumber(i)
        assert block.textList().format().style() == QTextListFormat.ListStyleUndefined
        assert block.blockFormat().marker() == QTextBlockFormat.MarkerType.Unchecked


def test_set_list_style_none_clears_checklist_marker(qapp):
    win = make_note_window("Buy milk")
    select_all(win)
    win._set_list_style(QTextListFormat.ListStyleUndefined)
    win._toggle_checklist_item(win.body.document().findBlockByNumber(0))

    select_all(win)
    win._set_list_style(None)

    block = win.body.document().findBlockByNumber(0)
    assert block.textList() is None
    assert block.blockFormat().marker() == QTextBlockFormat.MarkerType.NoMarker


def test_converting_a_single_checklist_item_does_not_affect_its_siblings(qapp):
    """The serious one, reported live: selecting and converting just ONE
    item out of a multi-item shared checklist silently converted every
    sibling too — since several checklist items sharing one QTextList
    (created together, e.g. via one multi-line selection) is exactly how
    numbering/grouping stays in sync, and the old code's
    current_list.setFormat() applied to that *entire* list object
    regardless of which single block's cursor triggered the change.
    "Convert the whole list" already worked correctly before this fix
    (still covered by test_set_list_style_applies_across_multiblock_
    selection) — this is specifically the partial-selection case."""
    win = make_note_window("carrots\nbacon\ncheese")
    select_all(win)
    win._set_list_style(QTextListFormat.ListStyleUndefined)
    doc = win.body.document()
    win._toggle_checklist_item(doc.findBlockByNumber(1))  # check "bacon"

    # Select only "bacon" (no real text selection needed — a bare caret in
    # that block already reaches the no-selection/_apply_real_style_to_blocks
    # path with just that one block) and convert just it.
    cursor = win.body.textCursor()
    cursor.setPosition(doc.findBlockByNumber(1).position())
    win.body.setTextCursor(cursor)
    win._set_list_style(QTextListFormat.ListDecimal)

    carrots = doc.findBlockByNumber(0)
    bacon = doc.findBlockByNumber(1)
    cheese = doc.findBlockByNumber(2)
    assert carrots.textList().format().style() == QTextListFormat.ListStyleUndefined
    assert cheese.textList().format().style() == QTextListFormat.ListStyleUndefined
    assert bacon.textList().format().style() == QTextListFormat.ListDecimal
    # carrots/cheese must still be one shared list together (just without
    # bacon), not two independent single-item lists.
    # == (Qt's own equality), not is — id() isn't stable across separate
    # QTextList wrapper fetches, same trap the app-code fix above avoids.
    assert carrots.textList() == cheese.textList()
    assert carrots.textList() != bacon.textList()
    # bacon left Checklist entirely, so its checked-item marker/formatting
    # clears too (same fix as test_switching_a_checked_item_to_another_
    # style_also_clears_its_text_formatting).
    assert bacon.blockFormat().marker() == QTextBlockFormat.MarkerType.NoMarker


def test_switching_checklist_item_to_another_style_clears_its_marker(qapp):
    """A block's marker() is only meaningful while its own list style is
    still Checklist — switching to e.g. Bullets should clear any stale
    Checked/Unchecked left over, not silently keep it around."""
    win = make_note_window("Buy milk")
    select_all(win)
    win._set_list_style(QTextListFormat.ListStyleUndefined)
    win._toggle_checklist_item(win.body.document().findBlockByNumber(0))

    select_all(win)
    win._set_list_style(QTextListFormat.ListDisc)

    block = win.body.document().findBlockByNumber(0)
    assert block.blockFormat().marker() == QTextBlockFormat.MarkerType.NoMarker


def test_switching_a_checked_item_to_another_style_also_clears_its_text_formatting(qapp):
    """Regression, reported live: converting a *checked* item to Numbers
    correctly dropped the checkbox but left the text permanently grey and
    strikethrough — this formatting was never a deliberate user choice
    (unlike, say, remove_hyperlink()'s unavoidable tradeoff), it's
    entirely auto-applied by this app's own checkbox toggle, so switching
    away from Checklist should auto-clear it too."""
    win = make_note_window("Wash dishes")
    select_all(win)
    win._set_list_style(QTextListFormat.ListStyleUndefined)
    block = win.body.document().findBlockByNumber(0)
    win._toggle_checklist_item(block)  # check it

    select_all(win)
    win._set_list_style(QTextListFormat.ListDecimal)

    block = win.body.document().findBlockByNumber(0)
    cursor = QTextCursor(block)
    cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
    fmt = cursor.charFormat()
    assert fmt.fontStrikeOut() is False
    assert fmt.foreground().color().name() != "#888888"


def test_switching_an_unchecked_item_to_another_style_does_not_touch_its_formatting(qapp):
    """An unchecked item was never given the grey/strikethrough treatment
    in the first place, so switching its style shouldn't merge any new
    formatting over it either — confirms the fix above is conditional on
    was_checked, not an unconditional reset that could clobber a user's
    own deliberate text color on an unchecked item."""
    win = make_note_window("Wash dishes")
    select_all(win)
    win._set_list_style(QTextListFormat.ListStyleUndefined)
    block = win.body.document().findBlockByNumber(0)
    cursor = QTextCursor(block)
    cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
    custom = QTextCharFormat()
    custom.setForeground(QColor("#ff0000"))
    cursor.mergeCharFormat(custom)

    select_all(win)
    win._set_list_style(QTextListFormat.ListDecimal)

    block = win.body.document().findBlockByNumber(0)
    cursor = QTextCursor(block)
    cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
    assert cursor.charFormat().foreground().color().name() == "#ff0000"


def test_toggle_checklist_marker_at_gutter_click_checks_item(qapp):
    win = make_note_window("Buy milk\nWalk the dog")
    select_all(win)
    win._set_list_style(QTextListFormat.ListStyleUndefined)

    hit = win._toggle_checklist_marker_at(_checklist_gutter_center(win, 0))

    block = win.body.document().findBlockByNumber(0)
    assert hit is True
    assert block.blockFormat().marker() == QTextBlockFormat.MarkerType.Checked


def test_toggle_checklist_marker_at_outside_gutter_does_nothing(qapp):
    win = make_note_window("Buy milk")
    select_all(win)
    win._set_list_style(QTextListFormat.ListStyleUndefined)

    hit = win._toggle_checklist_marker_at(QPointF(-1000, -1000))

    block = win.body.document().findBlockByNumber(0)
    assert hit is False
    assert block.blockFormat().marker() == QTextBlockFormat.MarkerType.Unchecked


def test_toggle_checklist_item_applies_and_clears_strikeout(qapp):
    win = make_note_window("Buy milk")
    select_all(win)
    win._set_list_style(QTextListFormat.ListStyleUndefined)
    block = win.body.document().findBlockByNumber(0)

    win._toggle_checklist_item(block)
    cursor = QTextCursor(block)
    cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
    assert cursor.charFormat().fontStrikeOut() is True

    win._toggle_checklist_item(block)
    cursor = QTextCursor(block)
    cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
    assert cursor.charFormat().fontStrikeOut() is False


def test_toggle_checklist_marker_survives_html_round_trip(qapp):
    """Also a regression guard: the checked item's strikeout/color merge
    originally extended through the block's trailing separator character
    (matching _merge_block_format_over_selection's own range, added there
    for an unrelated layout-corruption fix) — confirmed live this leaked
    the checked formatting onto the *next* block once round-tripped
    through toHtml()/setHtml(), striking through "Finish report" even
    though only "Walk the dog" was ever checked."""
    win = make_note_window("Buy milk\nWalk the dog\nFinish report")
    select_all(win)
    win._set_list_style(QTextListFormat.ListStyleUndefined)
    doc = win.body.document()
    win._toggle_checklist_item(doc.findBlockByNumber(1))

    html = win.body.toHtml()
    reloaded = make_note_window("")
    reloaded.body.setHtml(html)

    doc2 = reloaded.body.document()
    markers = [doc2.findBlockByNumber(i).blockFormat().marker() for i in range(3)]
    assert markers == [
        QTextBlockFormat.MarkerType.Unchecked,
        QTextBlockFormat.MarkerType.Checked,
        QTextBlockFormat.MarkerType.Unchecked,
    ]

    def strikeout_at(i):
        block = doc2.findBlockByNumber(i)
        cursor = QTextCursor(block)
        cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        return cursor.charFormat().fontStrikeOut()

    assert strikeout_at(0) is False
    assert strikeout_at(1) is True
    assert strikeout_at(2) is False


def test_checklist_style_survives_a_full_note_reload(qapp):
    """The serious one, reported live: a saved checklist reopened as a
    plain bulleted list. Root cause confirmed directly — Qt's own
    toHtml() export of a ListStyleUndefined list carries no
    list-style-type CSS at all, so its own HTML parser silently defaults
    a bare <ul> back to ListDisc on reload. marker() survives
    independently (already covered by the round-trip test above), which
    is exactly why the *checked* item kept its grey/strikethrough even
    though the whole list rendered as bullets — the underlying data
    looked checked, but paint_list_markers()/_current_list_style() both
    key off style() == ListStyleUndefined, not marker() alone. Goes
    through the real NoteWindow(Note(html=...)) constructor, not a bare
    setHtml() call, since the fix lives in __init__'s post-load heal
    pass."""
    win = make_note_window("Buy milk\nWalk the dog\nFinish report")
    select_all(win)
    win._set_list_style(QTextListFormat.ListStyleUndefined)
    win._toggle_checklist_item(win.body.document().findBlockByNumber(1))
    html = win.body.toHtml()

    reloaded = NoteWindow(Note(html=html), manager=FakeManager())

    doc = reloaded.body.document()
    for i in range(3):
        block = doc.findBlockByNumber(i)
        assert block.textList().format().style() == QTextListFormat.ListStyleUndefined
    assert doc.findBlockByNumber(1).blockFormat().marker() == QTextBlockFormat.MarkerType.Checked


def test_checklist_style_reload_does_not_affect_ordinary_lists(qapp):
    """The healing pass after load only touches lists that actually have
    a real marker on them — an ordinary Bullets/Numbers list (never a
    checklist at all) must come back exactly as saved, not get pulled
    into Checklist just because it's a list."""
    win = make_note_window("carrots\ncelery")
    select_all(win)
    win._set_list_style(QTextListFormat.ListDecimal)
    html = win.body.toHtml()

    reloaded = NoteWindow(Note(html=html), manager=FakeManager())

    doc = reloaded.body.document()
    for i in range(2):
        assert doc.findBlockByNumber(i).textList().format().style() == QTextListFormat.ListDecimal


def test_toggle_checklist_marker_blocked_when_locked(qapp):
    win = make_note_window("Buy milk")
    select_all(win)
    win._set_list_style(QTextListFormat.ListStyleUndefined)
    win.set_locked(True)

    hit = win._toggle_checklist_marker_at(_checklist_gutter_center(win, 0))

    block = win.body.document().findBlockByNumber(0)
    assert hit is False
    assert block.blockFormat().marker() == QTextBlockFormat.MarkerType.Unchecked


def test_enter_after_checked_item_does_not_inherit_strikeout(qapp):
    """Regression: Qt's own list continuation already resets a freshly
    created item's marker() to Unchecked on Enter, but that's a completely
    separate mechanism from char-format inheritance — confirmed live the
    new item's *text* kept the previous (checked) item's strikethrough and
    grey color even though its checkbox correctly rendered empty."""
    win = make_note_window("Finish report")
    select_all(win)
    win._set_list_style(QTextListFormat.ListStyleUndefined)
    block = win.body.document().findBlockByNumber(0)
    win._toggle_checklist_item(block)

    cursor = win.body.textCursor()
    cursor.movePosition(QTextCursor.End)
    win.body.setTextCursor(cursor)
    event = QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier)
    qapp.sendEvent(win.body, event)
    win.body.insertPlainText("Buy stamps")

    new_block = win.body.textCursor().block()
    assert new_block.blockFormat().marker() == QTextBlockFormat.MarkerType.Unchecked
    cursor = QTextCursor(new_block)
    cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
    assert cursor.charFormat().fontStrikeOut() is False


def test_enter_after_checked_item_fixes_the_new_checkbox_color_immediately(qapp):
    """Regression, reported live: the fix above (mergeCurrentCharFormat)
    only corrects what the *next keystroke* produces — it doesn't touch
    the block's own char format, which is what list_markers.py's
    _leading_char_format() actually reads to color the checkbox itself.
    Before this fix, a brand-new item's checkbox rendered pale/grey right
    after pressing Enter, only turning the normal color once text was
    actually typed into it. Probes the block's own format directly
    (a fresh QTextCursor at block.position(), same read
    _leading_char_format() does) rather than the live editing cursor,
    since that's specifically the read that stayed wrong before."""
    win = make_note_window("Finish report")
    select_all(win)
    win._set_list_style(QTextListFormat.ListStyleUndefined)
    win._toggle_checklist_item(win.body.document().findBlockByNumber(0))

    cursor = win.body.textCursor()
    cursor.movePosition(QTextCursor.End)
    win.body.setTextCursor(cursor)
    event = QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier)
    qapp.sendEvent(win.body, event)

    new_block = win.body.textCursor().block()
    probe = QTextCursor(win.body.document())
    probe.setPosition(new_block.position())
    assert probe.charFormat().foreground().color().name() != "#888888"


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


def test_increase_indent_does_not_compound_block_indent_at_deeper_levels(qapp):
    """Regression: the block-indent resync above used `new_indent - 1` as
    the "correct" absolute indent value, which only coincidentally equals
    0 at the first nesting level — for anything deeper it left a real,
    nonzero block indent stacked *on top of* the list's own nesting
    indent, compounding at every level. Reported live as a sub-bullet
    rendering much further right than one extra nesting level should
    produce. A list item's own blockFormat().indent() should always stay
    0 — the list's own indent() alone carries the nesting weight,
    confirmed by checking a never-touched top-level item."""
    win = make_note_window("Alpha\nBeta")
    select_all(win)
    win._set_list_style(QTextListFormat.ListDisc)

    goto_block(win, 1)
    win._increase_indent()  # level 2, brand-new list (no adjacent sibling)

    doc = win.body.document()
    alpha_block = doc.findBlockByNumber(0)
    beta_block = doc.findBlockByNumber(1)
    assert alpha_block.blockFormat().indent() == 0
    assert beta_block.blockFormat().indent() == 0
    assert beta_block.textList().format().indent() == alpha_block.textList().format().indent() + 1


def test_increase_indent_over_multiline_selection_preserves_relative_nesting(qapp):
    """Regression, reported live via before/after screenshots: selecting a
    7-item, 4-level nested list and hitting Increase Indent once
    collapsed the entire thing into one flat, renumbered level instead of
    shifting each line one level deeper relative to where it already was.
    Root cause: _list_indent_step used to run createList() (in the "no
    adjacent list to rejoin" branch) against the *selection cursor
    itself*, and createList() on a cursor with an active multi-block
    selection folds every touched block into one shared list regardless
    of each one's own prior depth. Fixed by stepping each block
    individually via its own collapsed cursor."""
    win = make_note_window(
        "Item 1\nItem 1 a\nItem 2\nItem 2 a\nItem 2 b\nItem 2 c\nItem 3"
    )
    select_all(win)
    win._set_list_style(QTextListFormat.ListUpperRoman)

    # Build depths 0,1,0,1,2,3,0 one line at a time, matching how a real
    # user would via Tab/Increase Indent on each line individually.
    for block_index, times in [(1, 1), (3, 1), (4, 2), (5, 3)]:
        goto_block(win, block_index)
        for _ in range(times):
            win._increase_indent()

    doc = win.body.document()
    before_indents = [doc.findBlockByNumber(i).textList().format().indent() for i in range(7)]
    assert before_indents == [1, 2, 1, 2, 3, 4, 1]

    select_all(win)
    win._increase_indent()

    after_indents = [doc.findBlockByNumber(i).textList().format().indent() for i in range(7)]
    assert after_indents == [2, 3, 2, 3, 4, 5, 2]
    # Every block's own separate block-indent must still stay 0 — only
    # each list's own nesting indent should carry the extra depth.
    assert all(doc.findBlockByNumber(i).blockFormat().indent() == 0 for i in range(7))
    # Siblings that were in the same list before the shift (0/2/6, all
    # originally at depth 1) must still share one list afterward, not
    # fragment into separate ones.
    list0 = doc.findBlockByNumber(0).textList()
    list2 = doc.findBlockByNumber(2).textList()
    list6 = doc.findBlockByNumber(6).textList()
    assert list0 is list2 is list6


def test_decrease_indent_below_top_level_removes_list(qapp):
    win = make_note_window("Item one")
    select_all(win)
    win._set_list_style(QTextListFormat.ListDecimal)

    win._decrease_indent()

    block = win.body.document().findBlockByNumber(0)
    assert block.textList() is None
    assert block.blockFormat().indent() == 0


def test_delete_key_on_full_selection_leaves_no_stray_list_formatting(qapp):
    """Regression: Select All + Delete on a note with a multi-level list
    merges everything down to one empty block, but Qt's Delete-key path
    (unlike QTextCursor.removeSelectedText()) keeps that block's list
    membership/indent from whichever original block survived — reported
    as a stray bullet/number floating in an otherwise blank note."""
    win = make_note_window("Fix Dinner\nGrate Cheese")
    select_all(win)
    win._set_list_style(QTextListFormat.ListLowerAlpha)
    goto_block(win, 1)
    win._increase_indent()
    win._increase_indent()

    select_all(win)
    event = QKeyEvent(QEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier)
    qapp.sendEvent(win.body, event)

    block = win.body.document().findBlockByNumber(0)
    assert win.body.toPlainText() == ""
    assert block.textList() is None
    assert block.blockFormat().indent() == 0


def test_backspace_key_on_full_selection_leaves_no_stray_list_formatting(qapp):
    win = make_note_window("Item one")
    select_all(win)
    win._set_list_style(QTextListFormat.ListDecimal)

    select_all(win)
    event = QKeyEvent(QEvent.KeyPress, Qt.Key_Backspace, Qt.NoModifier)
    qapp.sendEvent(win.body, event)

    block = win.body.document().findBlockByNumber(0)
    assert win.body.toPlainText() == ""
    assert block.textList() is None
    assert block.blockFormat().indent() == 0


def test_delete_key_on_partial_selection_keeps_list_intact(qapp):
    """The empty-note cleanup must only fire when the whole document is
    actually empty — deleting one item's text while another item still
    has content shouldn't strip list formatting."""
    win = make_note_window("Item one\nItem two")
    select_all(win)
    win._set_list_style(QTextListFormat.ListDecimal)

    cursor = win.body.textCursor()
    cursor.movePosition(QTextCursor.Start)
    cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
    win.body.setTextCursor(cursor)
    event = QKeyEvent(QEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier)
    qapp.sendEvent(win.body, event)

    assert win.body.toPlainText() != ""
    block = win.body.document().findBlockByNumber(0)
    assert block.textList() is not None


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


def test_set_text_color_on_plain_last_block_does_not_corrupt_layout(qapp):
    """Regression: the fix above only ever prevented the corruption for a
    block with a real *following* block to extend the merge range into —
    the document's own last block has no such separator to extend into
    regardless, so a plain (non-list) single-line note recoloring its
    own only/last block hit the identical corruption (collapsed to zero
    size, stopped painting) despite never touching a list. Reported live
    as "the text literally disappeared" after applying Font Color to a
    selection on an ordinary note. Fixed by skipping the block-level
    merge entirely for non-list blocks — it only exists to recolor list
    markers, which a plain paragraph doesn't have."""
    win = make_note_window("This is a test")
    select_all(win)

    win._set_text_color("#e65100")
    qapp.processEvents()

    doc = win.body.document()
    layout = doc.documentLayout()
    block0 = doc.findBlockByNumber(0)
    rect = layout.blockBoundingRect(block0)
    assert rect.width() > 0
    assert rect.height() > 0
    assert win.body.toPlainText() == "This is a test"


def test_set_text_color_on_partial_selection_of_only_block_does_not_corrupt_layout(qapp):
    """Even a selection that doesn't reach the block's end at all (just
    the first word) triggered the same corruption — the block-level
    merge always re-derives its own range from the whole block's length,
    not the actual selection's real endpoints, so any selection merely
    touching the document's last block was enough."""
    win = make_note_window("This is a test")
    cursor = win.body.textCursor()
    cursor.movePosition(QTextCursor.Start)
    cursor.movePosition(QTextCursor.WordRight, QTextCursor.KeepAnchor)
    win.body.setTextCursor(cursor)

    win._set_text_color("#e65100")
    qapp.processEvents()

    doc = win.body.document()
    layout = doc.documentLayout()
    block0 = doc.findBlockByNumber(0)
    rect = layout.blockBoundingRect(block0)
    assert rect.width() > 0
    assert rect.height() > 0
    assert win.body.toPlainText() == "This is a test"


def test_set_text_color_on_list_items_last_block_does_not_corrupt_layout(qapp):
    """Regression (backlog item 12, test case 3.4 — text visibly
    vanishing when Font Color is applied): the plain-paragraph fix above
    only skips the block-level merge for *non-list* blocks, since that
    merge exists solely to recolor list markers — but a list item that's
    also the document's last block (a single-item list, or just the last
    item of any list) still needs that merge, and still hit the identical
    corruption doing it. Confirmed directly: mergeBlockCharFormat leaves
    a stale, zero-size cached layout rect behind regardless of whether it
    was reached via a selection or a bare caret. Fixed by calling
    document().markContentsDirty() on that block right after the merge,
    forcing Qt to recompute the real layout instead of trusting the
    stale one mergeBlockCharFormat leaves behind."""
    win = make_note_window("Fix Dinner")
    select_all(win)
    win._set_list_style(QTextListFormat.ListDecimal)
    select_all(win)

    win._set_text_color("#c62828")
    qapp.processEvents()

    doc = win.body.document()
    layout = doc.documentLayout()
    block0 = doc.findBlockByNumber(0)
    rect = layout.blockBoundingRect(block0)
    assert rect.width() > 0
    assert rect.height() > 0
    assert win.body.toPlainText() == "Fix Dinner"
    assert block0.charFormat().foreground().color().name() == "#c62828"


def test_set_text_color_on_single_item_list_via_caret_does_not_corrupt_layout(qapp):
    """Same bug, reached via a bare caret (no selection) rather than a
    selection — the no-selection branch of
    _merge_block_format_over_selection needs the same fix as the
    selection-based one above. Confirmed this specific shape (a
    single-item list, caret-only) is what actually exercises that
    no-selection branch's corruption; a multi-item list with the caret
    just in its last item didn't reproduce it, since that block still
    has other list siblings for Qt's layout cache to stay consistent
    against — only reachable when the block is genuinely alone."""
    win = make_note_window("Fix Dinner")
    select_all(win)
    win._set_list_style(QTextListFormat.ListDecimal)

    cursor = win.body.textCursor()
    cursor.movePosition(QTextCursor.Start)  # caret only, no selection
    win.body.setTextCursor(cursor)
    win._set_text_color("#2e7d32")
    qapp.processEvents()

    doc = win.body.document()
    layout = doc.documentLayout()
    last_block = doc.findBlockByNumber(0)
    rect = layout.blockBoundingRect(last_block)
    assert rect.width() > 0
    assert rect.height() > 0
    assert last_block.charFormat().foreground().color().name() == "#2e7d32"


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


def _grab_marker_region(win, style, block_count, selected_blocks, target_block):
    """Build an N-item list, select exactly `selected_blocks` (a
    (start, end) block-index range, end exclusive), and grab the
    rendered marker gutter for `target_block`."""
    from take_note.list_markers import marker_gutter_rect

    win.body.setPlainText("\n".join(f"Item {i}" for i in range(block_count)))
    select_all(win)
    win._set_list_style(style)
    win.resize(320, 300)
    win.show()

    start, end = selected_blocks
    cursor = win.body.textCursor()
    cursor.setPosition(win.body.document().findBlockByNumber(start).position())
    for _ in range(end - start):
        cursor.movePosition(QTextCursor.NextBlock, QTextCursor.KeepAnchor)
    win.body.setTextCursor(cursor)
    win.body.repaint()

    block = win.body.document().findBlockByNumber(target_block)
    rect = marker_gutter_rect(win.body, block).toRect()
    return win.body.viewport().grab().toImage().copy(rect)


def test_multi_block_selected_disc_markers_render_identically_across_rows(qapp):
    """Regression: selecting 2+ bulleted list items spanning multiple
    blocks painted the first selected block's marker correctly but every
    other selected block's marker as a small checkbox-outline glyph
    instead — a confirmed Qt6 paint-engine bug, fixed by hand-drawing
    markers ourselves (list_markers.py) instead of trusting Qt's native
    list-marker rendering. This compares two selected rows' marker
    regions pixel-for-pixel rather than asserting hardcoded colors, so it
    directly targets the bug's own "first row right, rest wrong"
    shape without being fragile to theme/font."""
    if qapp.platformName() == "offscreen":
        pytest.skip("marker rendering needs real xcb glyph painting, not offscreen's fallback font")

    region0 = _grab_marker_region(make_note_window(), QTextListFormat.ListDisc, 4, (0, 3), 0)
    region1 = _grab_marker_region(make_note_window(), QTextListFormat.ListDisc, 4, (0, 3), 1)

    assert region0.size() == region1.size()
    assert region0 == region1


def test_multi_block_selected_decimal_markers_render_identically_across_rows(qapp):
    """Same regression as above, covering the hand-drawn text-marker path
    (numbers/letters/roman numerals) rather than just the disc-bullet
    path. Text markers differ row-to-row ("1." vs "2."), so this can't
    just diff two adjacent rows of one list like the disc test — instead
    it renders the *same* item ("2.") twice: once as a lone (first)
    selected block, once as the second of two selected blocks, and
    compares those. Item numbering restarts per-list, so both renders
    show identical text and (both selected) identical color; only
    whether the bug's trigger condition (being a non-first selected
    block) differs."""
    if qapp.platformName() == "offscreen":
        pytest.skip("marker rendering needs real xcb glyph painting, not offscreen's fallback font")

    lone_selected = _grab_marker_region(make_note_window(), QTextListFormat.ListDecimal, 2, (1, 2), 1)
    second_selected = _grab_marker_region(make_note_window(), QTextListFormat.ListDecimal, 2, (0, 2), 1)

    assert lone_selected.size() == second_selected.size()
    assert lone_selected == second_selected


def test_delete_confirmation_dialog_forces_stays_on_top(qapp, monkeypatch):
    """Regression: a plain child QMessageBox didn't reliably outrank this
    note's own raw EWMH always-on-top state in KWin's stacking layers,
    so the delete confirmation could end up hidden behind the note.
    Also verifies the later, separate palette-bleed fix (see
    _new_note_dialog's docstring): QMessageBox(self) used to inherit a
    board-attached note's own grey palette, making a destructive-action
    confirmation nearly illegible — no parent sidesteps that."""
    win = make_note_window()

    captured = {}

    def fake_exec(self):
        captured["stays_on_top"] = bool(self.windowFlags() & Qt.WindowStaysOnTopHint)
        captured["parent"] = self.parent()
        return QMessageBox.No

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    win.confirm_delete()

    assert captured["stays_on_top"] is True
    assert captured["parent"] is None


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


def test_font_style_actions_unchecked_for_plain_selection(qapp):
    win = make_note_window("Just plain text")
    select_all(win)
    menu = QMenu()

    win.populate_text_menu(menu)

    assert not win.bold_action.isChecked()
    assert not win.italic_action.isChecked()
    assert not win.underline_action.isChecked()
    assert not win.strikethrough_action.isChecked()


def test_font_style_actions_reflect_current_selection_formatting(qapp):
    """Regression: the Font Style submenu previously gave no visual
    indication of which styles the current selection already had, unlike
    Bullets & Numbering which already checks its matching action."""
    win = make_note_window("Bold italic text")
    select_all(win)
    win._toggle_bold()
    win._toggle_italic()
    menu = QMenu()

    win.populate_text_menu(menu)

    assert win.bold_action.isChecked()
    assert win.italic_action.isChecked()
    assert not win.underline_action.isChecked()
    assert not win.strikethrough_action.isChecked()


def test_alignment_actions_default_to_left_checked(qapp):
    """Regression: alignment gave no checked-state indication at all,
    same gap the Font Style styles (bold/italic/etc.) had before getting
    this same treatment. Left is Qt's own default paragraph alignment."""
    win = make_note_window("Just plain text")
    menu = QMenu()

    win.populate_text_menu(menu)

    assert win.align_left_action.isChecked()
    assert not win.align_center_action.isChecked()
    assert not win.align_right_action.isChecked()


def test_alignment_actions_reflect_current_paragraph_alignment(qapp):
    win = make_note_window("Centered text")
    win._set_alignment(Qt.AlignCenter)
    menu = QMenu()

    win.populate_text_menu(menu)

    assert not win.align_left_action.isChecked()
    assert win.align_center_action.isChecked()
    assert not win.align_right_action.isChecked()


def test_alignment_actions_are_mutually_exclusive(qapp):
    win = make_note_window("Right-aligned text")
    win._set_alignment(Qt.AlignRight)

    win.align_left_action.trigger()

    assert win.align_left_action.isChecked()
    assert not win.align_right_action.isChecked()


def test_text_menu_excludes_whole_note_actions(qapp):
    """Regression: right-clicking selected text used to show whole-note
    actions (Change Color, Transparency, Always on Top, Notepad,
    Delete) alongside text formatting, which doesn't make sense mid-
    selection — those now live only in the note-actions menu."""
    win = make_note_window("Some text")
    menu = QMenu()
    win.populate_text_menu(menu)

    titles = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert titles == [
        "Font…",
        "Font Style",
        "Font Color…",
        "Bullets && Numbering",
        "Increase Indent",
        "Decrease Indent",
        "Add picture…",
        "Hyperlink…",
        "Find…",
    ]


def test_note_actions_menu_excludes_text_formatting(qapp):
    win = make_note_window("Some text")
    menu = QMenu()
    win.populate_note_actions_menu(menu)

    titles = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert titles == [
        "Add Title…",
        "Set Reminder…",
        "Tags…",
        "Change Note Color…",
        "Note Transparency",
        "Always on Top",
        "Lock Note",
        "Stick to Window…",
        "Add to Notepad",
        "Hide Note",
        "Move to Trash",
    ]


def test_hide_note_action_hides_the_window(qapp):
    """Session-only, like the tray's bulk Show All/Hide All Notes — no
    persisted field, just a plain widget hide(). The Notes Manager
    already lists every note regardless of window visibility and its
    double-click handler already calls show() first, so it doubles as
    the "bring a hidden note back" mechanism with no changes needed
    there."""
    win = make_note_window("Some text")
    win.show()
    menu = QMenu()
    win.populate_note_actions_menu(menu)
    hide_action = next(a for a in menu.actions() if a.text() == "Hide Note")

    hide_action.trigger()

    assert win.isHidden()


def test_showing_a_note_again_reasserts_skip_taskbar(qapp, monkeypatch):
    """Regression, reported live: sticking a note to a window (whose
    minimize/restore just calls hide()/show() — see WindowWatcher wiring
    in __init__) or toggling Show/Hide All Notes eventually left the note
    showing up in the taskbar, with the same Vorta-icon KDE mislabeling
    bug already worked around elsewhere, until the app was restarted.
    set_skip_taskbar was only ever applied once, at construction, never
    reapplied on a later show() — same root cause attach_to_board's
    detach branch already knew to guard against for reparenting, just
    via a different trigger (a plain hide()/show() cycle)."""
    calls = []
    monkeypatch.setattr(
        "take_note.note_window.set_skip_taskbar",
        lambda win_id, enabled: calls.append((win_id, enabled)),
    )
    win = make_note_window()
    calls.clear()  # construction's own initial call isn't what's under test

    win.hide()
    win.show()

    assert calls == [(int(win.winId()), True)]


def test_showing_a_board_attached_note_does_not_touch_skip_taskbar(qapp, monkeypatch):
    """A board-attached note is a plain child widget (Qt.Widget), not a
    real top-level window, so it never has its own taskbar entry to skip
    — matches the same board_id is None guard construction already uses."""
    calls = []
    monkeypatch.setattr(
        "take_note.note_window.set_skip_taskbar",
        lambda win_id, enabled: calls.append((win_id, enabled)),
    )
    win = make_note_window()
    win.note.board_id = "some-board-id"
    calls.clear()

    win.hide()
    win.show()

    assert calls == []


def test_note_with_deleted_at_constructs_hidden(qapp):
    win = NoteWindow(Note(deleted_at="2026-01-01T00:00:00+00:00"), manager=FakeManager())

    assert win.isHidden()


def test_note_without_deleted_at_constructs_visible(qapp):
    win = NoteWindow(Note(), manager=FakeManager())

    assert not win.isHidden()


def test_confirm_delete_moves_note_to_trash_not_permanent_delete(qapp, monkeypatch):
    win = make_note_window()
    win.manager.trash_note = Mock()
    win.manager.delete_note = Mock()
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.Yes)

    win.confirm_delete()

    win.manager.trash_note.assert_called_once_with(win)
    win.manager.delete_note.assert_not_called()


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


def test_new_empty_note_defaults_to_12pt_black_font(qapp):
    """Left unset, the first character typed into a brand-new note used
    to pick up whatever Qt's system default font/palette happened to
    resolve to (varies by machine — observed as "Noto Sans" ~16pt with an
    unset/palette-default text color on the reporting system)."""
    win = make_note_window("")

    win.body.insertPlainText("Hello")

    cursor = win.body.textCursor()
    cursor.movePosition(QTextCursor.Start)
    cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)
    fmt = cursor.charFormat()
    assert fmt.fontPointSize() == 12
    assert fmt.foreground().color().name() == "#000000"


def test_new_empty_note_uses_manager_settings_font_size_and_color(qapp):
    """The default isn't a fixed constant — it's read from the manager's
    current Settings each time, so a user-configured default (Settings
    dialog) takes effect for notes created after the change."""

    class CustomManager:
        boards = {}
        settings = Settings(default_font_size=18, default_font_color="#c62828")

    win = NoteWindow(Note(), manager=CustomManager())
    win.body.insertPlainText("Hi")

    cursor = win.body.textCursor()
    cursor.movePosition(QTextCursor.Start)
    cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)
    fmt = cursor.charFormat()
    assert fmt.fontPointSize() == 18
    assert fmt.foreground().color().name() == "#c62828"


def test_default_new_note_format_not_applied_to_note_loaded_with_content(qapp, monkeypatch):
    """A note loaded from disk with real content keeps whatever formatting
    it already has — the 12pt/black default is only for a genuinely empty,
    brand-new note."""
    calls = []
    monkeypatch.setattr(
        NoteWindow, "_apply_default_new_note_format", lambda self: calls.append(1)
    )

    NoteWindow(Note(html="<p>Existing content</p>"), manager=FakeManager())

    assert calls == []


def test_default_new_note_format_applied_to_genuinely_empty_note(qapp, monkeypatch):
    calls = []
    monkeypatch.setattr(
        NoteWindow, "_apply_default_new_note_format", lambda self: calls.append(1)
    )

    NoteWindow(Note(html=""), manager=FakeManager())

    assert calls == [1]


def test_constructing_a_note_does_not_bump_its_modified_at(qapp):
    """Regression, reported live: launching the real app and quitting
    again with zero interaction bumped every note's modified_at anyway —
    confirmed via a real subprocess launch+quit against a scratch
    XDG_DATA_HOME. Root cause: setHtml(note.html) in __init__ (restoring
    a loaded note's saved content) fires textChanged, which is connected
    to mark_changed() — completely independent of moveEvent/resizeEvent
    (also guarded, for the same reason: resize()/move() in __init__
    restoring a loaded note's saved geometry fires those too). Both are
    covered by the same _initializing guard on mark_changed() itself,
    since nothing is connected to `changed` yet during construction
    anyway (NoteManager wires that up only after the constructor
    returns), so skipping it there loses nothing real."""
    original_modified_at = "2020-01-01T00:00:00+00:00"
    note = Note(html="<p>Existing content</p>", modified_at=original_modified_at)

    win = NoteWindow(note, manager=FakeManager())

    assert win.note.modified_at == original_modified_at


def test_real_edit_after_construction_still_bumps_modified_at(qapp):
    """Sanity check for the fix above: the guard only applies during
    construction — a real edit afterward must still update modified_at
    normally, or notes would never show as modified at all."""
    original_modified_at = "2020-01-01T00:00:00+00:00"
    win = NoteWindow(Note(html="<p>Existing content</p>", modified_at=original_modified_at), manager=FakeManager())

    win.mark_changed()

    assert win.note.modified_at != original_modified_at


def test_default_new_note_format_still_applied_after_a_save_without_typing(qapp, monkeypatch):
    """Regression: QTextEdit.toHtml() on an empty document returns Qt's
    own ~600-char boilerplate wrapper, not an empty string. A note saved
    once while still empty (e.g. rolled up and quit before ever being
    typed into) persisted that boilerplate as note.html — `if not
    note.html:` then read false on the next launch, silently skipping
    the default-format step, so text typed after a reload picked up
    whatever Qt's own unset format resolves to instead of the
    configured black default."""
    win = make_note_window()  # genuinely empty
    win.sync_model()  # same call NoteManager makes just before saving
    assert win.note.html  # confirms the boilerplate-not-empty premise

    calls = []
    monkeypatch.setattr(
        NoteWindow, "_apply_default_new_note_format", lambda self: calls.append(1)
    )
    NoteWindow(win.note, manager=FakeManager())

    assert calls == [1]


def test_show_font_dialog_applies_chosen_font(qapp, monkeypatch):
    """Font family/size used to be picked via QComboBox/QFontComboBox
    widgets embedded directly in the context menu, which fought QMenu's
    own popup handling (clicking the size dropdown closed the whole menu
    instead of opening it) and needed manual re-styling to avoid clashing
    with the theme. Replaced with a real QFontDialog instead — built as a
    bare instance rather than the static getFont(initial, self)
    convenience (same palette-bleed fix as every other note dialog; see
    _new_note_dialog's docstring), so tests patch exec()/currentFont() on
    the instance instead of getFont() itself."""
    win = make_note_window("Hello World")
    select_all(win)
    chosen_font = QFont("Monospace", 24)
    seen = {}

    def fake_exec(self):
        seen["parent"] = self.parent()
        return QFontDialog.Accepted

    monkeypatch.setattr(QFontDialog, "exec", fake_exec)
    monkeypatch.setattr(QFontDialog, "currentFont", lambda self: chosen_font)
    win.show_font_dialog()

    assert win.body.fontFamily() == "Monospace"
    assert win.body.fontPointSize() == 24
    assert seen["parent"] is None  # avoids the palette-bleed bug, see _new_note_dialog


def test_show_font_dialog_cancelled_leaves_font_unchanged(qapp, monkeypatch):
    win = make_note_window("Hello World")
    select_all(win)
    before_family = win.body.fontFamily()
    before_size = win.body.fontPointSize()

    monkeypatch.setattr(QFontDialog, "exec", lambda self: QFontDialog.Rejected)
    win.show_font_dialog()

    assert win.body.fontFamily() == before_family
    assert win.body.fontPointSize() == before_size


def test_show_font_dialog_preserves_bold_on_mixed_selection(qapp, monkeypatch):
    """Regression, reported live: bolding one word in a selection, then
    opening Font... on the whole selection and changing only the size,
    silently stripped bold from the word that had it. Root cause:
    currentFont() on a mixed-bold selection resolves the ambiguity to
    "not bold" for the dialog's own initial state, and setCurrentFont()
    (the old implementation) applies an entire QFont wholesale -- even
    though the user only touched the size field, the dialog's returned
    font still carried that "not bold" explicitly, wiping bold from the
    one word that actually had it. show_font_dialog() now only merges
    family/size, leaving each character's own actual weight alone."""
    win = make_note_window("plain BOLD plain")
    cursor = win.body.textCursor()
    cursor.setPosition(len("plain "))
    cursor.setPosition(len("plain BOLD"), QTextCursor.KeepAnchor)
    win.body.setTextCursor(cursor)
    win._toggle_bold()
    select_all(win)

    chosen_font = QFont("Noto Sans", 24)
    monkeypatch.setattr(QFontDialog, "exec", lambda self: QFontDialog.Accepted)
    monkeypatch.setattr(QFontDialog, "currentFont", lambda self: chosen_font)
    win.show_font_dialog()

    bold_cursor = win.body.textCursor()
    bold_cursor.setPosition(len("plain "))
    bold_cursor.setPosition(len("plain BOLD"), QTextCursor.KeepAnchor)
    fmt = bold_cursor.charFormat()
    assert fmt.fontWeight() > QFont.Normal
    assert fmt.fontPointSize() == 24


def test_text_menu_has_font_dialog_action(qapp):
    win = make_note_window("Some text")
    menu = QMenu()
    win.populate_text_menu(menu)

    titles = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert titles[0] == "Font…"


def test_qfontdialog_getfont_returns_ok_then_font(qapp):
    """Contract check against the real API: PySide6 returns (ok, font)
    from QFontDialog.getFont(), the reverse of PyQt5's (font, ok). Coding
    against the wrong assumption crashed show_font_dialog() for real even
    though a same-wrongly-ordered mock let a higher-level test pass — this
    guards the assumption itself, not just our usage of it."""

    def auto_accept():
        for w in qapp.topLevelWidgets():
            if isinstance(w, QFontDialog):
                w.accept()

    QTimer.singleShot(50, auto_accept)
    result = QFontDialog.getFont(QFont("Sans", 10))

    assert isinstance(result[0], bool)
    assert isinstance(result[1], QFont)


def _patch_title_dialog(monkeypatch, text, accepted):
    """show_title_dialog() builds a QInputDialog instance directly (rather
    than the static getText() convenience) so it can be resized wider than
    the cramped default — same pattern as show_hyperlink_dialog's own fix
    (see _patch_hyperlink_dialog above), and tests must patch exec()/
    textValue() on the instance for the same reason: a real, un-mockable
    modal dialog would otherwise hang the test."""
    monkeypatch.setattr(
        QInputDialog, "exec", lambda self: QInputDialog.Accepted if accepted else QInputDialog.Rejected
    )
    monkeypatch.setattr(QInputDialog, "textValue", lambda self: text)


def test_title_bar_hidden_by_default(qapp):
    win = make_note_window("Some text")
    assert win.title_bar.isHidden()


def test_title_bar_visible_for_note_constructed_with_title(qapp):
    win = NoteWindow(Note(title="Groceries"), manager=FakeManager())
    assert not win.title_bar.isHidden()
    assert win.title_bar.label.text() == "Groceries"


def test_title_bar_label_has_explicit_black_text_color(qapp):
    """Regression: left unset, the label fell back to the ambient
    QPalette::WindowText role instead of QTextEdit's own QPalette::Text —
    on the reporting system that resolved to a near-white color, reading
    as barely-visible pale text against every (light, pastel) note color."""
    win = NoteWindow(Note(title="Groceries"), manager=FakeManager())
    assert "color: black" in win.title_bar.styleSheet()


def test_title_bar_label_has_explicit_transparent_background(qapp):
    """Regression: a board-attached note's title bar painted the whole
    strip in the *board's* own background color instead of the note's —
    reported live via a screenshot. Root cause: the label's own
    backgroundRole() picks up the board canvas (a genuine QObject
    ancestor once attached) once styled-painting is active anywhere in
    the ancestor chain, and Qt paints that as the label's own implicit
    background — #titlebar's own background-color rule doesn't prevent
    that, since it's the label's own fill sitting on top of it. Only
    reproducible for a note actually attached to a board (see
    test_board_window.py for the full attached-note repro); this just
    guards the stylesheet text itself, cheaply, without needing a real
    board."""
    win = NoteWindow(Note(title="Groceries"), manager=FakeManager())
    assert "background-color: transparent" in win.title_bar.styleSheet()


def test_title_bar_font_matches_body_font_family_and_size(qapp):
    """The title used to just bold the label's own ambient default font,
    unrelated to whatever font the note body actually uses — now matches
    the body's family/size (still bold, since it's a heading)."""
    win = NoteWindow(Note(title="Groceries"), manager=FakeManager())
    body_font = win.body.currentFont()
    title_font = win.title_bar.label.font()
    assert title_font.family() == body_font.family()
    assert title_font.pointSize() == body_font.pointSize()
    assert title_font.bold()


def test_new_note_dialog_has_no_parent_to_avoid_palette_bleed(qapp):
    """Regression: QInputDialog(self) inherited a board-attached note's
    resolved palette — the board canvas's own inline background-color
    QSS (NotepadWindow._apply_color) cascades through the real widget
    tree into the note (a genuine descendant) and then into any dialog
    built with the note as its parent too, even though that dialog is a
    separate top-level window. Reported live via a screenshot: Note
    Title's dialog rendered with the board's own light grey background
    instead of the app's normal dark theme, with the still-normal
    dark-theme text nearly illegible on top of it. Confirmed directly: a
    board-parented QInputDialog's backgroundRole() color read back the
    board's own color instead of the theme default, and only ever
    reproducible for a note actually attached to a board. Passing no
    parent at all sidesteps the inheritance entirely (same fix already
    used for the hyperlink hover tooltip's own palette bleed)."""
    win = make_note_window("")
    dialog = win._new_note_dialog("Title", "Label:", "")
    assert dialog.parent() is None


def test_center_dialog_over_note_centers_on_the_notes_own_geometry(qapp):
    win = make_note_window("")
    win.move(100, 100)
    win.resize(220, 220)
    dialog = win._new_note_dialog("Title", "Label:", "")
    dialog.resize(300, 150)

    win._center_dialog_over_note(dialog)

    expected_center = win.mapToGlobal(win.rect().center())
    actual_center = dialog.geometry().center()
    assert abs(actual_center.x() - expected_center.x()) <= 1
    assert abs(actual_center.y() - expected_center.y()) <= 1


def test_show_title_dialog_sets_title_and_shows_bar(qapp, monkeypatch):
    win = make_note_window("Some text")
    _patch_title_dialog(monkeypatch, "Groceries", True)

    win.show_title_dialog()

    assert win.note.title == "Groceries"
    assert not win.title_bar.isHidden()
    assert win.title_bar.label.text() == "Groceries"


def test_show_title_dialog_cancelled_does_not_change_title(qapp, monkeypatch):
    win = NoteWindow(Note(title="Groceries"), manager=FakeManager())
    _patch_title_dialog(monkeypatch, "Something else", False)

    win.show_title_dialog()

    assert win.note.title == "Groceries"


def test_show_title_dialog_clearing_title_hides_bar(qapp, monkeypatch):
    win = NoteWindow(Note(title="Groceries"), manager=FakeManager())
    _patch_title_dialog(monkeypatch, "", True)

    win.show_title_dialog()

    assert win.note.title == ""
    assert win.title_bar.isHidden()


def test_show_title_dialog_strips_whitespace(qapp, monkeypatch):
    win = make_note_window("Some text")
    _patch_title_dialog(monkeypatch, "  Groceries  ", True)

    win.show_title_dialog()

    assert win.note.title == "Groceries"


def test_show_tags_dialog_sets_tags(qapp, monkeypatch):
    win = make_note_window("Some text")
    _patch_title_dialog(monkeypatch, "work, urgent", True)

    win.show_tags_dialog()

    assert win.note.tags == ["work", "urgent"]


def test_show_tags_dialog_strips_whitespace_drops_empties_dedupes(qapp, monkeypatch):
    win = make_note_window("Some text")
    _patch_title_dialog(monkeypatch, "  work ,, urgent, work", True)

    win.show_tags_dialog()

    assert win.note.tags == ["work", "urgent"]


def test_show_tags_dialog_prefills_existing_tags(qapp, monkeypatch):
    win = NoteWindow(Note(tags=["work", "urgent"]), manager=FakeManager())
    seen = {}

    def fake_exec(self):
        seen["initial"] = self.textValue()
        return QInputDialog.Rejected

    monkeypatch.setattr(QInputDialog, "exec", fake_exec)

    win.show_tags_dialog()

    assert seen["initial"] == "work, urgent"


def test_show_tags_dialog_cancelled_does_not_change_tags(qapp, monkeypatch):
    win = NoteWindow(Note(tags=["work"]), manager=FakeManager())
    _patch_title_dialog(monkeypatch, "something else", False)

    win.show_tags_dialog()

    assert win.note.tags == ["work"]


def _patch_reminder_dialog(monkeypatch, local_dt, result):
    """_ReminderDialog is this app's own QDialog subclass (same family as
    QMessageBox/QInputDialog, both already confirmed patchable at the
    class level — unlike QMenu.exec, which Shiboken silently no-ops on).
    Setting date_time_edit inside the patched exec() (rather than before
    calling show_reminder_dialog()) is necessary since the real instance
    only exists once show_reminder_dialog() constructs it.

    Explicitly selects the absolute-time radio — these callers are all
    testing the absolute date/time path specifically, and a brand-new
    reminder now defaults to the quick relative-minutes radio instead."""

    def fake_exec(self):
        if local_dt is not None:
            self.absolute_radio.setChecked(True)
            self.date_time_edit.setDateTime(QDateTime(local_dt))
        return result

    monkeypatch.setattr(_ReminderDialog, "exec", fake_exec)


def test_show_reminder_dialog_sets_reminder_and_shows_icon(qapp, monkeypatch):
    win = make_note_window("Some text")
    future = datetime.now() + timedelta(hours=2)
    _patch_reminder_dialog(monkeypatch, future, QDialog.Accepted)

    win.show_reminder_dialog()

    # Expected value round-tripped through QDateTime too, same as the
    # dialog itself does — QDateTime only retains millisecond precision,
    # not microseconds, so comparing against the raw `future` directly
    # would fail on the sub-millisecond digits.
    expected = local_datetime_to_utc_iso(QDateTime(future).toPython())
    assert win.note.reminder_at == expected
    assert not win.header.reminder_btn.isHidden()


def test_show_reminder_dialog_quick_minutes_sets_reminder(qapp, monkeypatch):
    """The quick "remind me in N minutes" path computes off the real
    current UTC instant directly (see show_reminder_dialog), not a
    QDateTime round-trip — compared with a tolerance rather than an
    exact value since real wall-clock time elapses between the dialog's
    accept and this assertion."""
    win = make_note_window("Some text")

    def fake_exec(self):
        self.quick_radio.setChecked(True)
        self.minutes_spin.setValue(20)
        return QDialog.Accepted

    monkeypatch.setattr(_ReminderDialog, "exec", fake_exec)

    win.show_reminder_dialog()

    expected = datetime.now(timezone.utc) + timedelta(minutes=20)
    actual = datetime.fromisoformat(win.note.reminder_at)
    assert abs((actual - expected).total_seconds()) < 5


def test_reminder_dialog_defaults_to_quick_mode_for_a_new_reminder(qapp):
    dialog = _ReminderDialog(None)

    assert dialog.quick_radio.isChecked()
    assert not dialog.absolute_radio.isChecked()
    assert dialog.minutes_spin.isEnabled()
    assert not dialog.date_time_edit.isEnabled()


def test_reminder_dialog_defaults_to_absolute_mode_when_editing(qapp):
    existing = local_datetime_to_utc_iso(datetime.now() + timedelta(hours=1))
    dialog = _ReminderDialog(existing)

    assert dialog.absolute_radio.isChecked()
    assert not dialog.quick_radio.isChecked()
    assert dialog.date_time_edit.isEnabled()
    assert not dialog.minutes_spin.isEnabled()


def test_reminder_dialog_switching_mode_toggles_widget_enabled_state(qapp):
    dialog = _ReminderDialog(None)

    dialog.absolute_radio.setChecked(True)

    assert dialog.date_time_edit.isEnabled()
    assert not dialog.minutes_spin.isEnabled()


def test_show_reminder_dialog_cancelled_does_not_change_reminder(qapp, monkeypatch):
    existing = local_datetime_to_utc_iso(datetime.now() + timedelta(hours=1))
    win = NoteWindow(Note(reminder_at=existing), manager=FakeManager())
    _patch_reminder_dialog(monkeypatch, datetime.now() + timedelta(hours=5), QDialog.Rejected)

    win.show_reminder_dialog()

    assert win.note.reminder_at == existing


def test_show_reminder_dialog_clear_clears_reminder_and_hides_icon(qapp, monkeypatch):
    existing = local_datetime_to_utc_iso(datetime.now() + timedelta(hours=1))
    win = NoteWindow(Note(reminder_at=existing), manager=FakeManager())
    _patch_reminder_dialog(monkeypatch, None, _ReminderDialog.Cleared)

    win.show_reminder_dialog()

    assert win.note.reminder_at is None
    assert win.header.reminder_btn.isHidden()


def test_show_reminder_dialog_prefills_existing_reminder(qapp, monkeypatch):
    existing_local = datetime.now() + timedelta(hours=3)
    existing_iso = local_datetime_to_utc_iso(existing_local)
    win = NoteWindow(Note(reminder_at=existing_iso), manager=FakeManager())
    seen = {}

    def fake_exec(self):
        seen["prefilled"] = self.date_time_edit.dateTime().toPython()
        return QDialog.Rejected

    monkeypatch.setattr(_ReminderDialog, "exec", fake_exec)

    win.show_reminder_dialog()

    # Compare at second precision — QDateTime doesn't retain microseconds.
    assert seen["prefilled"].replace(microsecond=0) == existing_local.replace(microsecond=0)


def test_reminder_action_label_is_edit_when_a_reminder_is_set(qapp):
    win = NoteWindow(
        Note(reminder_at=local_datetime_to_utc_iso(datetime.now() + timedelta(hours=1))),
        manager=FakeManager(),
    )
    menu = QMenu()

    win.populate_note_actions_menu(menu)

    titles = [a.text() for a in menu.actions()]
    assert "Edit Reminder…" in titles
    assert "Set Reminder…" not in titles


def test_update_reminder_indicator_shows_tooltip_with_local_time(qapp):
    win = make_note_window()
    reminder_at = local_datetime_to_utc_iso(datetime(2026, 3, 5, 14, 30))

    win.header.update_reminder_indicator(reminder_at)

    assert not win.header.reminder_btn.isHidden()
    assert "Reminder:" in win.header.reminder_btn.toolTip()


def test_update_reminder_indicator_hides_for_no_reminder(qapp):
    win = make_note_window()
    win.header.update_reminder_indicator(local_datetime_to_utc_iso(datetime.now() + timedelta(hours=1)))

    win.header.update_reminder_indicator(None)

    assert win.header.reminder_btn.isHidden()


def test_header_tag_indicator_hidden_for_untagged_note(qapp):
    win = make_note_window("Some text")

    assert not win.header.tag_btn.isVisible()


def test_header_tag_indicator_shown_for_tagged_note(qapp):
    win = NoteWindow(Note(tags=["work"]), manager=FakeManager())

    assert win.header.tag_btn.isVisible()


def test_header_tag_indicator_updates_after_saving_tags(qapp, monkeypatch):
    win = make_note_window("Some text")
    _patch_title_dialog(monkeypatch, "work, urgent", True)

    win.show_tags_dialog()

    assert win.header.tag_btn.isVisible()
    assert "work" in win.header.tag_btn.toolTip()
    assert "urgent" in win.header.tag_btn.toolTip()


def test_header_tag_indicator_hides_after_clearing_tags(qapp, monkeypatch):
    win = NoteWindow(Note(tags=["work"]), manager=FakeManager())
    _patch_title_dialog(monkeypatch, "", True)

    win.show_tags_dialog()

    assert not win.header.tag_btn.isVisible()


def test_clicking_tag_indicator_opens_tags_dialog(qapp, monkeypatch):
    win = NoteWindow(Note(tags=["work"]), manager=FakeManager())
    called = []
    monkeypatch.setattr(win, "show_tags_dialog", lambda: called.append(True))

    win.header.tag_btn.click()

    assert called == [True]


def test_title_and_hyperlink_dialogs_have_a_clear_button(qapp, monkeypatch):
    """Both go through the shared _new_note_dialog() helper, so one test
    covers both — matches the clear button the Notes Manager's search
    field already has (QLineEdit.setClearButtonEnabled(True))."""
    win = make_note_window("Some text")
    seen = {}

    def fake_exec(self):
        seen["has_clear_button"] = self.findChild(QLineEdit).isClearButtonEnabled()
        return QInputDialog.Rejected

    monkeypatch.setattr(QInputDialog, "exec", fake_exec)

    win.show_title_dialog()
    assert seen["has_clear_button"]

    seen.clear()
    win.show_hyperlink_dialog()
    assert seen["has_clear_button"]


def test_show_title_dialog_is_wide_enough_to_read_its_own_title(qapp, monkeypatch):
    """Regression: the static QInputDialog.getText() convenience's default
    width was too narrow to even read the dialog's own title bar — same
    class of bug reported live for NotepadWindow.rename()'s "Rename Notepad"
    dialog (board_window.py) and already fixed there and for
    show_hyperlink_dialog; Note Title had the identical issue. A first
    fix (320) still truncated on an unscaled monitor even though it read
    fine on a 125%-scaled one, since the OS-drawn title bar's own text
    width isn't controlled by Qt's content sizing at all — bumped to 480."""
    win = make_note_window("Some text")
    seen = {}

    def fake_exec(self):
        seen["width"] = self.width()
        return QInputDialog.Rejected

    monkeypatch.setattr(QInputDialog, "exec", fake_exec)

    win.show_title_dialog()

    assert seen["width"] >= 480


def test_note_actions_menu_shows_add_title_when_untitled(qapp):
    win = make_note_window("Some text")
    menu = QMenu()
    win.populate_note_actions_menu(menu)

    assert menu.actions()[0].text() == "Add Title…"


def test_note_actions_menu_shows_edit_title_when_titled(qapp):
    win = NoteWindow(Note(title="Groceries"), manager=FakeManager())
    menu = QMenu()
    win.populate_note_actions_menu(menu)

    assert menu.actions()[0].text() == "Edit Title…"


def test_title_action_has_shift_f2_shortcut(qapp):
    """Was Ctrl+F2, changed because it collides with KWin's default
    global "Switch to Desktop 2" shortcut — see note_window.py."""
    win = make_note_window("Some text")
    assert win.title_action.shortcut().toString() == "Shift+F2"


def _patch_hyperlink_dialog(monkeypatch, text, accepted):
    """show_hyperlink_dialog() builds a QInputDialog instance directly
    (rather than the static getText() convenience) so it can be resized
    wider than the cramped default — that means tests must patch exec()/
    textValue() on the instance, not getText(), or they'd hang on a real,
    un-mockable modal dialog. Confirmed QInputDialog.exec IS overridable
    at the class level (it's a QDialog, same family as QMessageBox, unlike
    QMenu.exec which silently isn't)."""
    monkeypatch.setattr(
        QInputDialog, "exec", lambda self: QInputDialog.Accepted if accepted else QInputDialog.Rejected
    )
    monkeypatch.setattr(QInputDialog, "textValue", lambda self: text)


def test_hyperlink_dialog_applies_anchor_to_selection(qapp, monkeypatch):
    win = make_note_window("Click here")
    select_all(win)

    _patch_hyperlink_dialog(monkeypatch, "https://example.com", True)
    win.show_hyperlink_dialog()

    cursor = win.body.textCursor()
    cursor.movePosition(QTextCursor.Start)
    fmt = cursor.charFormat()
    assert fmt.isAnchor()
    assert fmt.anchorHref() == "https://example.com"
    assert win.body.toPlainText() == "Click here"


def test_hyperlink_dialog_no_selection_inserts_url_as_text(qapp, monkeypatch):
    win = make_note_window("")
    _patch_hyperlink_dialog(monkeypatch, "https://example.com", True)

    win.show_hyperlink_dialog()

    assert win.body.toPlainText() == "https://example.com"
    cursor = win.body.textCursor()
    cursor.movePosition(QTextCursor.Start)
    assert cursor.charFormat().anchorHref() == "https://example.com"


def test_hyperlink_dialog_cancelled_does_not_modify_text(qapp, monkeypatch):
    win = make_note_window("Some text")
    _patch_hyperlink_dialog(monkeypatch, "https://example.com", False)

    win.show_hyperlink_dialog()

    assert win.body.toPlainText() == "Some text"


def test_hyperlink_dialog_empty_url_does_not_modify_text(qapp, monkeypatch):
    win = make_note_window("Some text")
    _patch_hyperlink_dialog(monkeypatch, "", True)

    win.show_hyperlink_dialog()

    assert win.body.toPlainText() == "Some text"


def test_hyperlink_dialog_prefills_existing_url_for_editing(qapp, monkeypatch):
    """Regression: editing an already-linked word used to always prompt
    with a blank "https://" default instead of the link's current URL,
    and inserted the new URL as fresh text splitting the link instead of
    replacing it in place."""
    win = make_note_window("Read my stories and poems today")
    cursor = win.body.textCursor()
    cursor.movePosition(QTextCursor.Start)
    cursor.movePosition(QTextCursor.NextWord)  # start of "stories"
    cursor.movePosition(QTextCursor.NextWord, QTextCursor.KeepAnchor)
    cursor.movePosition(QTextCursor.NextWord, QTextCursor.KeepAnchor)
    cursor.movePosition(QTextCursor.EndOfWord, QTextCursor.KeepAnchor)  # "stories and poems"
    win.body.setTextCursor(cursor)

    fmt = QTextCharFormat()
    fmt.setAnchor(True)
    fmt.setAnchorHref("https://old-example.com")
    cursor.mergeCharFormat(fmt)

    seen = {}

    def fake_exec(self):
        seen["prefilled"] = self.textValue()
        return QInputDialog.Rejected

    monkeypatch.setattr(QInputDialog, "exec", fake_exec)
    monkeypatch.setattr(QInputDialog, "textValue", lambda self: "https://old-example.com")

    # Caret with no selection, positioned inside the existing link.
    caret = win.body.textCursor()
    caret.setPosition(cursor.selectionStart() + 2)
    win.body.setTextCursor(caret)

    win.show_hyperlink_dialog()

    assert seen["prefilled"] == "https://old-example.com"


def test_remove_hyperlink_strips_anchor_from_caret_span(qapp):
    """Regression: there was previously no way to remove a hyperlink once
    inserted — clearing the URL field in the dialog just cancelled with
    no effect. A caret with no selection expands to the link's whole
    contiguous span first, same convenience as show_hyperlink_dialog()."""
    win = make_note_window("Read my stories and poems today")
    cursor = win.body.textCursor()
    cursor.movePosition(QTextCursor.Start)
    cursor.movePosition(QTextCursor.NextWord)
    cursor.movePosition(QTextCursor.NextWord, QTextCursor.KeepAnchor)
    cursor.movePosition(QTextCursor.NextWord, QTextCursor.KeepAnchor)
    cursor.movePosition(QTextCursor.EndOfWord, QTextCursor.KeepAnchor)  # "stories and poems"
    fmt = QTextCharFormat()
    fmt.setAnchor(True)
    fmt.setAnchorHref("https://example.com")
    cursor.mergeCharFormat(fmt)
    link_start = cursor.selectionStart()

    caret = win.body.textCursor()
    caret.setPosition(link_start + 2)
    win.body.setTextCursor(caret)

    win.remove_hyperlink()

    check = win.body.textCursor()
    check.setPosition(link_start)
    check.setPosition(link_start + len("stories and poems"), QTextCursor.KeepAnchor)
    result_fmt = check.charFormat()
    assert not result_fmt.isAnchor()
    assert result_fmt.anchorHref() == ""
    assert not result_fmt.fontUnderline()
    assert win.body.toPlainText() == "Read my stories and poems today"


def test_remove_hyperlink_strips_anchor_from_selection(qapp):
    win = make_note_window("Click here")
    select_all(win)
    fmt = QTextCharFormat()
    fmt.setAnchor(True)
    fmt.setAnchorHref("https://example.com")
    win.body.textCursor().mergeCharFormat(fmt)
    select_all(win)

    win.remove_hyperlink()

    cursor = win.body.textCursor()
    cursor.movePosition(QTextCursor.Start)
    assert not cursor.charFormat().isAnchor()


def test_remove_hyperlink_does_nothing_when_not_on_a_link(qapp):
    win = make_note_window("Just plain text")
    win.body.textCursor().movePosition(QTextCursor.Start)

    win.remove_hyperlink()

    assert win.body.toPlainText() == "Just plain text"


def test_context_menu_shows_remove_hyperlink_only_on_a_link(qapp):
    win = make_note_window("Click here")
    menu_without_link = QMenu()
    win.populate_text_menu(menu_without_link)
    assert not any(a.text() == "Remove Hyperlink" for a in menu_without_link.actions())

    fmt = QTextCharFormat()
    fmt.setAnchor(True)
    fmt.setAnchorHref("https://example.com")
    select_all(win)
    win.body.textCursor().mergeCharFormat(fmt)
    caret = win.body.textCursor()
    caret.setPosition(2)
    win.body.setTextCursor(caret)

    menu_with_link = QMenu()
    win.populate_text_menu(menu_with_link)
    assert any(a.text() == "Remove Hyperlink" for a in menu_with_link.actions())


def test_detect_url_span_finds_url_containing_the_offset():
    url = "https://example.com/page"
    text = f"Check out {url} for details"
    span = _detect_url_span(text, offset=15)
    assert span == (text.index(url), text.index(url) + len(url), url)


def test_detect_url_span_strips_trailing_sentence_punctuation():
    url = "https://example.com"
    text = f"See {url}."
    span = _detect_url_span(text, offset=6)
    assert span == (text.index(url), text.index(url) + len(url), url)


def test_detect_url_span_returns_none_outside_any_url():
    text = "Check out https://example.com/page for details"
    assert _detect_url_span(text, offset=2) is None
    assert _detect_url_span(text, offset=40) is None


def test_detect_url_span_returns_none_for_bare_domain_without_scheme():
    assert _detect_url_span("Visit www.example.com today", offset=8) is None


def test_detect_url_span_rejects_a_comma_where_a_dot_belongs():
    """Regression, reported live: "http://www,google.com" (a typo — a
    stray comma instead of a period) still linkified despite being
    obviously broken, since the old check only looked for the http(s)://
    scheme, never validating the host at all."""
    text = "See http://www,google.com for more"
    assert _detect_url_span(text, offset=6) is None


def test_detect_url_span_accepts_a_real_looking_domain():
    url = "http://www.google.com"
    text = f"See {url} for more"
    span = _detect_url_span(text, offset=6)
    assert span == (text.index(url), text.index(url) + len(url), url)


def test_detect_url_span_accepts_a_url_with_path_query_and_port():
    url = "https://example.com:8080/path?query=1"
    text = f"See {url} for more"
    span = _detect_url_span(text, offset=6)
    assert span == (text.index(url), text.index(url) + len(url), url)


def test_detect_url_span_accepts_an_ip_address_host():
    url = "http://192.168.1.1/admin"
    text = f"See {url} for more"
    span = _detect_url_span(text, offset=6)
    assert span == (text.index(url), text.index(url) + len(url), url)


def test_detect_url_span_rejects_a_single_label_host():
    """Accepted tradeoff of this simple a check — see _HOST_PATTERN's own
    docstring."""
    assert _detect_url_span("See http://localhost for more", offset=6) is None


def test_auto_linkify_turns_a_plain_url_into_a_real_link_at_right_click(qapp):
    """Backlog item 22: a URL typed as plain text (never run through the
    Hyperlink… dialog) becomes a real link the moment it's right-clicked
    — detection only runs at the point of interaction, not live as-you-
    type, matching this app's existing style elsewhere."""
    url = "https://example.com/page"
    text = f"Check out {url} for details"
    win = make_note_window(text)
    caret = win.body.textCursor()
    caret.setPosition(15)  # inside the URL
    win.body.setTextCursor(caret)

    win._auto_linkify_at_cursor()

    start = text.index(url)
    check = win.body.textCursor()
    check.setPosition(start)
    check.setPosition(start + len(url), QTextCursor.KeepAnchor)
    fmt = check.charFormat()
    assert fmt.isAnchor()
    assert fmt.anchorHref() == url
    assert fmt.fontUnderline()
    assert win.body.toPlainText() == text


def test_auto_linkify_does_nothing_outside_a_url(qapp):
    win = make_note_window("Just plain text")
    caret = win.body.textCursor()
    caret.setPosition(2)
    win.body.setTextCursor(caret)

    win._auto_linkify_at_cursor()

    check = win.body.textCursor()
    check.movePosition(QTextCursor.Start)
    assert not check.charFormat().isAnchor()


def test_auto_linkify_does_nothing_on_an_existing_link(qapp):
    """Confirms auto-linkify doesn't clobber a link that already has its
    own real anchor formatting (e.g. inserted via the Hyperlink… dialog
    with a different display href than what the plain text would say)."""
    win = make_note_window("Click here")
    fmt = QTextCharFormat()
    fmt.setAnchor(True)
    fmt.setAnchorHref("https://custom-url.example")
    select_all(win)
    win.body.textCursor().mergeCharFormat(fmt)
    caret = win.body.textCursor()
    caret.setPosition(2)
    win.body.setTextCursor(caret)

    win._auto_linkify_at_cursor()

    check = win.body.textCursor()
    check.movePosition(QTextCursor.Start)
    assert check.charFormat().anchorHref() == "https://custom-url.example"


def test_typing_a_space_after_a_link_does_not_extend_it(qapp):
    """Regression, reported live: linkifying a URL then typing a space
    right after it (still on the same line) produced a space that was
    itself part of the link — underlined, colored, and sharing its href.
    A collapsed cursor's format comes from the character immediately
    before it, which right after a link's last character is still that
    link's own anchor format."""
    url = "https://example.com/page"
    win = make_note_window(url)
    cursor = win.body.textCursor()
    cursor.movePosition(QTextCursor.End)
    win.body.setTextCursor(cursor)
    win._auto_linkify_at_cursor()
    # Auto-linkify only formats the URL span; it doesn't move the
    # widget's own cursor, so re-set it to the end to simulate the user
    # actually clicking/arrowing there afterward — the real repro step.
    cursor = win.body.textCursor()
    cursor.movePosition(QTextCursor.End)
    win.body.setTextCursor(cursor)

    win.body.insertPlainText(" hello")

    check = win.body.textCursor()
    check.setPosition(len(url))
    check.setPosition(len(url) + len(" hello"), QTextCursor.KeepAnchor)
    fmt = check.charFormat()
    assert fmt.isAnchor() is False
    assert fmt.fontUnderline() is False


def test_pressing_enter_after_a_link_does_not_extend_it(qapp):
    """Same bug, reported live via a second repro: pressing Enter right
    after a linkified URL (instead of typing a space on the same line)
    produced a brand-new block whose own ambient format was still the
    link's anchor formatting, so anything typed there came out
    underlined/colored and sharing the link's href too."""
    url = "https://example.com/page"
    win = make_note_window(url)
    cursor = win.body.textCursor()
    cursor.movePosition(QTextCursor.End)
    win.body.setTextCursor(cursor)
    win._auto_linkify_at_cursor()
    cursor = win.body.textCursor()
    cursor.movePosition(QTextCursor.End)
    win.body.setTextCursor(cursor)

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier)
    qapp.sendEvent(win.body, event)
    win.body.insertPlainText("hello")

    last_block = win.body.document().lastBlock()
    check = QTextCursor(last_block)
    check.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
    fmt = check.charFormat()
    assert fmt.isAnchor() is False
    assert fmt.fontUnderline() is False


def test_typing_inside_an_existing_link_is_left_alone(qapp):
    """Guard against over-triggering: a cursor genuinely inside a link's
    own text (anchored on both sides, not at the boundary) is legitimate
    — editing there shouldn't have its anchor formatting stripped."""
    url = "https://example.com/page"
    win = make_note_window(url)
    fmt = QTextCharFormat()
    fmt.setAnchor(True)
    fmt.setAnchorHref(url)
    fmt.setFontUnderline(True)
    select_all(win)
    win.body.textCursor().mergeCharFormat(fmt)

    cursor = win.body.textCursor()
    cursor.setPosition(5)  # mid-way through the URL, anchored on both sides
    win.body.setTextCursor(cursor)

    assert win.body.currentCharFormat().isAnchor() is True


def test_auto_linkify_then_menu_shows_edit_label_not_insert(qapp):
    """Confirms the two pieces compose correctly: once
    _auto_linkify_at_cursor() has turned the plain URL into a real link,
    populate_text_menu() (which contextMenuEvent calls right after) reads
    that same cursor state and already offers "Edit Hyperlink…", not
    "Hyperlink…" — no extra plumbing needed between the two."""
    win = make_note_window("Check out https://example.com/page for details")
    caret = win.body.textCursor()
    caret.setPosition(15)
    win.body.setTextCursor(caret)

    win._auto_linkify_at_cursor()

    menu = QMenu()
    win.populate_text_menu(menu)
    assert any(a.text() == "Edit Hyperlink…" for a in menu.actions())


def test_context_menu_label_reads_edit_hyperlink_inside_existing_link(qapp):
    """Regression: right-clicking with the caret inside an existing link
    (no new selection) always showed "Hyperlink…" — identical to the
    insert case — giving no hint that this invocation would edit the
    link in place rather than create a new one."""
    win = make_note_window("Read my stories and poems today")
    cursor = win.body.textCursor()
    cursor.movePosition(QTextCursor.Start)
    cursor.movePosition(QTextCursor.NextWord)
    cursor.movePosition(QTextCursor.NextWord, QTextCursor.KeepAnchor)
    cursor.movePosition(QTextCursor.NextWord, QTextCursor.KeepAnchor)
    cursor.movePosition(QTextCursor.EndOfWord, QTextCursor.KeepAnchor)
    link_start = cursor.selectionStart()
    win.body.setTextCursor(cursor)

    fmt = QTextCharFormat()
    fmt.setAnchor(True)
    fmt.setAnchorHref("https://example.com")
    cursor.mergeCharFormat(fmt)

    # Caret with no selection, positioned inside the existing link.
    caret = win.body.textCursor()
    caret.setPosition(link_start + 2)
    win.body.setTextCursor(caret)

    menu = QMenu()
    win.populate_text_menu(menu)
    titles = [a.text() for a in menu.actions()]
    assert "Edit Hyperlink…" in titles
    assert "Hyperlink…" not in titles


def test_context_menu_label_reads_hyperlink_outside_any_link(qapp):
    win = make_note_window("Just plain text")
    menu = QMenu()
    win.populate_text_menu(menu)
    titles = [a.text() for a in menu.actions()]
    assert "Hyperlink…" in titles
    assert "Edit Hyperlink…" not in titles


def test_right_click_directly_on_link_reads_edit_hyperlink_and_prefills_url(qapp, monkeypatch):
    """Regression (test case 3.11): right-clicking a hyperlink is Qt's
    default *context-menu* click, which — unlike a plain left-click —
    leaves the caret wherever it last happened to be instead of moving it
    to the click point (see _position_cursor_for_click). Reported live:
    right-clicking straight onto a link with the caret sitting elsewhere
    still showed "Hyperlink…" instead of "Edit Hyperlink…", and invoking
    it opened the dialog with a blank "https://" instead of the link's
    actual URL. The other Edit-Hyperlink tests above pre-position the
    caret directly and so never exercised the real right-click path that
    was actually broken."""
    win = make_note_window("Read my stories and poems today")
    cursor = win.body.textCursor()
    cursor.movePosition(QTextCursor.Start)
    cursor.movePosition(QTextCursor.NextWord)
    cursor.movePosition(QTextCursor.NextWord, QTextCursor.KeepAnchor)
    cursor.movePosition(QTextCursor.NextWord, QTextCursor.KeepAnchor)
    cursor.movePosition(QTextCursor.EndOfWord, QTextCursor.KeepAnchor)  # "stories and poems"
    link_start = cursor.selectionStart()

    fmt = QTextCharFormat()
    fmt.setAnchor(True)
    fmt.setAnchorHref("https://example.com")
    cursor.mergeCharFormat(fmt)

    # Caret left somewhere else entirely, as if the user had last clicked
    # or typed at the very start of the note — not on the link at all.
    win.body.setTextCursor(_cursor_at(win, 0))

    click_position = link_start + 2
    monkeypatch.setattr(
        win.body, "cursorForPosition", lambda pos: _cursor_at(win, click_position)
    )
    win.body._position_cursor_for_click(win.body.rect().center())

    menu = QMenu()
    win.populate_text_menu(menu)
    titles = [a.text() for a in menu.actions()]
    assert "Edit Hyperlink…" in titles
    assert "Hyperlink…" not in titles

    seen = {}

    def fake_exec(self):
        seen["prefilled"] = self.textValue()
        return QInputDialog.Rejected

    monkeypatch.setattr(QInputDialog, "exec", fake_exec)
    win.show_hyperlink_dialog()

    assert seen["prefilled"] == "https://example.com"


def test_anchor_span_finds_full_contiguous_link_text(qapp):
    win = make_note_window("Read my stories and poems today")
    cursor = win.body.textCursor()
    cursor.movePosition(QTextCursor.Start)
    cursor.movePosition(QTextCursor.NextWord)
    start_pos = cursor.position()
    cursor.movePosition(QTextCursor.NextWord, QTextCursor.KeepAnchor)
    cursor.movePosition(QTextCursor.NextWord, QTextCursor.KeepAnchor)
    cursor.movePosition(QTextCursor.EndOfWord, QTextCursor.KeepAnchor)
    end_pos = cursor.position()
    win.body.setTextCursor(cursor)

    fmt = QTextCharFormat()
    fmt.setAnchor(True)
    fmt.setAnchorHref("https://example.com")
    cursor.mergeCharFormat(fmt)

    start, end = win._anchor_span(start_pos + 2, "https://example.com")
    assert start == start_pos
    assert end == end_pos


def test_ctrl_click_on_link_opens_url(qapp, monkeypatch):
    win = make_note_window("Some text")
    win.body.anchorAt = lambda pos: "https://example.com"
    opened = {}
    monkeypatch.setattr(
        QDesktopServices, "openUrl", staticmethod(lambda url: opened.setdefault("url", url.toString()))
    )

    event = QMouseEvent(
        QEvent.MouseButtonRelease, QPointF(5, 5), Qt.LeftButton, Qt.LeftButton, Qt.ControlModifier
    )
    win.body.mouseReleaseEvent(event)

    assert opened["url"] == "https://example.com"


def test_plain_click_on_link_does_not_open_url(qapp, monkeypatch):
    win = make_note_window("Some text")
    win.body.anchorAt = lambda pos: "https://example.com"
    opened = {}
    monkeypatch.setattr(
        QDesktopServices, "openUrl", staticmethod(lambda url: opened.setdefault("url", url.toString()))
    )

    event = QMouseEvent(
        QEvent.MouseButtonRelease, QPointF(5, 5), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier
    )
    win.body.mouseReleaseEvent(event)

    assert "url" not in opened


def test_hyperlink_hover_tooltip_does_not_inherit_note_background(qapp):
    """Regression: QToolTip.showText()'s optional widget arg copies that
    widget's palette onto the tooltip — passing the note body (whose
    palette reflects its own background-color stylesheet) made the
    tooltip silently blend into the note's own color instead of
    rendering as a normal tooltip, reported as unreadable on hover."""
    if qapp.platformName() == "offscreen":
        pytest.skip("QToolTip isn't rendered under the offscreen QPA platform")

    from PySide6.QtGui import QPalette

    win = make_note_window("Some text")
    win.body.anchorAt = lambda pos: "https://example.com"

    # QToolTip only actually displays for an active/raised window — not
    # something a real hover needs, but required here to realize it
    # synthetically.
    win.activateWindow()
    win.raise_()
    for _ in range(10):
        qapp.processEvents()

    event = QMouseEvent(QEvent.MouseMove, QPointF(5, 5), Qt.NoButton, Qt.NoButton, Qt.NoModifier)
    win.body.mouseMoveEvent(event)
    for _ in range(10):
        qapp.processEvents()

    tooltip_widget = next(
        (w for w in qapp.topLevelWidgets() if w.windowType() == Qt.ToolTip and w.isVisible()),
        None,
    )
    assert tooltip_widget is not None
    bg = tooltip_widget.palette().color(QPalette.ToolTipBase)
    assert bg.name() != win.note.color


def _patch_image_dialog(monkeypatch, path):
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (path, "")))


def _make_png(tmp_path, name="pic.png", width=4, height=4, color="red"):
    path = tmp_path / name
    image = QImage(width, height, QImage.Format_RGB32)
    image.fill(QColor(color))
    image.save(str(path), "PNG")
    return str(path)


def test_insert_image_dialog_inserts_image_into_document(qapp, monkeypatch, tmp_path):
    win = make_note_window("")
    _patch_image_dialog(monkeypatch, _make_png(tmp_path))

    win.show_insert_image_dialog()

    cursor = win.body.textCursor()
    cursor.movePosition(QTextCursor.Start)
    cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)
    assert cursor.charFormat().isImageFormat()


def test_insert_image_dialog_replaces_selected_image_instead_of_stacking(qapp, monkeypatch, tmp_path):
    """Triggering the picture-insert action while a picture is already
    selected (the "Replace picture…" case in populate_text_menu) doesn't
    stack a second picture on top of the first — a QTextCursor insert
    always replaces its current selection, so the old picture is gone
    afterward, not just visually covered."""
    win = make_note_window("")
    _insert_test_image(win, color="red")
    image_end = win.body.textCursor().position()
    win.body._select_image_at(image_end)
    assert win._selection_is_image()

    _patch_image_dialog(monkeypatch, _make_png(tmp_path, color="blue"))
    win.show_insert_image_dialog()

    assert win.body.toPlainText() == "￼"


def test_insert_image_dialog_cancelled_does_nothing(qapp, monkeypatch):
    win = make_note_window("Some text")
    _patch_image_dialog(monkeypatch, "")

    win.show_insert_image_dialog()

    assert win.body.toPlainText() == "Some text"


def test_insert_image_dialog_invalid_file_shows_warning(qapp, monkeypatch, tmp_path):
    win = make_note_window("Some text")
    bad_path = tmp_path / "not-an-image.png"
    bad_path.write_bytes(b"not a real image")
    _patch_image_dialog(monkeypatch, str(bad_path))
    warned = {}
    monkeypatch.setattr(
        QMessageBox, "warning", staticmethod(lambda *a, **k: warned.setdefault("called", True))
    )

    win.show_insert_image_dialog()

    assert warned.get("called") is True
    assert win.body.toPlainText() == "Some text"


def test_insert_image_persists_through_html_round_trip(qapp, monkeypatch, tmp_path):
    """Regression guard for using a data: URI rather than the default
    cursor.insertImage(): that path stores pixel data only in an
    in-memory, process-wide QPixmapCache keyed by a generated name, so
    toHtml() serializes a bare reference that resolves to nothing once
    reloaded into a fresh document — e.g. after an app restart, which is
    exactly when notes.json gets read back via setHtml()."""
    win = make_note_window("")
    _patch_image_dialog(monkeypatch, _make_png(tmp_path))
    win.show_insert_image_dialog()

    html = win.body.toHtml()
    assert "data:image/png;base64," in html

    reloaded = make_note_window("")
    reloaded.body.setHtml(html)
    cursor = reloaded.body.textCursor()
    cursor.movePosition(QTextCursor.Start)
    cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)
    assert cursor.charFormat().isImageFormat()


def test_insert_image_grows_note_wider_to_fit_wide_picture(qapp, monkeypatch, tmp_path):
    """A picture wider than the note's current body isn't shrunk to fit —
    the note grows to accommodate it instead (see _grow_to_fit_content),
    since unlike a resize the user didn't ask for the picture to be made
    smaller."""
    win = make_note_window("")
    before_width = win.width()
    # Comfortably wider than the note but still well within the (offscreen
    # test) screen's available geometry, so this exercises growth rather
    # than the separate screen-cap path.
    target_width = before_width + (win.screen().availableGeometry().width() - before_width) // 2
    path = _make_png(tmp_path, width=target_width, height=40)
    _patch_image_dialog(monkeypatch, path)

    win.show_insert_image_dialog()

    cursor = win.body.textCursor()
    cursor.movePosition(QTextCursor.Start)
    cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)
    fmt = cursor.charFormat().toImageFormat()
    assert fmt.width() == target_width
    assert win.width() > before_width


def test_insert_image_grows_note_taller_to_fit_tall_picture(qapp, monkeypatch, tmp_path):
    """Same growth behavior as width, along the other axis: a tall/
    portrait picture grows the note's height instead of leaving it to
    scroll, since (unlike text) there's no way to keep reading past the
    fold."""
    win = make_note_window("")
    before_height = win.height()
    viewport_width = win.body.viewport().width()
    path = _make_png(tmp_path, width=viewport_width, height=viewport_width * 6)
    _patch_image_dialog(monkeypatch, path)

    win.show_insert_image_dialog()

    assert win.height() > before_height


def test_insert_image_caps_oversized_picture_to_screen(qapp, monkeypatch, tmp_path):
    """A picture too big to ever fit on screen (so the note can't simply
    grow to accommodate it) is the one case that still needs shrinking —
    down to the screen's available geometry, minus this note's own header/
    footer chrome."""
    win = make_note_window("")
    available = win.screen().availableGeometry()
    path = _make_png(tmp_path, width=available.width() * 4, height=available.height() * 4)
    _patch_image_dialog(monkeypatch, path)

    win.show_insert_image_dialog()

    cursor = win.body.textCursor()
    cursor.movePosition(QTextCursor.Start)
    cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)
    fmt = cursor.charFormat().toImageFormat()
    assert fmt.width() <= available.width()
    assert fmt.height() <= available.height() - win.header.height() - win.footer.height()


def test_insert_image_does_not_upscale_small_image(qapp, monkeypatch, tmp_path):
    win = make_note_window("")
    _patch_image_dialog(monkeypatch, _make_png(tmp_path, width=4, height=4))

    win.show_insert_image_dialog()

    cursor = win.body.textCursor()
    cursor.movePosition(QTextCursor.Start)
    cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)
    fmt = cursor.charFormat().toImageFormat()
    assert fmt.width() == 4


def test_insert_image_does_not_shrink_note_for_small_picture(qapp, monkeypatch, tmp_path):
    win = make_note_window("")
    before_width, before_height = win.width(), win.height()
    _patch_image_dialog(monkeypatch, _make_png(tmp_path, width=4, height=4))

    win.show_insert_image_dialog()

    assert (win.width(), win.height()) == (before_width, before_height)


def test_insert_image_growth_capped_at_screen_available_size(qapp, monkeypatch, tmp_path):
    win = make_note_window("")
    viewport_width = win.body.viewport().width()
    path = _make_png(tmp_path, width=viewport_width, height=viewport_width * 100)
    _patch_image_dialog(monkeypatch, path)

    win.show_insert_image_dialog()

    available = win.screen().availableGeometry()
    assert win.width() <= available.width()
    assert win.height() <= available.height()


def test_typing_after_backspacing_a_leading_image_keeps_default_format(qapp, monkeypatch, tmp_path):
    """Regression: backspacing away a picture that had nothing before it
    (e.g. the very first thing inserted into a note) left Qt's
    current-char-format tracking pointing at its own unset/ambient
    format — confirmed live. Text typed right after read faded/grey
    instead of the note's actual color, the same class of bug
    _apply_default_new_note_format already guards against for a
    brand-new note. See also
    test_typing_after_two_consecutive_enters_keeps_default_format below
    for the same underlying bug reached a different way, mid-document
    rather than at position 0 — _fix_ambient_char_format() (not
    ..._at_start(), renamed once it started handling both) covers both."""
    win = make_note_window("")
    _patch_image_dialog(monkeypatch, _make_png(tmp_path))
    win.show_insert_image_dialog()

    cursor = win.body.textCursor()
    cursor.movePosition(QTextCursor.End)
    win.body.setTextCursor(cursor)
    event = QKeyEvent(QEvent.KeyPress, Qt.Key_Backspace, Qt.NoModifier)
    qapp.sendEvent(win.body, event)
    assert win.body.toPlainText() == ""

    win.body.textCursor().insertText("hello")

    cursor = win.body.textCursor()
    cursor.movePosition(QTextCursor.Start)
    cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)
    fmt = cursor.charFormat()
    assert fmt.foreground().color().name() == win.manager.settings.default_font_color
    assert fmt.fontPointSize() == win.manager.settings.default_font_size


def test_typing_after_two_consecutive_enters_keeps_default_format(qapp):
    """Regression, reported live: type a line, press Enter twice (leaving
    a blank paragraph in between), type more — the new text read
    faded/grey instead of black. Confirmed directly: the character
    immediately before the cursor at that point already has the correct
    (real, non-ambient) format, but Qt's own current-char-format tracking
    — what newly typed text actually inherits — had desynced from it to
    its own unset/no-brush ambient format regardless. One Enter alone
    (no intervening empty paragraph) does not trigger this; confirmed
    that specifically too. Same underlying bug class as
    test_typing_after_backspacing_a_leading_image_keeps_default_format
    above, reached a different way — _fix_ambient_char_format() covers
    both since it no longer only checks cursor position 0."""
    win = make_note_window("")
    win.body.insertPlainText("First line")

    for _ in range(2):
        event = QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier)
        qapp.sendEvent(win.body, event)
    win.body.insertPlainText("Second")

    last_block = win.body.document().lastBlock()
    cursor = QTextCursor(last_block)
    cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
    fmt = cursor.charFormat()
    assert fmt.foreground().color().name() == win.manager.settings.default_font_color


def test_typing_after_a_single_enter_is_unaffected(qapp):
    """Sanity check for the fix above: a single Enter (no intervening
    empty paragraph) was never broken — confirms the fix doesn't
    over-trigger and start rewriting formatting that was already fine."""
    win = make_note_window("")
    win.body.insertPlainText("First line")

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier)
    qapp.sendEvent(win.body, event)
    win.body.insertPlainText("Second")

    last_block = win.body.document().lastBlock()
    cursor = QTextCursor(last_block)
    cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
    fmt = cursor.charFormat()
    assert fmt.foreground().color().name() == win.manager.settings.default_font_color


def test_typing_after_arrowing_up_into_a_blank_line_keeps_default_format(qapp):
    """Regression, reported live: type a line, press Enter several times,
    type on the new line, then arrow up into one of the blank lines left
    in between and type there — the text read grey. Distinct from
    test_typing_after_two_consecutive_enters_keeps_default_format above:
    that bug is caused by typing itself (textChanged fires and
    _fix_ambient_char_format runs, but only after the fact), whereas this
    one is caused by cursor movement alone. Confirmed directly: landing
    on that blank line via the Up arrow already desyncs the ambient
    format to no-brush with no text change at all — and textChanged never
    fires for a pure cursor move, so the fix never got a chance to run
    before the next character was typed. Fixed by also connecting
    _fix_ambient_char_format to cursorPositionChanged."""
    win = make_note_window("")
    win.body.insertPlainText("First line")

    for _ in range(6):
        event = QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier)
        qapp.sendEvent(win.body, event)
    win.body.insertPlainText("Second line")

    up_event = QKeyEvent(QEvent.KeyPress, Qt.Key_Up, Qt.NoModifier)
    qapp.sendEvent(win.body, up_event)
    win.body.insertPlainText("X")

    cursor = win.body.textCursor()
    cursor.movePosition(QTextCursor.PreviousCharacter, QTextCursor.KeepAnchor)
    fmt = cursor.charFormat()
    # An unset/no-brush foreground's .color() also happens to read back as
    # "#000000" (a default-constructed QColor), same as the real default
    # color here — checking .style() too is what actually distinguishes
    # "really set to black" from "never set at all", the exact gap that
    # let this bug through undetected.
    assert fmt.foreground().style() == Qt.BrushStyle.SolidPattern
    assert fmt.foreground().color().name() == win.manager.settings.default_font_color


def _insert_test_image(win, width=10, height=10, color="blue"):
    image = QImage(width, height, QImage.Format_RGB32)
    image.fill(QColor(color))
    win.body.textCursor().insertImage(image)


def _cursor_at(win, position):
    cursor = QTextCursor(win.body.document())
    cursor.setPosition(position)
    return cursor


def test_select_image_at_selects_image_from_position_before_it(qapp):
    win = make_note_window("")
    _insert_test_image(win)
    image_end = win.body.textCursor().position()
    image_start = image_end - 1

    win.body._select_image_at(image_start)

    cursor = win.body.textCursor()
    assert sorted((cursor.selectionStart(), cursor.selectionEnd())) == [image_start, image_end]
    assert cursor.charFormat().isImageFormat()


def test_select_image_at_selects_image_from_position_after_it(qapp):
    win = make_note_window("")
    _insert_test_image(win)
    image_end = win.body.textCursor().position()
    image_start = image_end - 1

    win.body._select_image_at(image_end)

    cursor = win.body.textCursor()
    assert sorted((cursor.selectionStart(), cursor.selectionEnd())) == [image_start, image_end]


def test_select_image_at_moves_plain_text_click_without_selecting(qapp):
    """No image at the click point: a right-click on plain text shouldn't
    manufacture a selection that wasn't there before, but the caret does
    move to the click position — regression guard for Edit Hyperlink and
    friends reading stale cursor state left over from wherever the user
    last clicked, instead of the actual right-click point (see
    _position_cursor_for_click)."""
    win = make_note_window("plain text, no image")
    cursor = win.body.textCursor()
    cursor.movePosition(QTextCursor.Start)
    win.body.setTextCursor(cursor)

    win.body._select_image_at(3)

    assert win.body.textCursor().hasSelection() is False
    assert win.body.textCursor().position() == 3


def test_select_image_at_preserves_ambient_format_on_empty_note(qapp):
    """Reported live: right-clicking a brand-new, never-typed note (e.g.
    to open Font…) showed the wrong font size — the app's base font
    instead of the configured default. Root cause: the default font/color
    set by _apply_default_new_note_format() lives only in the outgoing
    cursor's in-memory current-char-format, since an empty document has
    no real character to carry it — replacing the cursor via
    setTextCursor() below (what every right-click does, through
    _position_cursor_for_click) silently discarded it. Regression guard
    for that discard, not for anything image-related."""
    class CustomManager:
        boards = {}
        settings = Settings(default_font_size=22)

    win = NoteWindow(Note(), manager=CustomManager())
    assert win.body.currentCharFormat().fontPointSize() == 22

    win.body._select_image_at(0)

    assert win.body.currentCharFormat().fontPointSize() == 22


def test_select_image_at_leaves_existing_selection_when_click_inside_it(qapp):
    """Matches ordinary right-click behavior elsewhere in the app: clicking
    inside an existing multi-character selection keeps it (so Cut/Copy/
    Delete act on the whole selection), rather than collapsing it just
    because the click point happens to also sit next to an image
    boundary."""
    win = make_note_window("before")
    cursor = win.body.textCursor()
    cursor.movePosition(QTextCursor.Start)
    cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
    win.body.setTextCursor(cursor)

    win.body._select_image_at(2)

    cursor = win.body.textCursor()
    assert sorted((cursor.selectionStart(), cursor.selectionEnd())) == [0, len("before")]
    assert not cursor.charFormat().isImageFormat()


def test_context_menu_selects_image_and_enables_delete(qapp, monkeypatch):
    """Regression: right-clicking directly on an inserted picture used to
    leave whatever cursor/selection state already existed untouched (Qt's
    default right-click behavior only repositions the cursor for a plain
    click, not a context-menu click) — so Cut/Copy/Delete stayed disabled
    in the standard context menu even though the picture under the click
    was exactly what the user meant to act on."""
    win = make_note_window("")
    _insert_test_image(win)
    image_end = win.body.textCursor().position()
    image_start = image_end - 1
    win.body.setTextCursor(_cursor_at(win, image_start))  # plain cursor, no selection

    monkeypatch.setattr(win.body, "cursorForPosition", lambda pos: _cursor_at(win, image_start))
    win.body._position_cursor_for_click(win.body.rect().center())

    assert win.body.textCursor().hasSelection()
    menu = win.body.createStandardContextMenu()
    delete_action = next(a for a in menu.actions() if a.text() == "Delete")
    assert delete_action.isEnabled()


def test_text_menu_hides_font_bullets_indent_for_image_selection(qapp):
    """Font/Bullets/Indent don't do anything meaningful on an image
    selection, so the menu should skip them entirely rather than offering
    harmless-but-confusing no-ops."""
    win = make_note_window("")
    _insert_test_image(win)
    image_end = win.body.textCursor().position()
    win.body._select_image_at(image_end)
    assert win._selection_is_image()

    menu = QMenu()
    win.populate_text_menu(menu)

    titles = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert titles == ["Replace picture…", "Hyperlink…", "Find…"]


def test_text_menu_keeps_all_items_for_plain_text_selection(qapp):
    win = make_note_window("Some text")
    select_all(win)
    assert not win._selection_is_image()

    menu = QMenu()
    win.populate_text_menu(menu)

    titles = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert titles == [
        "Font…",
        "Font Style",
        "Font Color…",
        "Bullets && Numbering",
        "Increase Indent",
        "Decrease Indent",
        "Add picture…",
        "Hyperlink…",
        "Find…",
    ]


def test_text_menu_has_add_picture_action(qapp):
    win = make_note_window("Some text")
    menu = QMenu()
    win.populate_text_menu(menu)

    titles = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert "Add picture…" in titles


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


def test_toggle_rolled_hides_and_restores_title_bar(qapp):
    """Regression, reported live via a screenshot: rolling up a titled
    note left title_bar visible while the whole window shrank to just
    HEADER_HEIGHT — everything (header + title strip) got crammed into
    that sliver instead, rendering as a garbled mess of squashed text.
    title_bar must hide along with body/footer on roll, and only come
    back on unroll if the note actually still has a title (matching
    set_title()'s own rule, so an untitled note doesn't grow a blank
    title strip back)."""
    win = NoteWindow(Note(title="Groceries"), manager=FakeManager())
    assert not win.title_bar.isHidden()

    win.toggle_rolled()
    assert win.title_bar.isHidden()

    win.toggle_rolled()
    assert not win.title_bar.isHidden()
    assert win.title_bar.label.text() == "Groceries"


def test_toggle_rolled_keeps_title_bar_hidden_for_untitled_note(qapp):
    win = make_note_window("Some text")
    assert win.title_bar.isHidden()

    win.toggle_rolled()
    win.toggle_rolled()

    assert win.title_bar.isHidden()


def test_toggle_rolled_hides_find_bar(qapp):
    """find_bar is transient UI, not persisted note content — rolling up
    while it's open must hide it (same crammed-into-a-sliver bug as
    title_bar), and it shouldn't reopen itself on unroll either, same as
    any other reason it might have been closed."""
    win = make_note_window("Some text")
    win.find_bar.open_bar()
    assert not win.find_bar.isHidden()

    win.toggle_rolled()
    assert win.find_bar.isHidden()

    win.toggle_rolled()
    assert win.find_bar.isHidden()


def test_set_rolled_true_collapses_note(qapp):
    win = make_note_window()
    win.set_rolled(True)
    assert win.note.rolled_up is True
    assert win.body.isHidden()


def test_set_rolled_false_expands_note(qapp):
    win = make_note_window()
    win.toggle_rolled()
    win.set_rolled(False)
    assert win.note.rolled_up is False
    assert not win.body.isHidden()


def test_set_rolled_is_a_noop_when_already_in_requested_state(qapp):
    """Regression guard for the bulk "Roll Up/Down Notes" tray action:
    set_rolled() must skip the work (and the mark_changed() it triggers)
    when the note is already in the requested state, rather than treating
    every call as a fresh edit."""
    win = make_note_window()
    changed = []
    win.changed.connect(lambda: changed.append(1))

    win.set_rolled(False)  # already expanded

    assert len(changed) == 0


def test_find_action_disabled_when_note_empty(qapp):
    win = make_note_window("")
    assert win.find_action.isEnabled() is False


def test_find_action_enabled_when_note_has_text(qapp):
    win = make_note_window("Some text")
    assert win.find_action.isEnabled() is True


def test_find_action_disabled_after_deleting_all_text(qapp):
    """The requirement (per user): Find must only be enabled while the note
    actually has text — re-checked live, not just at construction."""
    win = make_note_window("Some text")
    assert win.find_action.isEnabled() is True

    win.body.setPlainText("")

    assert win.find_action.isEnabled() is False


def test_find_bar_background_tints_toward_note_color(qapp):
    win = make_note_window("Some text")
    assert find_bar_tint(win.note.color) in win.find_bar.styleSheet()


def test_find_bar_tint_updates_when_note_color_changes(qapp):
    win = make_note_window("Some text")

    win.set_color("#90caf9")

    assert find_bar_tint("#90caf9") in win.find_bar.styleSheet()


def test_toggle_find_bar_does_nothing_on_empty_note(qapp):
    win = make_note_window("")
    win.toggle_find_bar()
    assert win.find_bar.isHidden()


def test_toggle_find_bar_shows_and_focuses_field(qapp):
    win = make_note_window("Some text")

    win.toggle_find_bar()

    assert not win.find_bar.isHidden()
    win.activateWindow()
    for _ in range(5):
        qapp.processEvents()
    assert win.find_bar.field.hasFocus()


def test_find_bar_field_has_a_clear_button(qapp):
    """Regression, reported live: the native clear button
    (setClearButtonEnabled) draws a light icon, invisible against this
    field's hard-coded white background (FIND_BAR_QSS) -- every other
    text field in the app sits on the system's own, usually-dark palette
    instead, which is why only this one field needed a manual fixed-dark
    icon (see _dark_clear_icon). Only visible once there's text to
    clear, matching the native button's own behavior; clicking it clears
    the field."""
    win = make_note_window("Some text")
    actions = win.find_bar.field.actions()
    assert len(actions) == 1
    clear_action = actions[0]
    assert clear_action.isVisible() is False

    win.find_bar.field.setText("needle")
    assert clear_action.isVisible() is True

    clear_action.trigger()
    assert win.find_bar.field.text() == ""
    assert clear_action.isVisible() is False


def test_find_selects_first_match_as_you_type(qapp):
    win = make_note_window("alpha beta alpha")

    win.find_bar.field.setText("beta")

    cursor = win.body.textCursor()
    assert cursor.selectedText() == "beta"


def test_find_next_previous_actions_disabled_until_bar_opens(qapp):
    """Regression: F3/Shift+F3 must only fire while the find bar is
    actually open, matching how other in-note shortcuts are scoped (e.g.
    find_action itself is disabled for an empty note)."""
    win = make_note_window("alpha beta alpha")

    assert not win.find_next_action.isEnabled()
    assert not win.find_previous_action.isEnabled()

    win.find_bar.open_bar()

    assert win.find_next_action.isEnabled()
    assert win.find_previous_action.isEnabled()

    win.find_bar.close_bar()

    assert not win.find_next_action.isEnabled()
    assert not win.find_previous_action.isEnabled()


def test_find_next_action_triggers_find_next(qapp):
    win = make_note_window("alpha beta alpha")
    win.find_bar.open_bar()
    win.find_bar.field.setText("alpha")
    first_start = win.body.textCursor().selectionStart()

    win.find_next_action.trigger()

    cursor = win.body.textCursor()
    assert cursor.selectedText() == "alpha"
    assert cursor.selectionStart() > first_start


def test_find_previous_action_triggers_find_previous(qapp):
    win = make_note_window("alpha beta alpha")
    win.find_bar.open_bar()
    win.find_bar.field.setText("alpha")  # lands on the first match
    win.find_bar.find_next()  # now on the second "alpha"
    second_start = win.body.textCursor().selectionStart()

    win.find_previous_action.trigger()

    cursor = win.body.textCursor()
    assert cursor.selectedText() == "alpha"
    assert cursor.selectionStart() < second_start


def test_find_next_advances_to_subsequent_match(qapp):
    win = make_note_window("alpha beta alpha")
    win.find_bar.field.setText("alpha")
    first_start = win.body.textCursor().selectionStart()

    win.find_bar.find_next()

    cursor = win.body.textCursor()
    assert cursor.selectedText() == "alpha"
    assert cursor.selectionStart() > first_start


def test_find_next_wraps_around_to_first_match(qapp):
    win = make_note_window("alpha beta alpha")
    win.find_bar.field.setText("alpha")
    win.find_bar.find_next()  # now on the second "alpha"

    win.find_bar.find_next()  # should wrap back around

    assert win.body.textCursor().selectionStart() == 0


def test_find_previous_wraps_around_to_last_match(qapp):
    win = make_note_window("alpha beta alpha")
    win.find_bar.field.setText("alpha")  # lands on the first match

    win.find_bar.find_previous()

    cursor = win.body.textCursor()
    assert cursor.selectedText() == "alpha"
    assert cursor.selectionStart() > 0


def test_find_sets_not_found_style_for_missing_text(qapp):
    win = make_note_window("alpha beta")

    win.find_bar.field.setText("zzz")

    assert "ffcdd2" in win.find_bar.field.styleSheet()


def test_find_clears_not_found_style_once_a_match_resumes(qapp):
    win = make_note_window("alpha beta")
    win.find_bar.field.setText("zzz")
    assert "ffcdd2" in win.find_bar.field.styleSheet()

    win.find_bar.field.setText("alpha")

    assert win.find_bar.field.styleSheet() == ""


def test_close_bar_hides_and_refocuses_body(qapp):
    win = make_note_window("Some text")
    win.toggle_find_bar()
    assert not win.find_bar.isHidden()

    win.find_bar.close_bar()

    assert win.find_bar.isHidden()
    win.activateWindow()
    for _ in range(5):
        qapp.processEvents()
    assert win.body.hasFocus()


def test_escape_key_in_find_field_closes_bar(qapp):
    win = make_note_window("Some text")
    win.toggle_find_bar()

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
    qapp.sendEvent(win.find_bar.field, event)

    assert win.find_bar.isHidden()


def test_find_action_has_ctrl_f_shortcut(qapp):
    win = make_note_window("Some text")
    assert win.find_action.shortcut().toString() == "Ctrl+F"


def test_locked_note_is_read_only(qapp):
    win = make_note_window("Some text")
    assert win.body.isReadOnly() is False

    win.set_locked(True)

    assert win.note.locked is True
    assert win.body.isReadOnly() is True


def test_unlocking_note_restores_editing(qapp):
    win = make_note_window("Some text")
    win.set_locked(True)

    win.set_locked(False)

    assert win.note.locked is False
    assert win.body.isReadOnly() is False


def test_note_constructed_locked_applies_read_only_at_startup(qapp):
    win = NoteWindow(Note(locked=True), manager=FakeManager())
    assert win.body.isReadOnly() is True


def test_locked_note_disables_formatting_shortcuts(qapp):
    """setReadOnly() alone only blocks QTextEdit's own default keystroke
    handling — these persistent QActions carry their own global Ctrl+B/I/
    U/K shortcuts wired directly to the window, so locking must disable
    them too or a locked note could still be formatted from the keyboard."""
    win = make_note_window("Some text")

    win.set_locked(True)

    assert win.bold_action.isEnabled() is False
    assert win.italic_action.isEnabled() is False
    assert win.underline_action.isEnabled() is False
    assert win.strikethrough_action.isEnabled() is False


def test_unlocking_note_reenables_formatting_shortcuts(qapp):
    win = make_note_window("Some text")
    win.set_locked(True)

    win.set_locked(False)

    assert win.bold_action.isEnabled() is True
    assert win.italic_action.isEnabled() is True
    assert win.underline_action.isEnabled() is True
    assert win.strikethrough_action.isEnabled() is True


def test_text_menu_only_shows_find_when_locked(qapp):
    win = make_note_window("Some text")
    win.set_locked(True)

    menu = QMenu()
    win.populate_text_menu(menu)

    titles = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert titles == ["Find…"]


def test_note_actions_menu_lock_action_reflects_state(qapp):
    win = make_note_window("Some text")
    win.set_locked(True)

    menu = QMenu()
    win.populate_note_actions_menu(menu)

    lock_action = next(a for a in menu.actions() if a.text() == "Lock Note")
    assert lock_action.isCheckable() is True
    assert lock_action.isChecked() is True


def test_toggle_lock_action_in_menu_updates_note_model(qapp):
    win = make_note_window("Some text")
    menu = QMenu()
    win.populate_note_actions_menu(menu)
    lock_action = next(a for a in menu.actions() if a.text() == "Lock Note")

    lock_action.trigger()

    assert win.note.locked is True
    assert win.body.isReadOnly() is True


def test_tab_key_does_not_indent_list_when_locked(qapp):
    win = make_note_window("Item one")
    select_all(win)
    win._set_list_style(QTextListFormat.ListDecimal)
    win.set_locked(True)

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_Tab, Qt.NoModifier)
    qapp.sendEvent(win.body, event)

    block = win.body.document().findBlockByNumber(0)
    assert block.textList().format().indent() == 1


def test_find_action_stays_enabled_while_note_is_locked(qapp):
    """Find only edits nothing (search/navigation), so locking a note
    shouldn't disable it — it's excluded from set_locked's shortcut
    guard on purpose."""
    win = make_note_window("Some text")

    win.set_locked(True)

    assert win.find_action.isEnabled() is True


class _FakeWindowWatcher(QObject):
    """Stands in for the real WindowWatcher (a QThread that opens its own
    X11 connection) — matches this project's existing precedent for
    hotkey.HotkeyListener, whose actual X11 interaction also isn't unit
    tested, only its pure-logic helpers are. Signals are emitted manually
    in tests rather than by a real minimize/restore/close."""

    minimized = Signal()
    restored = Signal()
    closed = Signal()

    def __init__(self, window_id, parent=None):
        super().__init__(parent)
        self.window_id = window_id
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


def _patch_window_watcher(monkeypatch, iconic=False):
    monkeypatch.setattr("take_note.note_window.WindowWatcher", _FakeWindowWatcher)
    monkeypatch.setattr("take_note.note_window.is_window_iconic", lambda window_id: iconic)


def test_set_stuck_to_window_hides_note_if_already_iconic(qapp, monkeypatch):
    _patch_window_watcher(monkeypatch, iconic=True)
    win = make_note_window("Some text")

    win.set_stuck_to_window(12345)

    assert win._stuck_window_id == 12345
    assert win.isHidden()


def test_set_stuck_to_window_does_not_hide_note_if_not_iconic(qapp, monkeypatch):
    _patch_window_watcher(monkeypatch, iconic=False)
    win = make_note_window("Some text")

    win.set_stuck_to_window(12345)

    assert not win.isHidden()


def test_window_watcher_minimized_signal_hides_note(qapp, monkeypatch):
    _patch_window_watcher(monkeypatch)
    win = make_note_window("Some text")
    win.set_stuck_to_window(12345)

    win._window_watcher.minimized.emit()

    assert win.isHidden()


def test_window_watcher_restored_signal_shows_note(qapp, monkeypatch):
    _patch_window_watcher(monkeypatch)
    win = make_note_window("Some text")
    win.set_stuck_to_window(12345)
    win.hide()

    win._window_watcher.restored.emit()

    assert not win.isHidden()


def test_window_watcher_closed_signal_unsticks_and_shows_note(qapp, monkeypatch):
    _patch_window_watcher(monkeypatch)
    win = make_note_window("Some text")
    win.set_stuck_to_window(12345)
    win.hide()

    win._window_watcher.closed.emit()

    assert win._stuck_window_id is None
    assert not win.isHidden()


def test_unstick_from_window_stops_watcher_and_shows_note(qapp, monkeypatch):
    _patch_window_watcher(monkeypatch)
    win = make_note_window("Some text")
    win.set_stuck_to_window(12345)
    watcher = win._window_watcher

    win.unstick_from_window()

    assert watcher.stopped is True
    assert win._stuck_window_id is None
    assert not win.isHidden()


def test_sticking_to_new_window_stops_previous_watcher(qapp, monkeypatch):
    """Regression guard: re-sticking (without unsticking first) must not
    leak the previous WindowWatcher thread."""
    _patch_window_watcher(monkeypatch)
    win = make_note_window("Some text")
    win.set_stuck_to_window(111)
    first_watcher = win._window_watcher

    win.set_stuck_to_window(222)

    assert first_watcher.stopped is True
    assert win._stuck_window_id == 222


def test_note_actions_menu_shows_unstick_when_stuck(qapp, monkeypatch):
    _patch_window_watcher(monkeypatch)
    win = make_note_window("Some text")
    win.set_stuck_to_window(12345)

    menu = QMenu()
    win.populate_note_actions_menu(menu)

    titles = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert "Unstick from Window" in titles
    assert "Stick to Window…" not in titles


def test_show_stick_window_dialog_no_windows_shows_message(qapp, monkeypatch):
    """show_stick_window_dialog() builds a bare QMessageBox instance
    (rather than the static information(self, ...) convenience) so it
    doesn't inherit a board-attached note's own palette bleed — same fix
    as every other note dialog; see _new_note_dialog's docstring. Tests
    patch exec() on the instance instead of information()."""
    monkeypatch.setattr("take_note.note_window.list_windows", lambda: [])
    informed = {}

    def fake_exec(self):
        informed["called"] = True
        informed["parent"] = self.parent()
        return QMessageBox.Ok

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    win = make_note_window("Some text")

    win.show_stick_window_dialog()

    assert informed.get("called") is True
    assert informed.get("parent") is None
    assert win._stuck_window_id is None


def test_show_stick_window_dialog_picks_selected_window(qapp, monkeypatch):
    """show_stick_window_dialog() builds a bare QInputDialog combo-box
    instance (rather than the static getItem(self, ...) convenience) for
    the same palette-bleed reason — tests patch exec()/textValue() on the
    instance instead of getItem()."""
    _patch_window_watcher(monkeypatch)
    monkeypatch.setattr(
        "take_note.note_window.list_windows", lambda: [(111, "Firefox"), (222, "Terminal")]
    )
    seen = {}

    def fake_exec(self):
        seen["parent"] = self.parent()
        return QInputDialog.Accepted

    monkeypatch.setattr(QInputDialog, "exec", fake_exec)
    monkeypatch.setattr(QInputDialog, "textValue", lambda self: "Terminal (0x%x)" % 222)
    win = make_note_window("Some text")

    win.show_stick_window_dialog()

    assert win._stuck_window_id == 222
    assert seen["parent"] is None


def test_show_stick_window_dialog_cancelled_does_not_stick(qapp, monkeypatch):
    monkeypatch.setattr("take_note.note_window.list_windows", lambda: [(111, "Firefox")])
    monkeypatch.setattr(QInputDialog, "exec", lambda self: QInputDialog.Rejected)
    win = make_note_window("Some text")

    win.show_stick_window_dialog()

    assert win._stuck_window_id is None


def test_header_lock_button_reflects_initial_unlocked_state(qapp):
    win = make_note_window("Some text")
    assert not win.header.lock_btn.icon().isNull()
    assert win.header.lock_btn.toolTip() == "Lock note"


def test_header_lock_button_reflects_locked_state(qapp):
    """The lock icon is hand-drawn (see lock_icon()) rather than a text
    glyph — neither padlock emoji renders at all in this app's actual
    runtime environment, confirmed directly (a blank gap in the header)
    — so the two states are compared as rendered pixel data rather than
    by a QToolButton.text() value."""
    win = make_note_window("Some text")
    unlocked_image = win.header.lock_btn.icon().pixmap(18, 18).toImage()

    win.set_locked(True)

    locked_image = win.header.lock_btn.icon().pixmap(18, 18).toImage()
    assert locked_image != unlocked_image
    assert win.header.lock_btn.toolTip() == "Unlock note"


def _click_button(qapp, button):
    pos = QPointF(5, 5)
    for event_type in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
        event = QMouseEvent(event_type, pos, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        qapp.sendEvent(button, event)


def _double_click_button(qapp, button):
    pos = QPointF(5, 5)
    sequence = [
        QEvent.MouseButtonPress,
        QEvent.MouseButtonRelease,
        QEvent.MouseButtonDblClick,
        QEvent.MouseButtonRelease,
    ]
    for event_type in sequence:
        event = QMouseEvent(event_type, pos, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        qapp.sendEvent(button, event)


def test_single_click_on_lock_button_toggles_lock(qapp):
    win = make_note_window("Some text")
    assert win.note.locked is False

    _click_button(qapp, win.header.lock_btn)

    assert win.note.locked is True


def test_double_click_on_lock_button_toggles_lock_exactly_once(qapp):
    """Regression: a real double-click fires QAbstractButton's `clicked`
    signal twice (once per half of the double-click, confirmed directly)
    — wiring it straight to a toggle would flip the lock twice, a net
    no-op. _LockButton suppresses the second emission so a double-click
    still ends up toggling exactly once, same as a single click."""
    win = make_note_window("Some text")
    assert win.note.locked is False

    _double_click_button(qapp, win.header.lock_btn)

    assert win.note.locked is True


def test_double_click_on_lock_button_from_locked_state_unlocks_once(qapp):
    win = make_note_window("Some text")
    win.set_locked(True)

    _double_click_button(qapp, win.header.lock_btn)

    assert win.note.locked is False


class FakeBoard:
    """Bare stand-in for NotepadWindow — attach_to_board() only needs
    `.canvas` (a real QWidget to reparent into) and `.board.id`."""

    def __init__(self):
        self.canvas = QWidget()
        self.board = Board(id="board-1")


def test_size_grip_hidden_after_attaching_to_board(qapp):
    """QSizeGrip resizes self.window() — the nearest top-level ancestor.
    Once attached to a board, that's the board, not this note (confirmed
    live: dragging it resized the whole board). It also left a visible
    rendering artifact — a small notch cut into the note's rounded corner
    — since a plain child widget doesn't get the whole-window alpha
    clipping a real top-level translucent window gets from the
    compositor. Hiding it sidesteps both."""
    win = make_note_window("Some text")
    board = FakeBoard()
    assert win.size_grip.isVisible()

    win.attach_to_board(board)

    assert not win.size_grip.isVisible()


def test_size_grip_shown_again_after_detaching_from_board(qapp):
    win = make_note_window("Some text")
    board = FakeBoard()
    win.attach_to_board(board)

    win.attach_to_board(None)

    assert win.size_grip.isVisible()


def test_size_grip_hidden_for_note_constructed_already_attached(qapp):
    """Covers loading a note from disk that's already attached — not just
    the live attach_to_board() transition."""
    win = NoteWindow(Note(board_id="board-1"), manager=FakeManager())
    assert not win.size_grip.isVisible()


class _SpellCheckManager:
    boards = {}

    def __init__(self, spell_check_enabled=True):
        self.settings = Settings(spell_check_enabled=spell_check_enabled)

    def _schedule_save(self):
        pass


def test_attaching_spell_highlighter_to_existing_content_does_not_mark_note_changed(qapp, monkeypatch):
    """The regression this feature's whole design is built around:
    QSyntaxHighlighter's initial highlight pass on a document that
    already has content is deferred to the next event-loop iteration, not
    synchronous — confirmed directly. Naively attaching it would
    spuriously fire textChanged -> mark_changed() (bumping modified_at
    and scheduling a disk save) on every single note, on every launch,
    with spell-check on. NoteWindow._attach_spell_highlighter() guards
    against this via blockSignals()+rehighlight().

    mark_changed() already fires some number of times during perfectly
    normal construction regardless of spell-check (moveEvent/resizeEvent
    from the initial resize()/move() calls in __init__ call it directly)
    — confirmed directly, not assumed, by counting calls with spell-check
    off first. So the real regression check is that spell-check-enabled
    construction fires *exactly the same count* as spell-check-disabled
    construction of an otherwise-identical note, not that the count is
    zero outright."""
    monkeypatch.setattr(spellcheck, "is_available", lambda: True)
    monkeypatch.setattr(spellcheck, "check", lambda word: word != "wrold")

    class _CountingNoteWindow(NoteWindow):
        def __init__(self, *args, **kwargs):
            self.mark_changed_calls = 0
            super().__init__(*args, **kwargs)

        def mark_changed(self):
            self.mark_changed_calls += 1
            super().mark_changed()

    baseline = _CountingNoteWindow(
        Note(html="<p>hello wrold</p>"), manager=_SpellCheckManager(spell_check_enabled=False)
    )
    qapp.processEvents()

    win = _CountingNoteWindow(
        Note(html="<p>hello wrold</p>"), manager=_SpellCheckManager(spell_check_enabled=True)
    )
    assert win.spell_highlighter is not None
    assert win.mark_changed_calls == baseline.mark_changed_calls

    qapp.processEvents()
    assert win.mark_changed_calls == baseline.mark_changed_calls  # catches the deferred initial-highlight pass

    win.body.insertPlainText("!")
    assert win.mark_changed_calls > baseline.mark_changed_calls  # normal editing still works afterward


def test_spell_highlighter_underlines_misspelled_words_only(qapp, monkeypatch):
    monkeypatch.setattr(spellcheck, "is_available", lambda: True)
    monkeypatch.setattr(spellcheck, "check", lambda word: word != "wrold")

    manager = _SpellCheckManager(spell_check_enabled=True)
    win = NoteWindow(Note(html="<p>hello wrold today</p>"), manager=manager)
    qapp.processEvents()

    assert win.spell_highlighter is not None
    block = win.body.document().findBlockByNumber(0)
    formats = block.layout().formats()
    underlined = [(f.start, f.length) for f in formats]
    assert (6, 5) in underlined  # "wrold"
    assert not any(start in (0, 12) for start, _ in underlined)  # "hello"/"today" untouched


def test_spell_highlighter_skips_hyperlinked_text(qapp, monkeypatch):
    """Checking URL/hyperlink text as spelling errors would just be
    constant false-positive noise."""
    monkeypatch.setattr(spellcheck, "is_available", lambda: True)
    monkeypatch.setattr(spellcheck, "check", lambda word: False)  # everything "misspelled"

    manager = _SpellCheckManager(spell_check_enabled=True)
    win = NoteWindow(Note(), manager=manager)
    cursor = win.body.textCursor()
    fmt = QTextCharFormat()
    fmt.setAnchor(True)
    fmt.setAnchorHref("https://example.com")
    cursor.insertText("linktext", fmt)
    qapp.processEvents()

    block = win.body.document().findBlockByNumber(0)
    formats = block.layout().formats()
    assert formats == []


def test_spell_check_disabled_by_default(qapp):
    win = make_note_window("Some text")
    assert win.spell_highlighter is None


def test_attach_spell_highlighter_is_idempotent(qapp, monkeypatch):
    monkeypatch.setattr(spellcheck, "is_available", lambda: True)
    win = make_note_window("Some text")

    win._attach_spell_highlighter()
    first = win.spell_highlighter
    win._attach_spell_highlighter()

    assert win.spell_highlighter is first


def test_detach_spell_highlighter_removes_it(qapp, monkeypatch):
    monkeypatch.setattr(spellcheck, "is_available", lambda: True)
    win = make_note_window("Some text")
    win._attach_spell_highlighter()

    win._detach_spell_highlighter()

    assert win.spell_highlighter is None


def test_detach_spell_highlighter_is_a_no_op_when_never_attached(qapp):
    win = make_note_window("Some text")
    win._detach_spell_highlighter()  # must not raise
    assert win.spell_highlighter is None


def test_context_menu_offers_suggestions_for_misspelled_word(qapp, monkeypatch):
    monkeypatch.setattr(spellcheck, "is_available", lambda: True)
    monkeypatch.setattr(spellcheck, "check", lambda word: word != "wrold")
    monkeypatch.setattr(spellcheck, "suggest", lambda word: ["world", "word"])

    manager = _SpellCheckManager(spell_check_enabled=True)
    win = NoteWindow(Note(html="<p>hello wrold today</p>"), manager=manager)
    caret = win.body.textCursor()
    caret.setPosition(8)  # inside "wrold"
    win.body.setTextCursor(caret)

    menu = QMenu()
    win.populate_text_menu(menu)

    titles = [a.text() for a in menu.actions()]
    assert "world" in titles
    assert "word" in titles


def test_context_menu_omits_suggestions_for_correctly_spelled_word(qapp, monkeypatch):
    monkeypatch.setattr(spellcheck, "is_available", lambda: True)
    monkeypatch.setattr(spellcheck, "check", lambda word: True)

    manager = _SpellCheckManager(spell_check_enabled=True)
    win = NoteWindow(Note(html="<p>hello there</p>"), manager=manager)
    caret = win.body.textCursor()
    caret.setPosition(2)
    win.body.setTextCursor(caret)

    menu = QMenu()
    win.populate_text_menu(menu)

    assert "(No suggestions)" not in [a.text() for a in menu.actions()]


def test_clicking_a_suggestion_replaces_the_word_in_place(qapp, monkeypatch):
    monkeypatch.setattr(spellcheck, "is_available", lambda: True)
    monkeypatch.setattr(spellcheck, "check", lambda word: word != "wrold")
    monkeypatch.setattr(spellcheck, "suggest", lambda word: ["world"])

    manager = _SpellCheckManager(spell_check_enabled=True)
    win = NoteWindow(Note(html="<p>hello wrold today</p>"), manager=manager)
    caret = win.body.textCursor()
    caret.setPosition(8)
    win.body.setTextCursor(caret)

    menu = QMenu()
    win.populate_text_menu(menu)
    suggestion_action = next(a for a in menu.actions() if a.text() == "world")

    suggestion_action.trigger()

    assert win.body.toPlainText() == "hello world today"


def test_context_menu_offers_ignore_and_add_to_dictionary_for_misspelled_word(qapp, monkeypatch):
    monkeypatch.setattr(spellcheck, "is_available", lambda: True)
    monkeypatch.setattr(spellcheck, "check", lambda word: word != "wrold")
    monkeypatch.setattr(spellcheck, "suggest", lambda word: ["world"])

    manager = _SpellCheckManager(spell_check_enabled=True)
    win = NoteWindow(Note(html="<p>hello wrold today</p>"), manager=manager)
    caret = win.body.textCursor()
    caret.setPosition(8)
    win.body.setTextCursor(caret)

    menu = QMenu()
    win.populate_text_menu(menu)

    titles = [a.text() for a in menu.actions()]
    assert "Ignore" in titles
    assert "Add to Dictionary" in titles


def test_context_menu_omits_ignore_and_add_to_dictionary_for_correctly_spelled_word(qapp, monkeypatch):
    monkeypatch.setattr(spellcheck, "is_available", lambda: True)
    monkeypatch.setattr(spellcheck, "check", lambda word: True)

    manager = _SpellCheckManager(spell_check_enabled=True)
    win = NoteWindow(Note(html="<p>hello there</p>"), manager=manager)
    caret = win.body.textCursor()
    caret.setPosition(2)
    win.body.setTextCursor(caret)

    menu = QMenu()
    win.populate_text_menu(menu)

    titles = [a.text() for a in menu.actions()]
    assert "Ignore" not in titles
    assert "Add to Dictionary" not in titles


def test_clicking_ignore_calls_spellcheck_ignore_with_the_word(qapp, monkeypatch):
    monkeypatch.setattr(spellcheck, "is_available", lambda: True)
    monkeypatch.setattr(spellcheck, "check", lambda word: word != "wrold")
    monkeypatch.setattr(spellcheck, "suggest", lambda word: [])
    calls = []
    monkeypatch.setattr(spellcheck, "ignore", lambda word: calls.append(word))

    manager = _SpellCheckManager(spell_check_enabled=True)
    win = NoteWindow(Note(html="<p>hello wrold today</p>"), manager=manager)
    caret = win.body.textCursor()
    caret.setPosition(8)
    win.body.setTextCursor(caret)

    menu = QMenu()
    win.populate_text_menu(menu)
    ignore_action = next(a for a in menu.actions() if a.text() == "Ignore")

    ignore_action.trigger()

    assert calls == ["wrold"]


def test_ignoring_a_word_persists_it_to_settings_and_schedules_a_save(qapp, monkeypatch):
    """"Ignore" is permanent-within-Take-Note! now, not session-only —
    persisted to Settings.ignored_words (replayed on every launch by
    NoteManager._replay_ignored_words()) rather than just Enchant's
    in-memory session dict."""
    monkeypatch.setattr(spellcheck, "is_available", lambda: True)
    monkeypatch.setattr(spellcheck, "check", lambda word: word != "wrold")
    monkeypatch.setattr(spellcheck, "suggest", lambda word: [])
    monkeypatch.setattr(spellcheck, "ignore", lambda word: None)

    manager = _SpellCheckManager(spell_check_enabled=True)
    save_calls = []
    manager._schedule_save = lambda: save_calls.append(True)
    win = NoteWindow(Note(html="<p>hello wrold today</p>"), manager=manager)
    caret = win.body.textCursor()
    caret.setPosition(8)
    win.body.setTextCursor(caret)

    menu = QMenu()
    win.populate_text_menu(menu)
    ignore_action = next(a for a in menu.actions() if a.text() == "Ignore")
    ignore_action.trigger()

    assert manager.settings.ignored_words == ["wrold"]
    assert save_calls == [True]


def test_ignoring_the_same_word_twice_does_not_duplicate_it_in_settings(qapp, monkeypatch):
    monkeypatch.setattr(spellcheck, "is_available", lambda: True)
    monkeypatch.setattr(spellcheck, "check", lambda word: word != "wrold")
    monkeypatch.setattr(spellcheck, "suggest", lambda word: [])
    monkeypatch.setattr(spellcheck, "ignore", lambda word: None)

    manager = _SpellCheckManager(spell_check_enabled=True)
    win = NoteWindow(Note(html="<p>wrold wrold</p>"), manager=manager)

    win._ignore_word("wrold")
    win._ignore_word("wrold")

    assert manager.settings.ignored_words == ["wrold"]


def test_clicking_add_to_dictionary_calls_spellcheck_add_to_dictionary_with_the_word(qapp, monkeypatch):
    monkeypatch.setattr(spellcheck, "is_available", lambda: True)
    monkeypatch.setattr(spellcheck, "check", lambda word: word != "wrold")
    monkeypatch.setattr(spellcheck, "suggest", lambda word: [])
    calls = []
    monkeypatch.setattr(spellcheck, "add_to_dictionary", lambda word: calls.append(word))

    manager = _SpellCheckManager(spell_check_enabled=True)
    win = NoteWindow(Note(html="<p>hello wrold today</p>"), manager=manager)
    caret = win.body.textCursor()
    caret.setPosition(8)
    win.body.setTextCursor(caret)

    menu = QMenu()
    win.populate_text_menu(menu)
    add_action = next(a for a in menu.actions() if a.text() == "Add to Dictionary")

    add_action.trigger()

    assert calls == ["wrold"]


def test_ignoring_a_word_rehighlights_every_open_note_with_that_word(qapp, monkeypatch):
    """Ignoring/adding a word changes what spellcheck.check() returns
    globally, not just for the note the right-click happened in — every
    open note's highlighter needs to re-run so an already-underlined
    instance elsewhere clears immediately too."""
    monkeypatch.setattr(spellcheck, "is_available", lambda: True)
    words_ok = set()

    def fake_check(word):
        return word != "wrold" or word in words_ok

    monkeypatch.setattr(spellcheck, "check", fake_check)
    monkeypatch.setattr(spellcheck, "suggest", lambda word: [])

    def fake_ignore(word):
        words_ok.add(word)

    monkeypatch.setattr(spellcheck, "ignore", fake_ignore)

    class _NotesManager(_SpellCheckManager):
        def __init__(self):
            super().__init__(spell_check_enabled=True)
            self.notes = {}

    manager = _NotesManager()
    win1 = NoteWindow(Note(html="<p>hello wrold today</p>"), manager=manager)
    win2 = NoteWindow(Note(html="<p>wrold again</p>"), manager=manager)
    manager.notes = {win1.note.id: win1, win2.note.id: win2}
    qapp.processEvents()

    block2 = win2.body.document().findBlockByNumber(0)
    assert any(f.start == 0 for f in block2.layout().formats())  # "wrold" underlined in win2

    caret = win1.body.textCursor()
    caret.setPosition(8)  # inside win1's "wrold"
    win1.body.setTextCursor(caret)
    menu = QMenu()
    win1.populate_text_menu(menu)
    ignore_action = next(a for a in menu.actions() if a.text() == "Ignore")
    ignore_action.trigger()
    qapp.processEvents()

    block2_after = win2.body.document().findBlockByNumber(0)
    assert block2_after.layout().formats() == []  # win2's "wrold" cleared too
