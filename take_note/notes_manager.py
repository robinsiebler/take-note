from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .note_window import get_menu_qss
from .x11_wm import set_skip_taskbar

REFRESH_DEBOUNCE_MS = 500

ALL_NOTES = "__all__"
UNFILED = "__unfiled__"
TAG_PREFIX = "tag:"
TRASH = "__trash__"


def _format_modified(iso_timestamp: str) -> str:
    """note.modified_at is a full ISO-8601 string with microseconds and a
    UTC offset — far too wide for a table column, and not the US date
    convention the user wants displayed here.

    Regression, reported live: this displayed "07:11 PM" when the actual
    local wall-clock time was 12:33 PM. datetime.fromisoformat() on a
    string with a UTC offset produces a timezone-*aware* datetime still
    set to UTC — strftime() formats whatever fields that object holds
    without converting them, so the raw UTC hour/minute got displayed
    mislabeled as if they were already local time. astimezone() with no
    argument converts an aware datetime to the system's local timezone
    first."""
    try:
        return datetime.fromisoformat(iso_timestamp).astimezone().strftime("%B %d, %Y %I:%M %p")
    except ValueError:
        return iso_timestamp


class _DateTableWidgetItem(QTableWidgetItem):
    """"Month Day, Year" doesn't sort correctly as plain text (e.g.
    "January" > "February" alphabetically) — sorts by the underlying ISO
    timestamp instead, which stays chronological, while still displaying
    the US-formatted string."""

    def __init__(self, iso_timestamp: str):
        super().__init__(_format_modified(iso_timestamp))
        self._sort_key = iso_timestamp

    def __lt__(self, other):
        if isinstance(other, _DateTableWidgetItem):
            return self._sort_key < other._sort_key
        return super().__lt__(other)


class NotesManagerWindow(QWidget):
    """A tree of Notepad boards + a sortable, searchable list of every
    note, so a note pinned to some board (or just left on the desktop)
    can actually be found again. Deliberately plain, natively-decorated
    Qt chrome (unlike NoteWindow/NotepadWindow's custom frameless look)
    — this is a utility/document window, not a sticky note."""

    def __init__(self, manager):
        super().__init__(None)
        self.manager = manager
        # Not "Take Note! — Notes Manager" — every other window in this
        # app (Settings, Stick to Window, Delete Note, ...) just sets its
        # own plain descriptive title and lets the OS/WM append " — Take
        # Note!" automatically (same behavior already confirmed for
        # dialog titles when sizing them). This was the one outlier still
        # including the app name itself, rendering as a visibly
        # duplicated "Take Note! — Notes Manager — Take Note!" title bar
        # — caught via a live screenshot from test case 8.8.
        self.setWindowTitle("Notes Manager")

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(REFRESH_DEBOUNCE_MS)
        self._refresh_timer.timeout.connect(self._refresh)

        self._build_ui()
        self._refresh()
        self._restore_geometry()

        manager.notes_changed.connect(self._schedule_refresh)
        self.show()
        # The only Take Note! window that didn't already skip the taskbar
        # (notes/boards both do, via the same helper) — confirmed this was
        # the window Plasma's Task Manager mislabeled with an unrelated
        # app's icon (a real, upstream-confirmed KDE bug, not fixable from
        # here). With a dedicated global hotkey to reopen it (see
        # NoteManager._start_notes_manager_hotkey_listener), there's no
        # remaining need for taskbar/Alt-Tab reachability, so hiding it
        # removes the only window Plasma had left to mislabel.
        set_skip_taskbar(int(self.winId()), True)

    def _restore_geometry(self):
        settings = self.manager.settings
        # Wider than a bare 700 now that the table has grown from 2
        # columns (Title/Date Modified) to 4 (+ Preview/Notepad) — 700
        # left Preview too cramped to show more than a few characters.
        self.resize(settings.notes_browser_w or 900, settings.notes_browser_h or 450)
        if settings.notes_browser_x is not None and settings.notes_browser_y is not None:
            self.move(settings.notes_browser_x, settings.notes_browser_y)

    def moveEvent(self, event):
        super().moveEvent(event)
        settings = self.manager.settings
        settings.notes_browser_x, settings.notes_browser_y = self.x(), self.y()
        self.manager._schedule_save()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        settings = self.manager.settings
        settings.notes_browser_w, settings.notes_browser_h = self.width(), self.height()
        self.manager._schedule_save()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search notes…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._apply_filter)
        layout.addWidget(self.search_edit)

        splitter = QSplitter(Qt.Horizontal)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.currentItemChanged.connect(lambda *_: self._apply_filter())
        self.tree.itemDoubleClicked.connect(self._open_board_from_tree)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_tree_context_menu)
        splitter.addWidget(self.tree)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QHBoxLayout()
        new_note_btn = QPushButton("New Note")
        new_note_btn.clicked.connect(self._create_note)
        toolbar.addWidget(new_note_btn)

        new_board_btn = QPushButton("New Notepad")
        new_board_btn.clicked.connect(lambda: self.manager.create_board())
        toolbar.addWidget(new_board_btn)

        # Label/behavior both switch based on the Trash node's own
        # docstring/history above: Delete means Move to Trash everywhere
        # except while actually viewing Trash, where it's the only place
        # a permanent delete is reachable at all. See _update_toolbar().
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._delete_selected_notes)
        toolbar.addWidget(self.delete_btn)

        self.restore_btn = QPushButton("Restore")
        self.restore_btn.clicked.connect(self._restore_selected_notes)
        self.restore_btn.hide()  # only meaningful while viewing Trash
        toolbar.addWidget(self.restore_btn)

        toolbar.addStretch()
        right_layout.addLayout(toolbar)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Title", "Preview", "Notepad", "Date Modified", "Tags"])
        # Sorting must be enabled before sectionSizeHint() is read below —
        # the hint only reserves room for the sort-indicator arrow once
        # the header actually shows one, so computing it before this line
        # silently undercounts by the arrow's width.
        self.table.setSortingEnabled(True)
        # Title is Interactive (not Stretch) with a modest fixed starting
        # width — Preview is the column actually meant to distinguish
        # untitled notes, so it gets all the leftover space instead of
        # splitting evenly with Title and ending up too narrow to show
        # anything useful.
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.setColumnWidth(0, 140)
        # Title being Interactive (user-draggable) meant dragging it wide
        # enough could squeeze the Stretch'd Preview column below the
        # width its own header text + sort-indicator arrow need to fit —
        # reproduced live by sorting other columns a few times, then
        # sorting by Preview: its header clipped to "review", the
        # leading "P" cut clean off. Ask the header for what it actually
        # needs (sectionSizeHint, which accounts for the real runtime
        # font and the indicator arrow's reserved space) rather than a
        # hardcoded guess — a prior fix hardcoded 90px, which happened to
        # match the *offscreen* test platform's narrower fallback font
        # but undershot the real desktop font (122px under real xcb/Noto
        # Sans), so it clipped live despite tests passing.
        self.table.horizontalHeader().setMinimumSectionSize(
            self.table.horizontalHeader().sectionSizeHint(1)
        )
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.doubleClicked.connect(self._open_selected_note)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_table_context_menu)
        right_layout.addWidget(self.table)

        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, stretch=1)

    # -- refresh -----------------------------------------------------------

    def _schedule_refresh(self):
        self._refresh_timer.start()

    def _refresh(self):
        selected_id = self._current_tree_filter()

        self.tree.blockSignals(True)
        self.tree.clear()

        all_item = QTreeWidgetItem(["All Notes"])
        all_item.setData(0, Qt.UserRole, ALL_NOTES)
        self.tree.addTopLevelItem(all_item)

        unfiled_item = QTreeWidgetItem(["Unfiled"])
        unfiled_item.setData(0, Qt.UserRole, UNFILED)
        self.tree.addTopLevelItem(unfiled_item)

        restored_selection = None
        for board_window in self.manager.boards.values():
            board_item = QTreeWidgetItem([board_window.board.name])
            board_item.setData(0, Qt.UserRole, board_window.board.id)
            self.tree.addTopLevelItem(board_item)
            if board_window.board.id == selected_id:
                restored_selection = board_item

        # Computed fresh from live note data every refresh rather than a
        # separate tag registry — a tag exists implicitly as long as at
        # least one *active* (non-trashed) note still uses it, and
        # disappears from here the moment none do, matching the
        # fully-free-form vocabulary decision (no predefined/managed tag
        # list). Trashed notes' tags don't count — a tag orphaned only by
        # trashing shouldn't linger here as if it were still in use.
        all_tags = sorted(
            {
                tag
                for nw in self.manager.notes.values()
                if nw.note.deleted_at is None
                for tag in nw.note.tags
            }
        )
        if all_tags:
            tags_item = QTreeWidgetItem(["Tags"])
            # Not selectable — it has no natural "show notes with any
            # tag" filtering meaning of its own, only its children do.
            tags_item.setFlags(tags_item.flags() & ~Qt.ItemIsSelectable)
            self.tree.addTopLevelItem(tags_item)
            for tag in all_tags:
                tag_item = QTreeWidgetItem([tag])
                tag_data = TAG_PREFIX + tag
                tag_item.setData(0, Qt.UserRole, tag_data)
                tags_item.addChild(tag_item)
                if tag_data == selected_id:
                    restored_selection = tag_item
            tags_item.setExpanded(True)

        # Always present (unlike Tags, which only exists when at least
        # one tag is in use) — Trash is a structural concept, not
        # data-derived, so it should be as reliably findable as All
        # Notes/Unfiled even when empty.
        trash_item = QTreeWidgetItem(["Trash"])
        trash_item.setData(0, Qt.UserRole, TRASH)
        self.tree.addTopLevelItem(trash_item)
        if selected_id == TRASH:
            restored_selection = trash_item

        if restored_selection is not None:
            self.tree.setCurrentItem(restored_selection)
        elif selected_id == UNFILED:
            self.tree.setCurrentItem(unfiled_item)
        else:
            self.tree.setCurrentItem(all_item)

        self.tree.blockSignals(False)
        self._apply_filter()

    def _current_tree_filter(self) -> str:
        item = self.tree.currentItem()
        if item is None:
            return ALL_NOTES
        return item.data(0, Qt.UserRole)

    def _notes_for_current_selection(self):
        board_filter = self._current_tree_filter()
        notes = list(self.manager.notes.values())
        if board_filter == TRASH:
            return [nw for nw in notes if nw.note.deleted_at is not None]
        # Every other view excludes trashed notes — Trash is deliberately
        # separate from normal browsing, not just another filter.
        notes = [nw for nw in notes if nw.note.deleted_at is None]
        if board_filter == ALL_NOTES:
            return notes
        if board_filter == UNFILED:
            return [nw for nw in notes if nw.note.board_id is None]
        if isinstance(board_filter, str) and board_filter.startswith(TAG_PREFIX):
            tag = board_filter[len(TAG_PREFIX):]
            return [nw for nw in notes if tag in nw.note.tags]
        return [nw for nw in notes if nw.note.board_id == board_filter]

    def _apply_filter(self):
        in_trash = self._current_tree_filter() == TRASH
        self._update_toolbar(in_trash)

        query = self.search_edit.text().strip().lower()
        note_windows = self._notes_for_current_selection()
        if query:
            note_windows = [nw for nw in note_windows if self._matches_query(nw, query)]

        # "Date Deleted" while viewing Trash — deleted_at is guaranteed
        # set for every note _notes_for_current_selection() returns here,
        # since the TRASH branch only ever returns notes where it's set.
        date_header = "Date Deleted" if in_trash else "Date Modified"
        self.table.setHorizontalHeaderItem(3, QTableWidgetItem(date_header))

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(note_windows))
        for row, note_window in enumerate(note_windows):
            note = note_window.note
            title_item = QTableWidgetItem(note.title or "(untitled)")
            title_item.setData(Qt.UserRole, note.id)
            self.table.setItem(row, 0, title_item)
            self.table.setItem(row, 1, QTableWidgetItem(self._preview_text(note_window)))
            self.table.setItem(row, 2, QTableWidgetItem(self._board_name(note)))
            date_value = note.deleted_at if in_trash else note.modified_at
            self.table.setItem(row, 3, _DateTableWidgetItem(date_value))
            self.table.setItem(row, 4, QTableWidgetItem(", ".join(note.tags)))
        self.table.setSortingEnabled(True)

    def _update_toolbar(self, in_trash: bool):
        self.delete_btn.setText("Delete Permanently" if in_trash else "Delete")
        self.restore_btn.setVisible(in_trash)

    @staticmethod
    def _preview_text(note_window, limit: int = 60) -> str:
        # The only way to tell two untitled notes apart in this table —
        # collapse to one line so a multi-paragraph note doesn't turn a
        # table row into several visual lines.
        snippet = " ".join(note_window.body.toPlainText().split())
        if len(snippet) > limit:
            return snippet[:limit].rstrip() + "…"
        return snippet

    def _board_name(self, note) -> str:
        if note.board_id is None:
            return ""
        board_window = self.manager.boards.get(note.board_id)
        return board_window.board.name if board_window is not None else ""

    @staticmethod
    def _matches_query(note_window, query: str) -> bool:
        if query in note_window.note.title.lower():
            return True
        return query in note_window.body.toPlainText().lower()

    # -- toolbar actions -----------------------------------------------------

    def _create_note(self):
        board_filter = self._current_tree_filter()
        if board_filter in (ALL_NOTES, UNFILED):
            self.manager.create_note()
        else:
            board_window = self.manager.boards.get(board_filter)
            self.manager.create_note(board=board_window)

    def _selected_note_window(self):
        note_windows = self._selected_note_windows()
        return note_windows[0] if note_windows else None

    def _selected_note_windows(self):
        rows = self.table.selectionModel().selectedRows()
        note_windows = []
        for row in rows:
            note_id = self.table.item(row.row(), 0).data(Qt.UserRole)
            note_window = self.manager.notes.get(note_id)
            if note_window is not None:
                note_windows.append(note_window)
        return note_windows

    def _open_selected_note(self):
        note_window = self._selected_note_window()
        # A trashed note is deliberately hidden until restored (see
        # NoteManager.trash_note) — showing it here as a side effect of
        # double-clicking its Trash row would leave it in a confusing
        # half-restored state (visible again, but note.deleted_at still
        # set), so this is a no-op while viewing Trash. Use Restore.
        if note_window is None or note_window.note.deleted_at is not None:
            return
        # showNormal(), not show() — see NoteManager.open_notes_manager's
        # own comment on why show() alone can't recover a minimized window.
        note_window.showNormal()
        note_window.raise_()
        note_window.activateWindow()

    def _delete_selected_notes(self):
        note_windows = self._selected_note_windows()
        if not note_windows:
            return
        if self._current_tree_filter() == TRASH:
            self._confirm_and_delete_permanently(note_windows)
        else:
            self._confirm_and_trash(note_windows)

    def _restore_selected_notes(self):
        self._restore_note_windows(self._selected_note_windows())

    def _restore_note_windows(self, note_windows):
        for note_window in note_windows:
            self.manager.restore_note(note_window)

    def _confirm_and_trash(self, note_windows):
        if len(note_windows) == 1:
            question = "Move this note to Trash?"
        else:
            question = f"Move these {len(note_windows)} notes to Trash?"
        reply = QMessageBox.question(
            self, "Move to Trash", question, QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            for note_window in note_windows:
                self.manager.trash_note(note_window)

    def _confirm_and_delete_permanently(self, note_windows):
        if len(note_windows) == 1:
            question = "Delete this note permanently? This cannot be undone."
        else:
            question = f"Delete these {len(note_windows)} notes permanently? This cannot be undone."
        reply = QMessageBox.question(
            self, "Delete Permanently", question, QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            for note_window in note_windows:
                self.manager.delete_note(note_window)

    # -- context menus -----------------------------------------------------

    def _show_table_context_menu(self, pos):
        note_windows = self._selected_note_windows()
        if not note_windows:
            return

        menu = QMenu(self)
        menu.setStyleSheet(get_menu_qss())

        if self._current_tree_filter() == TRASH:
            if len(note_windows) == 1:
                restore_action = menu.addAction("Restore")
            else:
                restore_action = menu.addAction(f"Restore {len(note_windows)} Notes")
            restore_action.triggered.connect(lambda: self._restore_note_windows(note_windows))

            menu.addSeparator()
            if len(note_windows) == 1:
                delete_action = menu.addAction("Delete Permanently")
            else:
                delete_action = menu.addAction(f"Delete {len(note_windows)} Notes Permanently")
            delete_action.triggered.connect(lambda: self._confirm_and_delete_permanently(note_windows))
        else:
            if len(note_windows) == 1:
                note_window = note_windows[0]
                show_action = menu.addAction("Show Note")
                show_action.triggered.connect(self._open_selected_note)

                if note_window.note.board_id is not None:
                    remove_action = menu.addAction("Remove from Notepad")
                    remove_action.triggered.connect(
                        lambda: self.manager.detach_note_from_board(note_window)
                    )

                menu.addSeparator()
                delete_action = menu.addAction("Move to Trash")
            else:
                delete_action = menu.addAction(f"Move {len(note_windows)} Notes to Trash")
            delete_action.triggered.connect(lambda: self._confirm_and_trash(note_windows))

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _show_tree_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if item is None:
            return
        board_id = item.data(0, Qt.UserRole)
        if board_id in (ALL_NOTES, UNFILED):
            return
        board_window = self.manager.boards.get(board_id)
        if board_window is None:
            return

        menu = QMenu(self)
        menu.setStyleSheet(get_menu_qss())

        rename_action = menu.addAction("Rename")
        rename_action.triggered.connect(board_window.rename)

        delete_action = menu.addAction("Delete Notepad")
        delete_action.triggered.connect(board_window.confirm_delete)

        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _open_board_from_tree(self, item, _column):
        board_id = item.data(0, Qt.UserRole)
        if board_id in (ALL_NOTES, UNFILED):
            return
        board_window = self.manager.boards.get(board_id)
        if board_window is None:
            return
        # showNormal(), not show() — see NoteManager.open_notes_manager's
        # own comment on why show() alone can't recover a minimized window.
        board_window.showNormal()
        board_window.raise_()
        board_window.activateWindow()
