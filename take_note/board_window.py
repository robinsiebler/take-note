from __future__ import annotations

import random
from datetime import datetime, timezone

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QScrollArea,
    QSizeGrip,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from .models import FONT_SWATCHES, Board
from .note_window import ICON_BUTTON_QSS, RADIUS, NoteWindow, get_color_popup_qss, get_menu_qss, header_shade
from .widgets import build_color_swatch_grid
from .x11_wm import set_skip_taskbar

HEADER_HEIGHT = 24

# Flat, arrow-less, rounded — matches this app's existing translucent-
# white-overlay convention (ICON_BUTTON_QSS's rgba(255, 255, 255, N) hover
# states) rather than the platform's native beveled scrollbar, which read
# as one of the "ugly"/unpolished parts of this window. Fixed rgba
# overlays rather than a board-color-derived shade: translucent white
# holds reasonable contrast against every SWATCHES color without needing
# its own per-color contrast pass, the same reasoning ICON_BUTTON_QSS
# already relies on. Mocked up against two alternatives (a near-invisible
# overlay with no track, and a solid chrome-colored handle) first — this
# one (a faint dark track behind the handle, for a bit more at-a-glance
# discoverability) is what the user picked.
SCROLLBAR_QSS = """
QScrollBar:vertical { background: rgba(0, 0, 0, 30); width: 12px; margin: 0px; border-radius: 6px; }
QScrollBar::handle:vertical { background: rgba(255, 255, 255, 110); border-radius: 5px; min-height: 24px; margin: 1px; }
QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 160); }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QScrollBar:horizontal { background: rgba(0, 0, 0, 30); height: 12px; margin: 0px; border-radius: 6px; }
QScrollBar::handle:horizontal { background: rgba(255, 255, 255, 110); border-radius: 5px; min-width: 24px; margin: 1px; }
QScrollBar::handle:horizontal:hover { background: rgba(255, 255, 255, 160); }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }
"""

# A small tileable pattern rather than a full-canvas-sized one — QBrush
# tiles it natively (cheap, native Qt/GPU work), so this is only ever
# rendered once per board color, never regenerated on resize.
_TEXTURE_TILE_SIZE = 128


def _build_corkboard_texture(base_color: str) -> QPixmap:
    """Subtle noise grain, mocked up against 4 other options (flat/
    current, crosshatch, noise+vignette, cork-fiber-blotches) as real
    rendered images before writing this — user picked this one: distinct
    from a flat fill without fighting note colors sitting on top, and
    plainer than the crosshatch/blotch alternatives. A fixed seed keeps
    the pattern stable across regenerations of the same color (matters
    since QBrush tiles it — a re-seeded pattern each time would make
    already-visible tiles visibly shift on an unrelated repaint)."""
    base = QColor(base_color)
    tile = QPixmap(_TEXTURE_TILE_SIZE, _TEXTURE_TILE_SIZE)
    tile.fill(base)
    painter = QPainter(tile)
    painter.setPen(Qt.NoPen)
    rng = random.Random(base_color)
    darker = base.darker(122)
    lighter = base.lighter(115)
    for _ in range(_TEXTURE_TILE_SIZE * _TEXTURE_TILE_SIZE // 9):
        x = rng.randint(0, _TEXTURE_TILE_SIZE - 1)
        y = rng.randint(0, _TEXTURE_TILE_SIZE - 1)
        speck = QColor(darker if rng.random() < 0.6 else lighter)
        speck.setAlpha(rng.randint(18, 46))
        painter.setBrush(speck)
        painter.drawRect(x, y, 1, 1)
    painter.end()
    return tile


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BoardHeader(QWidget):
    """Drag handle for the board window itself. Same direct-reference
    pattern as NoteHeader: stores board_window explicitly rather than
    relying on self.window()."""

    def __init__(self, board_window: "NotepadWindow"):
        super().__init__()
        self.board_window = board_window
        self._drag_offset = None
        self.setObjectName("boardHeader")
        self.setFixedHeight(HEADER_HEIGHT)
        self.setAttribute(Qt.WA_StyledBackground, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(2)

        self.name_label = QLabel(board_window.board.name)
        self.name_label.setStyleSheet("color: white;")
        layout.addWidget(self.name_label)
        layout.addStretch()

        close_btn = QToolButton()
        close_btn.setText("×")
        close_btn.setAutoRaise(True)
        close_btn.setToolTip("Hide board")
        close_btn.clicked.connect(board_window.hide_board)
        layout.addWidget(close_btn)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.board_window.pos()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self._drag_offset is not None:
            self.board_window.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None


class BoardCanvas(QWidget):
    """The corkboard surface itself. Notes are reparented in here as plain
    child widgets, positioned via absolute move(x, y)."""

    # Was a flat setMinimumSize(600, 600) — bigger than the board's own
    # default window size (Board.w/h default to 400x300), guaranteeing a
    # scrollbar out of the box with zero content anywhere near an edge,
    # and clipping any note dragged past the currently-scrolled-into-view
    # region of that oversized, otherwise-empty canvas. grow_to_fit()
    # instead tracks the real viewport size, only growing past that when
    # a note is actually positioned beyond it.
    MARGIN = 20

    def __init__(self, board_window: "NotepadWindow"):
        super().__init__()
        self.board_window = board_window
        # Not WA_StyledBackground — the corkboard texture is painted
        # directly in paintEvent() below instead of via a stylesheet
        # background-color, so the widget needs its own paint to actually
        # run rather than relying on Qt's stylesheet-driven fill.
        self._texture: QPixmap | None = None

    def set_texture_color(self, color: str):
        self._texture = _build_corkboard_texture(color)
        self.update()

    def paintEvent(self, event):
        if self._texture is not None:
            painter = QPainter(self)
            painter.fillRect(self.rect(), QBrush(self._texture))
        super().paintEvent(event)

    def grow_to_fit(self):
        needed = self.board_window.scroll.viewport().size()
        needed_w, needed_h = needed.width(), needed.height()
        # NoteWindow instances only, not every QWidget child of the canvas —
        # contextMenuEvent() below creates `QMenu(self)`, parenting each
        # right-click's popup to the canvas for the lifetime of the canvas
        # (Qt never deletes it just because exec() returns and the local
        # Python variable goes out of scope), so plain findChildren(QWidget)
        # kept picking up every closed-but-never-deleted menu too. Its
        # leftover geometry() is in *screen*-absolute coordinates (it's a
        # top-level popup), not canvas-local ones, so treating it as note
        # content permanently inflated the required size to wherever on the
        # screen the user last right-clicked — confirmed live: reproduced by
        # triggering the real context menu (not calling create_note()
        # directly) and finding the closed QMenu still in
        # canvas.findChildren(QWidget) afterward, geometry frozen at the
        # click point regardless of any later resize.
        for child in self.findChildren(NoteWindow, options=Qt.FindDirectChildrenOnly):
            # A hidden note (Hide Note, or trashed — see
            # NoteManager.trash_note) shouldn't hold the canvas open at
            # its old size; it stays a real child widget the whole time,
            # just not shown, so it'd otherwise still count here.
            if not child.isVisible():
                continue
            geo = child.geometry()
            needed_w = max(needed_w, geo.right() + self.MARGIN)
            needed_h = max(needed_h, geo.bottom() + self.MARGIN)
        self.setMinimumSize(needed_w, needed_h)
        self.resize(needed_w, needed_h)

    def contextMenuEvent(self, event):
        board_window = self.board_window
        menu = QMenu(self)
        menu.setStyleSheet(get_menu_qss())

        new_note_action = menu.addAction("New Note on this Notepad")
        new_note_action.triggered.connect(
            lambda: board_window.manager.create_note(board=board_window, pos=event.pos())
        )

        rename_action = menu.addAction("Rename Notepad")
        rename_action.triggered.connect(board_window.rename)

        color_action = menu.addAction("Change Notepad Color…")
        # Anchored to the window itself, not this canvas — the canvas can
        # grow well past the visible viewport (grow_to_fit()), so its own
        # bottomLeft can sit far outside the window once scrolled, same
        # reasoning NoteWindow's own "Change Note Color…" anchors to the
        # whole note rather than whatever sub-widget was clicked.
        color_action.triggered.connect(lambda: board_window.show_color_menu(board_window))

        menu.addSeparator()
        delete_action = menu.addAction("Delete Notepad")
        delete_action.triggered.connect(board_window.confirm_delete)

        menu.exec(event.globalPos())


class NotepadWindow(QWidget):
    changed = Signal()

    def __init__(self, board: Board, manager):
        super().__init__(None)
        self.board = board
        self.manager = manager

        # Qt.Window (Normal type), not Qt.Tool (Utility type) — same fix,
        # same reason as NoteWindow's own STANDALONE_FLAGS (see that
        # comment in note_window.py): KWin keeps Utility-type windows in
        # an elevated stacking layer above Normal windows regardless of
        # state hints, which left an open board permanently rendering
        # above every note (reported live, intermittent/hard to force on
        # demand, but this is the same documented mechanism already fixed
        # for notes). Taskbar/pager hiding moves to set_skip_taskbar()
        # below accordingly, same as notes.
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setMinimumSize(240, 200)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._build_ui()
        self._apply_color()

        self.resize(board.w, board.h)
        self.move(board.x, board.y)
        # Always show() first, even for a board loaded already-hidden —
        # set_skip_taskbar() needs the window actually mapped to reliably
        # stick (same fix/reasoning as NoteWindow's own construction for a
        # trashed note), then hide() again right after if persisted hidden.
        self.show()
        set_skip_taskbar(int(self.winId()), True)
        self.canvas.grow_to_fit()
        if board.hidden:
            self.hide()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = BoardHeader(self)
        layout.addWidget(self.header)

        self.canvas = BoardCanvas(self)
        self.scroll = QScrollArea()
        self.scroll.setObjectName("boardScroll")
        self.scroll.setAttribute(Qt.WA_StyledBackground, True)
        self.scroll.setFrameStyle(0)
        self.scroll.setWidget(self.canvas)
        self.scroll.setWidgetResizable(False)
        layout.addWidget(self.scroll, stretch=1)

        self.footer = QWidget()
        self.footer.setObjectName("boardFooter")
        self.footer.setFixedHeight(14)
        self.footer.setAttribute(Qt.WA_StyledBackground, True)
        bottom_row = QHBoxLayout(self.footer)
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.addStretch()
        bottom_row.addWidget(QSizeGrip(self))
        layout.addWidget(self.footer)

    def _apply_color(self):
        header_color = header_shade(self.board.color)
        self.header.setStyleSheet(
            f"#boardHeader {{ background-color: {header_color}; "
            f"border-top-left-radius: {RADIUS}px; border-top-right-radius: {RADIUS}px; }}"
            + ICON_BUTTON_QSS
        )
        self.footer.setStyleSheet(
            f"#boardFooter {{ background-color: {self.board.color}; "
            f"border-bottom-left-radius: {RADIUS}px; border-bottom-right-radius: {RADIUS}px; }}"
        )
        # Flat fallback for the sliver of QScrollArea viewport that can
        # show around the canvas before grow_to_fit() has run — the
        # canvas itself (normally filling that whole viewport) paints the
        # real corkboard texture, not this flat color. Wrapped in its own
        # #boardScroll selector rather than a bare declaration: a bare
        # (selector-less) rule mixed with the class-selector QScrollBar
        # rules below silently fails to parse at all — the exact same
        # stylesheet-scoping trap already hit and fixed for the find bar's
        # own buttons in note_window.py.
        self.scroll.setStyleSheet(
            f"#boardScroll {{ background-color: {self.board.color}; border: none; }}" + SCROLLBAR_QSS
        )
        self.canvas.set_texture_color(self.board.color)

    def set_color(self, color_hex: str):
        self.board.color = color_hex
        self._apply_color()
        self.mark_changed()

    def show_color_menu(self, anchor_widget: QWidget):
        """Same popup mechanism NoteWindow.show_color_menu() builds for
        notes (same get_color_popup_qss chrome, same build_color_swatch_grid
        widget) but FONT_SWATCHES instead of the note SWATCHES — the note
        palette's own bright pastels collided badly with a note sitting on
        a same-colored board (confirmed live: a default-yellow note was
        essentially invisible on a yellow board). FONT_SWATCHES was already
        WCAG-contrast-checked against every note SWATCHES color (see its
        own comment in models.py), just never tried as a *background fill*
        before — mocked up against a muted/darkened note-SWATCHES-derived
        palette first, user picked FONT_SWATCHES for reading more vibrant."""
        menu = QMenu(self)
        menu.setAttribute(Qt.WA_TranslucentBackground, True)
        menu.setStyleSheet(get_color_popup_qss())

        grid_container = build_color_swatch_grid(
            FONT_SWATCHES, self.board.color, lambda c: self._pick_color(c, menu)
        )
        grid_container.setStyleSheet("background: transparent;")
        action = QWidgetAction(menu)
        action.setDefaultWidget(grid_container)
        menu.addAction(action)

        menu.exec(anchor_widget.mapToGlobal(anchor_widget.rect().bottomLeft()))

    def _pick_color(self, color: str, menu: QMenu):
        self.set_color(color)
        menu.close()

    def rename(self):
        # The static QInputDialog.getText() convenience defaults to a
        # width too narrow to even read its own title bar comfortably —
        # same fix as show_hyperlink_dialog() in note_window.py: build the
        # dialog directly so it can be sized explicitly.
        dialog = QInputDialog(self)
        dialog.setWindowTitle("Rename Notepad")
        dialog.setLabelText("Notepad name:")
        dialog.setTextValue(self.board.name)
        dialog.findChild(QLineEdit).setClearButtonEnabled(True)
        # 320px still truncated the title bar itself on an unscaled
        # (100%) monitor even though it read fine on a 125%-scaled one —
        # the OS window-manager-drawn title bar's own text needs more
        # width than the dialog's content does, and that requirement
        # isn't affected by Qt's own DPI handling at all since KWin draws
        # it, not Qt, not the dialog's own content.
        dialog.resize(480, dialog.sizeHint().height())
        if dialog.exec() != QInputDialog.Accepted:
            return
        name = dialog.textValue()
        if name.strip():
            self.board.name = name.strip()
            self.header.name_label.setText(self.board.name)
            self.mark_changed()

    def confirm_delete(self):
        # A plain child dialog doesn't reliably outrank an always-on-top
        # note's own raw EWMH state in KWin's stacking layers (that hint
        # elevates by window layer, not just parent/child order) — reported
        # live: this dialog appeared behind the notes previously on this
        # board. Same fix as NoteWindow.confirm_delete(): a parentless
        # QMessageBox with WindowStaysOnTopHint explicitly set, since that
        # (not parent/child stacking) is what actually keeps it above an
        # always-on-top note regardless.
        box = QMessageBox()
        box.setWindowTitle("Delete Notepad")
        box.setText("Delete this Notepad? Notes on it will be moved back to the desktop.")
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setWindowFlags(box.windowFlags() | Qt.WindowStaysOnTopHint)
        reply = box.exec()
        if reply == QMessageBox.Yes:
            self.manager.delete_board(self)

    # -- show/hide, persisted -------------------------------------------

    def show_board(self):
        # Only bumps modified_at on an actual hidden->visible transition —
        # this is also called from _open_board_from_tree() to just bring
        # an already-visible board to front (a plain re-focus, not a real
        # edit), matching how raising an already-visible note doesn't
        # bump its own modified_at either.
        was_hidden = self.board.hidden
        self.board.hidden = False
        # showNormal(), not show() — recovers a genuinely minimized
        # (window-manager-iconified) board, matching the same fix already
        # used for reopening notes/the Notes Manager.
        self.showNormal()
        self.raise_()
        self.activateWindow()
        if was_hidden:
            self.mark_changed()

    def hide_board(self):
        self.board.hidden = True
        self.hide()
        self.mark_changed()

    # -- persistence hooks -------------------------------------------------

    def sync_model(self) -> Board:
        self.board.x, self.board.y = self.pos().x(), self.pos().y()
        self.board.w, self.board.h = self.size().width(), self.size().height()
        return self.board

    def mark_changed(self):
        self.board.modified_at = _now_iso()
        self.changed.emit()

    def moveEvent(self, event):
        super().moveEvent(event)
        self.mark_changed()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.mark_changed()
        self.canvas.grow_to_fit()
