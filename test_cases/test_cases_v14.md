# Take Note! — Manual Test Cases (v14)

Covers only what's new since the v13 pass completed — that pass already ran to completion and its results (including three real bugs found: checklist reverting to bullets after a restart, a faded checkbox on a new item, and grey/strikethrough surviving a switch away from Checklist) are the closed historical record in `test_cases_v13.md`; don't append further cases there. This doc re-verifies those three fixes plus one design change made in response to a fourth v13 finding (yellow note invisible on a yellow Notepad): the Notepad color picker now uses the Font Color swatches instead of the note color swatches. Still on two branches, both unmerged as of this writing — check `git log --oneline -5` / `git branch -a` before assuming either has landed on `main`.

## Your system

- Repo: `/home/robinsiebler/Code/take_note`
- Checklist branch: `/home/robinsiebler/Code/take_note-checklist` (its own venv — launch via `/home/robinsiebler/Code/take_note-checklist/.venv/bin/take-note`, not the main repo's venv, or you'll silently run the wrong branch's code)
- Notepad color branch: `/home/robinsiebler/Code/take_note` itself (`feature/notepad-color`) — launch via `.venv/bin/take-note` there as usual
- Python 3.14.6, PySide6 6.11.1
- Desktop: KDE Plasma, running through XWayland (`QT_QPA_PLATFORM=xcb`, forced by `__main__.py`)
- Two monitors with **different scaling** — DP-1 (top, 1920×1080 @ 100%) and DP-3 (bottom/primary, effectively 3440×1440 @ 125%).
- `XDG_DATA_HOME`/`XDG_CONFIG_HOME` are **unset** on this machine, so the app uses the plain `~/.local/share` / `~/.config` fallbacks.

Each case is a checkbox. Check it off as `[x]` once verified, and mark the result line underneath. If a case fails or passes with an issue, note the actual behavior right there rather than just leaving it unchecked, so a re-test later doesn't have to rediscover the same bug.

* * *

## 1\. Interactive checklists — bug fixes (test on `feature/checklist`)

- [x] **1.1** (re-verifies v13 §1.5) Check a couple of items on a checklist, quit and relaunch the app — the list is still a checklist (checkboxes), not plain bullets. Checked items keep their checkmark/strikethrough/grey; unchecked items are still empty checkboxes with normal text.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **1.2** (re-verifies v13 §1.7) Check an item, place the cursor at the end of its text, press Enter — the brand-new item's checkbox is immediately a normal dark outline, not pale/faded, even before you type anything into it.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **1.3** (re-verifies v13 §1.9) Check an item, then select it and switch to a different style (e.g. **1, 2, 3**) — the checkbox is gone and the text is back to normal (no leftover grey or strikethrough).
    - [ ] Pass
    - [ ] Fail
    - [x] Pass with Issues - See screenshot TC 1.3 (v14): If I select the entire list and convert it, it works fine. If I only select 1 item in the cheklist and convert that something strange happens!
- [x] **1.4** (new) Check an item, then select it and choose **None** instead of switching to another style — same result as 1.3: text returns to fully normal, no leftover grey/strikethrough.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **1.5** (new — guards against overcorrection) Manually color some text on an _unchecked_ checklist item a custom color (Font Color…), then switch that item to a different style — its custom color is preserved, not reset to default. (This confirms the 1.3/1.4 fix only clears formatting it actually applied itself, not a deliberate color choice on an item that was never checked.)
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues

## 2\. Notepad color picker — now Font Color swatches (test on `feature/notepad-color`, this repo)

- [x] **2.1** Right-click a Notepad → **Change Notepad Color…** — the popup now shows the same 12 darker/richer swatches as a note's **Font Color…** picker, not the pastel note-color swatches.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **2.2** Pick one of these colors for a Notepad, then put a note of any color on it (including the note's own default yellow) — the note stays clearly visible against the Notepad background, no washing-out.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **2.3** Close and reopen the Notepad (or quit and relaunch the app) — the chosen color is still there.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues