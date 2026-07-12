from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import spellcheck
from .hotkey import HotkeyListener, parse_shortcut
from .models import FONT_SWATCHES, SWATCHES, Settings
from .widgets import build_color_swatch_grid


class SettingsDialog(QDialog):
    # Emitted only by the Apply button, carrying the same Settings that
    # result_settings() would build — lets a setting (e.g. a font/color
    # change) take effect immediately without closing the dialog. OK
    # keeps going through the existing post-exec() result_settings() path
    # in NoteManager.open_settings() instead of this signal, so nothing
    # about the OK/Cancel behavior changes.
    applied = Signal(Settings)

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self._settings = settings
        self._pending_color = settings.default_color
        self._pending_font_color = settings.default_font_color
        self._test_listener: HotkeyListener | None = None
        self._geometry_grown_to_fit = False

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)
        tabs.addTab(self._build_general_tab(), "General")
        tabs.addTab(self._scrollable(self._build_hotkey_tab()), "Hotkey")

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Apply | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.Apply).clicked.connect(
            lambda: self.applied.emit(self.result_settings())
        )
        layout.addWidget(buttons)

        self._restore_geometry()

    def _restore_geometry(self):
        # self._settings is the same object NoteManager holds (passed by
        # reference, not copied), so writing into it directly here — same
        # pattern as NotesBrowserWindow's notes_browser_x/y/w/h — persists
        # regardless of whether the dialog is ultimately OK'd or
        # cancelled, since window chrome position isn't really a "setting"
        # the user is choosing to discard.
        if self._settings.settings_dialog_w and self._settings.settings_dialog_h:
            self.resize(self._settings.settings_dialog_w, self._settings.settings_dialog_h)
        if self._settings.settings_dialog_x is not None and self._settings.settings_dialog_y is not None:
            self.move(self._settings.settings_dialog_x, self._settings.settings_dialog_y)

    def showEvent(self, event):
        super().showEvent(event)
        # Never let a restored (or Qt's own too-small default first-show)
        # size clip content — confirmed live twice: once with no saved
        # geometry at all (Qt's own default first-show size here is
        # noticeably smaller than sizeHint(), e.g. 426x637 vs. a true
        # 695x666), and again with a *saved* geometry from before a
        # later content change (the spell-check label growing) made it
        # insufficient — a stale saved size clips just as badly as no
        # saved size at all, and nothing before this ever re-checked it
        # against current content. Only grows dimensions that are
        # actually too small, so an intentionally-larger custom size is
        # left alone. Deliberately done here, not in _restore_geometry()
        # (called from __init__, before the dialog is ever shown/laid
        # out): reported live that resizing that early produced a
        # visually broken dialog (clipped color swatch grids, stray
        # unpainted regions) on the real desktop, where actual fonts/DPI
        # scaling can make sizeHint() computed before first paint
        # unreliable. Guarded to only ever run once.
        if self._geometry_grown_to_fit:
            return
        self._geometry_grown_to_fit = True
        needed = self.sizeHint()
        current = self.size()
        grown_w = max(current.width(), needed.width())
        grown_h = max(current.height(), needed.height())
        if (grown_w, grown_h) != (current.width(), current.height()):
            self.resize(grown_w, grown_h)

    def moveEvent(self, event):
        super().moveEvent(event)
        self._settings.settings_dialog_x, self._settings.settings_dialog_y = self.x(), self.y()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._settings.settings_dialog_w, self._settings.settings_dialog_h = self.width(), self.height()

    @staticmethod
    def _scrollable(content: QWidget) -> QScrollArea:
        """Wraps a tab's content in a scroll area rather than letting it
        size the whole dialog to fit. Without this, QFormLayout sets a
        hard minimum-size floor from its own content — with five stacked
        hotkey sections (up from two), that floor grew tall enough to
        fill both monitors and made the dialog impossible to shrink at
        all (not just visually cramped — a real resize-below-minimum
        block, confirmed live). A QScrollArea's own sizeHint/minimumSize
        don't need to match its contained widget's, so wrapping the tab
        in one gives the dialog a sane default height and an actual
        scrollbar for the rest, without touching the tab's own layout."""
        scroll = QScrollArea()
        scroll.setWidget(content)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        return scroll

    # -- General tab -------------------------------------------------------

    def _build_general_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)

        self.launch_at_login_check = QCheckBox("Launch at login")
        self.launch_at_login_check.setChecked(self._settings.launch_at_login)
        form.addRow(self.launch_at_login_check)

        self.always_on_top_check = QCheckBox("New notes stay on top by default")
        self.always_on_top_check.setChecked(self._settings.default_always_on_top)
        form.addRow(self.always_on_top_check)

        form.addRow(QLabel("Default note color:"))
        self._color_grid_layout = QVBoxLayout()
        self._color_grid_layout.addWidget(
            build_color_swatch_grid(SWATCHES, self._pending_color, self._on_pick_default_color)
        )
        form.addRow(self._color_grid_layout)

        self.randomize_color_check = QCheckBox("Randomize new note color")
        self.randomize_color_check.setChecked(self._settings.randomize_new_note_color)
        self.randomize_color_check.toggled.connect(self._on_toggle_randomize_color)
        form.addRow(self.randomize_color_check)
        self._on_toggle_randomize_color(self.randomize_color_check.isChecked())

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(6, 72)
        self.font_size_spin.setValue(self._settings.default_font_size)
        self.font_size_spin.setSuffix(" pt")
        form.addRow("Default font size:", self.font_size_spin)

        form.addRow(QLabel("Default font color:"))
        self._font_color_grid_layout = QVBoxLayout()
        self._font_color_grid_layout.addWidget(
            build_color_swatch_grid(
                FONT_SWATCHES, self._pending_font_color, self._on_pick_default_font_color
            )
        )
        form.addRow(self._font_color_grid_layout)

        self.spell_check_check = QCheckBox("Check spelling as you type")
        self.spell_check_check.setChecked(self._settings.spell_check_enabled)
        form.addRow(self.spell_check_check)
        if not spellcheck.is_available():
            # Force-unchecked (not just disabled) so a stale True from a
            # previous session where the dependency *was* available
            # doesn't silently linger as an unreachable "on" state — the
            # checkbox itself is the only place this gets toggled.
            self.spell_check_check.setChecked(False)
            self.spell_check_check.setEnabled(False)
            # setEnabled(False) alone reuses Qt's disabled-text palette
            # role, which the label below already proved too low-contrast
            # to read comfortably (see that comment) — same fixed grey
            # here, so the checkbox and its explanation read as one
            # visually consistent disabled unit rather than two different
            # shades of muted.
            self.spell_check_check.setStyleSheet("color: #888888;")
            # A tooltip alone isn't a reliable way to explain why a
            # control is disabled — reported live: hard to trigger, and
            # nothing hints one exists. Visible text under the checkbox
            # instead, same explanation, always there to see.
            unavailable_label = QLabel(
                "Requires the optional 'pyenchant' package and a system "
                "spell-check dictionary — see README."
            )
            unavailable_label.setWordWrap(True)
            # Two prior approaches both failed real screenshot checks,
            # reported live each time: a first fixed dark-tuned grey read
            # fine on dark but too light on light theme; switching to
            # setEnabled(False) (Qt's own disabled-text palette role, the
            # same mechanism graying out the checkbox above it) was
            # assumed theme-correct but turned out too low-contrast to
            # read on *either* theme in practice — disabled-text roles
            # are deliberately muted for de-emphasis, not tuned for
            # legibility of text that must actually be read. A fixed
            # medium grey instead: roughly equidistant from both a
            # near-black and a near-white background, so it reads
            # clearly on both without needing to special-case per theme.
            # Confirmed via rendered mockups on both before landing here.
            # No font-size override — reported live as way too small
            # next to every other label in this dialog; just inherit the
            # same size as the rest, only the color is different.
            unavailable_label.setStyleSheet("color: #888888;")
            # addRow(label) (not addRow("", label)) — the two-argument
            # form put it in the value column, indented to the right of
            # an empty label column instead of starting flush left under
            # "Check spelling..." above it, reported live as looking
            # wrong. A single-argument row spans the widget across both
            # columns instead, same as the "Default note/font color:"
            # section headers above.
            form.addRow(unavailable_label)

        return tab

    def _on_pick_default_color(self, color: str):
        self._pending_color = color
        # Rebuild the grid so the checkmark moves to the newly picked swatch.
        old_widget = self._color_grid_layout.itemAt(0).widget()
        self._color_grid_layout.removeWidget(old_widget)
        old_widget.deleteLater()
        new_grid = build_color_swatch_grid(SWATCHES, color, self._on_pick_default_color)
        self._color_grid_layout.addWidget(new_grid)
        self._set_default_color_grid_dimmed(self.randomize_color_check.isChecked())

    def _on_toggle_randomize_color(self, checked: bool):
        # The fixed default color is meaningless while randomizing is on
        # (it's never used), so grey the swatch grid out rather than
        # leaving a picker that silently does nothing.
        self._set_default_color_grid_dimmed(checked)

    def _set_default_color_grid_dimmed(self, dimmed: bool):
        grid = self._color_grid_layout.itemAt(0).widget()
        grid.setEnabled(not dimmed)
        # setEnabled() alone stops clicks but each swatch's own QSS
        # (background-color per swatch) has no :disabled rule, so it
        # doesn't look any different — a QGraphicsOpacityEffect on the
        # whole grid actually makes "disabled" visible. A fresh effect
        # instance is needed each time since Qt only lets one widget own
        # a given QGraphicsOpacityEffect at a time, and _on_pick_default_color
        # replaces this grid widget outright on every swatch pick.
        if dimmed:
            effect = QGraphicsOpacityEffect(grid)
            effect.setOpacity(0.35)
            grid.setGraphicsEffect(effect)
        else:
            grid.setGraphicsEffect(None)

    def _on_pick_default_font_color(self, color: str):
        self._pending_font_color = color
        old_widget = self._font_color_grid_layout.itemAt(0).widget()
        self._font_color_grid_layout.removeWidget(old_widget)
        old_widget.deleteLater()
        self._font_color_grid_layout.addWidget(
            build_color_swatch_grid(FONT_SWATCHES, color, self._on_pick_default_font_color)
        )

    # -- Hotkey tab --------------------------------------------------------

    def _build_hotkey_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)

        # A combo already grabbed by a system-level shortcut (KWin's own
        # global shortcuts, in particular) never reaches this dialog at
        # all — the keypress is intercepted before X11 delivers it to any
        # app window, so the field below just stays empty and nothing
        # visibly happens. Reported live: Meta+Alt+R (Spectacle) and
        # Meta+Alt+S ("Toggle Screen Reader") both do this. No reliable
        # way to detect every such conflict ahead of time — KDE only
        # persists a *customized* global shortcut to
        # ~/.config/kglobalshortcutsrc, not its large set of unmodified
        # built-in defaults (confirmed directly: Meta+Alt+S was in that
        # file, Meta+Alt+R wasn't, despite both being live-grabbed) — so
        # this is a plain explanatory hint, not an automated check.
        hint_label = QLabel(
            "If pressing a combo does nothing in a field below, it's "
            "likely already grabbed by a system shortcut elsewhere — "
            "check System Settings → Shortcuts."
        )
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet("color: #888888;")
        form.addRow(hint_label)

        form.addRow(QLabel(""))  # spacer before the first hotkey section

        self.hotkey_edit, self.hotkey_clear_button, hotkey_test_btn, self.hotkey_status = (
            self._build_hotkey_row(form, "Global hotkey to create a new note:", self._settings.hotkey)
        )
        hotkey_test_btn.clicked.connect(self._test_hotkey)

        form.addRow(QLabel(""))  # spacer between hotkey sections

        (
            self.notes_browser_hotkey_edit,
            self.notes_browser_hotkey_clear_button,
            notes_browser_test_btn,
            self.notes_browser_hotkey_status,
        ) = self._build_hotkey_row(
            form, "Global hotkey to open the Notes Browser:", self._settings.notes_browser_hotkey
        )
        notes_browser_test_btn.clicked.connect(self._test_notes_browser_hotkey)

        form.addRow(QLabel(""))

        (
            self.show_hide_all_notes_hotkey_edit,
            self.show_hide_all_notes_hotkey_clear_button,
            show_hide_test_btn,
            self.show_hide_all_notes_hotkey_status,
        ) = self._build_hotkey_row(
            form,
            "Global hotkey to show/hide all notes:",
            self._settings.show_hide_all_notes_hotkey,
        )
        show_hide_test_btn.clicked.connect(self._test_show_hide_all_notes_hotkey)

        form.addRow(QLabel(""))

        (
            self.roll_all_notes_hotkey_edit,
            self.roll_all_notes_hotkey_clear_button,
            roll_test_btn,
            self.roll_all_notes_hotkey_status,
        ) = self._build_hotkey_row(
            form, "Global hotkey to roll up/down all notes:", self._settings.roll_all_notes_hotkey
        )
        roll_test_btn.clicked.connect(self._test_roll_all_notes_hotkey)

        form.addRow(QLabel(""))

        (
            self.bring_all_notes_to_front_hotkey_edit,
            self.bring_all_notes_to_front_hotkey_clear_button,
            bring_to_front_test_btn,
            self.bring_all_notes_to_front_hotkey_status,
        ) = self._build_hotkey_row(
            form,
            "Global hotkey to bring all notes to front:",
            self._settings.bring_all_notes_to_front_hotkey,
        )
        bring_to_front_test_btn.clicked.connect(self._test_bring_all_notes_to_front_hotkey)

        return tab

    def _build_hotkey_row(
        self, form: QFormLayout, label: str, current_value: str | None
    ) -> tuple[QKeySequenceEdit, QPushButton, QPushButton, QLabel]:
        """One hotkey's field + inline Clear button + Test button + status
        line, matching the layout every hotkey section in this tab uses.
        Returns the widgets rather than storing them directly, since the
        caller needs to keep the existing self.hotkey_edit/
        self.notes_browser_hotkey_edit/etc. attribute names other code
        (and tests) already reference by name."""
        form.addRow(QLabel(label))
        edit = QKeySequenceEdit(QKeySequence(current_value or ""))
        row = QHBoxLayout()
        row.addWidget(edit)
        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(edit.clear)
        row.addWidget(clear_button)
        form.addRow(row)

        test_button = QPushButton("Test")
        form.addRow(test_button)

        status = QLabel("")
        form.addRow(status)

        return edit, clear_button, test_button, status

    def _all_hotkey_edits(self) -> list[tuple[QKeySequenceEdit, str]]:
        return [
            (self.hotkey_edit, "New Note"),
            (self.notes_browser_hotkey_edit, "Notes Browser"),
            (self.show_hide_all_notes_hotkey_edit, "Show/Hide All Notes"),
            (self.roll_all_notes_hotkey_edit, "Roll Up/Down Notes"),
            (self.bring_all_notes_to_front_hotkey_edit, "Bring Notes on Top"),
        ]

    def _test_hotkey(self):
        self._test_hotkey_combo(self.hotkey_edit, self.hotkey_status, self._settings.hotkey)

    def _test_notes_browser_hotkey(self):
        self._test_hotkey_combo(
            self.notes_browser_hotkey_edit,
            self.notes_browser_hotkey_status,
            self._settings.notes_browser_hotkey,
        )

    def _test_show_hide_all_notes_hotkey(self):
        self._test_hotkey_combo(
            self.show_hide_all_notes_hotkey_edit,
            self.show_hide_all_notes_hotkey_status,
            self._settings.show_hide_all_notes_hotkey,
        )

    def _test_roll_all_notes_hotkey(self):
        self._test_hotkey_combo(
            self.roll_all_notes_hotkey_edit,
            self.roll_all_notes_hotkey_status,
            self._settings.roll_all_notes_hotkey,
        )

    def _test_bring_all_notes_to_front_hotkey(self):
        self._test_hotkey_combo(
            self.bring_all_notes_to_front_hotkey_edit,
            self.bring_all_notes_to_front_hotkey_status,
            self._settings.bring_all_notes_to_front_hotkey,
        )

    def _test_hotkey_combo(
        self,
        edit: QKeySequenceEdit,
        status: QLabel,
        current_value: str | None,
    ):
        sequence = edit.keySequence().toString()
        if not sequence:
            status.setText("Enter a key combination first")
            return
        try:
            key, modifiers = parse_shortcut(sequence)
        except ValueError:
            status.setText("Invalid combination")
            return

        # Testing the combo that's already this app's own live global
        # hotkey would always "fail" — the app's real HotkeyListener (in
        # NoteManager, unaffected by this dialog being open) still holds
        # that exact grab, so a second grab for the same combo always
        # conflicts with it. Reported live: clicking Test without
        # changing the field printed 4 "Hotkey combo unavailable for one
        # modifier-lock variant" warnings and showed "Already in use by
        # another app" — technically true but misleading, since the
        # "other app" is this one. Skip the redundant self-conflicting
        # grab entirely rather than let it report a false conflict.
        if current_value and (key, modifiers) == parse_shortcut(current_value):
            status.setText("This is already your current hotkey")
            self._stop_test_listener()
            return

        # Same idea, but against every *other* hotkey field in this same
        # dialog rather than this field's own current value — covers both
        # "matches another hotkey's already-committed combo" (which
        # NoteManager also still holds live while this dialog is open)
        # and "matches what you just typed into another field but
        # haven't tested/saved yet" in one comparison, since either way
        # this is what that field's widget shows right now. Five hotkeys
        # now share one combo space, so this checks all of them, not just
        # a single hardcoded "other" field.
        for other_edit, other_label in self._all_hotkey_edits():
            if other_edit is edit:
                continue
            other_sequence = other_edit.keySequence().toString()
            if not other_sequence:
                continue
            try:
                if (key, modifiers) == parse_shortcut(other_sequence):
                    status.setText(f"Same as the {other_label} hotkey — pick a different combination")
                    self._stop_test_listener()
                    return
            except ValueError:
                continue  # the other field's own invalid state isn't this check's concern

        status.setText("Testing…")
        self._stop_test_listener()
        self._test_listener = HotkeyListener(key, modifiers)
        self._test_listener.grab_succeeded.connect(lambda: self._on_test_success(status))
        self._test_listener.grab_failed.connect(lambda: self._on_test_failed(status))
        self._test_listener.start()

    def _on_test_success(self, status: QLabel):
        # The test grab is released immediately after checking (see
        # _stop_test_listener below), so this combo isn't actually reserved
        # yet — say so explicitly, since "Available" alone reads as if the
        # combo already works, when only clicking OK commits it.
        status.setText("✓ Available — click OK to use it")
        self._stop_test_listener()

    def _on_test_failed(self, status: QLabel):
        status.setText("✗ Already in use by another app")
        self._stop_test_listener()

    def _stop_test_listener(self):
        if self._test_listener is not None:
            self._test_listener.stop()
            self._test_listener = None

    # -- result --------------------------------------------------------

    def result_settings(self) -> Settings:
        return Settings(
            default_color=self._pending_color,
            randomize_new_note_color=self.randomize_color_check.isChecked(),
            default_always_on_top=self.always_on_top_check.isChecked(),
            default_font_size=self.font_size_spin.value(),
            default_font_color=self._pending_font_color,
            launch_at_login=self.launch_at_login_check.isChecked(),
            # An empty field commits as None ("no hotkey"), not a
            # fallback to the old value — the Clear button exists
            # specifically so this is reachable; before it existed, a
            # cleared-but-otherwise-untouched field had no way to mean
            # anything other than "leave the old combo alone".
            hotkey=self.hotkey_edit.keySequence().toString() or None,
            notes_browser_hotkey=self.notes_browser_hotkey_edit.keySequence().toString() or None,
            show_hide_all_notes_hotkey=(
                self.show_hide_all_notes_hotkey_edit.keySequence().toString() or None
            ),
            roll_all_notes_hotkey=self.roll_all_notes_hotkey_edit.keySequence().toString() or None,
            bring_all_notes_to_front_hotkey=(
                self.bring_all_notes_to_front_hotkey_edit.keySequence().toString() or None
            ),
            spell_check_enabled=self.spell_check_check.isChecked(),
            # No UI for these (yet) — carry them through unchanged rather
            # than silently resetting them to their dataclass defaults,
            # which building a brand-new Settings() here would otherwise
            # do to any field this dialog doesn't have a control for.
            notes_browser_x=self._settings.notes_browser_x,
            notes_browser_y=self._settings.notes_browser_y,
            notes_browser_w=self._settings.notes_browser_w,
            notes_browser_h=self._settings.notes_browser_h,
            settings_dialog_x=self._settings.settings_dialog_x,
            settings_dialog_y=self._settings.settings_dialog_y,
            settings_dialog_w=self._settings.settings_dialog_w,
            settings_dialog_h=self._settings.settings_dialog_h,
        )

    def closeEvent(self, event):
        self._stop_test_listener()
        super().closeEvent(event)
