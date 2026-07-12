# Take Note!

A sticky notes app for Linux (Python + PySide6/Qt6).

## Features

Colored, resizable sticky notes with rich text (fonts, colors, bullets &
numbering, hyperlinks, embedded images), a global new-note hotkey, a
searchable Notes Browser with free-form tags, Notepads (shared
corkboards), Lock Note, in-note Find, optional spell check, and a
system tray for quick actions.

See [FEATURES.md](FEATURES.md) for the full, detailed list.

## Setup

### Install

```bash
pip install --user git+https://github.com/robinsiebler/take-note.git
```

After installing:

```bash
take-note
```

`--user` installs alongside your system Python rather than into an
isolated venv, and the `take-note` command lands in `~/.local/bin`,
which is on `PATH` by default on most distros. PySide6 ships prebuilt
wheels for this, so nothing needs to be compiled.

### Upgrading

```bash
pip install --user --upgrade git+https://github.com/robinsiebler/take-note.git
```

Since this points at a git URL rather than a plain package name, pip
actually re-fetches and reinstalls even without `--upgrade` — but pass
it anyway to make the intent explicit rather than relying on that.

### Developing (from a clone)

```bash
git clone https://github.com/robinsiebler/take-note.git
cd take-note
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/take-note
```

An editable venv install keeps dev tooling (pytest, etc.) isolated
from your system Python while you're changing code — see
[Tests](#tests) below.

## Spell check (optional)

Off by default. Enabling it (Settings → General → "Check spelling as you
type") needs the optional `pyenchant` extra *and* a system spell-check
library with a dictionary — `pip install` alone can't provide the latter,
since Enchant is a C library, not a Python package. On Fedora/Nobara:

```bash
sudo dnf install enchant2 hunspell hunspell-en-US
pip install --user "take-note[spellcheck] @ git+https://github.com/robinsiebler/take-note.git"
```

On Debian/Ubuntu (package names believed correct, not independently
verified — no `apt` available in this project's own dev/test environment):

```bash
sudo apt install libenchant-2-2 hunspell-en-us
pip install --user "take-note[spellcheck] @ git+https://github.com/robinsiebler/take-note.git"
```

From a clone (see [Developing](#developing-from-a-clone) above), add the
extra to the editable install instead: `.venv/bin/pip install -e ".[spellcheck]"`.

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
Browser, tags, and a manual test plan under `test_cases/`) is done — see
Features above rather than re-deriving it from history here.

**Still open, lower priority:**
- Reminders / alarms (needs a real notification/alarm subsystem)
- Interactive checklists inside notes (needs a custom `QTextObjectInterface`,
  unlike bullets/numbering above)
- Note-color/font-color picker popup: corners and border are already
  rounded; the swatch layout/background styling itself is still an open
  design question
- Configurable hotkeys for in-app actions (Bold/Italic/Add Title etc.) —
  currently only the two global hotkeys (new note, open Notes Browser)
  are user-configurable
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

## License

MIT — see [LICENSE](LICENSE).
