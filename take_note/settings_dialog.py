from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGraphicsOpacityEffect,
    QKeySequenceEdit,
    QLabel,
    QPushButton,
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

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)
        tabs.addTab(self._build_general_tab(), "General")
        tabs.addTab(self._build_hotkey_tab(), "Hotkey")

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
        else:
            # No saved geometry (first ever run, or a fresh Settings) —
            # confirmed directly that Qt's own default first-show size
            # here is noticeably smaller than sizeHint() (e.g. 426x637
            # vs. a true 695x666), clipping content at the bottom rather
            # than growing to fit it. Only matters once content is tall
            # enough to hit that gap, which is exactly what exposed it:
            # the spell-check-unavailable label below wrapped to 3 lines.
            self.resize(self.sizeHint())
        if self._settings.settings_dialog_x is not None and self._settings.settings_dialog_y is not None:
            self.move(self._settings.settings_dialog_x, self._settings.settings_dialog_y)

    def moveEvent(self, event):
        super().moveEvent(event)
        self._settings.settings_dialog_x, self._settings.settings_dialog_y = self.x(), self.y()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._settings.settings_dialog_w, self._settings.settings_dialog_h = self.width(), self.height()

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
            form.addRow("", unavailable_label)

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

        form.addRow(QLabel("Global hotkey to create a new note:"))
        self.hotkey_edit = QKeySequenceEdit(QKeySequence(self._settings.hotkey))
        form.addRow(self.hotkey_edit)

        test_button = QPushButton("Test")
        test_button.clicked.connect(self._test_hotkey)
        form.addRow(test_button)

        self.hotkey_status = QLabel("")
        form.addRow(self.hotkey_status)

        return tab

    def _test_hotkey(self):
        sequence = self.hotkey_edit.keySequence().toString()
        if not sequence:
            self.hotkey_status.setText("Enter a key combination first")
            return
        try:
            key, modifiers = parse_shortcut(sequence)
        except ValueError:
            self.hotkey_status.setText("Invalid combination")
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
        if (key, modifiers) == parse_shortcut(self._settings.hotkey):
            self.hotkey_status.setText("This is already your current hotkey")
            self._stop_test_listener()
            return

        self.hotkey_status.setText("Testing…")
        self._stop_test_listener()
        self._test_listener = HotkeyListener(key, modifiers)
        self._test_listener.grab_succeeded.connect(self._on_test_success)
        self._test_listener.grab_failed.connect(self._on_test_failed)
        self._test_listener.start()

    def _on_test_success(self):
        # The test grab is released immediately after checking (see
        # _stop_test_listener below), so this combo isn't actually reserved
        # yet — say so explicitly, since "Available" alone reads as if the
        # combo already works, when only clicking OK commits it.
        self.hotkey_status.setText("✓ Available — click OK to use it")
        self._stop_test_listener()

    def _on_test_failed(self):
        self.hotkey_status.setText("✗ Already in use by another app")
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
            hotkey=self.hotkey_edit.keySequence().toString() or self._settings.hotkey,
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
