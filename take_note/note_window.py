from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QFont,
    QGuiApplication,
    QKeySequence,
    QTextCharFormat,
    QTextCursor,
    QTextListFormat,
)
from PySide6.QtWidgets import (
    QFontDialog,
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

from .models import FONT_SWATCHES, SWATCHES, TRANSPARENCY_LEVELS, Note
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
        self.menu_btn.clicked.connect(lambda: note_window.show_note_menu(self.menu_btn))
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
        # Only text-formatting actions here — whole-note actions (color,
        # transparency, always-on-top, Memoboard, delete) don't make sense
        # to offer while the user is mid-selection in the text, and live in
        # the header's right-click menu / hamburger menu instead.
        menu = self.createStandardContextMenu()
        menu.setStyleSheet(get_menu_qss())
        menu.addSeparator()
        self.note_window.populate_text_menu(menu)
        menu.exec(event.globalPos())

    def keyPressEvent(self, event):
        # Tab/Shift+Tab indent or dedent the current list item, matching
        # standard word-processor behavior. Only intercepted while the
        # cursor is actually in a list, so plain-text Tab (insert a tab
        # character) is untouched elsewhere.
        if event.key() in (Qt.Key_Tab, Qt.Key_Backtab) and self.textCursor().currentList():
            if event.key() == Qt.Key_Backtab or event.modifiers() & Qt.ShiftModifier:
                self.note_window._decrease_indent()
            else:
                self.note_window._increase_indent()
            return
        super().keyPressEvent(event)


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
        self.setWindowOpacity(note.opacity)
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
        # Qt's default indent step is 40px/level — reasonable in a full-size
        # document but excessive in a note only ~140-220px wide, where two
        # or three nested list levels would otherwise eat most of the width.
        # 16px went too far the other way: Qt renders a list marker glyph
        # ending flush at the indent boundary, so a marker wider than the
        # step itself (confirmed for styles up to "viii.") overflows past
        # the note's left edge instead of just being tight against it.
        self.body.document().setIndentWidth(24)
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

        # (style-or-None, label) pairs backing the Bullets & Numbering
        # submenu. Kept as a table (not one-off actions) so populate_text_menu
        # can look up which action matches the cursor's current list style
        # and check it, giving the menu a visual indicator of the current
        # state rather than requiring the user to infer it from the note body.
        list_style_specs = [
            (None, "None"),
            (QTextListFormat.ListDisc, "• Bullets"),
            (QTextListFormat.ListDecimal, "1, 2, 3"),
            (QTextListFormat.ListLowerAlpha, "a, b, c"),
            (QTextListFormat.ListUpperAlpha, "A, B, C"),
            (QTextListFormat.ListLowerRoman, "i, ii, iii"),
            (QTextListFormat.ListUpperRoman, "I, II, III"),
        ]
        self.list_style_group = QActionGroup(self)
        self.list_style_group.setExclusive(True)
        self.list_style_actions = []
        for style, label in list_style_specs:
            action = QAction(label, self)
            action.setCheckable(True)
            action.triggered.connect(lambda checked=False, s=style: self._set_list_style(s))
            self.list_style_group.addAction(action)
            self.list_style_actions.append((style, action))

        self.increase_indent_action = QAction("Increase Indent", self)
        self.increase_indent_action.triggered.connect(self._increase_indent)
        self.decrease_indent_action = QAction("Decrease Indent", self)
        self.decrease_indent_action.triggered.connect(self._decrease_indent)

        self.opacity_group = QActionGroup(self)
        self.opacity_group.setExclusive(True)
        self.opacity_actions = []
        for label, value in TRANSPARENCY_LEVELS:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(value == self.note.opacity)
            action.triggered.connect(lambda checked=False, v=value: self.set_opacity(v))
            self.opacity_group.addAction(action)
            self.opacity_actions.append(action)

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

    def show_font_dialog(self):
        """A real QFontDialog rather than embedding font-family/size combo
        boxes directly in the context menu: those fought QMenu's own popup
        handling (clicking the size dropdown closed the whole menu instead
        of opening it) and needed constant manual re-styling just to match
        the theme, since QMenu.setStyleSheet() doesn't cascade into
        QWidgetAction-embedded widgets. A dialog sidesteps both problems
        and covers family/size/weight/italic/underline in one place."""
        # PySide6 returns (ok, font) here — the reverse of PyQt5's (font, ok)
        # convention, confirmed by direct inspection; got this backwards on
        # the first pass, which crashed setCurrentFont() with a bool.
        ok, font = QFontDialog.getFont(self.body.currentFont(), self)
        if ok:
            self.body.setCurrentFont(font)
            self.mark_changed()

    def _set_list_style(self, style: QTextListFormat.Style | None):
        cursor = self.body.textCursor()
        if not cursor.hasSelection():
            self._apply_list_style_to_block(cursor.block(), style)
            self.mark_changed()
            return

        # A multi-line selection can span several distinct QTextList
        # objects (each nesting depth created by indent/dedent is its own
        # list) — cursor.currentList() only reflects the cursor's single
        # active position, so applying a style change through it alone
        # would silently skip every other list the selection touches.
        doc = self.body.document()
        start = min(cursor.selectionStart(), cursor.selectionEnd())
        end = max(cursor.selectionStart(), cursor.selectionEnd())
        block = doc.findBlock(start)
        while block.isValid() and block.position() < end:
            self._apply_list_style_to_block(block, style)
            block = block.next()
        self.mark_changed()

    def _apply_list_style_to_block(self, block, style: QTextListFormat.Style | None):
        current_list = block.textList()
        if style is None:
            if current_list is not None:
                current_list.remove(block)
        elif current_list is not None:
            fmt = current_list.format()
            fmt.setStyle(style)
            current_list.setFormat(fmt)
        else:
            QTextCursor(block).createList(QTextListFormat.Style(style))

    def _current_list_style(self) -> QTextListFormat.Style | None:
        """The list style at the cursor, or None outside any list. Used to
        put a checkmark on the matching Bullets & Numbering menu entry."""
        current_list = self.body.textCursor().currentList()
        return current_list.format().style() if current_list is not None else None

    @staticmethod
    def _find_adjacent_list(block, target_indent: int):
        """Search backward through preceding blocks for the nearest list at
        exactly `target_indent`, so indenting/dedenting a line rejoins an
        adjacent sibling's (sub)list instead of always creating a new,
        disconnected one that restarts numbering unexpectedly."""
        b = block.previous()
        while b.isValid():
            lst = b.textList()
            if lst is None:
                return None
            indent = lst.format().indent()
            if indent == target_indent:
                return lst
            if indent < target_indent:
                return None
            b = b.previous()
        return None

    def _list_indent_step(self, delta: int):
        cursor = self.body.textCursor()
        current_list = cursor.currentList()
        if current_list is None:
            # Not in a list: a plain visual block indent (works for any
            # paragraph, not just list items).
            block_fmt = cursor.blockFormat()
            block_fmt.setIndent(max(0, block_fmt.indent() + delta))
            cursor.mergeBlockFormat(block_fmt)
            self.mark_changed()
            return

        style = current_list.format().style()
        new_indent = current_list.format().indent() + delta
        block = cursor.block()

        if new_indent < 1:
            current_list.remove(block)
            block_fmt = cursor.blockFormat()
            block_fmt.setIndent(0)
            cursor.mergeBlockFormat(block_fmt)
            self.mark_changed()
            return

        target_list = self._find_adjacent_list(block, new_indent)
        current_list.remove(block)
        if target_list is not None:
            target_list.add(block)
        else:
            fmt = QTextListFormat()
            fmt.setStyle(style)
            fmt.setIndent(new_indent)
            cursor.createList(fmt)

        # A block's own indent level (separate from the list's nesting
        # depth) doesn't get resynced when rejoining an existing list via
        # QTextList.add() — left stale, it visually narrows/widens the
        # line independent of where it actually sits in the list nesting.
        # Force it back in sync with the list depth explicitly.
        block_fmt = cursor.blockFormat()
        block_fmt.setIndent(new_indent - 1)
        cursor.mergeBlockFormat(block_fmt)
        self.mark_changed()

    def _increase_indent(self):
        self._list_indent_step(1)

    def _decrease_indent(self):
        self._list_indent_step(-1)

    def _set_text_color(self, color: str):
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        self._merge_format(fmt)
        # Automatic list markers (bullets/numbers) are painted using the
        # block's own char format, not the per-character format that
        # mergeCurrentCharFormat touches — without this, a list item's "1."
        # stays the old color even after the item's text is recolored.
        self._merge_block_format_over_selection(fmt)

    def _merge_block_format_over_selection(self, fmt: QTextCharFormat):
        """mergeBlockCharFormat on a selection that ends exactly at
        EndOfBlock (e.g. selecting one line's text, not crossing into the
        next block) corrupts that list item's cached layout rect in Qt,
        making it stop painting entirely. Selecting through each block's
        trailing separator instead (its full `block.length()`, not just
        its visible text) avoids that — reproduced and confirmed via a
        minimal QTextEdit case before landing this fix."""
        selection_cursor = self.body.textCursor()
        if not selection_cursor.hasSelection():
            selection_cursor.mergeBlockCharFormat(fmt)
            return
        doc = self.body.document()
        start = min(selection_cursor.selectionStart(), selection_cursor.selectionEnd())
        end = max(selection_cursor.selectionStart(), selection_cursor.selectionEnd())
        block = doc.findBlock(start)
        while block.isValid() and block.position() < end:
            block_cursor = QTextCursor(block)
            block_end = min(block.position() + block.length(), doc.characterCount() - 1)
            block_cursor.setPosition(block_end, QTextCursor.KeepAnchor)
            block_cursor.mergeBlockCharFormat(fmt)
            block = block.next()

    def show_font_color_menu(self, anchor_widget: QWidget):
        menu = QMenu(self)
        menu.setStyleSheet(get_menu_qss())

        grid_container = build_color_swatch_grid(
            FONT_SWATCHES, self.body.textColor().name(), lambda c: self._pick_font_color(c, menu)
        )
        action = QWidgetAction(menu)
        action.setDefaultWidget(grid_container)
        menu.addAction(action)

        menu.exec(anchor_widget.mapToGlobal(anchor_widget.rect().bottomLeft()))

    def _pick_font_color(self, color: str, menu: QMenu):
        self._set_text_color(color)
        menu.close()

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

    # -- transparency ------------------------------------------------------

    def set_opacity(self, value: float):
        self.note.opacity = value
        self.setWindowOpacity(value)
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
        # Right-clicking the header is about the note as a whole (there's
        # no text selection here), so it gets the same whole-note actions
        # as the hamburger menu rather than text-formatting options.
        menu = QMenu(self)
        menu.setStyleSheet(get_menu_qss())
        self.populate_note_actions_menu(menu)
        menu.exec(event.globalPos())

    def show_note_menu(self, anchor_widget: QWidget):
        menu = QMenu(self)
        menu.setStyleSheet(get_menu_qss())
        self.populate_note_actions_menu(menu)
        menu.exec(anchor_widget.mapToGlobal(anchor_widget.rect().bottomLeft()))

    def populate_text_menu(self, menu: QMenu):
        """Text-formatting actions (font style/color, bullets & numbering,
        indent). Used only by NoteBody's contextMenuEvent (right-click in
        the text, appended after the standard Undo/Cut/Copy/Paste menu) —
        these act on the current selection, so whole-note actions like
        color/transparency/always-on-top/Memoboard/delete don't belong
        here (see populate_note_actions_menu)."""
        font_action = menu.addAction("Font…")
        font_action.triggered.connect(self.show_font_dialog)

        font_style_menu = menu.addMenu("Font Style")
        font_style_menu.addAction(self.bold_action)
        font_style_menu.addAction(self.italic_action)
        font_style_menu.addAction(self.underline_action)
        font_style_menu.addAction(self.strikethrough_action)
        font_style_menu.addSeparator()
        font_style_menu.addAction(self.align_left_action)
        font_style_menu.addAction(self.align_center_action)
        font_style_menu.addAction(self.align_right_action)

        font_color_action = menu.addAction("Font Color…")
        font_color_action.triggered.connect(lambda: self.show_font_color_menu(self))

        bullets_menu = menu.addMenu("Bullets && Numbering")
        current_style = self._current_list_style()
        for style, action in self.list_style_actions:
            action.setChecked(style == current_style)
            bullets_menu.addAction(action)

        menu.addAction(self.increase_indent_action)
        menu.addAction(self.decrease_indent_action)

    def populate_note_actions_menu(self, menu: QMenu):
        """Whole-note actions (color, transparency, always-on-top,
        Memoboard membership, delete). Used by the header's right-click
        menu and the hamburger (☰) button's dropdown — these apply to the
        note as a whole, not to a text selection, so they're kept out of
        the body's text-formatting menu (see populate_text_menu)."""
        color_action = menu.addAction("Change Note Color…")
        color_action.triggered.connect(lambda: self.show_color_menu(self))

        transparency_menu = menu.addMenu("Note Transparency")
        for action in self.opacity_actions:
            transparency_menu.addAction(action)

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
        # A plain child dialog doesn't reliably outrank this note's own
        # raw EWMH "always on top" state in KWin's stacking layers (that
        # hint elevates by window layer, not just parent/child order) —
        # force the dialog on top too so it can't end up hidden behind an
        # always-on-top note.
        box = QMessageBox(self)
        box.setWindowTitle("Delete Note")
        box.setText("Delete this note permanently?")
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setWindowFlags(box.windowFlags() | Qt.WindowStaysOnTopHint)
        reply = box.exec()
        if reply == QMessageBox.Yes:
            self.manager.delete_note(self)
