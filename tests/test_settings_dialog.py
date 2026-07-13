from __future__ import annotations

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QScrollArea, QToolButton

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


def test_dialog_initializes_note_and_notepad_size_from_settings(qapp):
    settings = Settings(default_note_w=400, default_note_h=400, default_notepad_w=800, default_notepad_h=600)
    dialog = SettingsDialog(settings)

    assert dialog.note_size_combo.currentData() == (400, 400)
    assert dialog.notepad_size_combo.currentData() == (800, 600)


def _index_for_size(combo, w, h):
    # Not combo.findData((w, h)) — its equality check doesn't reliably
    # match a plain Python tuple stored as itemData under PySide6 (see
    # SettingsDialog._build_size_combo's own comment on this).
    for i in range(combo.count()):
        if combo.itemData(i) == (w, h):
            return i
    raise AssertionError(f"no preset matches ({w}, {h})")


def test_result_settings_reflects_changed_note_and_notepad_size(qapp):
    dialog = SettingsDialog(Settings())
    dialog.note_size_combo.setCurrentIndex(_index_for_size(dialog.note_size_combo, 400, 400))
    dialog.notepad_size_combo.setCurrentIndex(_index_for_size(dialog.notepad_size_combo, 800, 600))

    result = dialog.result_settings()

    assert (result.default_note_w, result.default_note_h) == (400, 400)
    assert (result.default_notepad_w, result.default_notepad_h) == (800, 600)


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


def test_result_settings_preserves_notes_manager_geometry(qapp):
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

    dialog.resize(700, 700)
    dialog.move(70, 80)

    assert settings.settings_dialog_w == 700
    assert settings.settings_dialog_h == 700
    assert settings.settings_dialog_x == 70
    assert settings.settings_dialog_y == 80


def test_hotkey_tab_is_scrollable(qapp):
    """Regression: five stacked hotkey sections (up from two) gave the
    Hotkey tab's own QFormLayout a real minimum-size floor tall enough
    to fill both of the reporting user's monitors and make the dialog
    impossible to shrink at all — not just visually cramped, a genuine
    resize-below-minimum block. Wrapping the tab in a QScrollArea (see
    SettingsDialog._scrollable's own docstring) decouples the dialog's
    own minimum size from the tab's full content height."""
    dialog = SettingsDialog(Settings())

    scroll_area = dialog.findChild(QScrollArea)

    assert scroll_area is not None
    assert scroll_area.widgetResizable()


def test_hotkey_tab_explains_combos_that_never_reach_the_field(qapp):
    """A combo already grabbed by a system-level shortcut (e.g. KWin's
    own) never reaches this dialog at all — no reliable way to detect
    every such conflict ahead of time (see _build_hotkey_tab's own
    docstring on why), so this is a plain explanatory hint rather than
    an automated check."""
    dialog = SettingsDialog(Settings())

    labels = [w.text() for w in dialog.findChildren(QLabel)]

    assert any("already grabbed by a system shortcut" in text for text in labels)


def test_dialog_can_shrink_well_below_the_hotkey_tabs_full_content_height(qapp):
    dialog = SettingsDialog(Settings())
    dialog.show()

    dialog.resize(400, 300)

    # Not asserting an exact floor (that's the General tab's own natural
    # size, not something this test should pin down precisely) — just
    # that it's nowhere near tall enough to need the full ~920px the
    # Hotkey tab's five sections would require unscrolled.
    assert dialog.height() < 700


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


def test_notes_manager_hotkey_field_initializes_from_settings(qapp):
    dialog = SettingsDialog(Settings(notes_browser_hotkey="Meta+Alt+B"))

    assert dialog.notes_manager_hotkey_edit.keySequence().toString() == "Meta+Alt+B"


def test_result_settings_reflects_changed_notes_manager_hotkey(qapp):
    dialog = SettingsDialog(Settings(notes_browser_hotkey="Meta+Alt+B"))
    dialog.notes_manager_hotkey_edit.setKeySequence(QKeySequence("Meta+Alt+X"))

    result = dialog.result_settings()

    assert result.notes_browser_hotkey == "Meta+Alt+X"


def test_dialog_initializes_cleanly_when_hotkeys_are_none(qapp):
    """A previously-cleared hotkey (Settings.hotkey/notes_browser_hotkey
    is None) must not crash QKeySequenceEdit's construction."""
    dialog = SettingsDialog(Settings(hotkey=None, notes_browser_hotkey=None))

    assert dialog.hotkey_edit.keySequence().isEmpty()
    assert dialog.notes_manager_hotkey_edit.keySequence().isEmpty()


def test_hotkey_clear_button_empties_the_field(qapp):
    dialog = SettingsDialog(Settings(hotkey="Meta+Alt+N"))

    dialog.hotkey_clear_button.click()

    assert dialog.hotkey_edit.keySequence().isEmpty()


def test_notes_manager_hotkey_clear_button_empties_the_field(qapp):
    dialog = SettingsDialog(Settings(notes_browser_hotkey="Meta+Alt+B"))

    dialog.notes_manager_hotkey_clear_button.click()

    assert dialog.notes_manager_hotkey_edit.keySequence().isEmpty()


def test_result_settings_commits_none_for_a_cleared_hotkey(qapp):
    """Regression: clearing the field used to silently fall back to the
    old value in result_settings() (`... or self._settings.hotkey`),
    so there was no way to actually remove a hotkey at all — only the
    Clear button (plus this fix) makes "no hotkey" reachable."""
    dialog = SettingsDialog(Settings(hotkey="Meta+Alt+N"))
    dialog.hotkey_edit.clear()

    result = dialog.result_settings()

    assert result.hotkey is None


def test_result_settings_commits_none_for_a_cleared_notes_manager_hotkey(qapp):
    dialog = SettingsDialog(Settings(notes_browser_hotkey="Meta+Alt+B"))
    dialog.notes_manager_hotkey_edit.clear()

    result = dialog.result_settings()

    assert result.notes_browser_hotkey is None


def test_test_hotkey_on_empty_field_prompts_for_a_combo_instead_of_crashing(qapp):
    """current_value can now legitimately be None (already-cleared
    hotkey) — the self-conflict check must not call parse_shortcut(None)."""
    dialog = SettingsDialog(Settings(hotkey=None))

    dialog._test_hotkey()

    assert dialog.hotkey_status.text() == "Enter a key combination first"


def test_test_notes_manager_hotkey_recognizes_unchanged_current_combo(qapp):
    settings = Settings(notes_browser_hotkey="Meta+Alt+B")
    dialog = SettingsDialog(settings)
    dialog.notes_manager_hotkey_edit.setKeySequence(QKeySequence("Meta+Alt+B"))

    dialog._test_notes_manager_hotkey()

    assert dialog.notes_manager_hotkey_status.text() == "This is already your current hotkey"
    assert dialog._test_listener is None


def test_test_hotkey_rejects_combo_matching_the_other_hotkey_field(qapp):
    """The two global hotkeys can't share a combo — setting the New Note
    field to whatever the Notes Manager field currently shows (edited or
    not) must be caught before a real test grab, not just left to fail
    confusingly once both are saved."""
    settings = Settings(hotkey="Meta+Alt+N", notes_browser_hotkey="Meta+Alt+B")
    dialog = SettingsDialog(settings)
    dialog.hotkey_edit.setKeySequence(QKeySequence("Meta+Alt+B"))

    dialog._test_hotkey()

    assert dialog.hotkey_status.text() == "Same as the Notes Manager hotkey — pick a different combination"
    assert dialog._test_listener is None


def test_test_notes_manager_hotkey_rejects_combo_matching_the_other_field(qapp):
    settings = Settings(hotkey="Meta+Alt+N", notes_browser_hotkey="Meta+Alt+B")
    dialog = SettingsDialog(settings)
    dialog.notes_manager_hotkey_edit.setKeySequence(QKeySequence("Meta+Alt+N"))

    dialog._test_notes_manager_hotkey()

    assert dialog.notes_manager_hotkey_status.text() == "Same as the New Note hotkey — pick a different combination"
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


def test_new_bulk_action_hotkey_fields_default_to_empty(qapp):
    """Unlike hotkey/notes_browser_hotkey, these three have no default
    combo — explicit user call, opt-in only. A fresh Settings() must
    show all three fields empty, not some guessed-at default."""
    dialog = SettingsDialog(Settings())

    assert dialog.show_hide_all_notes_hotkey_edit.keySequence().isEmpty()
    assert dialog.roll_all_notes_hotkey_edit.keySequence().isEmpty()
    assert dialog.bring_all_notes_to_front_hotkey_edit.keySequence().isEmpty()


def test_bulk_action_hotkey_fields_initialize_from_settings(qapp):
    dialog = SettingsDialog(
        Settings(
            show_hide_all_notes_hotkey="Meta+Alt+H",
            roll_all_notes_hotkey="Meta+Alt+R",
            bring_all_notes_to_front_hotkey="Meta+Alt+T",
        )
    )

    assert dialog.show_hide_all_notes_hotkey_edit.keySequence().toString() == "Meta+Alt+H"
    assert dialog.roll_all_notes_hotkey_edit.keySequence().toString() == "Meta+Alt+R"
    assert dialog.bring_all_notes_to_front_hotkey_edit.keySequence().toString() == "Meta+Alt+T"


def test_result_settings_reflects_changed_bulk_action_hotkeys(qapp):
    dialog = SettingsDialog(Settings())
    dialog.show_hide_all_notes_hotkey_edit.setKeySequence(QKeySequence("Meta+Alt+H"))
    dialog.roll_all_notes_hotkey_edit.setKeySequence(QKeySequence("Meta+Alt+R"))
    dialog.bring_all_notes_to_front_hotkey_edit.setKeySequence(QKeySequence("Meta+Alt+T"))

    result = dialog.result_settings()

    assert result.show_hide_all_notes_hotkey == "Meta+Alt+H"
    assert result.roll_all_notes_hotkey == "Meta+Alt+R"
    assert result.bring_all_notes_to_front_hotkey == "Meta+Alt+T"


def test_bulk_action_hotkey_clear_buttons_empty_their_fields(qapp):
    dialog = SettingsDialog(
        Settings(
            show_hide_all_notes_hotkey="Meta+Alt+H",
            roll_all_notes_hotkey="Meta+Alt+R",
            bring_all_notes_to_front_hotkey="Meta+Alt+T",
        )
    )

    dialog.show_hide_all_notes_hotkey_clear_button.click()
    dialog.roll_all_notes_hotkey_clear_button.click()
    dialog.bring_all_notes_to_front_hotkey_clear_button.click()

    assert dialog.show_hide_all_notes_hotkey_edit.keySequence().isEmpty()
    assert dialog.roll_all_notes_hotkey_edit.keySequence().isEmpty()
    assert dialog.bring_all_notes_to_front_hotkey_edit.keySequence().isEmpty()


def test_test_bulk_action_hotkey_rejects_combo_matching_any_other_field(qapp):
    """Five hotkeys now share one combo space — this checks a pairing
    that isn't the original two (hotkey/notes_browser_hotkey) to prove
    the cross-check in _test_hotkey_combo actually scans every other
    field, not just one hardcoded one."""
    settings = Settings(roll_all_notes_hotkey="Meta+Alt+R")
    dialog = SettingsDialog(settings)
    dialog.show_hide_all_notes_hotkey_edit.setKeySequence(QKeySequence("Meta+Alt+R"))

    dialog._test_show_hide_all_notes_hotkey()

    assert (
        dialog.show_hide_all_notes_hotkey_status.text()
        == "Same as the Roll Up/Down Notes hotkey — pick a different combination"
    )
    assert dialog._test_listener is None


def test_test_bring_all_notes_to_front_hotkey_recognizes_unchanged_current_combo(qapp):
    settings = Settings(bring_all_notes_to_front_hotkey="Meta+Alt+T")
    dialog = SettingsDialog(settings)
    dialog.bring_all_notes_to_front_hotkey_edit.setKeySequence(QKeySequence("Meta+Alt+T"))

    dialog._test_bring_all_notes_to_front_hotkey()

    assert dialog.bring_all_notes_to_front_hotkey_status.text() == "This is already your current hotkey"
    assert dialog._test_listener is None


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
