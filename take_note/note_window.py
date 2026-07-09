from __future__ import annotations

import base64
from datetime import datetime, timezone

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, QSize, QUrl, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QDesktopServices,
    QFont,
    QGuiApplication,
    QIcon,
    QImage,
    QKeySequence,
    QPainter,
    QPen,
    QPixmap,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextListFormat,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QFontDialog,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QMenu,
    QMessageBox,
    QSizeGrip,
    QTextEdit,
    QToolButton,
    QToolTip,
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

# A deep navy rather than the conventional bright hyperlink blue: one of
# our own SWATCHES is a pastel light blue, and bright blue text blends
# into it. Checked via WCAG contrast ratio against every SWATCHES color —
# this keeps a minimum of 5.5:1 (comfortably above the 4.5:1 AA
# threshold) everywhere, not just against the backgrounds it happens to
# clash with least.
HYPERLINK_COLOR = "#1a237e"

# How much darker the header strip is than the note's own color.
# Needs to be dark enough that white icon glyphs (ICON_BUTTON_QSS below)
# have real contrast against it, not just a slightly-shaded version of a
# pastel color that's still too light for white-on-it to read clearly.
HEADER_DARKEN = 230


def header_shade(color_hex: str) -> str:
    return QColor(color_hex).darker(HEADER_DARKEN).name()


#  Amber rather than white for the locked state — distinct at a glance from
#  the unlocked icon (plain white, matching every other header icon) and
#  reads as a "restricted" cue, not just a state swap. Picked over red/
#  orange candidates by checking WCAG contrast against header_shade() of
#  every SWATCHES color (same method as HYPERLINK_COLOR's own comment
#  above) — reds and oranges all fell below a 3:1 floor (WCAG's own bar
#  for graphical UI components, not full 4.5:1 text contrast) against at
#  least one note color's darkened header, since their hue is close to the
#  header's own warm dark tones; this amber clears 3:1 against all seven
#  with room to spare.
LOCK_ICON_COLOR_UNLOCKED = "white"
LOCK_ICON_COLOR_LOCKED = "#ffe57f"


def lock_icon(locked: bool, size: int = 18) -> QIcon:
    """A hand-drawn icon rather than a text glyph — neither of Unicode's
    padlock emoji (🔒/🔓, U+1F512/1F513) render at all in this app's actual
    runtime environment (confirmed directly: they left a blank gap in the
    header), so this avoids depending on emoji-font availability entirely,
    the same way the tray icon in tray.py draws its own pixmap rather than
    bundling an asset."""
    color = LOCK_ICON_COLOR_LOCKED if locked else LOCK_ICON_COLOR_UNLOCKED
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    pen = QPen(QColor(color))
    pen.setWidthF(size * 0.09)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    # Nudges the whole glyph down slightly within its canvas — centered
    # exactly on the canvas rendered a bit high compared to this header's
    # other, text-baseline-positioned icons (+, ▲/▼, ☰, ×).
    y_offset = size * 0.1

    shackle_w = size * 0.42
    shackle_h = size * 0.38
    shackle_top = size * 0.12 + y_offset
    if locked:
        shackle_rect = QRectF((size - shackle_w) / 2, shackle_top, shackle_w, shackle_h * 2)
        painter.drawArc(shackle_rect, 0, 180 * 16)
    else:
        # Open: shackle swung up and to the left, only its right leg still
        # planted in the body — a common minimal "unlocked" convention.
        shackle_rect = QRectF(
            (size - shackle_w) / 2 - size * 0.05, shackle_top - size * 0.12, shackle_w, shackle_h * 2
        )
        painter.drawArc(shackle_rect, 20 * 16, 160 * 16)

    painter.setBrush(QColor(color))
    painter.setPen(Qt.NoPen)
    body_w = size * 0.6
    body_h = size * 0.42
    body_rect = QRectF((size - body_w) / 2, size * 0.46 + y_offset, body_w, body_h)
    painter.drawRoundedRect(body_rect, size * 0.06, size * 0.06)

    painter.end()
    return QIcon(pixmap)

# Cascades to every QToolButton inside whatever container this is mixed
# into, so icons stay legible regardless of the app/system theme instead
# of inheriting near-invisible default text colors on a colored strip.
ICON_BUTTON_QSS = """
QToolButton { color: white; border: none; background: transparent; padding: 2px; }
QToolButton:hover { background-color: rgba(255, 255, 255, 50); border-radius: 4px; }
QToolButton:checked { background-color: rgba(255, 255, 255, 80); border-radius: 4px; }
"""

# The find bar's own background is a fixed light color regardless of note
# color or desktop theme (see NoteFindBar's docstring), so its field text
# and button glyphs need matching fixed dark colors too — left to inherit
# the app's ambient palette (which can itself be dark), the field text and
# ▲▼× glyphs rendered nearly invisible against the light bar.
FIND_BAR_QSS = """
QLineEdit { background-color: white; color: #202020; border: 1px solid #b0b0b0; border-radius: 3px; padding: 2px 4px; }
QToolButton { color: #202020; border: none; background: transparent; padding: 2px; }
QToolButton:hover { background-color: rgba(0, 0, 0, 30); border-radius: 4px; }
QToolButton:disabled { color: #a0a0a0; }
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


class _LockButton(QToolButton):
    """A real double-click on a QAbstractButton fires its `clicked` signal
    twice — once for each half of the double-click, confirmed directly
    (offscreen, sending Press/Release/DblClick/Release: the first Release
    fires `clicked` immediately, then a second `clicked` fires from the
    Release that follows the synthesized DblClick event). Wiring `clicked`
    alone to toggle the lock would flip it twice on a double-click (locked
    → unlocked → locked, a net no-op) — this suppresses that second
    emission so both a single click and a double-click toggle exactly
    once."""

    def __init__(self, note_window: "NoteWindow"):
        super().__init__()
        self._note_window = note_window
        self._suppress_next_click = False
        self.clicked.connect(self._handle_click)

    def _handle_click(self):
        if self._suppress_next_click:
            self._suppress_next_click = False
            return
        self._note_window.set_locked(not self._note_window.note.locked)

    def mouseDoubleClickEvent(self, event):
        # The first click's own Release already toggled the lock via the
        # normal _handle_click() path before Qt even recognizes a double-
        # click is underway — this only needs to suppress the *second*
        # click's Release (which follows this event) from toggling it
        # again, not perform a toggle of its own.
        self._suppress_next_click = True
        super().mouseDoubleClickEvent(event)


class NoteHeader(QWidget):
    """Colored drag handle strip. Holds a direct reference to its NoteWindow
    (not self.window()) so dragging still works correctly once a note is
    reparented into a Notepad's canvas."""

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

        self.lock_btn = _LockButton(note_window)
        self.lock_btn.setAutoRaise(True)
        self.lock_btn.setIconSize(QSize(18, 18))
        layout.addWidget(self.lock_btn)

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
        # transparency, always-on-top, Notepad, delete) don't make sense
        # to offer while the user is mid-selection in the text, and live in
        # the header's right-click menu / hamburger menu instead.
        self._select_image_under_click(event.pos())
        menu = self.createStandardContextMenu()
        menu.setStyleSheet(get_menu_qss())
        menu.addSeparator()
        self.note_window.populate_text_menu(menu)
        menu.exec(event.globalPos())

    def _select_image_under_click(self, pos):
        """Right-clicking directly on an inline image otherwise leaves any
        existing cursor/selection completely untouched (Qt's default
        behavior for a right-click), so Cut/Copy/Delete in the standard
        context menu stay disabled even though the image under the click
        is exactly what the user meant to act on. Thin pixel-to-position
        adapter — the actual decision logic lives in _select_image_at so
        it can be unit tested against known document positions instead of
        synthetic mouse coordinates."""
        self._select_image_at(self.cursorForPosition(pos).position())

    def _select_image_at(self, position: int):
        cursor = self.textCursor()
        if cursor.hasSelection():
            start, end = sorted((cursor.selectionStart(), cursor.selectionEnd()))
            if start <= position <= end:
                return  # clicked inside an existing selection; leave it alone

        # movePosition() can fail at a document boundary (no actual
        # movement), leaving anchor == position — but charFormat() on that
        # empty "selection" still reports the format of the preceding
        # character (the format that would be used for the next typed
        # character), which is a false positive right after an image.
        # hasSelection() rules that out.
        doc = self.document()
        forward = QTextCursor(doc)
        forward.setPosition(position)
        forward.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor)
        if forward.hasSelection() and forward.charFormat().isImageFormat():
            self.setTextCursor(forward)
            return

        backward = QTextCursor(doc)
        backward.setPosition(position)
        backward.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor)
        if backward.hasSelection() and backward.charFormat().isImageFormat():
            self.setTextCursor(backward)

    def keyPressEvent(self, event):
        # Tab/Shift+Tab indent or dedent the current list item, matching
        # standard word-processor behavior. Only intercepted while the
        # cursor is actually in a list, so plain-text Tab (insert a tab
        # character) is untouched elsewhere. Also skipped on a locked note:
        # unlike setReadOnly()'s own built-in keystroke handling, this
        # override calls _increase_indent()/_decrease_indent() directly and
        # would otherwise still edit the list's indent despite the lock.
        if (
            not self.note_window.note.locked
            and event.key() in (Qt.Key_Tab, Qt.Key_Backtab)
            and self.textCursor().currentList()
        ):
            if event.key() == Qt.Key_Backtab or event.modifiers() & Qt.ShiftModifier:
                self.note_window._decrease_indent()
            else:
                self.note_window._increase_indent()
            return
        super().keyPressEvent(event)
        # Deleting a whole multi-item list (e.g. Select All + Delete) merges
        # everything down to one empty block, but Qt's merge keeps that
        # block's list membership/indent from whichever original block
        # survived — leaving a stray bullet/number floating in an otherwise
        # blank note. removeSelectedText() doesn't have this problem; only
        # the Delete/Backspace key path does.
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace) and not self.toPlainText():
            self.note_window._clear_empty_list_formatting()

    def mouseMoveEvent(self, event):
        # A plain QTextEdit (unlike QTextBrowser) has no built-in hyperlink
        # affordance at all — no hand cursor, no click-to-open. Add the
        # hover cursor here; opening on click is handled in
        # mouseReleaseEvent (Ctrl+Click only, so a plain click can still
        # place the cursor to edit link text without launching a browser).
        # The tooltip exists because a plain click doing nothing was
        # reported as confusing on its own — the hand cursor alone didn't
        # communicate that Ctrl+Click is what's needed.
        anchor = self.anchorAt(event.position().toPoint())
        if anchor:
            self.viewport().setCursor(Qt.PointingHandCursor)
            # Deliberately not passing `self` as the optional widget arg
            # here: QToolTip.showText() copies that widget's *palette*
            # onto the tooltip when given, and a note body's palette
            # reflects its own background-color — so the tip silently
            # blended into whatever color the note happened to be.
            # Confirmed via widget.grab() (screenshotting a real QToolTip
            # window isn't reliable in this environment) that omitting it
            # restores Qt's normal system tooltip styling.
            tip = f"Ctrl+Click to open\nClick, then right-click to edit\n{anchor}"
            QToolTip.showText(event.globalPosition().toPoint(), tip)
        else:
            self.viewport().setCursor(Qt.IBeamCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and event.modifiers() & Qt.ControlModifier:
            anchor = self.anchorAt(event.position().toPoint())
            if anchor:
                QDesktopServices.openUrl(QUrl(anchor))
        super().mouseReleaseEvent(event)


class _FindLineEdit(QLineEdit):
    """Plain QLineEdit has no signal for Escape — needed so the find bar
    can be dismissed from the keyboard without reaching for the mouse."""

    escapePressed = Signal()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.escapePressed.emit()
            return
        super().keyPressEvent(event)


class NoteFindBar(QWidget):
    """Inline, non-modal find bar shown between the header and body,
    toggled by Ctrl+F / the text context menu's Find… action. Non-modal
    (rather than a dialog, unlike Hyperlink/Font) so the user can keep
    searching and see each match selected/scrolled into view in the note
    without losing focus on the text underneath. Deliberately styled with
    a fixed light background rather than the header/footer's note-color
    shading — it needs to stay readable against every note color and
    every desktop theme, not match either."""

    def __init__(self, note_window: "NoteWindow"):
        super().__init__()
        self.note_window = note_window
        self.setObjectName("findbar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        # Bare (selector-less) declarations don't mix reliably with the
        # class-selector rules in FIND_BAR_QSS in the same stylesheet
        # string — matches every other multi-rule stylesheet in this file
        # (e.g. the header's "#header { ... }" + ICON_BUTTON_QSS) by
        # scoping the bar's own background to its object name instead.
        self.setStyleSheet(
            "#findbar { background-color: #f0f0f0; border-bottom: 1px solid #c0c0c0; }"
            + FIND_BAR_QSS
        )
        self.hide()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)

        self.field = _FindLineEdit()
        self.field.setPlaceholderText("Find…")
        self.field.textChanged.connect(self._find_from_start)
        self.field.returnPressed.connect(self.find_next)
        self.field.escapePressed.connect(self.close_bar)
        layout.addWidget(self.field, stretch=1)

        prev_btn = QToolButton()
        prev_btn.setText("▲")
        prev_btn.setAutoRaise(True)
        prev_btn.setToolTip("Previous match")
        prev_btn.clicked.connect(self.find_previous)
        layout.addWidget(prev_btn)

        next_btn = QToolButton()
        next_btn.setText("▼")
        next_btn.setAutoRaise(True)
        next_btn.setToolTip("Next match")
        next_btn.clicked.connect(self.find_next)
        layout.addWidget(next_btn)

        close_btn = QToolButton()
        close_btn.setText("×")
        close_btn.setAutoRaise(True)
        close_btn.setToolTip("Close (Esc)")
        close_btn.clicked.connect(self.close_bar)
        layout.addWidget(close_btn)

    def open_bar(self):
        self.show()
        self.field.selectAll()
        self.field.setFocus()
        if self.field.text():
            self._find_from_start()

    def close_bar(self):
        self.hide()
        self.note_window.body.setFocus()

    def find_next(self):
        self._perform_find(backward=False)

    def find_previous(self):
        self._perform_find(backward=True)

    def _find_from_start(self):
        self._perform_find(backward=False, from_start=True)

    def _perform_find(self, backward: bool, from_start: bool = False):
        text = self.field.text()
        body = self.note_window.body
        if not text:
            self._set_not_found(False)
            return

        document = body.document()
        options = QTextDocument.FindBackward if backward else QTextDocument.FindFlags()
        cursor = QTextCursor(document) if from_start else body.textCursor()
        found = document.find(text, cursor, options)

        if found.isNull():
            # Wrap around: retry from the far end of the document rather
            # than reporting no match just because the search started
            # partway through.
            wrap_cursor = QTextCursor(document)
            if backward:
                wrap_cursor.movePosition(QTextCursor.End)
            found = document.find(text, wrap_cursor, options)

        if found.isNull():
            self._set_not_found(True)
        else:
            self._set_not_found(False)
            body.setTextCursor(found)
            body.ensureCursorVisible()

    def _set_not_found(self, not_found: bool):
        self.field.setStyleSheet("background-color: #ffcdd2;" if not_found else "")


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
        self.set_locked(note.locked, persist=False)
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

        self.find_bar = NoteFindBar(self)
        layout.addWidget(self.find_bar)

        self.body = NoteBody(self)
        self.body.setFrameStyle(0)
        # Qt's default indent step is 40px/level — reasonable in a full-size
        # document but excessive in a note only ~140-220px wide, where two
        # or three nested list levels would otherwise eat most of the width.
        # 16px went too far the other way: Qt renders a list marker glyph
        # ending flush at the indent boundary, so a marker wider than the
        # step itself overflows past the note's left edge instead of just
        # being tight against it. A prior fix to 24px was measured against
        # the *offscreen* QPA platform's generic fallback font rather than
        # xcb's real one (KDE's theme-integrated "Noto Sans"), which is
        # visibly wider — "viii." needs ~33px there, not ~19px. 36px
        # covers that under the real font with a few px to spare, while
        # still well below Qt's default.
        self.body.document().setIndentWidth(36)
        self.body.textChanged.connect(self.mark_changed)
        self.body.textChanged.connect(self._update_find_action_enabled)
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

        self.find_action = make_action("Find…", "Ctrl+F", self.toggle_find_bar)
        # Disabled until there's something to search — matches its initial
        # state here (the body is still empty at this point in __init__;
        # _build_ui's textChanged connection keeps it in sync afterward).
        self.find_action.setEnabled(bool(self.body.toPlainText()))

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

    def toggle_find_bar(self):
        # find_action.setEnabled() already keeps this out of reach from the
        # menu/shortcut for an empty note; guarded again here as a direct
        # safety net against calling this method itself.
        if not self.body.toPlainText():
            return
        self.find_bar.open_bar()

    def _update_find_action_enabled(self):
        self.find_action.setEnabled(bool(self.body.toPlainText()))

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

    def show_hyperlink_dialog(self):
        cursor = self.body.textCursor()
        existing_href = cursor.charFormat().anchorHref() if cursor.charFormat().isAnchor() else ""

        if not cursor.hasSelection() and existing_href:
            # Editing an existing link with just a caret (no selection):
            # expand to the link's whole contiguous text span first, so
            # the URL updates in place instead of inserting new text
            # in the middle of it.
            start, end = self._anchor_span(cursor.position(), existing_href)
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)

        # The static QInputDialog.getText() convenience defaults to a
        # width too narrow to read/edit a typical URL comfortably —
        # build the dialog directly so it can be sized explicitly.
        dialog = QInputDialog(self)
        dialog.setWindowTitle("Edit Hyperlink" if existing_href else "Insert Hyperlink")
        dialog.setLabelText("URL:")
        dialog.setTextValue(existing_href or "https://")
        dialog.resize(420, dialog.sizeHint().height())
        if dialog.exec() != QInputDialog.Accepted:
            return
        url = dialog.textValue()
        if not url:
            return

        fmt = QTextCharFormat()
        fmt.setAnchor(True)
        fmt.setAnchorHref(url)
        fmt.setForeground(QColor(HYPERLINK_COLOR))
        fmt.setFontUnderline(True)

        if cursor.hasSelection():
            cursor.mergeCharFormat(fmt)
        else:
            cursor.insertText(url, fmt)
        self.mark_changed()

    def show_insert_image_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Add Picture", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp)"
        )
        if not path:
            return

        image = QImage(path)
        if image.isNull():
            QMessageBox.warning(self, "Add Picture", "Could not load that image file.")
            return

        # The note itself grows to fit the picture (see
        # _grow_to_fit_content below), so the only thing that needs
        # shrinking here is a picture too big for the screen itself —
        # never upscale a smaller one.
        image = self._cap_image_to_screen(image)

        # Persisted as a self-contained base64 data: URI rather than via
        # QTextDocument's resource cache: cursor.insertImage() would add the
        # pixel data to an in-memory, process-wide QPixmapCache keyed by a
        # generated name, which toHtml() serializes as a bare reference to
        # that name — it looks fine within the same run but the actual image
        # bytes never reach notes.json, so the picture is gone after a
        # restart. A data: URI round-trips through setHtml()/toHtml() on its
        # own since Qt's default resource loader resolves data: URLs natively
        # (confirmed directly; nothing extra needed).
        buffer = QByteArray()
        device = QBuffer(buffer)
        device.open(QIODevice.WriteOnly)
        image.save(device, "PNG")
        data_uri = f"data:image/png;base64,{base64.b64encode(bytes(buffer)).decode('ascii')}"

        self.body.textCursor().insertHtml(
            f'<img src="{data_uri}" width="{image.width()}" height="{image.height()}">'
        )
        self.mark_changed()
        self._grow_to_fit_content()

    def _cap_image_to_screen(self, image: QImage) -> QImage:
        """Caps a picture to the screen's available geometry (minus this
        note's own header/footer chrome) before insertion, so
        _grow_to_fit_content always has room to grow the note to fully
        accommodate it — the image only actually needs shrinking here if it
        wouldn't fit even in a full-screen-sized note."""
        screen = self.screen() or QGuiApplication.primaryScreen()
        available = screen.availableGeometry()
        max_width = available.width()
        max_height = available.height() - self.header.height() - self.footer.height()
        if image.width() > max_width or image.height() > max_height:
            image = image.scaled(max_width, max_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return image

    def _grow_to_fit_content(self):
        """Grows the note — width and height independently — when its
        content (namely a freshly inserted picture) no longer fits the
        visible body area, so it's immediately visible without a manual
        resize or a scrollbar. Each dimension is capped at the screen's
        available geometry; _cap_image_to_screen already keeps any inserted
        picture within that same bound, so growth here should normally be
        enough on its own."""
        screen = self.screen() or QGuiApplication.primaryScreen()
        available = screen.availableGeometry()

        doc_size = self.body.document().size()
        width_shortfall = doc_size.width() - self.body.viewport().width()
        height_shortfall = doc_size.height() - self.body.viewport().height()

        new_width = self.width()
        if width_shortfall > 0:
            new_width = min(self.width() + width_shortfall, available.width())
        new_height = self.height()
        if height_shortfall > 0:
            new_height = min(self.height() + height_shortfall, available.height())

        if new_width > self.width() or new_height > self.height():
            self.resize(int(new_width), int(new_height))

    def _anchor_span(self, position: int, href: str) -> tuple[int, int]:
        """The [start, end) character range of the contiguous run of text
        around `position` that shares the given anchor href — found by
        format continuity, not word boundaries, so a multi-word link
        ("stories and poems") is treated as one span to edit or replace."""
        doc = self.body.document()
        probe = QTextCursor(doc)

        start = position
        while start > 0:
            probe.setPosition(start - 1)
            probe.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)
            if probe.charFormat().anchorHref() != href:
                break
            start -= 1

        doc_len = doc.characterCount() - 1
        end = position
        while end < doc_len:
            probe.setPosition(end)
            probe.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)
            if probe.charFormat().anchorHref() != href:
                break
            end += 1

        return start, end

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

    def _clear_empty_list_formatting(self):
        """Called after Delete/Backspace leaves the note completely empty.
        Strips any list membership and indent the surviving empty block
        kept from before the deletion, so an emptied note is truly blank
        rather than showing a stray bullet/number."""
        cursor = self.body.textCursor()
        cursor.movePosition(QTextCursor.Start)
        current_list = cursor.currentList()
        if current_list is not None:
            current_list.remove(cursor.block())
        block_fmt = cursor.blockFormat()
        if block_fmt.indent() != 0:
            block_fmt.setIndent(0)
            cursor.mergeBlockFormat(block_fmt)

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

    # -- lock --------------------------------------------------------------

    def set_locked(self, checked: bool, persist: bool = True):
        self.note.locked = checked
        self.body.setReadOnly(checked)
        # QTextEdit.setReadOnly() only blocks its own default keystroke
        # handling, not these persistent QActions' global Ctrl+B/I/U/K
        # shortcuts (wired directly to this window in _setup_actions) —
        # without disabling them too, a locked note could still be
        # formatted from the keyboard even with populate_text_menu's own
        # menu skipped below.
        for action in (
            self.bold_action,
            self.italic_action,
            self.underline_action,
            self.strikethrough_action,
        ):
            action.setEnabled(not checked)
        self.header.lock_btn.setIcon(lock_icon(checked))
        self.header.lock_btn.setToolTip("Unlock note" if checked else "Lock note")
        if persist:
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

    # -- Notepad attach/detach -----------------------------------------

    def attach_to_board(self, board, pos=None):
        """Reparent this note into (or out of) a Notepad canvas.

        `board` is a NotepadWindow, or None to pop back to the desktop.
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

    def _selection_is_image(self) -> bool:
        cursor = self.body.textCursor()
        return cursor.hasSelection() and cursor.charFormat().isImageFormat()

    def populate_text_menu(self, menu: QMenu):
        """Text-formatting actions (font style/color, bullets & numbering,
        indent). Used only by NoteBody's contextMenuEvent (right-click in
        the text, appended after the standard Undo/Cut/Copy/Paste menu) —
        these act on the current selection, so whole-note actions like
        color/transparency/always-on-top/Notepad/delete don't belong
        here (see populate_note_actions_menu).

        Font/Bullets/Indent are skipped entirely when the selection is
        exactly one image (e.g. right-clicking a picture, which
        _select_image_under_click turns into a one-character image
        selection) — none of them do anything meaningful there. The
        picture-insert action and Hyperlink… stay either way: inserting a
        picture while one is already selected replaces it (a QTextCursor
        insert always replaces its current selection first), so it's
        relabeled "Replace picture…" there rather than implying it stacks
        on top; wrapping the image itself in a link is still sensible too.

        A locked note skips straight to just Find… — every other action
        here edits content in some way, which is exactly what locking is
        meant to prevent."""
        if self.note.locked:
            menu.addAction(self.find_action)
            return

        is_image_selection = self._selection_is_image()

        if not is_image_selection:
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

        image_action = menu.addAction("Replace picture…" if is_image_selection else "Add picture…")
        image_action.triggered.connect(self.show_insert_image_dialog)

        # Same "no selection, caret inside an existing link" check as
        # show_hyperlink_dialog() itself — without this, the menu always
        # read "Hyperlink…" even when right-clicking inside an existing
        # link was actually going to edit it in place, giving no hint
        # that the resulting dialog wouldn't just be inserting a new one.
        cursor = self.body.textCursor()
        is_editing_link = not cursor.hasSelection() and cursor.charFormat().isAnchor()
        hyperlink_action = menu.addAction("Edit Hyperlink…" if is_editing_link else "Hyperlink…")
        hyperlink_action.triggered.connect(self.show_hyperlink_dialog)

        if not is_image_selection:
            bullets_menu = menu.addMenu("Bullets && Numbering")
            current_style = self._current_list_style()
            for style, action in self.list_style_actions:
                action.setChecked(style == current_style)
                bullets_menu.addAction(action)

            menu.addAction(self.increase_indent_action)
            menu.addAction(self.decrease_indent_action)

        menu.addAction(self.find_action)

    def populate_note_actions_menu(self, menu: QMenu):
        """Whole-note actions (color, transparency, always-on-top,
        Notepad membership, delete). Used by the header's right-click
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

        lock_action = menu.addAction("Lock Note")
        lock_action.setCheckable(True)
        lock_action.setChecked(self.note.locked)
        lock_action.toggled.connect(self.set_locked)

        menu.addSeparator()
        if self.note.board_id is None:
            board_menu = menu.addMenu("Add to Notepad")
            boards = list(self.manager.boards.values())
            for board_window in boards:
                action = board_menu.addAction(board_window.board.name)
                action.triggered.connect(
                    lambda checked=False, b=board_window: self.manager.attach_note_to_board(self, b)
                )
            if boards:
                board_menu.addSeparator()
            new_board_action = board_menu.addAction("New Notepad…")
            new_board_action.triggered.connect(
                lambda: self.manager.create_board_and_attach(self)
            )
        else:
            remove_action = menu.addAction("Remove from Notepad")
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
