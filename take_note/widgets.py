from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import QGridLayout, QToolButton, QWidget


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
        border = "2px solid white" if selected else "2px solid transparent"
        text_color = "white" if selected else "transparent"
        swatch_btn.setText("✓" if selected else "")
        swatch_btn.setStyleSheet(
            f"QToolButton {{ background-color: {color}; border-radius: 13px; "
            f"border: {border}; color: {text_color}; font-weight: bold; }}"
        )
        swatch_btn.clicked.connect(lambda checked=False, c=color: on_pick(c))
        grid.addWidget(swatch_btn, i // columns, i % columns)

    return container
