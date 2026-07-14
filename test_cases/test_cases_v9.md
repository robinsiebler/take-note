# Take Note! — Manual Test Cases (v9)

Covers only what's new since the v8 pass completed and shipped (v1.5.0) — that pass is the closed historical record in `test_cases_v8.md`; don't append further cases there. This doc will grow as more features land, rather than duplicating everything already tested.

## Your system

- Repo: `/home/robinsiebler/Code/take_note`
- Launch: `/home/robinsiebler/Code/take_note/.venv/bin/take-note` (or `cd` into the repo and run `.venv/bin/take-note`)
- Python 3.14.6, PySide6 6.11.1
- Desktop: KDE Plasma, running through XWayland (`QT_QPA_PLATFORM=xcb`, forced by `__main__.py`)
- Two monitors with **different scaling** — DP-1 (top, 1920×1080 @ 100%) and DP-3 (bottom/primary, effectively 3440×1440 @ 125%).
- `XDG_DATA_HOME`/`XDG_CONFIG_HOME` are **unset** on this machine, so the app uses the plain `~/.local/share` / `~/.config` fallbacks.

Each case is a checkbox. Check it off as `[x]` once verified, and mark the result line underneath. If a case fails or passes with an issue, note the actual behavior right there rather than just leaving it unchecked, so a re-test later doesn't have to rediscover the same bug.

* * *

## 1\. Notes Manager — Reminder column

- [x] **1.1** Open the Notes Manager — a new **Reminder** column appears after Tags, blank for any note with no reminder set.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **1.2** Set a reminder on a note (☰ → Set Reminder…) — the Notes Manager's Reminder column updates to show that note's due time, in the same local-time format as Date Modified (e.g. "August 01, 2026 03:30 PM").
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **1.3** Click the Reminder column header to sort by it — notes sort chronologically by when their reminder is due, not alphabetically by the displayed text (notes with no reminder should group predictably at one end, not scattered).
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **1.4** Clear a note's reminder (☰ → Edit Reminder… → Clear Reminder) — the Reminder column goes blank again for that note.
    - [x] Pass - initially crashed (SIGSEGV, confirmed via coredumpctl): `_DateTableWidgetItem.__lt__`'s fallback to `super().__lt__(other)` triggered a Shiboken virtual-dispatch recursion loop when compared against a plain `QTableWidgetItem` — only happened once the Reminder column mixed a set reminder with a blank one in the same sortable column (Date Modified never mixed types before). Fixed by comparing `.text()` directly instead. Retested 2026-07-14: no crash, column clears correctly.
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **1.5** Let a reminder fire — once it fires (and clears itself), the Reminder column for that note goes blank on its own without needing to manually refresh the Notes Manager.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues