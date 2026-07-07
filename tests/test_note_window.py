from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QPointF, QTimer, Qt
from PySide6.QtGui import (
    QDesktopServices,
    QFont,
    QKeyEvent,
    QMouseEvent,
    QTextCharFormat,
    QTextCursor,
    QTextListFormat,
)
from PySide6.QtWidgets import QFontDialog, QInputDialog, QMenu, QMessageBox, QToolButton

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
        "Font…",
        "Font Style",
        "Font Color…",
        "Hyperlink…",
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


def test_show_font_dialog_applies_chosen_font(qapp, monkeypatch):
    """Font family/size used to be picked via QComboBox/QFontComboBox
    widgets embedded directly in the context menu, which fought QMenu's
    own popup handling (clicking the size dropdown closed the whole menu
    instead of opening it) and needed manual re-styling to avoid clashing
    with the theme. Replaced with a real QFontDialog instead."""
    win = make_note_window("Hello World")
    select_all(win)
    chosen_font = QFont("Monospace", 24)

    # PySide6's real return order is (ok, font) — confirmed by direct
    # inspection of QFontDialog.getFont(), not assumed; get this backwards
    # here and the test would pass while the app crashes for real.
    monkeypatch.setattr(QFontDialog, "getFont", staticmethod(lambda initial, parent: (True, chosen_font)))
    win.show_font_dialog()

    assert win.body.fontFamily() == "Monospace"
    assert win.body.fontPointSize() == 24


def test_show_font_dialog_cancelled_leaves_font_unchanged(qapp, monkeypatch):
    win = make_note_window("Hello World")
    select_all(win)
    before_family = win.body.fontFamily()
    before_size = win.body.fontPointSize()

    monkeypatch.setattr(QFontDialog, "getFont", staticmethod(lambda initial, parent: (False, QFont())))
    win.show_font_dialog()

    assert win.body.fontFamily() == before_family
    assert win.body.fontPointSize() == before_size


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
