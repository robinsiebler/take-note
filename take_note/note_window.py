from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont, QGuiApplication, QKeySequence, QTextCharFormat
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMenu,
    QMessageBox,
    QSizeGrip,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from .models import SWATCHES, Note
from .widgets import build_color_swatch_grid
from .x11_wm import set_skip_taskbar, set_stays_on_top

# Qt.Window (Normal type), not Qt.Tool (Utility type): KWin keeps
# Utility-type windows in an elevated stacking layer above Normal windows
# regardless of state hints (confirmed via _NET_CLIENT_LIST_STACKING),
# which broke a genuinely optional Always-on-Top toggle. Normal type has no
# such inherent elevation, so taskbar/pager hiding is done explicitly via
# set_skip_taskbar() instead of relying on the window type for it.
STANDALONE_FLAGS = Qt.Window | Qt.FramelessWindowHint
HEADER_HEIGHT = 22
RADIUS = 10

# How much darker the header strip is than the note's own color.
# Needs to be dark enough that white icon glyphs (ICON_BUTTON_QSS below)
# have real contrast against it, not just a slightly-shaded version of a
# pastel color that's still too light for white-on-it to read clearly.
HEADER_DARKEN = 230


def header_shade(color_hex: str) -> str:
    return QColor(color_hex).darker(HEADER_DARKEN).name()

# Cascades to every QToolButton inside whatever container this is mixed
# into, so icons stay legible regardless of the app/system theme instead
# of inheriting near-invisible default text colors on a colored strip.
ICON_BUTTON_QSS = """
QToolButton { color: white; border: none; background: transparent; padding: 2px; }
QToolButton:hover { background-color: rgba(255, 255, 255, 50); border-radius: 4px; }
QToolButton:checked { background-color: rgba(255, 255, 255, 80); border-radius: 4px; }
"""

# Any QMenu we build (context menus, the color picker) needs one of these —
# once an app sets a stylesheet anywhere, Qt stops giving unstyled QMenus
# native theme integration, so without explicit colors they render
# low-contrast against the desktop theme and genuinely-enabled items look
# disabled. Unlike the note's own color chrome (always hard-coded, never
# theme-dependent), menus should match the system light/dark scheme.
MENU_QSS_DARK = """
QMenu { background-color: #3a3a3a; color: white; border: 1px solid #5a5a5a; padding: 4px; }
QMenu::item { padding: 4px 24px 4px 12px; border-radius: 4px; }
QMenu::item:selected { background-color: #5a5a5a; }
QMenu::item:disabled { color: #888888; }
QMenu::separator { height: 1px; background: #5a5a5a; margin: 4px 8px; }
"""

MENU_QSS_LIGHT = """
QMenu { background-color: #fafafa; color: #202020; border: 1px solid #c0c0c0; padding: 4px; }
QMenu::item { padding: 4px 24px 4px 12px; border-radius: 4px; }
QMenu::item:selected { background-color: #dcdcdc; }
QMenu::item:disabled { color: #a0a0a0; }
QMenu::separator { height: 1px; background: #c0c0c0; margin: 4px 8px; }
"""


def get_menu_qss() -> str:
    """Picks a menu stylesheet matching the system color scheme. Falls back
    to dark for Qt.ColorScheme.Unknown (older platform theme plugins that
    can't report a scheme) since that's the tested, known-good default."""
    scheme = QGuiApplication.styleHints().colorScheme()
    if scheme == Qt.ColorScheme.Light:
        return MENU_QSS_LIGHT
    return MENU_QSS_DARK


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class NoteHeader(QWidget):
    """Colored drag handle strip. Holds a direct reference to its NoteWindow
    (not self.window()) so dragging still works correctly once a note is
    reparented into a Memoboard's canvas."""

    def __init__(self, note_window: "NoteWindow"):
        super().__init__()
        self.note_window = note_window
        self._drag_offset = None
        self.setObjectName("header")
        self.setFixedHeight(HEADER_HEIGHT)
        self.setAttribute(Qt.WA_StyledBackground, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(2)

        new_btn = QToolButton()
        new_btn.setText("+")
        new_btn.setAutoRaise(True)
        new_btn.setToolTip("New note")
        new_btn.clicked.connect(lambda: note_window.manager.create_note())
        layout.addWidget(new_btn)

        layout.addStretch()

        self.roll_btn = QToolButton()
        self.roll_btn.setAutoRaise(True)
        self.roll_btn.setToolTip("Roll up / down")
        self.roll_btn.clicked.connect(note_window.toggle_rolled)
        layout.addWidget(self.roll_btn)

        self.menu_btn = QToolButton()
        self.menu_btn.setText("☰")
        self.menu_btn.setAutoRaise(True)
        self.menu_btn.setToolTip("Note menu")
        self.menu_btn.clicked.connect(lambda: note_window.show_color_menu(self.menu_btn))
        layout.addWidget(self.menu_btn)

        close_btn = QToolButton()
        close_btn.setText("×")
        close_btn.setAutoRaise(True)
        close_btn.setToolTip("Delete note")
        close_btn.clicked.connect(note_window.confirm_delete)
        layout.addWidget(close_btn)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.note_window.toggle_rolled()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.note_window.pos()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self._drag_offset is not None:
            self.note_window.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None


class NoteBody(QTextEdit):
    """QTextEdit overrides contextMenuEvent to show its own built-in
    Undo/Redo/Cut/Copy/Paste menu, which would otherwise intercept every
    right-click inside the note before NoteWindow ever sees it. Extend that
    built-in menu with our own note-level items instead of replacing it, so
    right-clicking anywhere in the note — body or header — gives the same
    combined set of options."""

    def __init__(self, note_window: "NoteWindow"):
        super().__init__()
        self.note_window = note_window

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        menu.setStyleSheet(get_menu_qss())
        menu.addSeparator()
        self.note_window.populate_note_menu(menu)
        menu.exec(event.globalPos())


class NoteWindow(QWidget):
    changed = Signal()

    def __init__(self, note: Note, manager, parent_board=None):
        super().__init__(parent_board.canvas if parent_board is not None else None)
        self.note = note
        self.manager = manager

        if parent_board is None:
            self._apply_standalone_flags()
        # else: embedded as a plain child widget, no top-level flags needed.

        # Translucent + rounded corners on the header/footer strips only
        # (see _apply_color): the window itself must stay unpainted so the
        # corner cutouts outside those curves show the desktop, not a
        # square black patch.
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumSize(140, 120)
        self._build_ui()
        self._setup_actions()
        self._apply_color()

        self._expanded_height = note.h

        self.resize(note.w, note.h)
        self.move(note.x, note.y)
        self.body.setHtml(note.html)
        self.show()
        if parent_board is None:
            set_skip_taskbar(int(self.winId()), True)
        if note.rolled_up:
            self._set_rolled(True, persist=False)
        else:
            self.header.roll_btn.setText("▲")

    # -- UI construction -------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = NoteHeader(self)
        layout.addWidget(self.header)

        self.body = NoteBody(self)
        self.body.setFrameStyle(0)
        self.body.textChanged.connect(self.mark_changed)
        layout.addWidget(self.body, stretch=1)

        self.footer = QWidget()
        self.footer.setObjectName("footer")
        self.footer.setFixedHeight(14)
        self.footer.setAttribute(Qt.WA_StyledBackground, True)
        bottom_row = QHBoxLayout(self.footer)
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.addStretch()
        bottom_row.addWidget(QSizeGrip(self))
        layout.addWidget(self.footer)

    # -- formatting --------------------------------------------------------

    def _setup_actions(self):
        """Persistent QActions (not menu-local ones) so their keyboard
        shortcuts (Ctrl+B/I/U/K) keep working whether or not the context
        menu is open."""

        def make_action(text, shortcut, slot):
            action = QAction(text, self)
            action.setShortcut(QKeySequence(shortcut))
            action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
            action.triggered.connect(slot)
            self.addAction(action)
            return action

        self.bold_action = make_action("Bold", "Ctrl+B", self._toggle_bold)
        self.italic_action = make_action("Italic", "Ctrl+I", self._toggle_italic)
        self.underline_action = make_action("Underline", "Ctrl+U", self._toggle_underline)
        self.strikethrough_action = make_action(
            "Strikethrough", "Ctrl+K", self._toggle_strikethrough
        )
        self.align_left_action = QAction("Left", self)
        self.align_left_action.triggered.connect(lambda: self._set_alignment(Qt.AlignLeft))
        self.align_center_action = QAction("Center", self)
        self.align_center_action.triggered.connect(lambda: self._set_alignment(Qt.AlignCenter))
        self.align_right_action = QAction("Right", self)
        self.align_right_action.triggered.connect(lambda: self._set_alignment(Qt.AlignRight))

    def _merge_format(self, fmt: QTextCharFormat):
        self.body.mergeCurrentCharFormat(fmt)

    def _toggle_bold(self):
        is_bold = self.body.fontWeight() > QFont.Normal
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Normal if is_bold else QFont.Bold)
        self._merge_format(fmt)

    def _toggle_italic(self):
        fmt = QTextCharFormat()
        fmt.setFontItalic(not self.body.fontItalic())
        self._merge_format(fmt)

    def _toggle_underline(self):
        fmt = QTextCharFormat()
        fmt.setFontUnderline(not self.body.fontUnderline())
        self._merge_format(fmt)

    def _toggle_strikethrough(self):
        fmt = QTextCharFormat()
        fmt.setFontStrikeOut(not self.body.currentCharFormat().fontStrikeOut())
        self._merge_format(fmt)

    def _set_alignment(self, alignment):
        self.body.setAlignment(alignment)
        self.mark_changed()

    # -- color -----------------------------------------------------------

    def set_color(self, color_hex: str):
        self.note.color = color_hex
        self._apply_color()
        self.mark_changed()

    def _apply_color(self):
        header_color = header_shade(self.note.color)
        self._update_header_style(header_color)
        self.footer.setStyleSheet(
            f"#footer {{ background-color: {self.note.color}; "
            f"border-bottom-left-radius: {RADIUS}px; border-bottom-right-radius: {RADIUS}px; }}"
        )
        self.body.setStyleSheet(
            f"background-color: {self.note.color}; border: none;"
        )

    def _update_header_style(self, header_color: str | None = None):
        """The header normally only rounds its top corners (the footer
        rounds the bottom ones), but when rolled up the header is the
        entire visible window, so it needs all four corners rounded or the
        bottom looks squared-off and broken."""
        if header_color is None:
            header_color = header_shade(self.note.color)
        if self.note.rolled_up:
            radii = (
                f"border-top-left-radius: {RADIUS}px; border-top-right-radius: {RADIUS}px; "
                f"border-bottom-left-radius: {RADIUS}px; border-bottom-right-radius: {RADIUS}px;"
            )
        else:
            radii = (
                f"border-top-left-radius: {RADIUS}px; border-top-right-radius: {RADIUS}px;"
            )
        self.header.setStyleSheet(
            f"#header {{ background-color: {header_color}; {radii} }}" + ICON_BUTTON_QSS
        )

    def show_color_menu(self, anchor_widget: QWidget):
        menu = QMenu(self)
        menu.setStyleSheet(get_menu_qss())

        grid_container = build_color_swatch_grid(
            SWATCHES, self.note.color, lambda c: self._pick_color(c, menu)
        )
        action = QWidgetAction(menu)
        action.setDefaultWidget(grid_container)
        menu.addAction(action)

        menu.addSeparator()
        delete_action = menu.addAction("Delete Note")
        delete_action.triggered.connect(self.confirm_delete)

        menu.exec(anchor_widget.mapToGlobal(anchor_widget.rect().bottomLeft()))

    def _pick_color(self, color: str, menu: QMenu):
        self.set_color(color)
        menu.close()

    # -- always-on-top ---------------------------------------------------

    def _apply_standalone_flags(self):
        flags = STANDALONE_FLAGS
        if self.note.always_on_top:
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)

    def set_always_on_top(self, checked: bool):
        self.note.always_on_top = checked
        if self.note.board_id is None:
            # A live re-toggle needs a direct EWMH state change, not
            # setWindowFlags() — see x11_wm.set_stays_on_top for why.
            set_stays_on_top(int(self.winId()), checked)
        self.mark_changed()

    # -- roll up / down ----------------------------------------------------

    def toggle_rolled(self):
        self._set_rolled(not self.note.rolled_up)

    def _set_rolled(self, rolled: bool, persist: bool = True):
        self.note.rolled_up = rolled
        if rolled:
            self._expanded_height = self.height()
            self.body.hide()
            self.footer.hide()
            self.setMinimumHeight(HEADER_HEIGHT)
            self.resize(self.width(), HEADER_HEIGHT)
        else:
            self.body.show()
            self.footer.show()
            self.setMinimumHeight(120)
            self.resize(self.width(), self._expanded_height)
        self._update_header_style()
        self.header.roll_btn.setText("▼" if rolled else "▲")
        if persist:
            self.mark_changed()

    # -- Memoboard attach/detach -----------------------------------------

    def attach_to_board(self, board, pos=None):
        """Reparent this note into (or out of) a Memoboard canvas.

        `board` is a MemoboardWindow, or None to pop back to the desktop.
        Window flags only take effect on a widget with no parent, so the
        parent/flags/show sequence below must stay in this order.
        """
        if board is not None:
            self.setParent(board.canvas)
            self.setWindowFlags(Qt.Widget)
            if pos is not None:
                self.move(pos)
            self.show()
            self.note.board_id = board.board.id
        else:
            self.setParent(None)
            self._apply_standalone_flags()
            if pos is not None:
                self.move(pos)
            self.show()
            # Reparenting recreates the native window, same as a fresh
            # construction — reapply both via direct state messages rather
            # than trusting the flags alone (see set_stays_on_top's docstring).
            win_id = int(self.winId())
            set_skip_taskbar(win_id, True)
            set_stays_on_top(win_id, self.note.always_on_top)
            self.note.board_id = None
        self.mark_changed()

    # -- persistence hooks -------------------------------------------------

    def sync_model(self) -> Note:
        """Pull the latest widget state into the Note model. Called by
        NoteManager just before writing to disk, rather than on every
        keystroke."""
        self.note.html = self.body.toHtml()
        self.note.x, self.note.y = self.pos().x(), self.pos().y()
        self.note.w = self.size().width()
        # While rolled up the window is squashed to header height only;
        # persist the last known expanded height instead so un-rolling
        # after a restart restores the note's real size.
        if self.note.rolled_up:
            self.note.h = self._expanded_height
        else:
            self.note.h = self.size().height()
        return self.note

    def mark_changed(self):
        self.note.modified_at = _now_iso()
        self.changed.emit()

    def moveEvent(self, event):
        super().moveEvent(event)
        self.mark_changed()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.mark_changed()

    # -- context menu / delete --------------------------------------------

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet(get_menu_qss())
        self.populate_note_menu(menu)
        menu.exec(event.globalPos())

    def populate_note_menu(self, menu: QMenu):
        """Builds the note-level menu contents (formatting, color,
        always-on-top, Memoboard, delete). Shared by NoteWindow's own
        contextMenuEvent (right-click on the header) and NoteBody's
        (right-click in the text, appended after the standard Undo/Cut/
        Copy/Paste menu) so both surfaces offer the same options."""
        font_style_menu = menu.addMenu("Font Style")
        font_style_menu.addAction(self.bold_action)
        font_style_menu.addAction(self.italic_action)
        font_style_menu.addAction(self.underline_action)
        font_style_menu.addAction(self.strikethrough_action)
        font_style_menu.addSeparator()
        font_style_menu.addAction(self.align_left_action)
        font_style_menu.addAction(self.align_center_action)
        font_style_menu.addAction(self.align_right_action)

        menu.addSeparator()
        color_action = menu.addAction("Change Color…")
        color_action.triggered.connect(lambda: self.show_color_menu(self))

        aot_action = menu.addAction("Always on Top")
        aot_action.setCheckable(True)
        aot_action.setChecked(self.note.always_on_top)
        aot_action.toggled.connect(self.set_always_on_top)

        menu.addSeparator()
        if self.note.board_id is None:
            board_menu = menu.addMenu("Add to Memoboard")
            boards = list(self.manager.boards.values())
            for board_window in boards:
                action = board_menu.addAction(board_window.board.name)
                action.triggered.connect(
                    lambda checked=False, b=board_window: self.manager.attach_note_to_board(self, b)
                )
            if boards:
                board_menu.addSeparator()
            new_board_action = board_menu.addAction("New Memoboard…")
            new_board_action.triggered.connect(
                lambda: self.manager.create_board_and_attach(self)
            )
        else:
            remove_action = menu.addAction("Remove from Memoboard")
            remove_action.triggered.connect(
                lambda: self.manager.detach_note_from_board(self)
            )

        menu.addSeparator()
        delete_action = menu.addAction("Delete Note")
        delete_action.triggered.connect(self.confirm_delete)

    def confirm_delete(self):
        reply = QMessageBox.question(
            self,
            "Delete Note",
            "Delete this note permanently?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.manager.delete_note(self)
