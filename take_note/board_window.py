from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QScrollArea,
    QSizeGrip,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .models import Board
from .note_window import ICON_BUTTON_QSS, RADIUS, get_menu_qss, header_shade

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
        for child in self.findChildren(QWidget, options=Qt.FindDirectChildrenOnly):
            geo = child.geometry()
            needed_w = max(needed_w, geo.right() + self.MARGIN)
            needed_h = max(needed_h, geo.bottom() + self.MARGIN)
        self.setMinimumSize(needed_w, needed_h)
        self.resize(needed_w, needed_h)

    def contextMenuEvent(self, event):
        board_window = self.board_window
        menu = QMenu(self)
        menu.setStyleSheet(get_menu_qss())

        new_note_action = menu.addAction("New Note on this Board")
        new_note_action.triggered.connect(
            lambda: board_window.manager.create_note(board=board_window, pos=event.pos())
        )

        rename_action = menu.addAction("Rename Board")
        rename_action.triggered.connect(board_window.rename)

        menu.addSeparator()
        delete_action = menu.addAction("Delete Board")
        delete_action.triggered.connect(board_window.confirm_delete)

        menu.exec(event.globalPos())


class NotepadWindow(QWidget):
    changed = Signal()

    def __init__(self, board: Board, manager):
        super().__init__(None)
        self.board = board
        self.manager = manager

        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        self.setMinimumSize(240, 200)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._build_ui()
        self._apply_color()

        self.resize(board.w, board.h)
        self.move(board.x, board.y)
        self.show()
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
        name, ok = QInputDialog.getText(self, "Rename Board", "Board name:", text=self.board.name)
        if ok and name.strip():
            self.board.name = name.strip()
            self.header.name_label.setText(self.board.name)
            self.mark_changed()

    def confirm_delete(self):
        reply = QMessageBox.question(
            self,
            "Delete Board",
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
