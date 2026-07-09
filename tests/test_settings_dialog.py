from __future__ import annotations

from PySide6.QtWidgets import QToolButton

from take_note.models import FONT_SWATCHES, Settings
from take_note.settings_dialog import SettingsDialog


def test_dialog_initializes_font_size_and_color_from_settings(qapp):
    settings = Settings(default_font_size=18, default_font_color="#c62828")
    dialog = SettingsDialog(settings)

    assert dialog.font_size_spin.value() == 18
    assert dialog._pending_font_color == "#c62828"


def test_result_settings_reflects_changed_font_size(qapp):
    dialog = SettingsDialog(Settings())
    dialog.font_size_spin.setValue(20)

    result = dialog.result_settings()

    assert result.default_font_size == 20


def test_result_settings_reflects_picked_font_color(qapp):
    dialog = SettingsDialog(Settings())
    grid = dialog._font_color_grid_layout.itemAt(0).widget()
    swatch_buttons = grid.findChildren(QToolButton)
    target_index = FONT_SWATCHES.index("#2e7d32")  # dark green, not the default black

    swatch_buttons[target_index].click()
    result = dialog.result_settings()

    assert result.default_font_color == "#2e7d32"


def test_picking_font_color_rebuilds_grid_with_new_checkmark(qapp):
    """Same pattern as the note-color picker: the swatch grid widget is
    rebuilt (not mutated in place) so the checkmark moves to the newly
    picked color."""
    dialog = SettingsDialog(Settings())
    original_grid = dialog._font_color_grid_layout.itemAt(0).widget()
    swatch_buttons = original_grid.findChildren(QToolButton)
    target_index = FONT_SWATCHES.index("#1565c0")  # dark blue

    swatch_buttons[target_index].click()

    new_grid = dialog._font_color_grid_layout.itemAt(0).widget()
    assert new_grid is not original_grid
    assert dialog._pending_font_color == "#1565c0"


def test_result_settings_preserves_other_fields_unrelated_to_font(qapp):
    settings = Settings(default_color="#a5d6a7", hotkey="Ctrl+Shift+N")
    dialog = SettingsDialog(settings)

    result = dialog.result_settings()

    assert result.default_color == "#a5d6a7"
    assert result.hotkey == "Ctrl+Shift+N"
