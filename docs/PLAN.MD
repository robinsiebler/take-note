> Original implementation plan approved before writing any code (2026-07-06), preserved
> here for historical reference (paths below updated to the project's current
> `take_note`/`take-note` naming). See the README for current setup instructions and the
> actual package layout. Several items below (Memoboard, hotkey defaults, window flags)
> evolved during implementation; this document reflects the plan as approved, not
> necessarily the final shipped behavior.

# Take Note! — MVP Implementation Plan

## Context

Linux has no good desktop sticky notes app in the same vein as the polished options
available on Windows. This is a brand-new project (the project directory currently
contains only an empty `.gitignore`). Goal: build a first working version,
scoped to two features the user picked as MVP:

1. **Basic sticky notes** — create/edit/delete colored notes with rich-text bodies,
   always-on-top, freely movable/resizable, persisted across restarts. Includes a
   fixed background-color swatch row per note (not a full custom color picker for v1).
2. **Tray icon + global hotkey** — a system tray menu to create notes/quit, plus a
   global keyboard shortcut to spawn a new note from anywhere.
3. **Memoboard** — a corkboard-style container window that groups multiple notes
   together as one unit: notes placed on a board show/hide/move together with it,
   closely matching how polished sticky-note apps handle grouped notes (see
   dedicated section below).

Explicitly out of scope for this pass: note-list/search window, reminders/alarms,
cloud sync, checklists (see note below on why), settings UI, full custom color picker,
drag-and-drop of notes onto a Memoboard (v1 uses a context-menu action instead — see below).

**Stack decisions already locked in with the user:**
- **Python + PySide6 (Qt6)** — chosen over GTK4 because `QTextEdit`/`QTextDocument`
  gives rich-text editing (bold/italic/color, embedded images, real hyperlinks) with far
  less custom code than GTK4's `GtkTextView` would need for the same result.
- User runs **KDE Plasma on Wayland**. Core Wayland protocol doesn't let a client
  position its own top-level window (compositor owns placement), which breaks
  "remember each note's position" and complicates always-on-top. Fix: force the app to
  run via **XWayland** by setting `QT_QPA_PLATFORM=xcb` before `QApplication` is
  constructed. Under `xcb`, Qt's `WindowStaysOnTopHint` maps straight to the EWMH
  `_NET_WM_STATE_ABOVE` hint, which KWin honors reliably — no native-Wayland
  layer-shell/portal work needed for v1. This is a deliberate simplicity tradeoff,
  documented as a known limitation if the user later moves off KDE/X11-compatible setups.

This plan was cross-checked with a Plan sub-agent for the two trickiest parts (global
hotkey mechanism, window flags for frameless always-on-top notes) — its recommendations
are incorporated below.

## Project layout

```
take_note/
  pyproject.toml                 # PySide6 + python-xlib deps, console-script entry point
  README.md                      # setup/run instructions, known Wayland/XWayland caveat
  take_note/
    __init__.py
    __main__.py                  # sets QT_QPA_PLATFORM=xcb BEFORE importing PySide6, bootstraps app
    app.py                       # QApplication setup, NoteManager, TrayIcon, HotkeyListener wiring
    models.py                    # Note dataclass
    storage.py                   # JSON persistence (XDG data dir), atomic writes
    note_window.py               # NoteWindow widget: frameless, always-on-top, draggable/resizable, rich text
    board_window.py              # MemoboardWindow: corkboard container hosting embedded NoteWindows
    tray.py                      # QSystemTrayIcon + context menu
    hotkey.py                    # global hotkey via python-xlib XGrabKey
  tests/
    test_storage.py              # round-trip / missing-file / corrupt-file tests (no GUI needed)
```

## Key implementation details

**`models.py`** — `Note` dataclass: `id` (uuid4 hex), `html` (body content), `color`
(hex string, from the fixed swatch palette), `x/y/w/h` (int geometry),
`always_on_top: bool = True`, `board_id: str | None = None`, `created_at` /
`modified_at` (ISO8601 strings). Include `always_on_top` from day one since the planned
context-menu toggle needs it to survive a restart. **Coordinate space depends on
`board_id`**: when `None`, `x/y` are global screen coordinates (standalone top-level
note); when set, `x/y` are coordinates relative to that board's canvas.

`Board` dataclass: `id` (uuid4 hex), `name` (str, e.g. "Work"), `color` (hex, canvas
background), `x/y/w/h` (int, the board window's own screen geometry),
`created_at`/`modified_at`.

**`storage.py`** — Single JSON file at `$XDG_DATA_HOME/take-note/notes.json`
(fallback `~/.local/share/take-note/notes.json`), now holding both `notes` and
`boards` top-level lists. `save_all(notes, boards, path=<default>)` and
`load_all(path=<default>) -> (notes, boards)`, both taking an explicit `path` param
(defaults to the real XDG path) so tests can point at a tmp dir without env
monkeypatching. Atomic write: write to a temp file in the same directory, then
`os.replace`. `load_all` must tolerate a missing file (return `([], [])`) and a corrupt
file (catch the JSON error, back up the bad file, return `([], [])`, log a warning)
rather than crashing on startup.

**`note_window.py`** — `NoteWindow(QWidget)`:
- Window flags set once in `__init__`, before first `show()`:
  `Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint`. Use `Qt.Tool` (not
  `Qt.Window`) so notes don't clutter the taskbar/alt-tab — Qt maps `Tool` toward a
  utility window type KWin filters out of the taskbar by default.
- Custom colored header strip (~24px) as the drag handle, since a frameless window has
  no native title bar. The header stores a direct reference to its owning `NoteWindow`
  (`header.note_window = self`, set in `NoteWindow.__init__`) rather than using
  `self.window()` — `mousePressEvent` records `globalPosition() - note_window.pos()`,
  `mouseMoveEvent` calls `note_window.move(globalPosition() - offset)`. **This matters
  once Memoboard exists**: `QWidget.move()` is relative to whatever the widget's actual
  parent is, so this same call correctly moves a standalone note on the screen *or*
  repositions an embedded note within its board's canvas — but `self.window()` would
  resolve to the *board's* top-level window once a note is reparented into a board
  (since `window()` walks up to the nearest top-level ancestor), silently turning a
  note-drag into a board-drag. Storing the direct reference avoids that trap.
- Resize via a plain `QSizeGrip` in the bottom-right corner — skip hand-rolled edge-drag
  hit-testing for v1.
- Body is a `QTextEdit`, persisted via `toHtml()`/`setHtml()`. Small fixed toolbar:
  bold/italic/underline + a fixed color swatch row — all native `QTextEdit` convenience
  methods (`setFontWeight`, `setTextColor`, etc.), genuinely free. **Checklists are
  explicitly deferred post-MVP** — `QTextEdit` has no native interactive checkbox list
  item; building one needs a custom `QTextObjectInterface` or hit-tested Unicode
  checkboxes, which is real custom work, not "free" like the rest of the formatting.
- Right-click context menu: color swatches, always-on-top toggle, delete, plus a
  Memoboard submenu — "Add to Memoboard ▸" (lists existing boards + "New Memoboard…")
  when standalone, or "Remove from Memoboard" when already embedded in one.
- On any content/geometry/color/board-membership change, emit a `changed` signal
  upward — **do not** give each `NoteWindow` its own debounce timer (N notes writing the
  same JSON file independently is wasteful and makes save timing hard to reason about).

**`board_window.py`** — `MemoboardWindow(QWidget)`, the corkboard container:
- Similar top-level treatment to `NoteWindow` (`Qt.Tool | Qt.FramelessWindowHint`, own
  colored header strip with the board's name + a drag handle using the same
  direct-reference pattern as notes), but **not** forced always-on-top by default —
  boards behave like a window you open/close, not a pinned overlay.
- Body is a plain canvas `QWidget` (optionally inside a `QScrollArea` if boards can grow
  larger than their visible window) where member notes are placed via absolute
  `move(x, y)` positioning, `x/y` being canvas-relative per the model above. Resizable
  via `QSizeGrip` like notes.
- **Reparenting mechanics** (the trickiest new part, so spelled out explicitly): to add
  a standalone `NoteWindow` to a board, call `note.setParent(board.canvas)`, then
  `note.setWindowFlags(Qt.Widget)` (clears the top-level tool/frameless/on-top flags —
  a widget's window flags only take effect when it has no parent), then `note.move(x, y)`
  to its canvas position, then `note.show()` (reparenting implicitly hides the widget;
  it must be explicitly shown again). To remove a note from a board (send back to the
  desktop): `note.setParent(None)`, restore
  `note.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)`,
  `note.move(<last known or offset desktop position>)`, `note.show()`. Do this reparenting
  in a single `NoteWindow.attach_to_board(board_or_none)` method so the flag/parent/show
  sequencing lives in one place rather than being duplicated at each call site.
- Right-click on empty canvas area: "Rename Board", "New Note on this Board" (creates a
  note pre-attached to this board), "Delete Board".
- **Deleting a board** pops all member notes back to the standalone desktop (via the
  same `attach_to_board(None)` path, cascading their positions near the board's last
  screen location) rather than deleting the notes themselves — safer default, avoids
  silent data loss from what looks like closing a window.

**`app.py`** — `NoteManager` owns `notes: dict[id, NoteWindow]`, `boards: dict[id,
MemoboardWindow]`, and **one shared** single-shot debounce `QTimer` (~800ms, restarted
on any note's or board's `changed` signal) that calls `storage.save_all()` once.
Methods: `create_note(color=default, board=None)`, `delete_note(id)`,
`create_board(name)`, `delete_board(id)`, `load_from_disk()` (called once at startup —
**boards first, then notes**, so each note's board canvas already exists when a note
with a `board_id` needs to be parented into it), `save_all()`. Call
`QApplication.setQuitOnLastWindowClosed(False)` — required so the tray-resident app
doesn't quit when the last note/board window closes.

**`tray.py`** — `QSystemTrayIcon` with menu: "New Note", "New Memoboard", "Quit" (no
"Show All" — nothing in MVP scope needs a hidden/shown-notes concept beyond what boards
already provide). Left-click (`activated` signal) also triggers "New Note" as a
convenience, matching common sticky-note UX.

**`hotkey.py`** — Raw `python-xlib` + `XGrabKey`, **not** a wrapper library:
- Rejected `pynput` (hooks the X11 record extension = watches every keystroke system-wide,
  keylogger-shaped just to catch one combo), `keyboard` (needs raw `/dev/input`/root on
  Linux), and `system_hotkey` (has an open bug where grab-failure errors don't propagate
  across its background thread — exactly the failure mode that matters when a combo is
  already taken).
- `HotkeyListener(QThread)` with a `triggered = Signal()`. In `run()`: open an
  `Xlib.display.Display()` (connects via XWayland), grab the keycode for the chosen
  combo (default `Ctrl+Alt+N`) on the root window **once per NumLock/CapsLock/ScrollLock
  modifier-bit combination** (X won't deliver the event if an ignored lock bit is set
  otherwise), via `root.grab_key(...)` inside a try/except `BadAccess` (combo already
  owned by something else — log and continue with whichever variants succeeded; emit a
  `grabFailed` signal if none succeed at all).
- Do **not** block on `next_event()` for shutdown — poll `display.pending_events()` in a
  loop with a short `time.sleep(0.05)`, checking a `_stop` flag, so `stop()` (called from
  `app.aboutToQuit`) can actually return promptly instead of hanging on a blocking call.
- Connect `hotkey.triggered.connect(note_manager.create_note)` directly — since the
  signal is emitted from the worker thread but the slot lives on a main-thread object,
  Qt auto-delivers it as a queued connection. No manual mutex/marshaling needed.

**`__main__.py`** — set `os.environ["QT_QPA_PLATFORM"] = "xcb"` as the very first line,
before any `PySide6` import, then construct `QApplication`, wire up `NoteManager`,
`TrayIcon`, `HotkeyListener`, call `load_from_disk()`, `app.exec()`.

**`pyproject.toml`** — deps `PySide6`, `python-xlib`; `[project.scripts]
take-note = "take_note.__main__:main"`; setuptools or hatchling backend.

## Verification

**Automated** (`tests/test_storage.py`, no GUI needed): round-trip save/load of a list
of `Note`s and `Board`s (including a note with `board_id` set); `load_all` on a missing
file returns `([], [])`; `load_all` on a corrupt file returns `([], [])` without raising.

**Manual checklist** (run once the app launches, since GUI automation isn't practical
for a first pass):
1. Launch with no `notes.json` — tray icon appears, no notes open, no extra taskbar entry.
2. Press the global hotkey while focus is on a different app (e.g. a terminal) — a new
   blank note appears, focused, on top.
3. Type formatted text (bold/italic/color) in a note; drag it by its header strip;
   resize via the `QSizeGrip` corner.
4. Right-click → change color (header + body update) → toggle always-on-top off →
   alt-tab through other windows to confirm it no longer stays above.
5. Close (delete) a note — confirm it doesn't reappear after restart.
6. Open 2-3 notes, quit via tray "Quit", relaunch — confirm all notes reappear at their
   exact prior position/size/color/text/always-on-top state.
7. `kill -9` the process mid-edit, relaunch — confirm `notes.json` isn't corrupted (last
   <800ms of unsaved keystrokes may be lost — acceptable, known MVP tradeoff).
8. Confirm the hotkey fires both with a note focused and with no Qt window focused at
   all (validates the grab is truly global).
9. Create a Memoboard, attach two standalone notes to it via their context menus —
   confirm both notes now appear positioned within the board canvas. Move the board —
   confirm both notes move with it. Hide/close the board — confirm both notes disappear
   with it, and reappear when the board is reopened.
10. "Remove from Memoboard" one of the notes — confirm it pops back to a standalone,
    always-on-top desktop note. Delete the board with one note still on it — confirm
    that note pops back to the desktop rather than being deleted.
11. Quit and relaunch — confirm boards reappear at their prior position/size with the
    correct notes still embedded at their correct canvas-relative positions, and any
    standalone notes remain standalone.

## Critical files
- `take_note/hotkey.py` — trickiest piece, global X11 key grab + thread-safe Qt signal
- `take_note/note_window.py` — window flags, drag/resize, rich text persistence,
  board-attach/detach reparenting
- `take_note/board_window.py` — Memoboard canvas, reparenting mechanics
- `take_note/storage.py` — JSON persistence for notes + boards, atomic writes, corruption handling
- `take_note/app.py` — NoteManager, shared debounce save, tray/hotkey wiring, board lifecycle
- `pyproject.toml` — dependencies and entry point
