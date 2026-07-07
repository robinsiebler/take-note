# Take Note!

A sticky notes app for Linux (Python + PySide6/Qt6).

## Features

- Colored sticky notes with rounded corners, rich text (bold/italic/
  underline/strikethrough, alignment, bullets & numbering with indent/
  dedent) via a right-click "Font Style"/"Bullets & Numbering" menu, plus
  a "Font Color…" swatch picker (including black) for selected text,
  always-on-top (toggleable per note), adjustable transparency, freely
  movable and resizable, collapsible to just the header ("roll up"),
  persisted across restarts.
- Right-click the note body for text-formatting actions only; whole-note
  actions (color, transparency, always-on-top, Memoboard, delete) live in
  the header's right-click menu and the hamburger (☰) button instead.
- System tray icon: create notes/boards, open Settings, quit.
- Global hotkey (default `Ctrl+Alt+N`, user-configurable in Settings) to
  create a new note from anywhere.
- Settings dialog (tray → Settings…): launch at login, default note color,
  whether new notes start always-on-top, and a hotkey recorder that
  live-tests a combo for conflicts before committing to it.
- Memoboards: group notes onto a shared corkboard-style window that shows,
  hides, and moves as one unit.
- Context menus and the color picker adapt to your system's light/dark
  theme; note colors themselves stay as you set them regardless of theme.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/take-note
```

## Known limitation: Wayland

Wayland's core protocol doesn't let an app position its own top-level
windows, which breaks "remember each note's position" and always-on-top.
To work around this, the app forces itself to run through **XWayland** by
setting `QT_QPA_PLATFORM=xcb` before Qt starts (see `take_note/__main__.py`).
This works reliably on KDE Plasma (X11 or Wayland-with-XWayland). If you're on
a compositor that doesn't run XWayland, window positioning and the global
hotkey (which also uses X11's `XGrabKey`) won't work.

## Data

Notes and boards are stored as a single JSON file at
`$XDG_DATA_HOME/take-note/notes.json` (falls back to
`~/.local/share/take-note/notes.json`).

## Tests

```bash
.venv/bin/pip install -e . pytest
.venv/bin/pytest
```

## Roadmap / explicitly out of scope for v1

**Planned (v3)**, sourced from reference screenshots in `Screenshots/` (untracked,
not part of the repo). Bullets & numbering and note transparency are done
(see Features above); remaining:
- Font family / size pickers in the context menu
- Hyperlinks and embedded images in the note body
- In-note Find (Ctrl+F)
- Lock note (disable editing)
- Note title (Edit title, Ctrl+F2)
- Bulk tray actions: Show all notes, Hide all notes, Roll up/down notes,
  Bring notes on top
- "Stick a note to a window" — hide/show a note synced with another
  window's minimize/restore/close (whole-window granularity only;
  browser-tab-level isn't feasible on Linux — no clean per-tab signal)

**Future / lower priority:**
- Note list / search window ("Notes Browser")
- Tags (only pays off once a Notes Browser/search exists to filter by them)
- Reminders / alarms (needs a real notification/alarm subsystem)
- Cloud sync
- Interactive checklists inside notes (needs a custom `QTextObjectInterface`,
  unlike bullets/numbering above)
- A more advanced note-color picker beyond the fixed swatch palette
- Note "skins" / a Markdown editing mode
- Spell check (would add a real dependency — hunspell/enchant)
- Drag-and-drop of notes onto a Memoboard (currently a right-click "Add to
  Memoboard" menu action instead)

See [docs/PLAN.MD](docs/PLAN.MD) for the original pre-implementation design
plan (historical reference; some details evolved during implementation).
