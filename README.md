# Sticky Notes

A sticky notes app for Linux (Python + PySide6/Qt6).

## Features

- Colored sticky notes with rich text (bold/italic/underline), always-on-top,
  freely movable and resizable, persisted across restarts.
- System tray icon: create notes/boards, quit.
- Global hotkey (default `Ctrl+Alt+N`) to create a new note from anywhere.
- Memoboards: group notes onto a shared corkboard-style window that shows,
  hides, and moves as one unit.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/sticky-notes
```

## Known limitation: Wayland

Wayland's core protocol doesn't let an app position its own top-level
windows, which breaks "remember each note's position" and always-on-top.
To work around this, the app forces itself to run through **XWayland** by
setting `QT_QPA_PLATFORM=xcb` before Qt starts (see `sticky_notes/__main__.py`).
This works reliably on KDE Plasma (X11 or Wayland-with-XWayland). If you're on
a compositor that doesn't run XWayland, window positioning and the global
hotkey (which also uses X11's `XGrabKey`) won't work.

## Data

Notes and boards are stored as a single JSON file at
`$XDG_DATA_HOME/sticky-notes/notes.json` (falls back to
`~/.local/share/sticky-notes/notes.json`).

## Tests

```bash
.venv/bin/pip install -e . pytest
.venv/bin/pytest
```

## Roadmap / explicitly out of scope for v1

- Note list / search window
- Reminders / alarms
- Cloud sync
- Interactive checklists inside notes
- Full custom color picker (v1 uses a fixed swatch palette)
- Drag-and-drop of notes onto a Memoboard (v1 uses a right-click "Add to
  Memoboard" menu action instead)
