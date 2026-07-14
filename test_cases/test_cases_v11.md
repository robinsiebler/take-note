# Take Note! — Manual Test Cases (v11)

Covers only what's new since the last pass(es). Numbered v11 rather than v10 deliberately — `test_cases_v10.md` (Notepad corkboard texture) already exists on a separate, not-yet-merged branch; this avoids two branches independently creating the same filename. Don't append further cases to either already-closed doc.

## Your system

- Repo: `/home/robinsiebler/Code/take_note`
- Launch: `/home/robinsiebler/Code/take_note/.venv/bin/take-note` (or `cd` into the repo and run `.venv/bin/take-note`)
- Python 3.14.6, PySide6 6.11.1
- Desktop: KDE Plasma, running through XWayland (`QT_QPA_PLATFORM=xcb`, forced by `__main__.py`)
- Two monitors with **different scaling** — DP-1 (top, 1920×1080 @ 100%) and DP-3 (bottom/primary, effectively 3440×1440 @ 125%).
- `XDG_DATA_HOME`/`XDG_CONFIG_HOME` are **unset** on this machine, so the app uses the plain `~/.local/share` / `~/.config` fallbacks.

Each case is a checkbox. Check it off as `[x]` once verified, and mark the result line underneath. If a case fails or passes with an issue, note the actual behavior right there rather than just leaving it unchecked, so a re-test later doesn't have to rediscover the same bug.

* * *

## 1\. Tray: Notepads submenu

- [x] **1.1** With no Notepads created yet, the tray menu's "Notepads" item is greyed out/disabled (can't be opened).
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **1.2** Create a couple of Notepads — the tray's "Notepads" submenu now lists each one by name, with a checkmark (checked = currently shown).
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **1.3** Close a Notepad via its own × — reopen the tray menu, that board's checkmark is now unchecked.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **1.4** Click an unchecked board in the Notepads submenu — it reopens, raises to the front, and becomes active. Checking it again in the menu afterward shows it checked.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **1.5** Click a checked (currently visible) board in the Notepads submenu — it hides, same as clicking its own × would.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **1.6** Create a new Notepad while the tray menu is closed, then reopen the tray menu — the new board shows up in the Notepads submenu without needing to restart the app.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **1.7** Delete a Notepad (right-click canvas → Delete Notepad, confirm) — reopen the tray menu, it's no longer listed in Notepads.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues