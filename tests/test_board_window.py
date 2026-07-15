from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtWidgets import QApplication, QInputDialog, QLineEdit, QMessageBox, QToolButton

from take_note.board_window import _TEXTURE_TILE_SIZE, _build_corkboard_texture, NotepadWindow
from take_note.models import FONT_SWATCHES, Board, Note, Settings
from take_note.note_window import NoteWindow


class FakeManager:
    boards = {}
    settings = Settings()

    def create_note(self, board=None, pos=None):
        note = NoteWindow(Note(color="#80deea"), FakeManager())
        note.show()
        note.attach_to_board(board, pos=pos)
        return note


def test_build_corkboard_texture_returns_expected_tile_size(qapp):
    tile = _build_corkboard_texture("#fff59d")

    assert tile.width() == _TEXTURE_TILE_SIZE
    assert tile.height() == _TEXTURE_TILE_SIZE


def test_build_corkboard_texture_is_deterministic_for_the_same_color(qapp):
    """A fixed seed per color, not re-randomized on every call — QBrush
    tiles this pixmap, so a re-seeded pattern each regeneration would
    make already-visible tiles visibly shift on an unrelated repaint."""
    first = _build_corkboard_texture("#90caf9")
    second = _build_corkboard_texture("#90caf9")

    assert first.toImage() == second.toImage()


def test_build_corkboard_texture_differs_between_colors(qapp):
    yellow = _build_corkboard_texture("#fff59d")
    blue = _build_corkboard_texture("#90caf9")

    assert yellow.toImage() != blue.toImage()


def test_notepad_window_applies_texture_to_canvas(qapp):
    board = NotepadWindow(Board(color="#fff59d"), FakeManager())

    assert board.canvas._texture is not None
    assert board.canvas._texture.toImage() == _build_corkboard_texture("#fff59d").toImage()


def test_empty_board_canvas_matches_viewport_not_a_fixed_minimum(qapp):
    """Regression: the canvas used to have a flat setMinimumSize(600, 600)
    — bigger than the board's own default window size (400x300) — which
    forced a scrollbar with zero content anywhere near an edge."""
    board = NotepadWindow(Board(), FakeManager())

    assert not board.scroll.horizontalScrollBar().isVisible()
    assert not board.scroll.verticalScrollBar().isVisible()


def test_board_loaded_hidden_stays_hidden(qapp):
    """Regression: NotepadWindow.__init__ used to unconditionally show()
    with no way to load already-closed - every board reopened on every
    launch regardless of whether it had been closed before quitting."""
    board = NotepadWindow(Board(hidden=True), FakeManager())

    assert board.isHidden()


def test_board_loaded_not_hidden_shows_normally(qapp):
    board = NotepadWindow(Board(hidden=False), FakeManager())

    assert not board.isHidden()


def test_hide_board_persists_hidden_and_hides(qapp):
    board = NotepadWindow(Board(), FakeManager())

    board.hide_board()

    assert board.board.hidden is True
    assert board.isHidden()


def test_show_board_persists_not_hidden_and_shows(qapp):
    board = NotepadWindow(Board(hidden=True), FakeManager())

    board.show_board()

    assert board.board.hidden is False
    assert not board.isHidden()


def test_show_board_on_an_already_visible_board_does_not_bump_modified_at(qapp):
    """show_board() also serves as the plain "bring to front" action
    (_open_board_from_tree, the tray's checkmark toggle) - re-focusing an
    already-visible board is not a real edit, matching how raising an
    already-visible note doesn't bump its own modified_at either."""
    board = NotepadWindow(Board(hidden=False), FakeManager())
    before = board.board.modified_at

    board.show_board()

    assert board.board.modified_at == before


def test_close_button_calls_hide_board(qapp):
    board = NotepadWindow(Board(), FakeManager())

    board.header.findChild(QToolButton).click()

    assert board.board.hidden is True
    assert board.isHidden()


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


def test_grow_to_fit_ignores_hidden_notes(qapp):
    """A trashed note (NoteManager.trash_note) or a session-hidden one
    stays a real child of the canvas the whole time, just not shown —
    it shouldn't hold the canvas open at its old position."""
    board = NotepadWindow(Board(), FakeManager())
    note = NoteWindow(Note(color="#80deea"), FakeManager())
    note.show()
    note.attach_to_board(board, pos=QPoint(20, 20))
    note.move(700, 500)
    grown = board.canvas.size()

    note.hide()
    board.canvas.grow_to_fit()

    shrunk = board.canvas.size()
    assert shrunk.width() < grown.width()
    assert shrunk.height() < grown.height()


def test_detaching_a_trashed_note_does_not_show_it(qapp):
    board = NotepadWindow(Board(), FakeManager())
    note = NoteWindow(
        Note(color="#80deea", deleted_at="2026-01-01T00:00:00+00:00"), FakeManager()
    )
    note.attach_to_board(board, pos=QPoint(20, 20))
    assert note.isHidden()

    note.attach_to_board(None, pos=QPoint(300, 300))

    assert note.isHidden()
    assert note.note.board_id is None


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


def test_set_color_updates_board_reapplies_chrome_and_marks_changed(qapp):
    board = NotepadWindow(Board(), FakeManager())
    before_mtime = board.board.modified_at
    events = []
    board.changed.connect(lambda: events.append(board.board.color))

    board.set_color(FONT_SWATCHES[3])

    assert board.board.color == FONT_SWATCHES[3]
    assert board.board.modified_at != before_mtime
    assert events == [FONT_SWATCHES[3]]
    from take_note.board_window import header_shade

    assert header_shade(FONT_SWATCHES[3]) in board.header.styleSheet()
    assert FONT_SWATCHES[3] in board.scroll.styleSheet()


def test_change_notepad_color_action_opens_swatch_popup_and_applies_pick(qapp):
    """Same nested-popup pattern already proven by
    test_right_click_menu_triggers_new_note_and_leaves_a_child_behind (the
    outer context menu) and note_window.py's own
    test_show_font_color_menu_uses_font_swatches_and_applies_pick (the
    swatch popup itself) — combined here since "Change Notepad Color…"
    opens a second, nested popup from within the first, and QMenu.exec()'s
    own nested event loop can't be driven by monkeypatching exec()
    (Shiboken-wrapped, silently no-ops), only by scheduling clicks ahead of
    time via QTimer so they fire once each nested loop is actually running."""
    board = NotepadWindow(Board(), FakeManager())
    before_mtime = board.board.modified_at

    def pick_swatch():
        popup = QApplication.activePopupWidget()
        assert popup is not None, "color swatch popup never opened"
        buttons = popup.findChildren(QToolButton)
        assert len(buttons) == len(FONT_SWATCHES)
        buttons[3].click()

    def pick_color_action():
        menu = QApplication.activePopupWidget()
        assert menu is not None, "context menu never opened"
        action = next(a for a in menu.actions() if a.text() == "Change Notepad Color…")
        QTimer.singleShot(0, pick_swatch)
        action.trigger()  # blocks inside show_color_menu()'s own nested exec()
        menu.close()

    click_pos = board.canvas.mapToGlobal(QPoint(60, 50))
    QTimer.singleShot(0, pick_color_action)
    event = QContextMenuEvent(QContextMenuEvent.Mouse, board.canvas.mapFromGlobal(click_pos), click_pos)
    board.canvas.contextMenuEvent(event)  # blocks until pick_color_action() closes the menu

    assert board.board.color == FONT_SWATCHES[3]
    assert board.board.modified_at != before_mtime


def test_right_click_menu_triggers_new_note_and_leaves_a_child_behind(qapp):
    """Documents the actual leak, exercised through the real context menu
    (not calling create_note() directly): BoardCanvas.contextMenuEvent()
    builds `QMenu(self)`, parenting the popup to the canvas. Qt's QObject
    parent/child ownership keeps that QMenu alive as a child of the canvas
    forever once exec() returns — it's never explicitly deleted — so it's
    still sitting in canvas.findChildren(QWidget) long after closing.
    grow_to_fit() itself is guarded against this by the fix (see the next
    test below, which pins down *why* this leak matters); this test only
    pins down that the leak itself is real, so a future change can't
    silently reintroduce it without noticing."""
    board = NotepadWindow(Board(), FakeManager())

    def pick_new_note_action():
        menu = QApplication.activePopupWidget()
        assert menu is not None, "context menu never opened"
        action = next(a for a in menu.actions() if a.text() == "New Note on this Notepad")
        action.trigger()
        menu.close()

    click_pos = board.canvas.mapToGlobal(QPoint(60, 50))
    QTimer.singleShot(0, pick_new_note_action)
    event = QContextMenuEvent(QContextMenuEvent.Mouse, board.canvas.mapFromGlobal(click_pos), click_pos)
    board.canvas.contextMenuEvent(event)  # blocks until pick_new_note_action() closes the menu

    from PySide6.QtWidgets import QMenu, QWidget
    from PySide6.QtCore import Qt as QtNS

    leftover_menus = [
        child
        for child in board.canvas.findChildren(QWidget, options=QtNS.FindDirectChildrenOnly)
        if isinstance(child, QMenu)
    ]
    assert leftover_menus, "expected the closed context menu to still be a live child of the canvas"


def test_canvas_ignores_non_note_children_when_growing(qapp):
    """Regression (test case 7.2, reported live): after the leak documented
    above, grow_to_fit() used to scan *every* QWidget child of the canvas
    — including that closed-but-undead QMenu — and trusted its geometry()
    as canvas-local note-content bounds. A QMenu is a top-level popup
    though, so its geometry() is in *screen*-absolute coordinates, not
    canvas-local ones. A board sitting well away from the screen's origin
    turned that stale absolute position into a huge phantom "note" the
    canvas thought it must always leave room for, permanently, regardless
    of any later resize — confirmed live on the real running app via a
    real corner-grip drag that never cleared the scrollbars, no matter how
    big the window got. Reproduced here by planting a stand-in "leaked
    popup" directly, since actually forcing the real absolute-screen-
    position skew depends on window-manager placement behavior that the
    offscreen QPA platform this suite normally runs under doesn't
    reproduce (real xcb does — confirmed both ways) — this covers the
    exact mechanism (grow_to_fit() must ignore non-NoteWindow children)
    without depending on that platform-specific positioning."""
    from PySide6.QtWidgets import QMenu

    board = NotepadWindow(Board(), FakeManager())
    leaked_popup = QMenu(board.canvas)
    leaked_popup.setGeometry(5000, 5000, 200, 100)  # stale screen-absolute geometry

    board.canvas.grow_to_fit()
    board.resize(1200, 900)

    assert not board.scroll.horizontalScrollBar().isVisible()
    assert not board.scroll.verticalScrollBar().isVisible()


def _patch_rename_dialog(monkeypatch, text, accepted):
    """rename() builds a QInputDialog instance directly (rather than the
    static getText() convenience) so it can be resized wider than the
    cramped default — same pattern as show_hyperlink_dialog's own fix in
    note_window.py (see _patch_hyperlink_dialog there), and tests must
    patch exec()/textValue() on the instance for the same reason: a real,
    un-mockable modal dialog would otherwise hang the test."""
    monkeypatch.setattr(
        QInputDialog, "exec", lambda self: QInputDialog.Accepted if accepted else QInputDialog.Rejected
    )
    monkeypatch.setattr(QInputDialog, "textValue", lambda self: text)


def test_rename_dialog_is_wide_enough_to_read_its_own_title(qapp, monkeypatch):
    """Regression: the static QInputDialog.getText() convenience's default
    width was too narrow to even read the dialog's own title bar ("Rename
    Board" rendered as "Ren...te!" against KDE's own window-title
    truncation) — reported live via a screenshot. First fix (resize to
    320) turned out to still truncate on an unscaled (100%) monitor even
    though it read fine on a 125%-scaled one — the OS-drawn title bar's
    text width isn't something Qt's own content sizing controls at all.
    Bumped to 480, same fix as show_hyperlink_dialog(): build the dialog
    directly so it can be resized."""
    board = NotepadWindow(Board(name="Test Notepad"), FakeManager())
    seen = {}

    def fake_exec(self):
        seen["width"] = self.width()
        return QInputDialog.Rejected

    monkeypatch.setattr(QInputDialog, "exec", fake_exec)

    board.rename()

    assert seen["width"] >= 480


def test_rename_dialog_has_a_clear_button(qapp, monkeypatch):
    board = NotepadWindow(Board(name="Test Notepad"), FakeManager())
    seen = {}

    def fake_exec(self):
        seen["has_clear_button"] = self.findChild(QLineEdit).isClearButtonEnabled()
        return QInputDialog.Rejected

    monkeypatch.setattr(QInputDialog, "exec", fake_exec)

    board.rename()

    assert seen["has_clear_button"]


def test_rename_dialog_prefills_current_name_and_applies_pick(qapp, monkeypatch):
    board = NotepadWindow(Board(name="Old Name"), FakeManager())
    _patch_rename_dialog(monkeypatch, "New Name", True)

    board.rename()

    assert board.board.name == "New Name"
    assert board.header.name_label.text() == "New Name"


def test_rename_dialog_cancelled_does_not_modify_name(qapp, monkeypatch):
    board = NotepadWindow(Board(name="Old Name"), FakeManager())
    _patch_rename_dialog(monkeypatch, "New Name", False)

    board.rename()

    assert board.board.name == "Old Name"


def test_rename_dialog_empty_name_does_not_modify_name(qapp, monkeypatch):
    board = NotepadWindow(Board(name="Old Name"), FakeManager())
    _patch_rename_dialog(monkeypatch, "   ", True)

    board.rename()

    assert board.board.name == "Old Name"


def test_set_opacity_on_board_attached_note_uses_graphics_effect(qapp):
    """Regression: NoteWindow.set_opacity() called setWindowOpacity(),
    which is silently a no-op for anything that isn't a real top-level
    window — confirmed directly (reading windowOpacity() back afterward
    stayed 1.0 regardless of what was just set). attach_to_board()
    reparents the note to Qt.Widget (a plain child of the board's
    canvas), so a note living on a board is never a top-level window.
    Reported live as changing a board note's transparency doing visibly
    nothing. Fixed via a QGraphicsOpacityEffect, which works on any
    widget regardless of window-ness."""
    from PySide6.QtWidgets import QGraphicsOpacityEffect

    board = NotepadWindow(Board(), FakeManager())
    note = NoteWindow(Note(color="#80deea"), FakeManager())
    note.show()
    note.attach_to_board(board, pos=QPoint(20, 20))

    note.set_opacity(0.4)

    assert note.windowOpacity() == 1.0  # confirms the no-op path is real
    effect = note.graphicsEffect()
    assert isinstance(effect, QGraphicsOpacityEffect)
    assert effect.opacity() == 0.4


def test_set_opacity_reapplies_correctly_across_attach_and_detach(qapp):
    """A note's transparency, set while standalone, must keep working
    after attach_to_board() switches its opacity mechanism — and must
    switch back to the (cheaper, compositor-driven) setWindowOpacity()
    path once detached again, not stay on the graphics-effect path
    forever."""
    from PySide6.QtWidgets import QGraphicsOpacityEffect

    board = NotepadWindow(Board(), FakeManager())
    note = NoteWindow(Note(color="#80deea"), FakeManager())
    note.show()
    note.set_opacity(0.40)
    assert note.windowOpacity() == 0.40

    note.attach_to_board(board, pos=QPoint(20, 20))

    effect = note.graphicsEffect()
    assert isinstance(effect, QGraphicsOpacityEffect)
    assert effect.opacity() == 0.40

    note.attach_to_board(None, pos=QPoint(300, 300))

    assert note.windowOpacity() == 0.40
    assert note.graphicsEffect() is None


def test_note_created_directly_on_board_gets_working_opacity(qapp):
    """Same bug, different entry point: a note created straight onto a
    board (app.py's create_note(board=...), not attach_to_board() on an
    existing standalone note) is never a top-level window from
    construction onward — set_opacity() must use the graphics-effect
    path from the very first call, not just after some later attach."""
    from PySide6.QtWidgets import QGraphicsOpacityEffect

    board = NotepadWindow(Board(), FakeManager())
    note = NoteWindow(Note(color="#80deea", board_id=board.board.id), FakeManager(), parent_board=board)
    note.show()

    note.set_opacity(0.4)

    effect = note.graphicsEffect()
    assert isinstance(effect, QGraphicsOpacityEffect)
    assert effect.opacity() == 0.4


def test_note_title_bar_label_does_not_inherit_board_background(qapp):
    """Regression, reported live via a screenshot: a board-attached note's
    title bar painted the whole strip in the *board's* own grey
    background instead of the note's own color. Root cause: the title
    label's own backgroundRole() picks up the board canvas (a genuine
    QObject ancestor once attached) since Qt's style-sheet engine paints
    a QLabel's implicit background from its resolved palette once
    styled-painting is active anywhere in the ancestor chain — even
    though nothing here ever asked for autoFillBackground, and even
    though #titlebar's own background-color rule is correct the whole
    time. Fixed with an explicit `background-color: transparent` on the
    label itself.

    Checks the label's resolved backgroundRole() color rather than an
    actual rendered pixel: confirmed directly that this reads the wrong
    (board) color 100% reliably pre-fix, in both offscreen and real xcb,
    whereas grabbing a real pixel to check what actually got *painted*
    turned out to depend on incidental paint-cascade timing (how many
    other notes/boards existed first, exact processEvents/sleep timing)
    that a minimal single-note-per-board repro didn't reliably trigger
    even pre-fix — a real but separate flakiness from the underlying
    palette bug this test guards against."""
    board = NotepadWindow(Board(color="#e0e0e0"), FakeManager())
    note = NoteWindow(
        Note(color="#fff59d", title="Groceries", board_id=board.board.id), FakeManager(), parent_board=board
    )
    note.show()

    label_bg = note.title_bar.label.palette().color(note.title_bar.label.backgroundRole()).name()
    assert label_bg != board.board.color


def test_header_new_note_button_creates_note_on_same_board(qapp):
    """Regression, reported live: clicking a board-attached note's header
    + button created a plain standalone note back on the desktop instead
    of a sibling on the same board — the header wired its + button to
    manager.create_note() with no board argument at all, regardless of
    where the note doing the clicking actually lived."""
    mgr = FakeManager()
    board = NotepadWindow(Board(), mgr)
    mgr.boards[board.board.id] = board
    note = NoteWindow(Note(color="#80deea", board_id=board.board.id), mgr, parent_board=board)
    note.show()

    note.header.new_btn.click()

    siblings = [w for w in board.canvas.findChildren(NoteWindow) if w is not note]
    assert len(siblings) == 1
    assert siblings[0].note.board_id == board.board.id


def test_header_new_note_button_creates_standalone_note_for_unattached_note(qapp):
    """Sanity check for the fix above: an ordinary desktop note's + button
    must still create a plain standalone note, not get accidentally
    attached to some board."""
    mgr = FakeManager()
    note = NoteWindow(Note(color="#80deea"), mgr)
    note.show()

    created = {}
    original_create_note = FakeManager.create_note

    def spy_create_note(self, board=None, pos=None):
        created["board"] = board
        return original_create_note(self, board=board, pos=pos)

    FakeManager.create_note = spy_create_note
    try:
        note.header.new_btn.click()
    finally:
        FakeManager.create_note = original_create_note

    assert created["board"] is None


def test_confirm_delete_dialog_stays_on_top_of_always_on_top_notes(qapp, monkeypatch):
    """Regression, reported live: a plain child QMessageBox doesn't
    reliably outrank an always-on-top note's own raw EWMH state in KWin's
    stacking layers — the confirmation dialog appeared behind the notes
    previously on this board. Same fix as NoteWindow.confirm_delete():
    WindowStaysOnTopHint explicitly set, since that (not parent/child
    stacking) is what actually keeps a dialog above an always-on-top
    window regardless."""
    board = NotepadWindow(Board(), FakeManager())
    seen = {}

    def fake_exec(self):
        seen["flags"] = self.windowFlags()
        return QMessageBox.No

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)

    board.confirm_delete()

    assert seen["flags"] & Qt.WindowStaysOnTopHint
