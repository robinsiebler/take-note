from __future__ import annotations

from PySide6.QtGui import QKeySequence
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


def test_randomize_color_checkbox_reflects_settings(qapp):
    dialog = SettingsDialog(Settings(randomize_new_note_color=True))

    assert dialog.randomize_color_check.isChecked()


def test_result_settings_reflects_randomize_checkbox(qapp):
    dialog = SettingsDialog(Settings(randomize_new_note_color=False))
    dialog.randomize_color_check.setChecked(True)

    result = dialog.result_settings()

    assert result.randomize_new_note_color is True


def test_checking_randomize_disables_default_color_grid(qapp):
    dialog = SettingsDialog(Settings(randomize_new_note_color=False))
    grid = dialog._color_grid_layout.itemAt(0).widget()
    assert grid.isEnabled()

    dialog.randomize_color_check.setChecked(True)

    assert not grid.isEnabled()


def test_result_settings_preserves_notes_browser_geometry(qapp):
    """result_settings() builds a brand-new Settings() with only the
    fields this dialog has controls for — anything else (like the Notes
    Browser's own persisted geometry) must be carried through unchanged,
    not silently reset to the dataclass defaults."""
    settings = Settings(
        notes_browser_x=50, notes_browser_y=60, notes_browser_w=800, notes_browser_h=500
    )
    dialog = SettingsDialog(settings)

    result = dialog.result_settings()

    assert result.notes_browser_x == 50
    assert result.notes_browser_y == 60
    assert result.notes_browser_w == 800
    assert result.notes_browser_h == 500


def test_test_hotkey_recognizes_unchanged_current_combo(qapp):
    """Regression: testing the combo that's already this app's own live
    global hotkey always "failed" — the app's real HotkeyListener (in
    NoteManager, unaffected by this dialog being open) still holds that
    exact X11 grab, so a second grab for the same combo always conflicts
    with it. Reported live: clicking Test without changing the field
    printed 4 "Hotkey combo unavailable for one modifier-lock variant"
    warnings and showed "Already in use by another app" — technically
    true but misleading, since the "other app" is this one. Now
    recognized and skipped before ever starting a competing grab."""
    settings = Settings(hotkey="Ctrl+Alt+N")
    dialog = SettingsDialog(settings)
    dialog.hotkey_edit.setKeySequence(QKeySequence("Ctrl+Alt+N"))

    dialog._test_hotkey()

    assert dialog.hotkey_status.text() == "This is already your current hotkey"
    assert dialog._test_listener is None


def test_test_hotkey_starts_a_real_test_for_a_different_combo(qapp, monkeypatch):
    """Sanity check for the guard above: a genuinely different combo must
    still go through the real test-listener path, not get swallowed by
    the unchanged-combo shortcut."""
    from take_note.hotkey import HotkeyListener

    started = []
    monkeypatch.setattr(HotkeyListener, "start", lambda self: started.append(self))

    settings = Settings(hotkey="Ctrl+Alt+N")
    dialog = SettingsDialog(settings)
    dialog.hotkey_edit.setKeySequence(QKeySequence("Ctrl+Alt+M"))

    dialog._test_hotkey()

    assert dialog.hotkey_status.text() == "Testing…"
    assert len(started) == 1
    assert dialog._test_listener is not None
