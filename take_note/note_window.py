from __future__ import annotations

import base64
import re
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
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QInputDialog,
    QLabel,
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

from . import spellcheck
from .list_markers import paint_list_markers
from .models import FONT_SWATCHES, SWATCHES, TRANSPARENCY_LEVELS, Note
from .widgets import build_color_swatch_grid
from .window_watch import WindowWatcher, is_window_iconic, list_windows
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

# Backlog item 22: plain-text URLs auto-detected as links at right-click
# time only (not live as-you-type, matching this app's existing "check at
# the point of interaction" style — e.g. the Edit Hyperlink…/Hyperlink…
# label check). Requires an explicit http(s):// scheme rather than also
# matching bare "www.example.com" text, to keep false positives (e.g.
# "e.g." or a stray "file.txt") out. Trailing sentence punctuation
# (".", ",", ")", etc. immediately after a URL in prose) is stripped from
# the match so "See https://example.com." doesn't linkify the period too.
_URL_PATTERN = re.compile(r"https?://\S+")
_URL_TRAILING_PUNCTUATION = ".,;:!?)]}\"'"


def _detect_url_span(text: str, offset: int) -> tuple[int, int, str] | None:
    """The [start, end) span and URL text of a plain-text URL in `text`
    that contains character position `offset`, or None. A pure function
    (no Qt dependency) so it's directly unit-testable against plain
    strings rather than needing a real QTextDocument."""
    for match in _URL_PATTERN.finditer(text):
        start, end = match.span()
        url = match.group().rstrip(_URL_TRAILING_PUNCTUATION)
        end = start + len(url)
        if start <= offset < end:
            return start, end, url
    return None

# How much darker the header strip is than the note's own color.
# Needs to be dark enough that white icon glyphs (ICON_BUTTON_QSS below)
# have real contrast against it, not just a slightly-shaded version of a
# pastel color that's still too light for white-on-it to read clearly.
HEADER_DARKEN = 230


def header_shade(color_hex: str) -> str:
    return QColor(color_hex).darker(HEADER_DARKEN).name()


# How much of the note's own color shows through the find bar's
# background, blended toward white — mocked up at 55%/35% against yellow/
# blue/pink and picked by the user; a flat use of note.color (100%) would
# be too saturated for FIND_BAR_QSS's fixed dark text/icon colors to stay
# comfortably legible against every SWATCHES entry.
FIND_BAR_TINT_RATIO = 0.55


def find_bar_tint(color_hex: str, ratio: float = FIND_BAR_TINT_RATIO) -> str:
    color = QColor(color_hex)
    white = QColor(255, 255, 255)
    r = int(color.red() * ratio + white.red() * (1 - ratio))
    g = int(color.green() * ratio + white.green() * (1 - ratio))
    b = int(color.blue() * ratio + white.blue() * (1 - ratio))
    return QColor(r, g, b).name()


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


# The note/font color-picker popup only — deliberately not folded into
# MENU_QSS_DARK/_LIGHT above, since rounded corners + a heavier border are
# scoped to this one popup (per user feedback), not the app's other menus
# (context menus, hamburger, tray). Mocked up as real rendered images
# (rounded corners, several border/shadow treatments) before writing this;
# user picked rounded corners + a thicker, lighter border with no shadow.
COLOR_POPUP_QSS_DARK = """
QMenu { background-color: #3a3a3a; color: white; border: 2px solid #9a9a9a; border-radius: 12px; padding: 4px; }
"""

COLOR_POPUP_QSS_LIGHT = """
QMenu { background-color: #fafafa; color: #202020; border: 2px solid #a8a8a8; border-radius: 12px; padding: 4px; }
"""


def get_color_popup_qss() -> str:
    scheme = QGuiApplication.styleHints().colorScheme()
    if scheme == Qt.ColorScheme.Light:
        return COLOR_POPUP_QSS_LIGHT
    return COLOR_POPUP_QSS_DARK


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

        self.new_btn = QToolButton()
        self.new_btn.setText("+")
        self.new_btn.setAutoRaise(True)
        self.new_btn.setToolTip("New note")
        # A note attached to a board should spawn its new sibling on that
        # same board, not back out on the desktop — reported live:
        # clicking + on a board note created a plain standalone note
        # instead. boards.get(None) is None for an unattached note, so
        # this naturally covers both cases without an explicit branch.
        self.new_btn.clicked.connect(
            lambda: note_window.manager.create_note(
                board=note_window.manager.boards.get(note_window.note.board_id)
            )
        )
        layout.addWidget(self.new_btn)

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

    def paintEvent(self, event):
        # Qt6's native list-marker painting renders a checkbox-outline
        # glyph instead of the real bullet/number for every block after
        # the first in a multi-block selection — a confirmed Qt paint-
        # engine bug, not something this app's own formatting causes (the
        # underlying QTextListFormat data stays correct throughout). Cover
        # each list block's marker gutter and hand-draw the marker
        # ourselves instead of trusting Qt's native rendering there.
        super().paintEvent(event)
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing)
        paint_list_markers(self, painter)
        painter.end()

    def contextMenuEvent(self, event):
        # Only text-formatting actions here — whole-note actions (color,
        # transparency, always-on-top, Notepad, delete) don't make sense
        # to offer while the user is mid-selection in the text, and live in
        # the header's right-click menu / hamburger menu instead.
        self._position_cursor_for_click(event.pos())
        self.note_window._auto_linkify_at_cursor()
        menu = self.createStandardContextMenu()
        menu.setStyleSheet(get_menu_qss())
        menu.addSeparator()
        self.note_window.populate_text_menu(menu)
        menu.exec(event.globalPos())

    def _position_cursor_for_click(self, pos):
        """Right-clicking otherwise leaves any existing cursor/selection
        completely untouched (Qt's default behavior for a right-click,
        unlike a plain left-click), so the context menu that follows acts
        on wherever the caret last happened to be rather than where the
        user just clicked. Most visibly with images — Cut/Copy/Delete in
        the standard context menu stayed disabled even though the picture
        under the click was exactly what the user meant to act on — but
        the same staleness hit plain text too: right-clicking directly on
        a hyperlink still read "Hyperlink…" instead of "Edit Hyperlink…"
        and didn't prefill its URL, since that check reads
        self.textCursor() same as everything else in populate_text_menu.
        Thin pixel-to-position adapter — the actual decision logic lives
        in _select_image_at so it can be unit tested against known
        document positions instead of synthetic mouse coordinates."""
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
            return

        # No image at the click point either direction: land a plain,
        # collapsed caret there so hyperlink/format checks that follow
        # (Edit Hyperlink's URL prefill, Bullets & Numbering's checked
        # style, ...) read the click position instead of stale state.
        plain = QTextCursor(doc)
        plain.setPosition(position)
        self.setTextCursor(plain)

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
    without losing focus on the text underneath. Background is a tint of
    the note's own color (see find_bar_tint) rather than an exact match —
    FIND_BAR_QSS's fixed dark text/icon colors need to stay legible
    against every note color, which a full-strength match wouldn't
    guarantee the way header_shade's darkening does for the header."""

    def __init__(self, note_window: "NoteWindow"):
        super().__init__()
        self.note_window = note_window
        self.setObjectName("findbar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.apply_color(note_window.note.color)
        self.hide()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)

        self.field = _FindLineEdit()
        self.field.setPlaceholderText("Find…")
        self.field.setClearButtonEnabled(True)
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

    def apply_color(self, color_hex: str):
        # Bare (selector-less) declarations don't mix reliably with the
        # class-selector rules in FIND_BAR_QSS in the same stylesheet
        # string — matches every other multi-rule stylesheet in this file
        # (e.g. the header's "#header { ... }" + ICON_BUTTON_QSS) by
        # scoping the bar's own background to its object name instead.
        self.setStyleSheet(
            f"#findbar {{ background-color: {find_bar_tint(color_hex)}; "
            f"border-bottom: 1px solid {header_shade(color_hex)}; }}"
            + FIND_BAR_QSS
        )

    def open_bar(self):
        self.show()
        self.field.selectAll()
        self.field.setFocus()
        if self.field.text():
            self._find_from_start()
        # F3/Shift+F3 only fire while the find bar is actually open —
        # matches how other in-note shortcuts are scoped (e.g. find_action
        # itself is disabled for an empty note rather than firing into a
        # no-op) — kept enabled/disabled here rather than always-on so the
        # keys are free for whatever else while the bar is closed.
        self.note_window.find_next_action.setEnabled(True)
        self.note_window.find_previous_action.setEnabled(True)

    def close_bar(self):
        self.hide()
        self.note_window.body.setFocus()
        self.note_window.find_next_action.setEnabled(False)
        self.note_window.find_previous_action.setEnabled(False)

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


class NoteTitleBar(QWidget):
    """Shown only when the note has a title set, between the header and the
    find bar — collapses away entirely for an untitled note (the common
    case), so existing notes' layout looks exactly as it did before this
    existed. Unlike the find bar's fixed neutral background, this uses the
    note's own color: a title is part of the note's own content, not a
    transient tool overlaid on top of it."""

    def __init__(self, note_window: "NoteWindow"):
        super().__init__()
        self.note_window = note_window
        self.setObjectName("titlebar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.hide()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 3)

        self.label = QLabel()
        layout.addWidget(self.label)

    def set_title(self, title: str):
        if title:
            self.label.setText(title)
            # Match the body's current font (family + size) rather than
            # the ambient default the label started with, so the title
            # reads as the same "voice" as the note itself — still bold,
            # since it's a heading, just not a mismatched typeface. If a
            # user picks an ugly body font, the title inherits that too;
            # that's their own choice via the Font… dialog, not a bug.
            body_font = self.note_window.body.currentFont()
            font = self.label.font()
            font.setFamily(body_font.family())
            font.setPointSize(body_font.pointSize())
            font.setBold(True)
            self.label.setFont(font)
            self.show()
        else:
            self.hide()

    def apply_color(self, color_hex: str):
        # Explicit black text: left unset, the label falls back to the
        # ambient QPalette::WindowText role rather than QTextEdit's own
        # QPalette::Text — on this system that resolves to a light color
        # meant for a dark theme, reading as barely-visible pale text
        # against every (light, pastel) note color.
        #
        # Explicit background-color: transparent on the label itself:
        # without it, a note attached to a board painted this whole strip
        # in the *board's* own background color instead of the note's —
        # reported live via a screenshot. Root cause confirmed directly:
        # the label's own resolved backgroundRole() picked up the board
        # canvas's color (a genuine QObject ancestor once attached), and
        # Qt's style-sheet engine paints a QLabel's implicit background
        # from that resolved palette once styled-painting is active
        # anywhere in the ancestor chain — even though nothing here ever
        # asked for autoFillBackground. #titlebar's own background-color
        # rule alone doesn't prevent that, since it's the *label's* own
        # implicit fill sitting on top of it, not a failure to paint
        # #titlebar itself (confirmed: #titlebar's own backgroundRole()
        # read back correctly the whole time). Only reproducible for a
        # note actually attached to a board — a standalone note has no
        # such ancestor to inherit from.
        self.setStyleSheet(
            f"#titlebar {{ background-color: {color_hex}; "
            f"border-bottom: 1px solid {header_shade(color_hex)}; }}"
            "QLabel { color: black; background-color: transparent; }"
        )


class NoteWindow(QWidget):
    changed = Signal()

    def __init__(self, note: Note, manager, parent_board=None):
        super().__init__(parent_board.canvas if parent_board is not None else None)
        # Guards moveEvent/resizeEvent below: the resize()/move()/show()
        # calls later in this constructor (restoring a loaded note's saved
        # geometry, or the window manager finalizing placement) fire real
        # Qt move/resize events even though nothing the user did actually
        # changed — confirmed live via a real subprocess launch+quit with
        # zero interaction: every note's modified_at bumped anyway, and
        # NoteManager's on-quit save then persisted that bump to disk.
        self._initializing = True
        self.note = note
        self.manager = manager
        # Not persisted (see set_stuck_to_window's docstring) — always
        # unset at construction, whether this is a brand-new note or one
        # freshly loaded from disk.
        self._stuck_window_id: int | None = None
        self._window_watcher = None

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
        # Not `if not note.html:` — QTextEdit.toHtml() on a genuinely
        # empty document returns Qt's ~600-char boilerplate wrapper, not
        # an empty string. A note saved once while still empty (e.g.
        # rolled up and quit before ever being typed into) would persist
        # that boilerplate as note.html, making this check false on the
        # next launch and silently skipping the default-format
        # application — text then typed into it picked up whatever Qt's
        # own unset/ambient format resolves to instead of the configured
        # default, reading as faded/grey rather than black. Checking the
        # actual visible content instead of the raw HTML string is
        # immune to Qt's own serialization boilerplate.
        if not self.body.toPlainText():
            self._apply_default_new_note_format()

        self.spell_highlighter: spellcheck.SpellHighlighter | None = None
        if self.manager.settings.spell_check_enabled and spellcheck.is_available():
            self._attach_spell_highlighter()

        # Connected only after the initial load/default-format handling
        # above rather than in _build_ui — connecting earlier fires this
        # during setHtml() itself, double-applying the default format
        # (harmless, but breaks tests asserting a single call) before the
        # explicit empty-note check even runs.
        self.body.textChanged.connect(self._fix_ambient_char_format)
        self.set_locked(note.locked, persist=False)
        self.title_bar.set_title(note.title)
        self._apply_opacity()
        self.show()
        if parent_board is None:
            set_skip_taskbar(int(self.winId()), True)
        if note.rolled_up:
            self._set_rolled(True, persist=False)
        else:
            self.header.roll_btn.setText("▲")
        # Real user-initiated moves/resizes from here on should still mark
        # the note changed — only the construction-time ones above (and
        # whatever the window manager does while show() is finalizing
        # placement) are exempt.
        self._initializing = False

    # -- UI construction -------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = NoteHeader(self)
        layout.addWidget(self.header)

        self.title_bar = NoteTitleBar(self)
        layout.addWidget(self.title_bar)

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
        self.size_grip = QSizeGrip(self.footer)
        bottom_row.addWidget(self.size_grip)
        layout.addWidget(self.footer)
        # QSizeGrip resizes self.window() — the nearest *top-level*
        # ancestor. Once attached to a board, that's the board, not this
        # note (confirmed live: dragging it would resize the whole
        # board). Also left a visible rendering artifact in that state — a
        # small rectangular notch cut into the note's rounded corner,
        # since a plain child widget doesn't get the whole-window alpha
        # clipping a real top-level translucent window gets from the
        # compositor, so the grip's native square icon could poke past
        # the painted rounded-corner curve instead of being invisibly
        # clipped away. Hidden whenever attached; see attach_to_board().
        if self.note.board_id is not None:
            self.size_grip.hide()

    def _apply_default_new_note_format(self):
        """Only called for a genuinely empty note (see __init__) — a note
        loaded from disk with real content keeps whatever formatting it
        already has; this just fixes what the very first character typed
        into a brand-new note picks up. Reads the current Settings rather
        than a fixed constant, so a user-configured default (Settings
        dialog) takes effect for notes created after the change."""
        settings = self.manager.settings
        fmt = QTextCharFormat()
        fmt.setFontPointSize(settings.default_font_size)
        fmt.setForeground(QColor(settings.default_font_color))
        self.body.mergeCurrentCharFormat(fmt)

    def _attach_spell_highlighter(self):
        """Constructing QSyntaxHighlighter on a document that already has
        content (a note loaded from disk) schedules an initial highlight
        pass on the *next event-loop iteration*, not synchronously —
        confirmed directly. That deferred pass fires textChanged once,
        which this window's own textChanged -> mark_changed() connection
        (below, in _build_ui) would otherwise turn into a spurious
        "modified" note and a scheduled disk save on every single launch
        with spell-check on. Reordering source lines can't dodge this
        either way — mark_changed is wired inside _build_ui(), which runs
        before setHtml() ever loads real content to check, so there's no
        point after real content exists that's also before that connect.
        Forcing the pass synchronously via rehighlight() while the
        document's signals are blocked sidesteps both problems: the
        forced pass consumes the queued one (confirmed it doesn't double-
        fire once unblocked), and blockSignals() suppresses the one-time
        emission that pass would otherwise cause, without affecting the
        highlighter's own formatting work (the squiggle is still applied
        correctly despite the block, confirmed via a real test).

        Idempotent (no-op if already attached) since NoteManager can call
        this from _apply_settings() on every Apply click, and re-checks
        availability defensively even though callers already gate on it,
        in case the optional dependency vanished mid-session."""
        if self.spell_highlighter is not None or not spellcheck.is_available():
            return
        document = self.body.document()
        document.blockSignals(True)
        self.spell_highlighter = spellcheck.SpellHighlighter(document)
        self.spell_highlighter.rehighlight()
        document.blockSignals(False)

    def _detach_spell_highlighter(self):
        if self.spell_highlighter is None:
            return
        self.spell_highlighter.setDocument(None)
        self.spell_highlighter = None

    def _fix_ambient_char_format(self):
        """Qt's own current-char-format tracking (what newly typed text
        inherits) can end up pointing at its own unset/no-brush ambient
        format instead of picking up real formatting from nearby text —
        confirmed live in two distinct situations: deleting content back
        down to the very start of the document (backspacing an inline
        picture that had nothing before it, or clearing all text), and
        typing through 2+ consecutive Enters partway through a note (the
        empty paragraph in between is enough to desync Qt's ambient
        format from the real formatting already present, even though the
        character immediately before the cursor — confirmed directly —
        still carries the correct one). Both read as the next typed
        character coming out faded/grey instead of the note's actual
        color.

        Originally this only fired at cursor position 0, which covered
        the first case but not the second (a mid-document position).
        Generalized: whenever the ambient format is no-brush, inherit
        from the character immediately before the cursor if one exists
        and is itself real (so a note with custom-colored text keeps
        that color, rather than a formatting glitch elsewhere in the
        note silently resetting it to the app's global default color);
        only fall back to the configured default format when there's
        truly nothing before the cursor to inherit from — a brand-new
        empty note, or genuinely at position 0."""
        cursor = self.body.textCursor()
        if cursor.hasSelection():
            return
        if self.body.currentCharFormat().foreground().style() != Qt.NoBrush:
            return
        if cursor.position() > 0:
            probe = QTextCursor(self.body.document())
            probe.setPosition(cursor.position())
            probe.movePosition(QTextCursor.PreviousCharacter, QTextCursor.KeepAnchor)
            prev_format = probe.charFormat()
            if prev_format.foreground().style() != Qt.NoBrush:
                self.body.mergeCurrentCharFormat(prev_format)
                return
        self._apply_default_new_note_format()

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
        # Checkable so the Font Style submenu can show which styles the
        # current selection already has (same pattern as Bullets &
        # Numbering's list_style_actions below) — actual formatting is
        # still driven entirely by _toggle_bold()/etc. reading the real
        # cursor state, not by this checked flag, so any drift from Qt's
        # own auto-toggle-on-trigger behavior self-corrects the next time
        # populate_text_menu() recomputes it from the cursor on open.
        for action in (self.bold_action, self.italic_action, self.underline_action, self.strikethrough_action):
            action.setCheckable(True)

        self.find_action = make_action("Find…", "Ctrl+F", self.toggle_find_bar)
        # Disabled until there's something to search — matches its initial
        # state here (the body is still empty at this point in __init__;
        # _build_ui's textChanged connection keeps it in sync afterward).
        self.find_action.setEnabled(bool(self.body.toPlainText()))

        # F3/Shift+F3 jump to the next/previous match — self.find_bar
        # doesn't exist yet at this point in __init__ (built later in
        # _build_ui), but that's fine since these are only evaluated when
        # actually triggered. Start disabled; NoteFindBar.open_bar()/
        # close_bar() enable/disable them so the shortcut only fires while
        # the bar is actually open (see those methods' own comments).
        self.find_next_action = make_action("Find Next", "F3", lambda: self.find_bar.find_next())
        self.find_next_action.setEnabled(False)
        self.find_previous_action = make_action(
            "Find Previous", "Shift+F3", lambda: self.find_bar.find_previous()
        )
        self.find_previous_action.setEnabled(False)

        # Label is set dynamically each time the Hamburger menu opens (see
        # populate_note_actions_menu) — "Add Title…" vs "Edit Title…",
        # matching Hyperlink…/Edit Hyperlink…'s pattern in populate_text_menu.
        # Was Ctrl+F2, but that collides with KWin's default global "Switch
        # to Desktop 2" shortcut (~/.config/kglobalshortcutsrc) on at least
        # one user's KDE setup — a compositor-level grab that eats the key
        # before X11 ever delivers it to this window, so the action never
        # fired no matter how correctly it was wired here. Shift+F2 is
        # free in both this app's own shortcuts and KWin's global defaults.
        self.title_action = make_action("Add Title…", "Shift+F2", self.show_title_dialog)

        # Checkable + exclusive (same pattern as list_style_group below)
        # so the submenu shows which alignment the current paragraph
        # already has — same gap Bold/Italic/Underline/Strikethrough had
        # before getting this same treatment.
        self.align_group = QActionGroup(self)
        self.align_group.setExclusive(True)
        self.align_left_action = QAction("Left", self)
        self.align_left_action.setCheckable(True)
        self.align_left_action.triggered.connect(lambda: self._set_alignment(Qt.AlignLeft))
        self.align_group.addAction(self.align_left_action)
        self.align_center_action = QAction("Center", self)
        self.align_center_action.setCheckable(True)
        self.align_center_action.triggered.connect(lambda: self._set_alignment(Qt.AlignCenter))
        self.align_group.addAction(self.align_center_action)
        self.align_right_action = QAction("Right", self)
        self.align_right_action.setCheckable(True)
        self.align_right_action.triggered.connect(lambda: self._set_alignment(Qt.AlignRight))
        self.align_group.addAction(self.align_right_action)

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
        # A bare QFontDialog() instance (not the getFont(initial, self)
        # convenience) for the same reason every other dialog here avoids
        # self as parent — see _new_note_dialog's docstring for the full
        # palette-bleed explanation. Confirmed this one's susceptible too:
        # a board-attached note's QFontDialog(self) read back the board's
        # own grey background instead of the theme's normal dark one.
        dialog = QFontDialog()
        dialog.setCurrentFont(self.body.currentFont())
        self._center_dialog_over_note(dialog)
        if dialog.exec() != QFontDialog.Accepted:
            return
        self.body.setCurrentFont(dialog.currentFont())
        self.mark_changed()

    def _new_note_dialog(self, title: str, label: str, initial: str) -> QInputDialog:
        """Deliberately parentless — QInputDialog(self) would inherit this
        note's resolved palette when the note is attached to a Notepad
        board: the board canvas has an inline `background-color: ...`
        stylesheet (see NotepadWindow._apply_color), which cascades
        through the real widget tree into the note (a genuine descendant)
        and then into a dialog built with the note as its parent too,
        even though that dialog is a separate top-level window — Qt
        copies a widget's initial palette from whatever parent argument
        it's constructed with. Result, reported live via a screenshot:
        the dialog silently painted with the *board's* own light grey
        background instead of the app's normal dark theme, with the
        still-normal dark-theme text now nearly illegible on top of it.
        Only ever reproducible for a note actually attached to a board —
        a standalone note has no such ancestor to inherit from, which is
        exactly why this wasn't caught by the earlier width fix (tested
        against a standalone note only). Confirmed directly: a
        board-parented QInputDialog's backgroundRole() color read back
        the board's own #e0e0e0 instead of the theme's normal dark navy,
        and explicitly resetting the palette afterward (even after
        show()) didn't reliably stick before the first paint. Passing no
        parent sidesteps the inheritance entirely — same fix already used
        for the hyperlink hover tooltip's own palette bleed — so callers
        explicitly re-center the dialog over the note via
        _center_dialog_over_note() instead, to keep it landing on the
        right monitor rather than relying on implicit parent placement."""
        dialog = QInputDialog()
        dialog.setWindowTitle(title)
        dialog.setLabelText(label)
        dialog.setTextValue(initial)
        dialog.findChild(QLineEdit).setClearButtonEnabled(True)
        return dialog

    def _center_dialog_over_note(self, dialog: QInputDialog):
        center = self.mapToGlobal(self.rect().center())
        dialog.move(center - dialog.rect().center())

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
        dialog = self._new_note_dialog(
            "Edit Hyperlink" if existing_href else "Insert Hyperlink", "URL:", existing_href or "https://"
        )
        dialog.resize(420, dialog.sizeHint().height())
        self._center_dialog_over_note(dialog)
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

    def remove_hyperlink(self):
        """Strips the anchor entirely rather than just editing its URL —
        clearing the URL field in the Hyperlink dialog only ever cancelled
        (no way to actually remove a link once inserted, confirmed there
        was no such action anywhere in this menu)."""
        cursor = self.body.textCursor()
        href = cursor.charFormat().anchorHref() if cursor.charFormat().isAnchor() else ""
        if not href:
            return

        if not cursor.hasSelection():
            # Same caret-convenience as show_hyperlink_dialog(): expand to
            # the link's whole contiguous span rather than requiring the
            # user to select it exactly first.
            start, end = self._anchor_span(cursor.position(), href)
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)

        fmt = QTextCharFormat()
        fmt.setAnchor(False)
        fmt.setAnchorHref("")
        # Resets to this app's own configured default text color/no
        # underline rather than trying to recover whatever formatting
        # existed before the link was created — nothing tracks that.
        # Known tradeoff: if this text was also deliberately colored/
        # underlined by the user themselves (independent of being a
        # link), that styling is lost too — there's no way to tell the
        # two apart without tracking pre-link formatting, which this app
        # doesn't do anywhere today.
        fmt.setForeground(QColor(self.manager.settings.default_font_color))
        fmt.setFontUnderline(False)
        cursor.mergeCharFormat(fmt)
        self.mark_changed()

    def _auto_linkify_at_cursor(self):
        """Backlog item 22: a URL typed directly as plain text (never run
        through the Hyperlink… dialog) previously stayed plain-looking
        forever — right-clicking it showed "Hyperlink…", not "Edit
        Hyperlink…", and offered no way to make it a real link short of
        selecting it manually and opening the dialog. Called from
        NoteBody.contextMenuEvent right after the cursor is repositioned
        to the click point, so if that position is inside a detected URL,
        it becomes a real link immediately (same anchor/color/underline
        formatting show_hyperlink_dialog() applies) before the context
        menu is even built — by the time populate_text_menu() reads
        cursor.charFormat().isAnchor(), it's already true, so "Edit
        Hyperlink…"/"Remove Hyperlink" show up correctly with no further
        plumbing needed there."""
        cursor = self.body.textCursor()
        if cursor.hasSelection() or cursor.charFormat().isAnchor():
            return
        block = cursor.block()
        span = _detect_url_span(block.text(), cursor.positionInBlock())
        if span is None:
            return
        start, end, url = span

        link_cursor = QTextCursor(block)
        link_cursor.setPosition(block.position() + start)
        link_cursor.setPosition(block.position() + end, QTextCursor.KeepAnchor)
        fmt = QTextCharFormat()
        fmt.setAnchor(True)
        fmt.setAnchorHref(url)
        fmt.setForeground(QColor(HYPERLINK_COLOR))
        fmt.setFontUnderline(True)
        link_cursor.mergeCharFormat(fmt)
        self.mark_changed()

    def show_title_dialog(self):
        # The static QInputDialog.getText() convenience defaults to a
        # width too narrow to even read its own title bar comfortably —
        # same fix as show_hyperlink_dialog() below and NotepadWindow.
        # rename() in board_window.py: build the dialog directly so it
        # can be sized explicitly.
        dialog = self._new_note_dialog("Note Title", "Title:", self.note.title)
        # 320px still truncated the title bar itself on an unscaled
        # (100%) monitor even though it read fine on a 125%-scaled one —
        # see the identical fix/comment on NotepadWindow.rename() in
        # board_window.py.
        dialog.resize(480, dialog.sizeHint().height())
        self._center_dialog_over_note(dialog)
        if dialog.exec() != QInputDialog.Accepted:
            return
        # Unlike NotepadWindow.rename() (where an empty name just leaves
        # the previous one in place, since a board always has *some* name),
        # a note's title is optional — clearing the field and confirming
        # removes it entirely, collapsing the title bar back away.
        self.note.title = dialog.textValue().strip()
        self.title_bar.set_title(self.note.title)
        self.mark_changed()

    def show_insert_image_dialog(self):
        # No parent (see _new_note_dialog's docstring) — the OS's native
        # file picker isn't affected by this note's own palette bleed,
        # but Qt's own non-native fallback would be, same as every other
        # dialog fixed here.
        path, _ = QFileDialog.getOpenFileName(
            None, "Add Picture", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp)"
        )
        if not path:
            return

        image = QImage(path)
        if image.isNull():
            QMessageBox.warning(None, "Add Picture", "Could not load that image file.")
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

        if style is None:
            block = doc.findBlock(start)
            while block.isValid() and block.position() < end:
                self._apply_list_style_to_block(block, style)
                block = block.next()
            self.mark_changed()
            return

        # Applying a real style: blocks that don't already belong to a
        # list must become ONE shared list per contiguous run, not one
        # independent single-item list per block. createList() called
        # separately for each block (the old per-block loop, still used
        # above for removal) created N separate lists that each started
        # counting from 1 — reported live as every item in a numbered
        # list showing "1." instead of incrementing 1, 2, 3... Blocks
        # that already belong to a list just get that list's own style
        # updated in place, same as before.
        block = doc.findBlock(start)
        run_start = None
        run_end = None
        while block.isValid() and block.position() < end:
            if block.textList() is not None:
                if run_start is not None:
                    self._create_shared_list(run_start, run_end, style)
                    run_start = None
                fmt = block.textList().format()
                fmt.setStyle(style)
                block.textList().setFormat(fmt)
            else:
                if run_start is None:
                    run_start = block
                run_end = block
            block = block.next()
        if run_start is not None:
            self._create_shared_list(run_start, run_end, style)
        self.mark_changed()

    def _create_shared_list(self, start_block, end_block, style: QTextListFormat.Style):
        run_cursor = QTextCursor(start_block)
        end_pos = end_block.position() + end_block.length() - 1
        end_pos = min(end_pos, self.body.document().characterCount() - 1)
        run_cursor.setPosition(end_pos, QTextCursor.KeepAnchor)
        run_cursor.createList(QTextListFormat.Style(style))

    def _apply_list_style_to_block(self, block, style: QTextListFormat.Style | None):
        current_list = block.textList()
        if style is None:
            if current_list is not None:
                # QTextList.remove() drops the block's list membership
                # but leaves its own blockFormat().indent() at whatever
                # the list's nesting indent used to be — Qt preserves the
                # visual position by transferring that weight onto the
                # block itself instead of snapping back to the margin.
                # Reported live via a screenshot: selecting a multi-level
                # nested list and choosing "None" removed every bullet,
                # but each line stayed staggered at its old nesting
                # depth as plain paragraph indent, looking like the
                # reset silently half-failed. Nesting depth belongs to
                # the list alone once one exists (see _list_indent_step);
                # once the list is gone there's nothing left to justify
                # a nonzero block indent either.
                current_list.remove(block)
                cursor = QTextCursor(block)
                block_fmt = cursor.blockFormat()
                block_fmt.setIndent(0)
                cursor.mergeBlockFormat(block_fmt)
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
        if not cursor.hasSelection():
            self._indent_step_for_block(cursor.block(), delta)
            self.mark_changed()
            return

        # A multi-line selection can span several distinct nesting depths
        # (each depth is its own QTextList) — stepping it through the
        # single-block path below via the *selection cursor itself*
        # would run createList() (in the "no adjacent list to rejoin"
        # branch) while that cursor still has the whole selection
        # active, and createList() on a cursor with an active selection
        # folds *every* block the selection touches into one shared
        # list, discarding each line's own prior depth. Reported live:
        # selecting a 7-item, 4-level nested list and hitting Increase
        # Indent once collapsed the entire thing into one flat,
        # renumbered level instead of shifting each line one level
        # deeper relative to where it already was. Apply the exact same
        # step to each block individually instead, via a fresh collapsed
        # cursor per block, using that block's own current depth as the
        # starting point — matches ordinary word-processor behavior
        # (Tab on a multi-level selection shifts everything deeper by
        # one level, preserving relative structure) and naturally still
        # rejoins newly-adjacent siblings into one shared list via
        # _find_adjacent_list, same as the single-line case already did.
        doc = self.body.document()
        start = min(cursor.selectionStart(), cursor.selectionEnd())
        end = max(cursor.selectionStart(), cursor.selectionEnd())
        block = doc.findBlock(start)
        while block.isValid() and block.position() < end:
            self._indent_step_for_block(block, delta)
            block = block.next()
        self.mark_changed()

    def _indent_step_for_block(self, block, delta: int):
        cursor = QTextCursor(block)
        current_list = block.textList()
        if current_list is None:
            # Not in a list: a plain visual block indent (works for any
            # paragraph, not just list items).
            block_fmt = cursor.blockFormat()
            block_fmt.setIndent(max(0, block_fmt.indent() + delta))
            cursor.mergeBlockFormat(block_fmt)
            return

        style = current_list.format().style()
        new_indent = current_list.format().indent() + delta

        if new_indent < 1:
            current_list.remove(block)
            block_fmt = cursor.blockFormat()
            block_fmt.setIndent(0)
            cursor.mergeBlockFormat(block_fmt)
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
        # depth, and normally 0 for any list item — confirmed live: a
        # never-touched top-level item's blockFormat().indent() is 0,
        # with only its *list's* own indent() carrying the nesting
        # weight) doesn't get resynced when rejoining an existing list
        # via QTextList.add(), left stale from wherever the block was
        # before. Previously "fixed" by setting it to `new_indent - 1`,
        # which only coincidentally lands on 0 for the first nesting
        # level — for anything deeper it set a real, nonzero block
        # indent *in addition to* the list's own nesting indent, adding
        # a second, compounding indent on top of the correct one.
        # Reported live as a sub-bullet rendering much further right
        # than one extra nesting level should ever produce. Always 0:
        # list nesting alone should carry all of it.
        block_fmt = cursor.blockFormat()
        block_fmt.setIndent(0)
        cursor.mergeBlockFormat(block_fmt)

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
        """Only list items actually need this — mergeBlockCharFormat sets
        the format list *markers* are painted with, which the regular
        per-character merge in _merge_format() doesn't touch. For a plain
        (non-list) paragraph this call does nothing useful, and touching
        the *document's own last block* — not just "ending exactly at
        EndOfBlock" as originally diagnosed — corrupts that block's
        cached layout rect in Qt, collapsing it to zero size so it stops
        painting entirely. The block-length-including-separator fix below
        only ever prevented that for a block with a *real* following
        block to extend the range into; the document's last block has no
        such separator to extend into regardless, so the same corruption
        was still reachable there all along (confirmed live: a plain,
        listless single-line note recoloring its own only/last block, and
        separately a single-item/last-item list recoloring its own last
        block — backlog item 12, text visibly vanishing). Skipping
        non-list blocks entirely sidesteps the bug for the common case,
        but list blocks still need mergeBlockCharFormat for their marker
        color, corruption and all — markContentsDirty() right after each
        merge forces Qt to recompute that block's cached layout rect
        instead of trusting the stale (zero-size) one mergeBlockCharFormat
        itself leaves behind. Confirmed directly: without it, a
        last-block list item's blockBoundingRect().width() reads 0 right
        after the merge, regardless of whether the merge used a selection
        or a bare caret; with it, the same block reads its real width and
        renders normally, marker color and all."""
        selection_cursor = self.body.textCursor()
        doc = self.body.document()
        if not selection_cursor.hasSelection():
            block = selection_cursor.block()
            if block.textList() is not None:
                selection_cursor.mergeBlockCharFormat(fmt)
                doc.markContentsDirty(block.position(), block.length())
            return
        start = min(selection_cursor.selectionStart(), selection_cursor.selectionEnd())
        end = max(selection_cursor.selectionStart(), selection_cursor.selectionEnd())
        block = doc.findBlock(start)
        while block.isValid() and block.position() < end:
            if block.textList() is not None:
                block_cursor = QTextCursor(block)
                block_end = min(block.position() + block.length(), doc.characterCount() - 1)
                block_cursor.setPosition(block_end, QTextCursor.KeepAnchor)
                block_cursor.mergeBlockCharFormat(fmt)
                doc.markContentsDirty(block.position(), block.length())
            block = block.next()

    def show_font_color_menu(self, anchor_widget: QWidget):
        menu = QMenu(self)
        menu.setAttribute(Qt.WA_TranslucentBackground, True)
        menu.setStyleSheet(get_color_popup_qss())

        grid_container = build_color_swatch_grid(
            FONT_SWATCHES, self.body.textColor().name(), lambda c: self._pick_font_color(c, menu)
        )
        grid_container.setStyleSheet("background: transparent;")
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
        self.title_bar.apply_color(self.note.color)
        self.find_bar.apply_color(self.note.color)
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
        menu.setAttribute(Qt.WA_TranslucentBackground, True)
        menu.setStyleSheet(get_color_popup_qss())

        grid_container = build_color_swatch_grid(
            SWATCHES, self.note.color, lambda c: self._pick_color(c, menu)
        )
        grid_container.setStyleSheet("background: transparent;")
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

    # -- stick to window -----------------------------------------------------

    # Shown in both the picker and the "nothing found" dialog — most users
    # won't have read the README's "Known limitation: Wayland" section
    # explaining why a native Wayland app (e.g. a browser started with
    # --ozone-platform=wayland) never shows up here.
    _STICK_WINDOW_SCOPE_NOTE = (
        "(Only X11/XWayland windows appear here — native Wayland\n"
        "apps, like some browsers, won't show up.)"
    )

    def show_stick_window_dialog(self):
        windows = list_windows()
        if not windows:
            # No parent (see _new_note_dialog's docstring for why) — a
            # board-attached note's QMessageBox.information(self, ...)
            # inherited the board's own grey background the same way
            # every other dialog fixed here did.
            info = QMessageBox()
            info.setIcon(QMessageBox.Information)
            info.setWindowTitle("Stick to Window")
            info.setText(
                "No other windows were found to stick this note to.\n\n"
                + self._STICK_WINDOW_SCOPE_NOTE
            )
            self._center_dialog_over_note(info)
            info.exec()
            return

        # Window titles aren't guaranteed unique, and the label round trip
        # below only gives back the chosen string — appending each
        # window's id (already unique by definition) keeps that
        # unambiguous without needing a custom list widget just to carry
        # an id per row.
        labels = [f"{title} (0x{window_id:x})" for window_id, title in windows]
        # QInputDialog.getItem(self, ...) is the same static-convenience
        # class as getText() — same palette-bleed fix as
        # _new_note_dialog(), built as a combo-box instance instead.
        dialog = QInputDialog()
        dialog.setWindowTitle("Stick to Window")
        dialog.setLabelText("Window:\n" + self._STICK_WINDOW_SCOPE_NOTE)
        dialog.setComboBoxItems(labels)
        dialog.setComboBoxEditable(False)
        self._center_dialog_over_note(dialog)
        if dialog.exec() != QInputDialog.Accepted:
            return
        label = dialog.textValue()
        index = labels.index(label)
        window_id = windows[index][0]
        self.set_stuck_to_window(window_id)

    def set_stuck_to_window(self, window_id: int):
        """Not persisted in the Note model: an X11 window id is only valid
        for as long as that specific window instance exists, and isn't
        stable across the target app's own restarts, let alone ours — a
        stuck association is a live, in-session thing only."""
        self._clear_window_watcher()
        self._stuck_window_id = window_id

        self._window_watcher = WindowWatcher(window_id, self)
        self._window_watcher.minimized.connect(self.hide)
        self._window_watcher.restored.connect(self.show)
        self._window_watcher.closed.connect(self.unstick_from_window)
        self._window_watcher.start()

        # WindowWatcher's signals only fire on *future* state changes —
        # without this, sticking to a window that's already minimized
        # would leave the note visible until some unrelated later toggle.
        if is_window_iconic(window_id):
            self.hide()

        self.mark_changed()

    def unstick_from_window(self):
        self._clear_window_watcher()
        self._stuck_window_id = None
        self.show()
        self.mark_changed()

    def _clear_window_watcher(self):
        if self._window_watcher is not None:
            self._window_watcher.stop()
            self._window_watcher = None

    # -- transparency ------------------------------------------------------

    def set_opacity(self, value: float):
        self.note.opacity = value
        self._apply_opacity()
        self.mark_changed()

    def _apply_opacity(self):
        """setWindowOpacity() is silently a no-op for anything that isn't
        a real top-level window — confirmed directly: reading it back
        after calling it on a board-attached note stayed 1.0 regardless
        of what was just set, since attach_to_board() reparents the note
        to Qt.Widget (a plain child of the board's canvas) rather than
        leaving it a Qt.Window. Reported live as changing a board note's
        transparency doing visibly nothing. A QGraphicsOpacityEffect
        works on any widget, window or not, so it's used instead whenever
        this note isn't currently its own top-level window; switched back
        to the normal (compositor-accelerated, no offscreen-buffer
        overhead) setWindowOpacity() otherwise, since that's still the
        better mechanism for a standalone note and was already working
        fine for it."""
        if self.isWindow():
            if self.graphicsEffect() is not None:
                self.setGraphicsEffect(None)
            self.setWindowOpacity(self.note.opacity)
        else:
            effect = self.graphicsEffect()
            if not isinstance(effect, QGraphicsOpacityEffect):
                effect = QGraphicsOpacityEffect(self)
                self.setGraphicsEffect(effect)
            effect.setOpacity(self.note.opacity)

    # -- roll up / down ----------------------------------------------------

    def toggle_rolled(self):
        self._set_rolled(not self.note.rolled_up)

    def set_rolled(self, rolled: bool):
        """Public entry point for external callers (e.g. NoteManager's bulk
        tray actions) that need to force a specific state rather than
        toggle — skips the redundant work/mark_changed() when the note is
        already in the requested state."""
        if rolled != self.note.rolled_up:
            self._set_rolled(rolled)

    def _set_rolled(self, rolled: bool, persist: bool = True):
        self.note.rolled_up = rolled
        if rolled:
            self._expanded_height = self.height()
            self.body.hide()
            self.footer.hide()
            # Rolling up shrinks the whole window to just HEADER_HEIGHT —
            # title_bar/find_bar are two more strips between the header
            # and body that were never included in that math, so leaving
            # either visible crammed everything into a sliver instead of
            # actually hiding along with the body. Reported live via a
            # screenshot (a titled note collapsing into a garbled mess of
            # squashed text) and reproduced exactly. find_bar is a
            # transient tool, not persisted note content, so it's just
            # force-hidden here rather than reopened on unroll below —
            # closing it is the expected side effect of rolling up, same
            # as it doesn't reopen itself after any other reason it might
            # have been hidden.
            self.title_bar.hide()
            self.find_bar.close_bar()
            self.setMinimumHeight(HEADER_HEIGHT)
            self.resize(self.width(), HEADER_HEIGHT)
        else:
            self.body.show()
            self.footer.show()
            # Only re-shows for a note that actually has a title — same
            # rule set_title() itself already applies, so an untitled
            # note doesn't grow a blank title strip back on unroll.
            self.title_bar.set_title(self.note.title)
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
            # Must be set before move() below — moveEvent's canvas-fit
            # hook only acts when board_id is already set, and this is
            # the very first positioning onto the board.
            self.note.board_id = board.board.id
            if pos is not None:
                self.move(pos)
            self.show()
            # See _build_ui()'s size_grip comment: wrong resize target and
            # a rendering artifact once this note is no longer top-level.
            self.size_grip.hide()
            # No longer a real top-level window, so setWindowOpacity()
            # (already applied, possibly to something other than 1.0)
            # would silently stop doing anything from here on — switch to
            # the QGraphicsOpacityEffect path now rather than leaving a
            # transparency setting that visually reverts to opaque the
            # moment a note lands on a board. See _apply_opacity().
            self._apply_opacity()
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
            self.size_grip.show()
            # Back to being a real top-level window — switch back to
            # setWindowOpacity() (the graphics-effect path still works
            # here, but costs an extra offscreen-buffer composite on
            # every repaint for no benefit once the cheaper native
            # mechanism is available again).
            self._apply_opacity()
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
        # Guarded, not just moveEvent/resizeEvent: setHtml(note.html) in
        # __init__ (restoring a loaded note's saved content) also fires
        # textChanged, which is connected to this same method — confirmed
        # live via a real subprocess launch+quit with zero interaction,
        # every note's modified_at bumped anyway, purely from loading.
        # Nothing is connected to `changed` yet during construction either
        # (NoteManager wires that up only after the constructor returns),
        # so skipping the emit here loses nothing real.
        if self._initializing:
            return
        self.note.modified_at = _now_iso()
        self.changed.emit()

    def moveEvent(self, event):
        super().moveEvent(event)
        self.mark_changed()
        self._notify_board_canvas()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.mark_changed()
        self._notify_board_canvas()

    def _notify_board_canvas(self):
        # Duck-typed rather than importing BoardCanvas (board_window.py
        # already imports from this module — importing back would be
        # circular). Lets the board's canvas grow to keep covering this
        # note if it's been dragged/resized past the canvas's current
        # bounds, or shrink back down once it's no longer needed.
        if self.note.board_id is None:
            return
        grow_to_fit = getattr(self.parent(), "grow_to_fit", None)
        if grow_to_fit is not None:
            grow_to_fit()

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

    def _add_spelling_suggestions(self, menu: QMenu):
        """Only shown when the right-click landed on an actually-misspelled
        word — same "act on wherever the cursor was just repositioned to"
        guarantee _auto_linkify_at_cursor already relies on, since
        _position_cursor_for_click() already ran before this."""
        cursor = self.body.textCursor()
        if cursor.hasSelection() or cursor.charFormat().isAnchor():
            return
        block = cursor.block()
        span = spellcheck._word_at(block.text(), cursor.positionInBlock())
        if span is None:
            return
        start, end, word = span
        if spellcheck.check(word):
            return

        suggestions = spellcheck.suggest(word)[: spellcheck.MAX_SUGGESTIONS]
        if not suggestions:
            no_suggestions_action = menu.addAction("(No suggestions)")
            no_suggestions_action.setEnabled(False)
        else:
            for suggestion in suggestions:
                action = menu.addAction(suggestion)
                action.triggered.connect(
                    lambda checked=False, s=suggestion, st=start, e=end, b=block: self._replace_word(b, st, e, s)
                )
        menu.addSeparator()

    def _replace_word(self, block, start: int, end: int, replacement: str):
        cursor = QTextCursor(block)
        cursor.setPosition(block.position() + start)
        cursor.setPosition(block.position() + end, QTextCursor.KeepAnchor)
        cursor.insertText(replacement)
        self.mark_changed()

    def populate_text_menu(self, menu: QMenu):
        """Text-formatting actions (font style/color, bullets & numbering,
        indent). Used only by NoteBody's contextMenuEvent (right-click in
        the text, appended after the standard Undo/Cut/Copy/Paste menu) —
        these act on the current selection, so whole-note actions like
        color/transparency/always-on-top/Notepad/delete don't belong
        here (see populate_note_actions_menu).

        Font/Bullets/Indent are skipped entirely when the selection is
        exactly one image (e.g. right-clicking a picture, which
        _position_cursor_for_click turns into a one-character image
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

        if self.spell_highlighter is not None:
            self._add_spelling_suggestions(menu)

        is_image_selection = self._selection_is_image()

        if not is_image_selection:
            font_action = menu.addAction("Font…")
            font_action.triggered.connect(self.show_font_dialog)

            font_style_menu = menu.addMenu("Font Style")
            # Reflect the current selection's actual formatting — same
            # calls _toggle_bold()/_toggle_italic()/etc. already use to
            # decide what to flip *to* — so the submenu shows which
            # styles are already applied instead of giving no indication
            # at all (same gap Bullets & Numbering already didn't have).
            self.bold_action.setChecked(self.body.fontWeight() > QFont.Normal)
            self.italic_action.setChecked(self.body.fontItalic())
            self.underline_action.setChecked(self.body.fontUnderline())
            self.strikethrough_action.setChecked(self.body.currentCharFormat().fontStrikeOut())
            font_style_menu.addAction(self.bold_action)
            font_style_menu.addAction(self.italic_action)
            font_style_menu.addAction(self.underline_action)
            font_style_menu.addAction(self.strikethrough_action)
            font_style_menu.addSeparator()
            current_alignment = self.body.alignment()
            self.align_left_action.setChecked(current_alignment == Qt.AlignLeft)
            self.align_center_action.setChecked(current_alignment == Qt.AlignCenter)
            self.align_right_action.setChecked(current_alignment == Qt.AlignRight)
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

        # Only offered when the caret/selection is actually on a link —
        # same anchor-detection read as existing_href in
        # show_hyperlink_dialog(), not just the caret-only is_editing_link
        # check above, so it also shows up for a selection that starts on
        # linked text.
        if cursor.charFormat().isAnchor():
            remove_hyperlink_action = menu.addAction("Remove Hyperlink")
            remove_hyperlink_action.triggered.connect(self.remove_hyperlink)

        menu.addAction(self.find_action)

    def populate_note_actions_menu(self, menu: QMenu):
        """Whole-note actions (color, transparency, always-on-top,
        Notepad membership, delete). Used by the header's right-click
        menu and the hamburger (☰) button's dropdown — these apply to the
        note as a whole, not to a text selection, so they're kept out of
        the body's text-formatting menu (see populate_text_menu)."""
        self.title_action.setText("Edit Title…" if self.note.title else "Add Title…")
        menu.addAction(self.title_action)

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

        if self._stuck_window_id is not None:
            stick_action = menu.addAction("Unstick from Window")
            stick_action.triggered.connect(self.unstick_from_window)
        else:
            stick_action = menu.addAction("Stick to Window…")
            stick_action.triggered.connect(self.show_stick_window_dialog)

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
        # Session-only, like the tray's bulk Show All/Hide All Notes — a
        # hidden note reappears on the next launch rather than staying
        # hidden unexpectedly. To bring one specific note back without
        # reopening every note: the Notes Browser lists every note
        # regardless of window visibility, and double-clicking a row
        # already calls .show() before .raise_()/.activateWindow(), so
        # it already works as the "bring it back" mechanism with no
        # further changes needed there.
        hide_action = menu.addAction("Hide Note")
        hide_action.triggered.connect(self.hide)

        delete_action = menu.addAction("Delete Note")
        delete_action.triggered.connect(self.confirm_delete)

    def confirm_delete(self):
        # A plain child dialog doesn't reliably outrank this note's own
        # raw EWMH "always on top" state in KWin's stacking layers (that
        # hint elevates by window layer, not just parent/child order) —
        # force the dialog on top too so it can't end up hidden behind an
        # always-on-top note. No parent (see _new_note_dialog's docstring)
        # — QMessageBox(self) inherited a board-attached note's own
        # palette bleed the same way every other dialog fixed here did;
        # WindowStaysOnTopHint below (not parent/child stacking) is what
        # actually keeps this above an always-on-top note regardless.
        box = QMessageBox()
        box.setWindowTitle("Delete Note")
        box.setText("Delete this note permanently?")
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setWindowFlags(box.windowFlags() | Qt.WindowStaysOnTopHint)
        self._center_dialog_over_note(box)
        reply = box.exec()
        if reply == QMessageBox.Yes:
            self.manager.delete_note(self)
