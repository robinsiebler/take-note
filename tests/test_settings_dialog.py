from __future__ import annotations

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QToolButton

from take_note import spellcheck
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


def test_apply_button_emits_result_settings_without_closing(qapp):
    """Regression: the dialog previously only had OK/Cancel, so trying a
    setting change required closing (and possibly reopening) the dialog
    to adjust further. Apply must emit the same Settings result_settings()
    would build, without accepting/closing the dialog."""
    dialog = SettingsDialog(Settings(default_font_size=12))
    dialog.font_size_spin.setValue(18)

    applied = []
    dialog.applied.connect(applied.append)
    dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Apply).click()

    assert len(applied) == 1
    assert applied[0].default_font_size == 18
    assert dialog.result() != QDialog.Accepted


def test_restores_saved_dialog_geometry(qapp):
    settings = Settings(settings_dialog_x=50, settings_dialog_y=60, settings_dialog_w=500, settings_dialog_h=400)

    dialog = SettingsDialog(settings)

    assert dialog.size().width() == 500
    assert dialog.size().height() == 400
    assert dialog.pos().x() == 50
    assert dialog.pos().y() == 60


def test_saved_geometry_smaller_than_content_grows_on_show(qapp):
    """Regression, reported live: a saved size from before a later
    content change (the spell-check-unavailable label growing) was
    smaller than what the dialog now actually needs -- restored
    verbatim and left clipping content at the bottom, same failure mode
    as having no saved size at all, just never re-checked against
    current content."""
    dialog = SettingsDialog(Settings(settings_dialog_w=10, settings_dialog_h=10))
    needed = dialog.sizeHint()

    dialog.show()

    assert dialog.size().width() >= needed.width()
    assert dialog.size().height() >= needed.height()


def test_saved_geometry_larger_than_content_is_not_shrunk(qapp):
    dialog = SettingsDialog(Settings(settings_dialog_w=1200, settings_dialog_h=1000))

    dialog.show()

    assert dialog.size().width() == 1200
    assert dialog.size().height() == 1000


def test_resizing_persists_geometry_into_the_same_settings_object(qapp):
    """settings passed into the dialog is the same object NoteManager
    holds, not a copy — moveEvent/resizeEvent write directly into it so
    geometry survives even if the dialog is later cancelled."""
    settings = Settings()
    dialog = SettingsDialog(settings)
    dialog.show()

    dialog.resize(700, 600)
    dialog.move(70, 80)

    assert settings.settings_dialog_w == 700
    assert settings.settings_dialog_h == 600
    assert settings.settings_dialog_x == 70
    assert settings.settings_dialog_y == 80


def test_result_settings_preserves_dialog_geometry(qapp):
    settings = Settings(settings_dialog_x=50, settings_dialog_y=60, settings_dialog_w=500, settings_dialog_h=400)
    dialog = SettingsDialog(settings)

    result = dialog.result_settings()

    assert result.settings_dialog_x == 50
    assert result.settings_dialog_y == 60
    assert result.settings_dialog_w == 500
    assert result.settings_dialog_h == 400


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


def test_notes_browser_hotkey_field_initializes_from_settings(qapp):
    dialog = SettingsDialog(Settings(notes_browser_hotkey="Meta+Alt+B"))

    assert dialog.notes_browser_hotkey_edit.keySequence().toString() == "Meta+Alt+B"


def test_result_settings_reflects_changed_notes_browser_hotkey(qapp):
    dialog = SettingsDialog(Settings(notes_browser_hotkey="Meta+Alt+B"))
    dialog.notes_browser_hotkey_edit.setKeySequence(QKeySequence("Meta+Alt+X"))

    result = dialog.result_settings()

    assert result.notes_browser_hotkey == "Meta+Alt+X"


def test_dialog_initializes_cleanly_when_hotkeys_are_none(qapp):
    """A previously-cleared hotkey (Settings.hotkey/notes_browser_hotkey
    is None) must not crash QKeySequenceEdit's construction."""
    dialog = SettingsDialog(Settings(hotkey=None, notes_browser_hotkey=None))

    assert dialog.hotkey_edit.keySequence().isEmpty()
    assert dialog.notes_browser_hotkey_edit.keySequence().isEmpty()


def test_hotkey_clear_button_empties_the_field(qapp):
    dialog = SettingsDialog(Settings(hotkey="Meta+Alt+N"))

    dialog.hotkey_clear_button.click()

    assert dialog.hotkey_edit.keySequence().isEmpty()


def test_notes_browser_hotkey_clear_button_empties_the_field(qapp):
    dialog = SettingsDialog(Settings(notes_browser_hotkey="Meta+Alt+B"))

    dialog.notes_browser_hotkey_clear_button.click()

    assert dialog.notes_browser_hotkey_edit.keySequence().isEmpty()


def test_result_settings_commits_none_for_a_cleared_hotkey(qapp):
    """Regression: clearing the field used to silently fall back to the
    old value in result_settings() (`... or self._settings.hotkey`),
    so there was no way to actually remove a hotkey at all — only the
    Clear button (plus this fix) makes "no hotkey" reachable."""
    dialog = SettingsDialog(Settings(hotkey="Meta+Alt+N"))
    dialog.hotkey_edit.clear()

    result = dialog.result_settings()

    assert result.hotkey is None


def test_result_settings_commits_none_for_a_cleared_notes_browser_hotkey(qapp):
    dialog = SettingsDialog(Settings(notes_browser_hotkey="Meta+Alt+B"))
    dialog.notes_browser_hotkey_edit.clear()

    result = dialog.result_settings()

    assert result.notes_browser_hotkey is None


def test_test_hotkey_on_empty_field_prompts_for_a_combo_instead_of_crashing(qapp):
    """current_value can now legitimately be None (already-cleared
    hotkey) — the self-conflict check must not call parse_shortcut(None)."""
    dialog = SettingsDialog(Settings(hotkey=None))

    dialog._test_hotkey()

    assert dialog.hotkey_status.text() == "Enter a key combination first"


def test_test_notes_browser_hotkey_recognizes_unchanged_current_combo(qapp):
    settings = Settings(notes_browser_hotkey="Meta+Alt+B")
    dialog = SettingsDialog(settings)
    dialog.notes_browser_hotkey_edit.setKeySequence(QKeySequence("Meta+Alt+B"))

    dialog._test_notes_browser_hotkey()

    assert dialog.notes_browser_hotkey_status.text() == "This is already your current hotkey"
    assert dialog._test_listener is None


def test_test_hotkey_rejects_combo_matching_the_other_hotkey_field(qapp):
    """The two global hotkeys can't share a combo — setting the New Note
    field to whatever the Notes Browser field currently shows (edited or
    not) must be caught before a real test grab, not just left to fail
    confusingly once both are saved."""
    settings = Settings(hotkey="Meta+Alt+N", notes_browser_hotkey="Meta+Alt+B")
    dialog = SettingsDialog(settings)
    dialog.hotkey_edit.setKeySequence(QKeySequence("Meta+Alt+B"))

    dialog._test_hotkey()

    assert dialog.hotkey_status.text() == "Same as the Notes Browser hotkey — pick a different combination"
    assert dialog._test_listener is None


def test_test_notes_browser_hotkey_rejects_combo_matching_the_other_field(qapp):
    settings = Settings(hotkey="Meta+Alt+N", notes_browser_hotkey="Meta+Alt+B")
    dialog = SettingsDialog(settings)
    dialog.notes_browser_hotkey_edit.setKeySequence(QKeySequence("Meta+Alt+N"))

    dialog._test_notes_browser_hotkey()

    assert dialog.notes_browser_hotkey_status.text() == "Same as the New Note hotkey — pick a different combination"
    assert dialog._test_listener is None


def test_test_hotkey_allows_a_combo_matching_neither_field(qapp, monkeypatch):
    from take_note.hotkey import HotkeyListener

    started = []
    monkeypatch.setattr(HotkeyListener, "start", lambda self: started.append(self))
    settings = Settings(hotkey="Meta+Alt+N", notes_browser_hotkey="Meta+Alt+B")
    dialog = SettingsDialog(settings)
    dialog.hotkey_edit.setKeySequence(QKeySequence("Meta+Alt+X"))

    dialog._test_hotkey()

    assert dialog.hotkey_status.text() == "Testing…"
    assert len(started) == 1


def test_spell_check_checkbox_reflects_settings_when_available(qapp, monkeypatch):
    monkeypatch.setattr(spellcheck, "is_available", lambda: True)

    dialog = SettingsDialog(Settings(spell_check_enabled=True))

    assert dialog.spell_check_check.isChecked()
    assert dialog.spell_check_check.isEnabled()


def test_spell_check_checkbox_disabled_and_unchecked_when_unavailable(qapp, monkeypatch):
    """Force-unchecked (not just disabled) even if the persisted setting
    was True from an earlier session where the dependency was available —
    a checkbox that's both disabled and checked would misleadingly imply
    the feature is currently active."""
    monkeypatch.setattr(spellcheck, "is_available", lambda: False)

    dialog = SettingsDialog(Settings(spell_check_enabled=True))

    assert not dialog.spell_check_check.isChecked()
    assert not dialog.spell_check_check.isEnabled()


def test_spell_check_unavailable_explanation_is_visible_not_just_a_tooltip(qapp, monkeypatch):
    """Regression, reported live: a tooltip alone was hard to trigger and
    gave no hint one even existed. Explanation text must be a real,
    always-visible label, not just something you'd have to hover to
    discover."""
    from PySide6.QtWidgets import QLabel

    monkeypatch.setattr(spellcheck, "is_available", lambda: False)

    dialog = SettingsDialog(Settings())

    labels = [w for w in dialog.findChildren(QLabel) if "pyenchant" in w.text()]
    assert len(labels) == 1
    assert labels[0].isVisible() or not labels[0].isHidden()


def test_no_explanation_label_when_spell_check_is_available(qapp, monkeypatch):
    from PySide6.QtWidgets import QLabel

    monkeypatch.setattr(spellcheck, "is_available", lambda: True)

    dialog = SettingsDialog(Settings())

    labels = [w for w in dialog.findChildren(QLabel) if "pyenchant" in w.text()]
    assert labels == []


def test_result_settings_reflects_spell_check_checkbox(qapp, monkeypatch):
    monkeypatch.setattr(spellcheck, "is_available", lambda: True)
    dialog = SettingsDialog(Settings(spell_check_enabled=False))
    dialog.spell_check_check.setChecked(True)

    result = dialog.result_settings()

    assert result.spell_check_enabled is True
