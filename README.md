# Take Note!

A sticky notes app for Linux (Python + PySide6/Qt6).

## Features

- Colored sticky notes with rounded corners, rich text (a "Font…" action
  opens the native font-family/size/style dialog; plus quick bold/italic/
  underline/strikethrough, alignment, and bullets & numbering with
  indent/dedent via a right-click menu — Font Style and Bullets &
  Numbering both show which style the current selection already has),
  plus a "Font Color…" swatch picker (including black) for selected
  text, always-on-top (toggleable per note), adjustable transparency,
  freely movable and resizable, collapsible to just the header ("roll
  up"), persisted across restarts. New notes stagger slightly instead of
  stacking exactly on top of each other.
  Hyperlinks: "Hyperlink…" turns the selection (or a typed URL) into a
  clickable link, or edits an existing one in place (pre-filling its
  current URL) if invoked with just the caret inside it rather than a
  new selection — hover shows a hand cursor and tooltip, Ctrl+Click opens
  it, a plain click still just places the cursor for editing. Plain-text
  URLs also auto-detect as links the moment you right-click them, and
  "Remove Hyperlink" strips a link back to plain text.
- Spell check (optional, off by default — see below): a red squiggly
  underline under misspelled words as you type, with suggested
  corrections in the right-click menu.
- Right-click the note body for text-formatting actions only; whole-note
  actions (color, transparency, always-on-top, Notepad, delete, hide)
  live in the header's right-click menu and the hamburger (☰) button
  instead.
- System tray icon: create notes/boards, open the Notes Browser, open
  Settings, quit.
- Global hotkey (default `Ctrl+Alt+N`, user-configurable in Settings) to
  create a new note from anywhere.
- Notes Browser (tray → "Notes Browser…"): a sortable, searchable table
  of every note (Title/Preview/Notepad/Date Modified columns) plus a
  tree of boards to filter by, for finding a note (including a hidden
  one) without hunting across the desktop.
- Settings dialog (tray → Settings…): launch at login, default note
  color/font size/color, whether new notes start always-on-top, optional
  spell check, and a hotkey recorder that live-tests a combo for
  conflicts before committing to it. Has Apply (try a setting without
  closing the dialog) alongside OK/Cancel, and remembers its own window
  position across restarts.
- Notepads: group notes onto a shared corkboard-style window that shows,
  hides, and moves as one unit.
- Context menus and the color picker adapt to your system's light/dark
  theme; note colors themselves stay as you set them regardless of theme.
- Embedded images: right-click → "Add picture…" (or "Replace picture…"
  when one is already selected) inserts a picture inline, persisted
  directly in the note's saved HTML so it survives a restart. The note
  grows in width and height to fit the picture rather than shrinking it,
  capped at the screen's available size.
- In-note Find (Ctrl+F, or the context menu's "Find…" — disabled on an
  empty note): a small non-modal find bar with Next/Previous
  (F3/Shift+F3 also work while it's open) and wrap-around search. Find,
  Title, and Hyperlink text fields all have a clear (×) button.
- Lock Note (hamburger ☰ menu): makes the note read-only — the
  text-formatting context menu collapses to just Find…, and Ctrl+B/I/U/K
  stop working too, so a locked note can't be edited from the keyboard
  either.
- Note title (hamburger ☰ menu's first item, or Shift+F2): shows as a bold
  line above the note body, only when set.
- Tray menu bulk actions: Bring Notes on Top, Show/Hide All Notes
  (collapses to one item, converging to all-shown or all-hidden), and
  Roll Up/Down Notes (rolls every note up if any are expanded, otherwise
  expands them all — one consistent end state for the whole batch rather
  than flipping each note independently). A single note can also be
  hidden on its own via the header/hamburger menu — session-only, same
  as the bulk actions, and still listed (and reopenable) in the Notes
  Browser while hidden.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/take-note
```

## Spell check (optional)

Off by default. Enabling it (Settings → General → "Check spelling as you
type") needs the optional `pyenchant` extra *and* a system spell-check
library with a dictionary — `pip install` alone can't provide the latter,
since Enchant is a C library, not a Python package. On Fedora/Nobara:

```bash
sudo dnf install enchant2 hunspell hunspell-en-US
.venv/bin/pip install -e ".[spellcheck]"
```

On Debian/Ubuntu (package names believed correct, not independently
verified — no `apt` available in this project's own dev/test environment):

```bash
sudo apt install libenchant-2-2 hunspell-en-us
.venv/bin/pip install -e ".[spellcheck]"
```

If either half is missing, the checkbox in Settings is disabled with an
explanatory label rather than silently doing nothing.

## Known limitation: Wayland

Wayland's core protocol doesn't let an app position its own top-level
windows, which breaks "remember each note's position" and always-on-top.
To work around this, the app forces itself to run through **XWayland** by
setting `QT_QPA_PLATFORM=xcb` before Qt starts (see `take_note/__main__.py`).
This works reliably on KDE Plasma (X11 or Wayland-with-XWayland). If you're on
a compositor that doesn't run XWayland, window positioning and the global
hotkey (which also uses X11's `XGrabKey`) won't work.

The same boundary limits "Stick to Window": its window picker (`_NET_CLIENT_LIST`)
only sees X11/XWayland clients. A native Wayland app (e.g. a browser launched
with `--ozone-platform=wayland`, or many modern Electron apps) is invisible to
it — Wayland's security model doesn't let one client enumerate another's
windows, and there's no bridge back to X11 for them. Getting those apps to
list would need either the *other* app to run through XWayland itself, or a
compositor-specific extension (e.g. a KWin Script + D-Bus bridge) — not
pursued, since that would only work on KDE/KWin and add real fragility for a
single feature.

## Data

Notes and boards are stored as a single JSON file at
`$XDG_DATA_HOME/take-note/notes.json` (falls back to
`~/.local/share/take-note/notes.json`).

## Tests

```bash
.venv/bin/pip install -e . pytest
.venv/bin/pytest
```

## Roadmap / explicitly out of scope

Everything originally planned for v1-v3 (bullets & numbering, note
transparency, a font picker, hyperlinks, embedded images, in-note Find,
Lock Note, Note title, "Stick to Window", bulk tray actions, the Notes
Browser, and a manual test plan under `test_cases/`) is done — see
Features above rather than re-deriving it from history here.

**Still open, lower priority:**
- Tags — only pays off once a way to filter by them exists (the Notes
  Browser now does, so this is unblocked whenever it's picked up)
- Reminders / alarms (needs a real notification/alarm subsystem)
- Interactive checklists inside notes (needs a custom `QTextObjectInterface`,
  unlike bullets/numbering above)
- Note-color/font-color picker popup: corners and border are already
  rounded; the swatch layout/background styling itself is still an open
  design question
- Configurable hotkeys for in-app actions (Bold/Italic/Add Title etc.) —
  currently only the one global "new note" hotkey is user-configurable
- The Notepad corkboard window's own chrome is still visually plain
  compared to note windows, has no tray listing of existing boards or
  bulk reopen, and doesn't remember which boards were hidden across a
  restart
- Drag-and-drop of notes onto a Notepad (currently a right-click "Add to
  Notepad" menu action instead)
- Thumbnail + open-full-size for oversized embedded pictures
- Tray menu separators render as plain gaps (KDE's native tray menu
  protocol doesn't pick up the app's own stylesheet — no clean fix found)

**Distant future, not scoped:** cloud sync, note "skins" / a Markdown
editing mode.

See [docs/PLAN.MD](docs/PLAN.MD) for the original pre-implementation design
plan (historical reference; some details evolved during implementation).
