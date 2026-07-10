from __future__ import annotations

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

from .hotkey import HotkeyListener, parse_shortcut
from .models import FONT_SWATCHES, SWATCHES, Settings
from .widgets import build_color_swatch_grid


class SettingsDialog(QDialog):
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

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

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
            # No UI for these (yet) — carry them through unchanged rather
            # than silently resetting them to their dataclass defaults,
            # which building a brand-new Settings() here would otherwise
            # do to any field this dialog doesn't have a control for.
            notes_browser_x=self._settings.notes_browser_x,
            notes_browser_y=self._settings.notes_browser_y,
            notes_browser_w=self._settings.notes_browser_w,
            notes_browser_h=self._settings.notes_browser_h,
        )

    def closeEvent(self, event):
        self._stop_test_listener()
        super().closeEvent(event)
