from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QObject, QPointF, QTimer, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QTextCharFormat,
    QTextCursor,
    QTextListFormat,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QFontDialog,
    QInputDialog,
    QMenu,
    QMessageBox,
    QToolButton,
)

from take_note.models import Note, Settings
from take_note.note_window import NoteWindow, find_bar_tint


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
        "Change Note Color…",
        "Note Transparency",
        "Always on Top",
        "Lock Note",
        "Stick to Window…",
        "Add to Notepad",
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


def _patch_title_dialog(monkeypatch, text, accepted):
    """show_title_dialog() uses the static QInputDialog.getText() convenience
    (matching MemoboardWindow.rename()'s pattern, unlike show_hyperlink_dialog's
    instance-based approach) — so tests patch getText() directly rather than
    exec()/textValue() on an instance."""
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: (text, accepted)))


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


def test_select_image_at_leaves_plain_text_click_untouched(qapp):
    """No image at the click point: a right-click on plain text shouldn't
    manufacture a selection that wasn't there before."""
    win = make_note_window("plain text, no image")
    cursor = win.body.textCursor()
    cursor.movePosition(QTextCursor.Start)
    win.body.setTextCursor(cursor)

    win.body._select_image_at(3)

    assert win.body.textCursor().hasSelection() is False
    assert win.body.textCursor().position() == 0


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
    win.body._select_image_under_click(win.body.rect().center())

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


def test_find_selects_first_match_as_you_type(qapp):
    win = make_note_window("alpha beta alpha")

    win.find_bar.field.setText("beta")

    cursor = win.body.textCursor()
    assert cursor.selectedText() == "beta"


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
    monkeypatch.setattr("take_note.note_window.list_windows", lambda: [])
    informed = {}
    monkeypatch.setattr(
        QMessageBox, "information", staticmethod(lambda *a, **k: informed.setdefault("called", True))
    )
    win = make_note_window("Some text")

    win.show_stick_window_dialog()

    assert informed.get("called") is True
    assert win._stuck_window_id is None


def test_show_stick_window_dialog_picks_selected_window(qapp, monkeypatch):
    _patch_window_watcher(monkeypatch)
    monkeypatch.setattr(
        "take_note.note_window.list_windows", lambda: [(111, "Firefox"), (222, "Terminal")]
    )
    monkeypatch.setattr(
        QInputDialog, "getItem", staticmethod(lambda *a, **k: ("Terminal (0x%x)" % 222, True))
    )
    win = make_note_window("Some text")

    win.show_stick_window_dialog()

    assert win._stuck_window_id == 222


def test_show_stick_window_dialog_cancelled_does_not_stick(qapp, monkeypatch):
    monkeypatch.setattr("take_note.note_window.list_windows", lambda: [(111, "Firefox")])
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(lambda *a, **k: ("", False)))
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
