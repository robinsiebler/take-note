from __future__ import annotations

import re

from PySide6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat, QTextCursor

try:
    import enchant
except ImportError:
    # Raised either when pyenchant itself isn't pip-installed, or when it
    # is but the system Enchant C library isn't present at all — confirmed
    # directly, not guessed: enchant/__init__.py itself re-raises
    # ImportError from its native-library probe unless a specific env var
    # is set to suppress it.
    enchant = None

# One shared word tokenizer for both live highlighting (every word in a
# block) and the right-click suggestion lookup (the one word at the click
# position) — same pattern as _URL_PATTERN/_detect_url_span in
# note_window.py. Letters plus internal apostrophes only ("don't",
# "O'Brien"), no leading/trailing apostrophe.
_WORD_PATTERN = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)*")

MAX_SUGGESTIONS = 8

_dict = None
_dict_checked = False


def _get_dict():
    """Lazily constructs and caches a single en_US Dict for the process —
    real Enchant Dict construction loads a dictionary file, not something
    to redo per note window. Catches every failure mode: pyenchant not
    pip-installed or the system Enchant library missing (enchant is None,
    set above), or Enchant present but no en_US backend/dictionary
    installed (enchant.Dict raises enchant.errors.DictNotFoundError,
    confirmed directly against a real install)."""
    global _dict, _dict_checked
    if not _dict_checked:
        _dict_checked = True
        if enchant is not None:
            try:
                _dict = enchant.Dict("en_US")
            except Exception:
                _dict = None
    return _dict


def is_available() -> bool:
    return _get_dict() is not None


def check(word: str) -> bool:
    """Fails open (True, i.e. "not misspelled") when unavailable, so
    callers never need their own is_available() branch just to stay
    correct with the feature off/uninstalled."""
    d = _get_dict()
    if d is None or not word:
        return True
    return d.check(word)


def suggest(word: str) -> list[str]:
    d = _get_dict()
    if d is None or not word:
        return []
    return d.suggest(word)


def ignore(word: str) -> None:
    """By itself, session-only: check() treats `word` as correctly
    spelled for the rest of this process's lifetime, forgotten on the
    next launch. NoteWindow._ignore_word() also persists `word` to
    Settings.ignored_words and NoteManager replays every word there
    through this same function on every launch (see
    NoteManager._replay_ignored_words()) — the combination is what
    actually makes "Ignore" behave as permanent-within-Take-Note!, not
    this function alone."""
    d = _get_dict()
    if d is not None and word:
        d.add_to_session(word)


def add_to_dictionary(word: str) -> None:
    """Permanent: Enchant itself persists `word` to the user's personal
    word list, so check() treats it as correct across restarts too, not
    just this session."""
    d = _get_dict()
    if d is not None and word:
        d.add(word)


def _word_at(text: str, offset: int) -> tuple[int, int, str] | None:
    """The [start, end) span and text of the word in `text` containing
    character position `offset`, or None. Pure function, no Qt dependency
    — directly unit-testable, mirrors _detect_url_span in note_window.py."""
    for match in _WORD_PATTERN.finditer(text):
        start, end = match.span()
        if start <= offset < end:
            return start, end, match.group()
    return None


class SpellHighlighter(QSyntaxHighlighter):
    """Live as-you-type squiggly underline via QTextCharFormat.setFormat()
    — confirmed directly this never touches the document's real formatting
    state (isModified()/isUndoAvailable() stay False, never appears in
    toHtml()) and Qt re-highlights only the block(s) that actually changed
    as the user types, no manual re-check bookkeeping needed. See
    NoteWindow._attach_spell_highlighter for why simply constructing this
    on a document that already has content still needs care to avoid
    spuriously marking the note "modified"."""

    def __init__(self, document):
        super().__init__(document)
        self._format = QTextCharFormat()
        self._format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)
        self._format.setUnderlineColor(QColor("red"))

    def highlightBlock(self, text: str) -> None:
        block = self.currentBlock()
        for match in _WORD_PATTERN.finditer(text):
            start, end = match.span()
            if self._is_anchor(block, start):
                continue  # hyperlink text — checking URL text as spelling errors is just noise
            if not check(match.group()):
                self.setFormat(start, end - start, self._format)

    def _is_anchor(self, block, offset_in_block: int) -> bool:
        # A one-character KeepAnchor selection, same boundary-safety
        # reasoning NoteBody._select_image_at already relies on: movePosition()
        # failing at a document boundary would leave anchor == position, and
        # charFormat() on that empty "selection" reports the *preceding*
        # character's format instead — hasSelection() rules that out here.
        cursor = QTextCursor(self.document())
        cursor.setPosition(block.position() + offset_in_block)
        cursor.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor)
        return cursor.hasSelection() and cursor.charFormat().isAnchor()
