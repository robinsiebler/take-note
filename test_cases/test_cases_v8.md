# Take Note! — Manual Test Cases (v8)

Covers only what's new since the v7 pass completed — that pass already
ran to completion and its results are the closed historical record in
`test_cases_v7.md`; don't append further cases there. This doc will
grow as more features land, rather than duplicating everything v7
already tested.

## Your system

- Repo: `/home/robinsiebler/Code/take_note`
- Launch: `/home/robinsiebler/Code/take_note/.venv/bin/take-note` (or `cd` into the repo and run `.venv/bin/take-note`)
- Python 3.14.6, PySide6 6.11.1
- Desktop: KDE Plasma, running through XWayland (`QT_QPA_PLATFORM=xcb`, forced by `__main__.py`)
- Two monitors with **different scaling** — DP-1 (top, 1920×1080 @ 100%) and DP-3 (bottom/primary, effectively 3440×1440 @ 125%).
- `XDG_DATA_HOME`/`XDG_CONFIG_HOME` are **unset** on this machine, so the app uses the plain `~/.local/share` / `~/.config` fallbacks.

Each case is a checkbox. Check it off as `[x]` once verified, and mark
the result line underneath. If a case fails or passes with an issue,
note the actual behavior right there rather than just leaving it
unchecked, so a re-test later doesn't have to rediscover the same bug.

* * *

## 1. Reminders — sound on fire

- [x] **1.1** Settings → General has a **"Play a sound when a reminder fires"** checkbox, checked by default.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **1.2** With it checked, set a short reminder — you should actually **hear** a brief chime the moment it fires (at the same time it raises/flashes to the front).
    - [x] Pass - confirmed live 2026-07-13; volume bumped from 0.6 to 0.72 (20% louder) per feedback, then confirmed good.
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **1.3** Uncheck it, click OK, set another reminder — it fires silently (still raises visually, just no sound).
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues

## 2. Reminders — quick relative time picker

- [x] **2.1** ☰ → **Set Reminder…** on a note with no existing reminder shows two radio-button options: **"Remind me in"** (a minutes spinbox, defaulting to 15, and selected by default) and **"Remind me at"** (the original date/time picker, greyed out while the first option is selected).
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **2.2** Selecting **"Remind me at"** enables its date/time picker and greys out the minutes spinbox instead — only one is ever editable at a time.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **2.3** With "Remind me in" selected, set it to a couple of minutes and click OK — the bell icon appears immediately, and its tooltip shows a time that's actually about that many minutes from now.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **2.4** ☰ → **Edit Reminder…** on a note that already has a reminder set defaults to **"Remind me at"** (not the quick minutes option), prefilled with the existing time — same as before this change.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
