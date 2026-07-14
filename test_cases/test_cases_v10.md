# Take Note! — Manual Test Cases (v10)

Covers only what's new since the v9 pass completed and shipped (v1.6.0) — that pass is the closed historical record in `test_cases_v9.md`; don't append further cases there. This doc will grow as more features land, rather than duplicating everything already tested.

## Your system

- Repo: `/home/robinsiebler/Code/take_note`
- Launch: `/home/robinsiebler/Code/take_note/.venv/bin/take-note` (or `cd` into the repo and run `.venv/bin/take-note`)
- Python 3.14.6, PySide6 6.11.1
- Desktop: KDE Plasma, running through XWayland (`QT_QPA_PLATFORM=xcb`, forced by `__main__.py`)
- Two monitors with **different scaling** — DP-1 (top, 1920×1080 @ 100%) and DP-3 (bottom/primary, effectively 3440×1440 @ 125%).
- `XDG_DATA_HOME`/`XDG_CONFIG_HOME` are **unset** on this machine, so the app uses the plain `~/.local/share` / `~/.config` fallbacks.

Each case is a checkbox. Check it off as `[x]` once verified, and mark the result line underneath. If a case fails or passes with an issue, note the actual behavior right there rather than just leaving it unchecked, so a re-test later doesn't have to rediscover the same bug.

* * *

## 1\. Notepad corkboard texture

- [x] **1.1** Open (or create) a Notepad — the corkboard surface has a subtle grainy/speckled texture now, not a flat solid color.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **1.2** The texture should read as a subtle grain, not busy or distracting — check it against a couple of different Notepad colors (New Notepad uses whatever default color is configured; try changing it if you have a way to, or just check the default).
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **1.3** Put a couple of notes on the board — the texture shouldn't visually clash with or make the notes themselves harder to read.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **1.4** Resize the Notepad window (drag the bottom-right corner grip) — the texture should resize/tile smoothly with no visible lag or stutter during the drag, and no hard seams or visible repeating tile edges once you stop.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **1.5** Quit and relaunch the app — the Notepad's texture still renders correctly on reload (not reverted to flat).
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues