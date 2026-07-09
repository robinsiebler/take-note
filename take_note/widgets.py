from __future__ import annotations

from typing import Callable

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGridLayout, QToolButton, QWidget


def _swatch_border_color(color_hex: str) -> str:
    """A border shade that contrasts with the swatch's *own* fill, not a
    single fixed grey — #888888 read fine against dark swatches (black,
    charcoal, navy) but was too close in brightness to light pastel ones
    (yellow, grey/white) to look like a real border there. Picks a darker
    outline for light swatches and a lighter one for dark swatches, so
    every swatch gets a visibly distinct edge regardless of its own color."""
    color = QColor(color_hex)
    luminance = (0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()) / 255
    return "#666666" if luminance > 0.6 else "#999999"


def build_color_swatch_grid(
    colors: list[str],
    selected_color: str,
    on_pick: Callable[[str], None],
    columns: int = 4,
) -> QWidget:
    """A grid of round color swatch buttons with a checkmark on the
    currently selected color. Shared between the note's color-picker menu
    and the settings dialog's default-color picker."""
    container = QWidget()
    grid = QGridLayout(container)
    grid.setContentsMargins(4, 4, 4, 4)
    grid.setSpacing(6)

    for i, color in enumerate(colors):
        swatch_btn = QToolButton()
        swatch_btn.setFixedSize(26, 26)
        selected = color.lower() == selected_color.lower()
        border = "2px solid white" if selected else f"1px solid {_swatch_border_color(color)}"
        text_color = "white" if selected else "transparent"
        swatch_btn.setText("✓" if selected else "")
        swatch_btn.setStyleSheet(
            f"QToolButton {{ background-color: {color}; border-radius: 13px; "
            f"border: {border}; color: {text_color}; font-weight: bold; }}"
        )
        swatch_btn.clicked.connect(lambda checked=False, c=color: on_pick(c))
        grid.addWidget(swatch_btn, i // columns, i % columns)

    return container
