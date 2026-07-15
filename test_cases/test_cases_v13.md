# Take Note! — Manual Test Cases (v13)

Covers only what's new since the v12 pass completed — that pass already ran to completion and its results are the closed historical record in `test_cases_v12.md`; don't append further cases there. Combines two small, otherwise-unrelated features tested together in one pass at the user's request: interactive checklists (built on `feature/checklist`) and Notepad scrollbar styling + a Notepad color picker (built on `feature/notepad-color`). Both branches are unmerged as of this writing — check `git log --oneline -5` / `git branch -a` before assuming either has landed on `main`.

## Your system

- Repo: `/home/robinsiebler/Code/take_note`
- Launch: `/home/robinsiebler/Code/take_note/.venv/bin/take-note` (or `cd` into the repo and run `.venv/bin/take-note`)
- Python 3.14.6, PySide6 6.11.1
- Desktop: KDE Plasma, running through XWayland (`QT_QPA_PLATFORM=xcb`, forced by `__main__.py`)
- Two monitors with **different scaling** — DP-1 (top, 1920×1080 @ 100%) and DP-3 (bottom/primary, effectively 3440×1440 @ 125%).
- `XDG_DATA_HOME`/`XDG_CONFIG_HOME` are **unset** on this machine, so the app uses the plain `~/.local/share` / `~/.config` fallbacks.

Each case is a checkbox. Check it off as `[x]` once verified, and mark the result line underneath. If a case fails or passes with an issue, note the actual behavior right there rather than just leaving it unchecked, so a re-test later doesn't have to rediscover the same bug.

* * *

## 1\. Interactive checklists

- [x] **1.1** Right-click in a note's text → **Bullets && Numbering** submenu now has a **Checklist** option, right after **• Bullets**.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **1.2** Select one or more lines of text and choose **Checklist** — each selected line becomes a checklist item with an empty (unchecked) checkbox to its left.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **1.3** Click a checkbox — it fills in with a checkmark, and that line's text turns strikethrough and a muted grey.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **1.4** Click the same checkbox again — it empties back out, and the text returns to normal (no strikethrough, normal color).
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **1.5** Check a couple of items on a checklist, then close and reopen the note (or quit and relaunch the app) — every item's checked/unchecked state, and the checked items' strikethrough/grey text, both survive exactly as left.
    - [ ] Pass
    - [x] Fail - See screenshot TC 1.5 - Checklist into bullets: After closing/opening the app, the checklist turned into bullets.
    - [ ] Pass with Issues
- [x] **1.6** With the cursor on any checklist item (checked or unchecked), right-click → **Bullets && Numbering** shows **Checklist** with a checkmark next to it, same as **• Bullets**/**1, 2, 3** would show when the cursor is on that style — this just indicates the _style_, not whether that particular item is itself checked.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [ ] **1.7** Check an item, place the cursor at the end of its text, and press Enter to create a new item right below it — the new item starts unchecked and in completely normal text (not strikethrough/grey, even though it was created immediately after a checked item).
    - [ ] Pass
    - [ ] Fail
    - [x] Pass with Issues - See TC 1.7 - Faded checkbox: The checkbox starts out faded. When you start typing, it turns to black
- [x] **1.8** Lock the note (☰ → **Lock Note**), then click one of its checkboxes — nothing happens; it stays exactly as it was before locking.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **1.9** Select a checklist item and switch it to another style (e.g. **• Bullets**) — it converts cleanly, no leftover checkbox or stray strikethrough.
    - [ ] Pass
    - [x] Fail - SZee screenshot TC 1.9 - Grey and strikethrough - After converting to numbers, the checked item (now a numbered item) is grey and has strikethrough
    - [ ] Pass with Issues
- [x] **1.10** Select a checklist item and choose **None** — the checkbox disappears entirely, back to a plain paragraph.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues

## 2\. Notepad scrollbar styling

- [x] **2.1** Open a Notepad and add/move notes until a scrollbar appears (vertical and/or horizontal, by dragging a note past the visible edge) — it's a slim, flat, rounded bar with no up/down arrow buttons, not the plain system-default grey scrollbar.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **2.2** Drag the scrollbar handle — the canvas scrolls normally, same as before.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues

## 3\. Notepad color picker

- [x] **3.1** Right-click on empty Notepad canvas — the menu now has a **Change Notepad Color…** option, between **Rename Notepad** and the separator above **Delete Notepad**.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **3.2** Click it — the same 12-swatch color popup notes already use for **Change Note Color…** opens.
    - [ ] Pass
    - [x] Fail - See screenshot TC  3.2 - Yellow on yellow: - The note color and the Notepad color cannot be the same. You a probably need to use the Font Color swatches for the Notepad color swatches (or create a new set of swatches) so there is no conflict.
    - [ ] Pass with Issues
- [x] **3.3** Pick a color — the Notepad's header, footer, canvas texture, and scrollbar all recolor immediately to match.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **3.4** Close and reopen the Notepad (or quit and relaunch the app) — the chosen color is still there.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **3.5** Try both a very light swatch and the near-black one — the header title text and the scrollbar both stay legible against each.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues