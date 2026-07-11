from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import Qt, Signal
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
)

from .models import Board
from .note_window import ICON_BUTTON_QSS, RADIUS, NoteWindow, get_menu_qss, header_shade
from .x11_wm import set_skip_taskbar

HEADER_HEIGHT = 24


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
        close_btn.clicked.connect(board_window.hide)
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
        self.setAttribute(Qt.WA_StyledBackground, True)

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
        self.show()
        set_skip_taskbar(int(self.winId()), True)
        self.canvas.grow_to_fit()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = BoardHeader(self)
        layout.addWidget(self.header)

        self.canvas = BoardCanvas(self)
        self.scroll = QScrollArea()
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
        self.scroll.setStyleSheet(f"background-color: {self.board.color}; border: none;")
        self.canvas.setStyleSheet(f"background-color: {self.board.color};")

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
        reply = QMessageBox.question(
            self,
            "Delete Notepad",
            "Delete this Notepad? Notes on it will be moved back to the desktop.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.manager.delete_board(self)

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
