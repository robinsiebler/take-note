# Take Note! — Manual Test Cases (v12)

Covers only what's new since the last pass(es). Numbered v12 rather than v10 deliberately — `test_cases_v10.md` (Notepad corkboard texture) already exists on a separate, not-yet-merged branch; this avoids two branches independently creating the same filename. Don't append further cases to any already-closed doc.

## Your system

- Repo: `/home/robinsiebler/Code/take_note`
- Launch: `/home/robinsiebler/Code/take_note/.venv/bin/take-note` (or `cd` into the repo and run `.venv/bin/take-note`)
- Python 3.14.6, PySide6 6.11.1
- Desktop: KDE Plasma, running through XWayland (`QT_QPA_PLATFORM=xcb`, forced by `__main__.py`)
- Two monitors with **different scaling** — DP-1 (top, 1920×1080 @ 100%) and DP-3 (bottom/primary, effectively 3440×1440 @ 125%).
- `XDG_DATA_HOME`/`XDG_CONFIG_HOME` are **unset** on this machine, so the app uses the plain `~/.local/share` / `~/.config` fallbacks.

Each case is a checkbox. Check it off as `[x]` once verified, and mark the result line underneath. If a case fails or passes with an issue, note the actual behavior right there rather than just leaving it unchecked, so a re-test later doesn't have to rediscover the same bug.

* * *

## 1\. Notepad hidden-state persistence

- [x] **1.1** Create a couple of Notepads, close one via its own × — quit and relaunch the app. The closed one stays closed (doesn't reopen automatically); the other one reopens normally.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **1.2** With a Notepad closed (from 1.1), reopen it via the tray's Notepads submenu — quit and relaunch. It now reopens automatically (its closed state was cleared by reopening it).
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **1.3** Close a Notepad via the tray's Notepads submenu (uncheck it) instead of its own × — quit and relaunch. Same result as 1.1: stays closed.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **1.4** Reopen a closed Notepad via the Notes Manager (double-click its entry in the tree) — quit and relaunch. It now reopens automatically too.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **1.5** With a Notepad already open and on-screen, double-click it in the Notes Manager tree (just to bring it to front) — this should not be treated as a meaningful change (nothing to verify visually here, but flag anything that seems off, e.g. an unexpected save/notification).
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues