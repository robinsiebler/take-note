# Take Note! — Manual Test Cases (v15)

A **full pass**, not a delta — covers everything in the app as it stands today, not just what changed since v14. Two locations to test from:

- **Everything except §4 (Interactive Checklists) and §13's Permanent Ignore cases**: already on `main`, released as **v1.9.0**. Just launch normally: `/home/robinsiebler/Code/take_note/.venv/bin/take-note`.
- **§13's new Permanent Ignore cases (§13.10-§13.13)**: on branch `feature/spellcheck-ignore-list`, same directory as above (no separate worktree/venv needed this time — `cd /home/robinsiebler/Code/take_note`, confirm `git branch --show-current` says `feature/spellcheck-ignore-list`, then launch the same way).

§4 (Checklists) itself is already merged to `main` along with everything else — only the _ignore-list_ piece of §13 is still on its own branch.

Distinct from the automated `pytest` suite in `tests/` — this is for exercising the real app by hand under a real desktop (XWayland/KDE Plasma), where window-manager interaction, real fonts, and compositor behavior actually matter.

## Your system

- Repo: `/home/robinsiebler/Code/take_note`
- Python 3.14.6, PySide6 6.11.1
- Desktop: KDE Plasma, running through XWayland (`QT_QPA_PLATFORM=xcb`, forced by `__main__.py`)
- Two monitors with **different scaling** — DP-1 (top, 1920×1080 @ 100%) and DP-3 (bottom/primary, effectively 3440×1440 @ 125%). A few dialog-sizing bugs have only ever shown up on the unscaled monitor historically — worth spot-checking dialogs on **both** if anything looks cramped.
- `XDG_DATA_HOME`/`XDG_CONFIG_HOME` are **unset** on this machine, so the app uses the plain `~/.local/share` / `~/.config` fallbacks.
- Spell check's optional dependency is normally installed on this machine (`enchant2`/`hunspell`/`hunspell-en-US` at the OS level, `pyenchant` pip-installed into `.venv`) — §13 should be fully testable as-is except where noted.

Each case is a checkbox. Check it off as `[x]` once verified, and mark the result line underneath. If a case fails or passes with an issue, note the actual behavior right there rather than just leaving it unchecked, so a re-test later doesn't have to rediscover the same bug.

* * *

## 1\. App lifecycle

- [x] **1.1** Test the fresh-install path first, without touching your real data — run once with an isolated scratch dir: `XDG_DATA_HOME=/tmp/take-note-scratch /home/robinsiebler/Code/take_note/.venv/bin/take-note`. One default note should be created automatically. Quit it, then confirm your **real** data is untouched at `/home/robinsiebler/.local/share/take-note/notes.json`.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **1.2** Quit via tray icon → **Quit**. App exits cleanly — no crash dialog.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **1.3** Relaunch after quitting. All notes/boards reappear exactly where they were left (position, size, color, content).
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **1.4** Click the tray icon directly (not right-click) → creates a new note, same as **New Note**.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **1.5** Note a couple of notes' **Date Modified** in the Notes Manager. Quit _without editing anything_ and relaunch — those same notes' Date Modified reads identically, not bumped to "just now".
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues

## 2\. Note creation & window basics

- [x] **2.1** Tray → **New Note** creates a note at a sensible default position/size, default color, always-on-top by default.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **2.2** Create several new notes in a row — each appears slightly offset from the last rather than stacked exactly on top of each other, wrapping around after a dozen or so rather than drifting off-screen.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **2.3** Global hotkey (check Settings → Hotkey tab for the current combo — default `Meta+Alt+N`) creates a new note from anywhere, even with no Take Note! window focused.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **2.4** Note header's `+` button creates another new note.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **2.5** Drag a note by its header — moves smoothly, no lag/tearing.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **2.6** Resize a standalone note by dragging its bottom-right corner grip.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **2.7** Header **▲/▼** button (or double-click the header) rolls the note up to just its header, and back down — including on a note **with a title set**, where the collapsed header should stay clean, not garbled. Roll-up state and position/size persist across a restart.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **2.8** Header `×` → confirmation dialog **"Move this note to Trash?"**, centered over the note itself. **Yes** moves it to Trash (window disappears, not destroyed — see §9), **No**/close leaves it untouched.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **2.9** **Always on Top** (hamburger ☰ menu) keeps a note above normal windows when checked, behaves normally when unchecked.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **2.10** Note Transparency submenu (☰ → **Note Transparency**): None/Low/Medium/High/Full each visibly change opacity, exclusive selection, persists across restart.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **2.11** Insert a picture (§3.8), backspace it away completely back to an empty note, then type — new text reads in the note's normal color, not faded/grey.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues

## 3\. Rich text editing (right-click the note body)

- [x] **3.1** **Font…** opens the native font-family/size/style picker; applies to the current selection (or becomes the typing default with none). On a note **never typed into**, right-click first then open **Font…** — should show your configured default size, not some other size.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **3.2** Bold one word in a sentence, select the whole sentence, open **Font…**, change only the size (leave Style alone), OK — the bolded word stays bold.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **3.3** **Font Style** submenu: **Bold** (`Ctrl+B`), **Italic** (`Ctrl+I`), **Underline** (`Ctrl+U`), **Strikethrough** (`Ctrl+K`) each toggle correctly, both via the menu and their shortcuts, and show a checked state matching the current selection's actual formatting.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **3.4** **Font Style** → **Left/Center/Right** alignment applies to the current paragraph and shows the correct one checked (a plain new paragraph shows Left checked).
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **3.5** **Font Color…** swatch picker recolors selected text; picker has rounded corners and a visible border. Try it on a list item too, including one that's the only/last line in the note — text stays visible, doesn't vanish.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **3.6** **Bullets && Numbering** submenu: **• Bullets**, **1, 2, 3**, **a, b, c**, **A, B, C**, **i, ii, iii**, **I, II, III** each apply to a multi-line selection as one shared list (numbers read 1, 2, 3… not "1." repeated); **None** removes list formatting; selection is exclusive and shows the current style checked. (**Checklist** is covered separately in §4.)
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **3.7** **Increase Indent** / **Decrease Indent** nest/un-nest list items correctly across multi-line selections at mixed depths, each level stepping a consistent, modest amount. Tab/Shift+Tab do the same inline.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **3.8** **Add picture…** inserts an image inline; note grows to fit (width and height) rather than shrinking the image, capped at screen size for an oversized one. Right-click the inserted picture → now says **Replace picture…**; replacing it works.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **3.9** **Hyperlink…** on a selection (or typed URL) turns it into a clickable link. Plain click just places the cursor; `Ctrl+Click` opens it. Right-click directly **on** an existing link → **Edit Hyperlink…**, pre-filled. Right-click it → also shows **Remove Hyperlink**, which reverts it to plain text.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **3.10** Type a plain `http(s)://` URL directly into text (not via the dialog) — stays plain as you type. Right-click directly on it — becomes a real clickable link immediately, menu already reads **Edit Hyperlink…**. Right-click ordinary text with a period that isn't a URL (e.g. "e.g." or "notes.txt") — does **not** get auto-linkified.
    - [ ] Pass
    - [ ] Fail
    - [x] Pass with Issues - See TC 3.10 - URL with comma - I thought this was already fixexd? If not, need basic URL detection that will catch this and not convert it to a URL
    - **Fix verified**, branch `bugfix/url-detection-basic-validation`: a basic host-sanity check now rejects `http://www,google.com` (and similar obviously-broken hosts) while still correctly linkifying real domains, domains with a path/query/port, and IP addresses. A related bug found and fixed on the same branch during follow-up testing: typing a space or pressing Enter right after a linkified URL no longer carries the link's underline/color/href into whatever's typed next.
- [x] **3.11** Undo/Redo/Cut/Copy/Paste/Select All (Qt's built-in menu, shown above the app's own items) all work normally.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **3.12** Type a line, press Enter 5-6 times, type on the new last line, then arrow **up** (not click) into one of the blank lines and type there — reads in the note's normal color, not faded/grey.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **3.13** _(Watch-for, still unconfirmed — has happened occasionally in past passes, exact trigger unknown)_ Only the **first character** of a newly-typed word reads faded/grey while the rest is normal. If you see this, mark Fail and capture the exact keystrokes in the ~10-15s before it appeared, whether any formatting was touched recently, and a screenshot. Passing just means you didn't see it this time — not treated as fixed.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues

## 4\. Interactive Checklists

- [x] **4.1** Right-click in a note's text → **Bullets && Numbering** submenu has a **Checklist** option, right after **• Bullets**.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **4.2** Select one or more lines and choose **Checklist** — each becomes a checklist item with an empty (unchecked) checkbox to its left.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **4.3** Click a checkbox — it fills in with a checkmark, and that line's text turns strikethrough and a muted grey. Click it again — empties back out, text returns to normal.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **4.4** Check a couple of items, then quit and relaunch the app — every item's checked/unchecked state, and the checked items' strikethrough/grey text, both survive exactly as left (the list stays a checklist, doesn't turn into plain bullets).
    - [ ] Pass
    - [ ] Fail
    - [x] Pass with Issues - I had a checklist item that was red. I checked it and then quit/relaunched the app./ Then I unchecked the item. It was no longer red.
- [x] **4.5** With the cursor on any checklist item (checked or unchecked), right-click → **Bullets && Numbering** shows **Checklist** checked, same as any other style would for the cursor's current list.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **4.6** Check an item, place the cursor at the end of its text, press Enter — the new item's checkbox is immediately a normal dark outline (not faded/pale), and its text is fully normal (not strikethrough/grey), even though it was created right after a checked item.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **4.7** Lock the note (☰ → **Lock Note**), then click one of its checkboxes — nothing happens, stays exactly as it was.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **4.8** Check an item, select it alone, and switch it to a different style (e.g. **1, 2, 3**) — checkbox disappears cleanly, and the text is **not** left grey/strikethrough (it reverts to normal formatting, since that look was only ever the checklist's own auto-applied indicator).
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **4.9** Select a checklist item and choose **None** — same clean result as 4.8: checkbox and any grey/strikethrough both gone.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **4.10** Manually color some text on an **unchecked** checklist item (Font Color…), then switch that item to a different style — its custom color is preserved, not reset to default. (Confirms 4.8's cleanup only clears formatting the checklist itself applied, not a deliberate color choice.)
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **4.11** Create a checklist with 3+ items sharing one list (select all the lines together, choose Checklist). Check the middle item, then select **just that one item** (not the others) and switch its style to **1, 2, 3** — only that item converts; the other items stay checkboxes and stay grouped together as one list (not each becoming its own independent single-item list). Contrast with selecting the **whole list** and converting it — that still converts everything together as before.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues

## 5\. Find, Lock, and Title

- [x] **5.1** `Ctrl+F` or right-click → **Find…** opens a find bar between header and body. Typing searches live; **▲/▼** step through matches with wraparound; `×`/Esc closes it. `F3`/`Shift+F3` also step through matches while it's open (and do nothing once closed). The search field has a visible dark clear (×) button.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **5.2** **Find…** is disabled on a completely empty note, enabled the moment you type anything.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **5.3** ☰ → **Lock Note** makes the body read-only. Right-click menu collapses to just **Find…**. `Ctrl+B`/`I`/`U`/`K` stop working while locked.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **5.4** Header padlock icon toggles lock too — white/unlocked vs. amber/locked. A single click toggles once; a double-click also toggles exactly once (not a net no-op).
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **5.5** `Shift+F2` (or ☰ → **Add Title…**) opens a dialog to set a title; once set, a bold title bar appears between header and body, and the menu item reads **Edit Title…**. Clearing the title (empty string, OK) hides the bar again. Cancelling the dialog leaves an existing title unchanged. The title field has a visible clear (×) button.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **5.6** Title's font (family + size) matches the note body's current font and stays bold.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues

## 6\. Note color & appearance

- [x] **6.1** ☰ → **Change Note Color…** opens a swatch-grid popup with rounded corners and a visible border — 12 swatches, checkmark on the current one, readable regardless of swatch lightness (dark checkmark on light swatches, white on dark ones).
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **6.2** Picking a color updates the note (header/body/footer/find-bar tint) immediately and persists across restart.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **6.3** The in-note find bar's background tints toward the note's own color, updating live if you change the note color while it's open.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues

## 7\. Stick to Window

- [x] **7.1** ☰ → **Stick to Window…** opens a picker listing other real windows on your desktop (not Take Note's own).
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **7.2** After sticking, minimizing/restoring the target window hides/shows the note in sync, several times in a row — check your taskbar/Alt-Tab afterward, the note shouldn't appear there (a brief flash during the remap moment is a known, accepted limitation, not a bug — see the list at the end of this doc). Closing the target window unsticks the note (stays visible), and the ☰ menu reverts to **Stick to Window…**.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **7.3** ☰ menu shows **Unstick from Window** for a stuck note; using it detaches it.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **7.4** A native Wayland app doesn't appear in the picker — expected limitation on this Wayland-with-XWayland setup.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues

## 8\. Notepad (the per-board corkboard window)

- [x] **8.1** Tray → **New Notepad** creates a small corkboard-style window (subtle grainy texture, rounded chrome matching note windows) titled with the board's name.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **8.2** Right-click empty canvas → **New Note on this Notepad** creates a note already attached. Resize the board window bigger/smaller a few times — no scrollbar should get stuck showing once content comfortably fits.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **8.3** Right-click empty canvas → **Rename Notepad** renames it via a dialog wide enough to read its own title; header label updates immediately.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **8.4** Right-click empty canvas → **Change Notepad Color…** opens a color popup showing the **Font Color** swatches (dark/rich colors, not the pastel note-color swatches) — this is deliberate, chosen after live testing found a default-yellow note could be invisible on a same-colored Notepad.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **8.5** Pick a color — the Notepad's header, footer, canvas texture, and scrollbar all recolor immediately to match, and persist across a restart. Put a note of any color (including plain yellow) on the recolored board — stays clearly visible against it.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **8.6** Drag a note past the visible edge of the canvas to force a scrollbar — it's a slim, flat, rounded bar (a faint dark track behind a lighter handle), no up/down arrow buttons, not the plain system-default scrollbar. Dragging the handle scrolls normally.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **8.7** Right-click empty canvas, with at least one always-on-top note attached → **Delete Notepad** → confirmation appears **in front of** those notes, not behind them. Confirming moves the board's notes back to standalone.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **8.8** From a standalone note, ☰ → **Add to Notepad** submenu lists every existing board by name plus **New Notepad…**. Once attached, that note's ☰ menu shows **Remove from Notepad** instead.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **8.9** A board-attached note has no visible resize grip and its rounded corner renders cleanly (no grey notch). A standalone note still has its grip.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **8.10** Drag a note far outside the board's visible area — the canvas grows to keep it reachable; drag it back — canvas shrinks back down.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **8.11** Board header's `×` hides the board (doesn't delete it). Quit and relaunch — the closed board **stays closed**, doesn't reappear automatically.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **8.12** Tray icon → hover or click to open its menu — a **Notepads** submenu lists every existing board by name, each with a checkmark showing shown/hidden; click one to toggle it directly. Use it to reopen the board you closed in 8.11.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **8.13** Change a board-attached note's transparency — it visibly blends with the board behind it. Set a title on one — the title bar shows the note's own color, not the board's background showing through. Open any dialog from a board-attached note (Font…/Hyperlink…/Add picture…/Stick to Window…/Delete…) — renders in the app's normal dark theme, not a washed-out grey.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **8.14** Open a Notepad, then create several new standalone notes — every new note renders **above** the board window regardless of the notes' own always-on-top setting.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues

## 9\. Notes Manager

- [x] **9.1** Tray → **Notes Manager…** opens a single window. Opening it again while already open just raises/focuses the existing one. Minimizing it (not closing) then reopening via tray/hotkey actually restores it.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **9.2** Left tree shows **All Notes**, **Unfiled**, then one entry per board, then **Tags** (once any note has a tag) and always-present **Trash**. Selecting each filters the table correctly.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **9.3** Table has Title/Preview/Notepad/Date Modified (US format)/Tags columns. An untitled note shows **(untitled)** in Title but a real body-text snippet in Preview. A board-attached note shows that board's name in Notepad; unattached is blank.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **9.4** **Search notes…** filters live by both title and body text, with a visible clear (×) button.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **9.5** Clicking a column header sorts by it; Date Modified sorts chronologically, not alphabetically by the displayed text.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **9.6** Double-clicking a note row raises/shows that note; double-clicking a board row raises/shows that board. Works even if the target was minimized first.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **9.7** Ctrl-click/Shift-click selects multiple rows; toolbar **Delete** (or right-click → **Move N Notes to Trash**) asks one confirmation and moves them all to Trash.
    - [ ] Pass
    - [ ] Fail
    - [x] Pass with Issues - If you select 4 notes and delete them and there are 4 or more notes left in the list, they are selected. The selection should clear with the delete.
    - **Fix verified**, branch `bugfix/notes-manager-selection-after-delete`: the table's selection now explicitly clears both after a delete and when switching the tree filter (e.g. All Notes → Trash) — a second, related bug found during testing, where switching filters left the same number of rows "selected" in the new, completely different set of notes shown.
- [x] **9.8** Toolbar **New Note** creates unattached (on All Notes/Unfiled) or attached to whichever board is selected in the tree. **New Notepad** creates a board that immediately appears in the tree.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **9.9** Creating/deleting/renaming a note or board elsewhere updates this window's list live within about half a second.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **9.10** Resize/move the window, quit, relaunch — reopens at the exact size/position left. Global hotkey (default `Meta+Alt+B`) opens/raises it from anywhere. Doesn't appear in the taskbar or Alt-Tab switcher.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues

### Trash

- [x] **9.11** Trash a note (any delete action anywhere in the app) — it appears under the **Trash** node, disappears from All Notes/its board/any tag filter. Date Modified header changes to **Date Deleted** while viewing Trash.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **9.12** While viewing Trash, toolbar **Delete** becomes **Delete Permanently** and a **Restore** button appears (both revert the moment you select any other tree node). **Restore** puts a note back in All Notes with no confirmation dialog; a board-attached note lands back on the same board (or unfiled if that board was deleted meanwhile).
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **9.13** **Delete Permanently** shows a stronger-worded confirmation ("cannot be undone"); confirming removes it for real. Double-clicking a row while viewing Trash does nothing (Restore is the only way back).
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues

## 10\. Settings dialog (tray → Settings…)

### General tab

- [x] **10.1** Settings doesn't appear in the taskbar. Reopening it from the tray while already open just raises/focuses the existing dialog.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **10.2** **Launch at login** checkbox reflects and controls the real autostart-file state (`~/.config/autostart/take-note.desktop`).
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **10.3** **New notes stay on top by default** checkbox controls new notes' initial always-on-top state.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **10.4** **Default note size** / **Default notepad size** dropdowns (Small/Medium/Large/Extra Large, with pixel dimensions shown) apply to newly-created notes/notepads only, existing ones unaffected.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **10.5** **Default note color** swatch grid picks new notes' starting color when **Randomize new note color** is off; checking Randomize visibly dims that grid and switches to a random color per new note.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **10.6** **Default font size**/**Default font color** apply to the first character typed into a brand-new empty note only.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **10.7** Button row is **OK / Apply / Cancel**. Apply takes effect immediately without closing the dialog; OK afterward doesn't double-apply. Changing one setting doesn't silently reset unrelated ones (e.g. the Notes Manager's remembered window position survives). The dialog remembers its own position/size across restarts (both OK and Cancel), and starts sized to fit all its content even with no saved size yet.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **10.8** **"Check spelling as you type"** checkbox at the bottom, unchecked by default — see §13 for the full pass.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues

### Hotkey tab

Five independent recorder sections — New Note (default `Meta+Alt+N`), Notes Manager (default `Meta+Alt+B`), Show/Hide All Notes, Roll Up/Down All Notes, Bring All Notes to Front (these last three: no default, opt-in only). Each has its own field, Clear button, Test button, and status line. The tab scrolls rather than growing the dialog to fill the screen.

- [x] **10.9** A grey hint at the top of the tab explains that a combo doing nothing in a field is likely already grabbed by a system shortcut. Confirm by trying a combo you know is bound in System Settings → Shortcuts — nothing appears in the field at all.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **10.10** Typing a new combo and clicking that section's **Test** reports "✓ Available" or "✗ Already in use by another app" live, without committing it.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **10.11** Clicking **OK** actually commits a changed hotkey — old combo stops working, new one does. Changing one section doesn't disturb any other's still-working hotkey.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **10.12** Type the same not-currently-configured combo into two different fields, click Test on one — reports it matches the other section's field instead of attempting a real conflicting grab. OK/Apply without fixing either — a dialog names both conflicting fields rather than silently committing the duplicate. _(Don't type a combo that's already live-grabbed by one of this app's own listeners into a field — see Known Limitations at the end for why that can't be recorded at all; it'll trigger the real action instead, e.g. typing `Meta+Alt+N` into any field just creates a new note.)_
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **10.13** Click **Clear** next to any field — empties immediately, no confirmation. OK — that hotkey stops working entirely and stays blank on reopen. Every other hotkey keeps working throughout. With a field cleared, Test reports "Enter a key combination first."
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **10.14** Set and OK a combo for each of Show/Hide All Notes, Roll Up/Down All Notes, and Bring All Notes to Front — each works from anywhere, matching the tray menu's equivalent bulk action.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues

## 11\. Tray menu (full pass)

- [x] **11.1** **New Note** / **New Notepad** / **Notes Manager…** each work as described above. **Notepads** submenu (§8.12) lists every board with a shown/hidden checkmark.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **11.2** **Bring Notes on Top** raises every open note above other windows.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **11.3** One **Show/Hide All Notes** item: converges to all-visible or all-hidden regardless of current mixed state. A single note can also be hidden on its own via ☰ → **Hide Note** — still listed and reopenable (double-click) in the Notes Manager while hidden. Both session-only, don't expect either to persist across a restart.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **11.4** **Roll Up/Down Notes**: converges to all-rolled-up or all-expanded, never a mixed state.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **11.5** **Settings…** and **Quit** work as described above.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues

## 12\. Cross-cutting / theme

- [x] **12.1** Switch your desktop between light and dark mode — context menus and color pickers adapt to match, but note colors themselves stay exactly as set regardless of theme.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **12.2** `Shift+F2` opens Add Title correctly; `Ctrl+F2` does not (switches your virtual desktop instead — a real KWin conflict on this machine, not a bug here).
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues

## 13\. Spell check (optional, off by default)

- [x] **13.1** Settings → General shows **"Check spelling as you type,"** unchecked by default. Checking it (Apply or OK) takes effect immediately on already-open notes.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **13.2** Type a misspelled word (e.g. "teh", "wrold") — a red wavy underline appears shortly after. Correctly-spelled words never get underlined; fixing the typo clears the underline live.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **13.3** A misspelled word inside hyperlink text is not underlined (link text is skipped from checking entirely).
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **13.4** Right-click a misspelled word — suggested corrections appear above **Font…**, followed by **Ignore** and **Add to Dictionary**. Clicking a suggestion replaces the word in place. Right-click a correctly-spelled word — none of this appears.
    - [ ] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **13.5** Right-click a badly garbled "word" with no close match — either a short suggestion list or a disabled "(No suggestions)" placeholder, still followed by Ignore/Add to Dictionary — not a crash or broken menu.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **13.6** Click **Add to Dictionary** on a misspelled word — underline disappears immediately. Quit and relaunch, type that word again anywhere — still not flagged (persists system-wide, across restarts).
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **13.7** Unchecking the setting (Apply) removes underlines from all open notes immediately; right-clicking a misspelled-looking word shows the normal menu, no suggestions.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **13.8** With spell-check on, quit and relaunch — notes' Date Modified (checked beforehand) doesn't bump just from being reopened.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **13.9** With the optional dependency unavailable (`pip uninstall pyenchant` from `.venv`, relaunch), the checkbox is disabled with an always-visible, clearly legible explanatory line below it (medium grey, same font size as other labels, flush left) — in both light and dark desktop theme. **Remember to `pip install pyenchant` back into `.venv` afterward.**
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues

### Permanent Ignore (new — test on branch `feature/spellcheck-ignore-list`)

"Ignore" no longer forgets the word when you restart the app — it's now remembered permanently, but scoped to Take Note! only, never touching your system's real Enchant dictionary the way Add to Dictionary does.

- [x] **13.10** Right-click a misspelled word and click **Ignore** — underline disappears immediately, including every other instance of that word already visible in any open note. (Same as before — this part hasn't changed.)
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **13.11** Quit and relaunch the app, then type that same word again in any note — it is **not** flagged as misspelled (this is the actual behavior change — it used to come back flagged after a restart, now it stays ignored).
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **13.12** Check `~/.local/share/take-note/notes.json`'s `settings.ignored_words` list directly (`cat` it, or `python -c "import json; print(json.load(open('...'))['settings']['ignored_words'])"`) — the word you ignored is in there.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **13.13** Ignore the same word a second time (on a different instance of it, or after retyping it) — no error, and `ignored_words` in the JSON file still lists it only once, not duplicated.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues

## 14\. Tags

- [x] **14.1** ☰ → **Tags…** opens a dialog with a comma-separated text field. Setting tags shows a small filled-ribbon icon in the header, left of the lock icon. Reopening the dialog pre-fills the current tags.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **14.2** Cancel leaves tags unchanged. Clearing the field and OK removes all tags (icon disappears from the header). Messy input (extra spaces, trailing comma, a duplicate tag) gets cleaned up and deduplicated on save.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **14.3** Tagged notes show their tags in the Notes Manager's **Tags** column. A **Tags** tree node lists every unique tag in use, alphabetically; clicking one filters the table to notes with that tag. Removing a tag from every note that had it makes it disappear from the tree live.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **14.4** Hovering the header's tag icon (note focused) shows a tooltip listing the tags. Clicking it opens the Tags… dialog directly. Tag and lock icons coexist side by side without overlapping, each independently clickable. The icon survives a restart.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues

## 15\. Reminders

One-shot only — fires once and clears itself, no repeat. Delivery is raising the note itself, not a desktop notification.

- [x] **15.1** ☰ → **Set Reminder…** opens a date/time picker (calendar popup, can't pick a past time) or a quick "remind me in N minutes" option (default for a brand-new reminder). Once set, a bell icon appears in the header with a tooltip showing the due time in local wall-clock time.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **15.2** ☰ now reads **Edit Reminder…**, prefilling the picker with the existing time (defaults to the absolute picker, not the quick one, when editing). **Clear Reminder** removes the bell icon and reverts the menu label.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **15.3** Set a short reminder, then roll the note up or put other windows in front — within ~30s of the due time, it un-rolls/restores and raises itself to the front on its own, and plays a brief chime (Settings → General, on by default — toggle it off and confirm a reminder fires silently instead).
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **15.4** Set a reminder, quit before it fires, wait past the due time, relaunch — the note is raised/shown immediately on launch and the reminder clears.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **15.5** Set a reminder, then move that note to Trash before it fires — it does not pop back up at the due time, and doesn't fire later even once restored.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **15.6** Set reminders on two different notes for close to the same time — both fire independently, no interference.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues
- [x] **15.7** Notes Manager's **Reminder** column shows each note's reminder due time, blank when unset.
    - [x] Pass
    - [ ] Fail
    - [ ] Pass with Issues

* * *

## Known, accepted limitations — do not file these as bugs

- Wayland: window positioning and the global hotkeys require XWayland; this machine already runs through it.
- "Stick to Window" can't see native-Wayland client windows, only X11/XWayland ones. A stuck note's taskbar-skip hint can briefly flash on during the target window's minimize/restore remap before self-correcting almost immediately — an apparent property of the mechanism itself, not something further tuning fully eliminates.
- Some other apps' own global hotkeys can out-prioritize this app's hotkey grab; not fixable from our side.
- Typing a combo that's **already live-grabbed by one of this app's own hotkey listeners** into any field anywhere can't be recorded at all — it fires the real global action instead (e.g. typing `Meta+Alt+N` creates a new note rather than landing in the field). All 5 listeners stay live the whole time the app runs, Settings open or not.
- Board/note windows only resize from the bottom-right corner grip — no edge-dragging (frameless windows, no OS-native resize border).
- No per-action custom hotkeys (Bold/Italic/Add Title, etc.) — only the five global hotkeys above are configurable. Explicitly not planned; these are universal/standard shortcuts nobody's asked to remap.
- Spell check needs its optional dependency (`pyenchant` + a system Enchant/dictionary install) — the Settings checkbox is disabled with an explanatory label when missing.
- No autocomplete in the Tags dialog — plain comma-separated free text, deliberately kept simple.
- Reminders are one-shot only and fire by raising the note itself, not a desktop notification — deliberate scope choices.
- Auto-detected plain-text URLs (§3.10) only do a basic host-sanity check, not real domain validation — an obviously-broken host like `http://www,google.com` is correctly rejected, but a syntactically-valid-looking fake domain would still linkify.