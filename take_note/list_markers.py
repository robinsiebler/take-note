from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFontMetricsF, QPainter, QPalette, QTextCursor, QTextListFormat

_ROMAN_VALUES = [
    (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
    (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
    (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
]

# Gap between a marker (bullet dot or text like "3."/"iv.") and the note
# text that follows. This only repositions the marker within its existing
# gutter box (closer to the note's left edge) — it never moves the text
# or changes document().setIndentWidth()'s 36px, so the list's overall
# indent from the note's own margin is unaffected either way.
_MARKER_TEXT_GAP = 12


def to_alpha(n: int) -> str:
    """1-based bijective base-26 (Excel-column style): 26 -> "z", 27 ->
    "aa", 28 -> "ab" — confirmed against Qt's own ListLowerAlpha/
    ListUpperAlpha rendering past item 26, which is not the naive
    chr(ord('a') + n % 26) wraparound."""
    letters = []
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        letters.append(chr(ord("a") + remainder))
    return "".join(reversed(letters))


def to_roman(n: int) -> str:
    result = []
    for value, numeral in _ROMAN_VALUES:
        count, n = divmod(n, value)
        result.append(numeral * count)
    return "".join(result)


def marker_text(style: QTextListFormat.Style, item_number_1based: int) -> str | None:
    """None for styles with no text marker (Disc/Circle/Square/no list).
    Every numbered style renders as "<value>." with a trailing period,
    confirmed against Qt's own native rendering of each style."""
    if style == QTextListFormat.ListDecimal:
        return f"{item_number_1based}."
    if style == QTextListFormat.ListLowerAlpha:
        return f"{to_alpha(item_number_1based)}."
    if style == QTextListFormat.ListUpperAlpha:
        return f"{to_alpha(item_number_1based).upper()}."
    if style == QTextListFormat.ListLowerRoman:
        return f"{to_roman(item_number_1based).lower()}."
    if style == QTextListFormat.ListUpperRoman:
        return f"{to_roman(item_number_1based)}."
    return None


def marker_gutter_rect(body, block) -> QRectF:
    """The column immediately left of a list block's text, where Qt's own
    native marker paints today — confirmed via body.cursorRect(), which
    already accounts for scroll position, so no manual scroll-offset math
    is needed."""
    row_rect = body.cursorRect(QTextCursor(block))
    gutter_width = body.document().indentWidth()
    return QRectF(row_rect.left() - gutter_width, row_rect.top(), gutter_width, row_rect.height())


def _is_block_selected(block, selection_start: int, selection_end: int) -> bool:
    return selection_start <= block.position() < selection_end


def _leading_char_format(document, block):
    cursor = QTextCursor(document)
    cursor.setPosition(block.position())
    return cursor.charFormat()


def paint_list_markers(body, painter: QPainter) -> None:
    """Cover the gutter Qt's native list rendering already painted into
    (checkbox-glyph bug and all) and hand-draw the correct marker on top.
    Never touches QTextList/QTextListFormat/block data — confirmed via
    signal-counting that this produces zero textChanged/contentsChanged
    activity, unlike an earlier tried-and-rejected approach that swapped
    QTextListFormat.style() to suppress the native glyph, which fired
    those signals (and would schedule a disk save) on every repaint."""
    document = body.document()
    cursor = body.textCursor()
    has_selection = cursor.hasSelection()
    selection_start = cursor.selectionStart() if has_selection else -1
    selection_end = cursor.selectionEnd() if has_selection else -1
    palette = body.palette()
    note_color = body.note_window.note.color

    block = document.begin()
    while block.isValid():
        text_list = block.textList()
        if text_list is None:
            block = block.next()
            continue

        gutter_rect = marker_gutter_rect(body, block)
        selected = has_selection and _is_block_selected(block, selection_start, selection_end)

        if selected:
            background = palette.color(QPalette.Highlight)
            foreground = palette.color(QPalette.HighlightedText)
        else:
            background = note_color
            foreground = _leading_char_format(document, block).foreground().color()

        painter.fillRect(gutter_rect, background)

        style = text_list.format().style()
        item_number = text_list.itemNumber(block) + 1
        font = _leading_char_format(document, block).font()
        text = marker_text(style, item_number)

        if text is not None:
            painter.setFont(font)
            painter.setPen(foreground)
            text_rect = gutter_rect.adjusted(0, 0, -_MARKER_TEXT_GAP, 0)
            painter.drawText(text_rect, Qt.AlignRight | Qt.AlignVCenter, text)
        elif style in (QTextListFormat.ListDisc, QTextListFormat.ListCircle, QTextListFormat.ListSquare):
            metrics = QFontMetricsF(font)
            diameter = metrics.xHeight() * 0.85
            cy = gutter_rect.center().y()
            cx = gutter_rect.right() - _MARKER_TEXT_GAP - diameter
            marker_rect = QRectF(cx, cy - diameter / 2, diameter, diameter)
            painter.setPen(foreground)
            if style == QTextListFormat.ListDisc:
                painter.setBrush(foreground)
            else:
                painter.setBrush(Qt.NoBrush)
            if style == QTextListFormat.ListSquare:
                painter.drawRect(marker_rect)
            else:
                painter.drawEllipse(marker_rect)
            painter.setBrush(Qt.NoBrush)

        block = block.next()
