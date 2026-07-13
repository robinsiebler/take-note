# Take Note! — Manual Test Cases (v1)

Covers everything built as of commit `77b52c2` on `main` (2026-07-10).
Distinct from the automated `pytest` suite in `tests/` — this is for
exercising the real app by hand under a real desktop (XWayland/KDE
Plasma), where things like window-manager interaction, real fonts, and
compositor behavior actually matter.

**How to run:** `.venv/bin/take-note`, or `python3 -m take_note` from
the repo root with the venv active.

Each case is a checkbox. Check it off as `[x]` once verified. If a case
fails, note the actual behavior next to it rather than just leaving it
unchecked, so a re-test later doesn't have to rediscover the same bug.

---

## 1. App lifecycle

- [ ] **1.1** Launch the app with no `notes.json` present (fresh install, or point `XDG_DATA_HOME` at an empty dir). One default note is created automatically.
- [ ] **1.2** Quit via tray icon → **Quit**. App exits cleanly — no crash dialog ("Service Crash for Python 3.14" or similar). *(Regression: this used to crash on every quit — see §9.)*
- [ ] **1.3** Relaunch after quitting. All notes/boards reappear exactly where they were left (position, size, color, content).
- [ ] **1.4** Click the tray icon directly (not right-click) → creates a new note, same as **New Note**.

## 2. Note creation & window basics

- [ ] **2.1** Tray → **New Note** creates a note at a sensible default position/size, default color, always-on-top by default.
- [ ] **2.2** Global hotkey (default `Ctrl+Alt+N`, or whatever's configured in Settings) creates a new note from anywhere, even with no Take Note! window focused.
- [ ] **2.3** Note header's `+` button creates another new note.
- [ ] **2.4** Drag a note by its header — moves smoothly, no lag/tearing.
- [ ] **2.5** Resize a note by dragging its bottom-right corner grip. *(Only present on a standalone note — see §7 for board-attached behavior.)*
- [ ] **2.6** Header **▲/▼** button (or double-click the header) rolls the note up to just its header, and back down. Roll-up state and each note's position/size persist across a restart.
- [ ] **2.7** Header `×` → confirmation dialog **"Delete this note permanently?"**; **Yes** deletes it, **No**/close leaves it untouched.
- [ ] **2.8** A note stays on top of normal windows when **Always on Top** is checked (hamburger ☰ menu), and behaves like a normal window (can be covered) when unchecked.
- [ ] **2.9** Note Transparency submenu (☰ → **Note Transparency**): **None/Low/Medium/High/Full** each visibly change opacity; selection is exclusive (only one checked at a time) and persists across restart.

## 3. Rich text editing (right-click the note body)

- [ ] **3.1** **Font…** opens the native font-family/size/style picker; applies to the current selection (or becomes the typing default with no selection).
- [ ] **3.2** **Font Style** submenu: **Bold** (`Ctrl+B`), **Italic** (`Ctrl+I`), **Underline** (`Ctrl+U`), **Strikethrough** (`Ctrl+K`) each toggle correctly on a selection and via their shortcuts.
- [ ] **3.3** **Font Style** → **Left/Center/Right** alignment applies to the current paragraph.
- [ ] **3.4** **Font Color…** swatch picker recolors selected text; picker itself has rounded corners and a visible border (not square/flat).
- [ ] **3.5** **Bullets && Numbering** submenu: each style (•, 1/2/3, a/b/c, A/B/C, i/ii/iii, I/II/III) applies correctly; **None** removes list formatting. Selection is exclusive.
- [ ] **3.6** **Increase Indent** / **Decrease Indent** nest/un-nest list items correctly, including across multi-line selections at different depths.
- [ ] **3.7** Tab / Shift+Tab inside a list item also indent/dedent (not just the menu items).
- [ ] **3.8** **Add picture…** inserts an image inline; note grows to fit (width and height) rather than shrinking the image, capped at screen size for an oversized picture.
- [ ] **3.9** Right-click an inserted picture → menu now says **Replace picture…** instead of **Add picture…**; replacing it works.
- [ ] **3.10** **Hyperlink…** on a selection (or typed URL) turns it into a clickable link. Plain click on a link just places the cursor (link text stays editable); `Ctrl+Click` opens it in the default browser. Hovering shows a hand cursor + tooltip.
- [ ] **3.11** Right-click with the caret inside an existing link (no selection) → menu says **Edit Hyperlink…** and pre-fills the current URL.
- [ ] **3.12** Undo/Redo/Cut/Copy/Paste/Select All (Qt's built-in menu, shown above the app's own items) all work normally.

## 4. Find, Lock, and Title

- [ ] **4.1** `Ctrl+F` or right-click → **Find…** opens a small find bar between header and body. Typing searches live; **▲/▼** step through matches with wraparound; `×` (or Esc) closes it.
- [ ] **4.2** **Find…** is disabled (greyed out, not clickable) on a completely empty note, and becomes enabled the moment you type anything.
- [ ] **4.3** ☰ → **Lock Note** makes the body read-only. Right-click menu collapses to just **Find…**. `Ctrl+B`/`I`/`U`/`K` no longer do anything while locked.
- [ ] **4.4** Header padlock icon toggles lock too — white/unlocked vs. amber/locked. A single click toggles once; a double-click also toggles exactly once (not twice/net-no-op).
- [ ] **4.5** `Shift+F2` (or ☰ → **Add Title…**) opens a dialog to set a title. Once set, a bold title bar appears between header and body, and the menu item now reads **Edit Title…**.
- [ ] **4.6** Title's font (family + size) matches whatever the note body's font currently is, and stays bold. Change the note's font size (via **Font…**) and re-open/re-set the title — the title should scale with it.
- [ ] **4.7** Clearing the title (empty string in the dialog) hides the title bar again and reverts the menu label to **Add Title…**.
- [ ] **4.8** Cancelling the title dialog leaves the existing title unchanged.

## 5. Note color & appearance

- [ ] **5.1** ☰ → **Change Note Color…** opens a swatch-grid popup with **rounded corners and a visible thicker border** (not the old square/flat look) — 12 swatches, checkmark on the currently-selected one.
- [ ] **5.2** Picking a color updates the note (header/body/footer/find-bar tint) immediately and persists across restart.
- [ ] **5.3** The in-note find bar's background tints toward the note's own color (a lighter blend), and updates live if you change the note color while the find bar is open.
- [ ] **5.4** Every color swatch (in both the note-color and font-color pickers, and in Settings) has a visible border regardless of how light or dark the swatch itself is — no swatch blends invisibly into the popup background.

## 6. Stick to Window

- [ ] **6.1** ☰ → **Stick to Window…** opens a picker listing other real windows on the desktop (not Take Note's own windows).
- [ ] **6.2** After sticking, minimizing/restoring the target window hides/shows the note in sync; closing the target window also hides/closes the association appropriately.
- [ ] **6.3** ☰ menu now shows **Unstick from Window** for a stuck note; using it detaches it.
- [ ] **6.4** A native Wayland app (e.g. a browser launched with `--ozone-platform=wayland`) does **not** appear in the picker — expected limitation, not a bug (see README).

## 7. Notepad (the per-board corkboard window)

- [ ] **7.1** Tray → **New Notepad** creates a small corkboard-style window titled with the board's name.
- [ ] **7.2** Right-click empty canvas → **New Note on this Board** creates a note already attached to that board.
- [ ] **7.3** Right-click empty canvas → **Rename Board** lets you rename it; the header label updates immediately.
- [ ] **7.4** Right-click empty canvas → **Delete Board** → confirmation ("Delete this Notepad? Notes on it will be moved back to the desktop.") → notes previously on it reappear as standalone notes rather than being deleted.
- [ ] **7.5** From an existing standalone note, ☰ → **Add to Notepad** submenu lists every existing board by name, plus **New Notepad…** at the bottom. Picking a board reparents the note onto it.
- [ ] **7.6** Once attached, that note's ☰ menu now shows **Remove from Notepad** (no submenu) instead of **Add to Notepad**; using it pops the note back to the desktop.
- [ ] **7.7** **A note attached to a board has no visible resize grip in its footer**, and its rounded bottom-right corner renders cleanly — no grey notch/artifact cut into it. *(Regression: this used to show a rendering artifact and, if you could still find the grip, dragging it would resize the whole board instead of the note.)*
- [ ] **7.8** A standalone (non-board) note **does** still have its resize grip, and dragging it resizes just that note.
- [ ] **7.9** Detaching a note (7.6) brings its resize grip back.
- [ ] **7.10** Drag a note's header to reposition it within the board canvas — moves smoothly, corner still renders cleanly afterward (no leftover artifact at the old or new position).
- [ ] **7.11** Board header's `×` hides the board (doesn't delete it). *(Known gap: no in-app way to reopen it afterward except via the Notes Browser — see §8.9 — and it does **not** currently remember being closed across a restart; it'll reopen automatically next launch. Not a bug to file, just confirming current behavior.)*
- [ ] **7.12** Drag the board window's own bottom-right corner grip — resizes the whole board window (this one's supposed to affect the board, unlike 7.7's note-level grip).
- [ ] **7.13** *(Known gap, not a bug)* The board window's own chrome (flat grey header/canvas, native scrollbars) still looks visually plain/unpolished compared to note windows — no fix expected yet.

## 8. Notes Browser

- [ ] **8.1** Tray → **Notes Browser…** opens a single window titled "Take Note! — Notes Browser". Opening it again while already open just raises/focuses the existing one (doesn't spawn a second).
- [ ] **8.2** Left tree shows **All Notes**, **Unfiled**, then one entry per existing board (by name).
- [ ] **8.3** Selecting **All Notes** lists every note; **Unfiled** shows only notes with no board; a board name shows only that board's notes.
- [ ] **8.4** Table has four columns: **Title**, **Preview**, **Notepad**, **Date Modified** (US format, e.g. "July 10, 2026 03:56 PM").
- [ ] **8.5** An untitled note shows **(untitled)** in Title but a real snippet of its body text in **Preview** — enough to actually tell two untitled notes apart at a glance.
- [ ] **8.6** A note attached to a board shows that board's name in the **Notepad** column; an unattached note shows that column blank.
- [ ] **8.7** Typing in **Search notes…** filters live by both title *and* body text (e.g. searching a word that only appears in the body still finds it). The field has a visible clear (×) button once you've typed something.
- [ ] **8.8** Clicking a column header sorts by that column; **Date Modified** sorts chronologically (not alphabetically by the displayed "Month Day, Year" text).
- [ ] **8.9** Double-clicking a note row raises/shows that real note window. Double-clicking a board row in the tree raises/shows that board window.
- [ ] **8.10** Ctrl-click / Shift-click selects multiple rows. Toolbar **Delete** (or right-click → **Delete N Notes**) asks **one** confirmation for the whole selection and deletes them all.
- [ ] **8.11** Right-click a single row → **Show Note**, **Remove from Notepad** (only if attached), **Delete Note**.
- [ ] **8.12** Right-click a board in the tree → **Rename** / **Delete Notepad** (same effect as doing it from the board window itself).
- [ ] **8.13** Toolbar **New Note**: creates an unattached note when **All Notes**/**Unfiled** is selected, or attaches it to whichever board is currently selected in the tree.
- [ ] **8.14** Toolbar **New Notepad** creates a new board, which immediately appears in the tree.
- [ ] **8.15** Creating/deleting/renaming a note or board elsewhere in the app (not through this window) updates the browser's list live within about half a second, without needing to close/reopen it.
- [ ] **8.16** Resize and/or move the Notes Browser window, then quit and relaunch the app — it reopens at the exact size/position you left it at.

## 9. Settings dialog (tray → Settings…)

### General tab
- [ ] **9.1** **Launch at login** checkbox reflects real autostart-file state and toggling it actually creates/removes that file.
- [ ] **9.2** **New notes stay on top by default** checkbox controls new notes' initial always-on-top state.
- [ ] **9.3** **Default note color** swatch grid picks the color new notes start with (when randomize, below, is off).
- [ ] **9.4** **Randomize new note color** checkbox: when checked, the color swatch grid above visibly dims (not just stops responding — actually looks disabled), and new notes get a random color from the palette instead of the fixed default. Unchecking restores the fixed-default behavior.
- [ ] **9.5** **Default font size** (6–72pt) and **Default font color** swatch grid apply to the first character typed into a brand-new empty note — not to notes that already have content.
- [ ] **9.6** Clicking **OK** after changing *only* one setting doesn't silently reset unrelated settings (e.g. the Notes Browser's remembered window position/size from §8.16 should survive going through Settings and clicking OK).

### Hotkey tab
- [ ] **9.7** Current global hotkey shows in the recorder field; typing a new combo and clicking **Test** reports **"✓ Available"** or **"✗ Already in use by another app"** live, without committing it.
- [ ] **9.8** Clicking **OK** actually commits a changed hotkey — the old combo stops creating notes, the new one does.

## 10. Tray menu (full pass)

- [ ] **10.1** **New Note** / **New Notepad** / **Notes Browser…** each work as described above.
- [ ] **10.2** **Bring Notes on Top** raises every open note above other windows.
- [ ] **10.3** **Show All Notes** / **Hide All Notes** show/hide every note (session-only — don't expect this to persist across a restart).
- [ ] **10.4** **Roll Up/Down Notes**: if any note is currently expanded, rolls *all* of them up; if all are already rolled up, expands *all* of them — never leaves a mixed state.
- [ ] **10.5** **Settings…** opens the dialog from §9.
- [ ] **10.6** **Quit** exits cleanly (see §1.2).

## 11. Cross-cutting / theme

- [ ] **11.1** Switch your desktop between light and dark mode (if easy to do) — context menus and the color-picker popup adapt to match, but note colors themselves stay exactly as set regardless of theme.
- [ ] **11.2** With a KDE global shortcut bound to `Ctrl+F2` (KDE's classic default for "Switch to Desktop 2"), confirm `Shift+F2` still opens the Add Title dialog correctly (i.e. the app's own shortcut no longer collides).

---

## Known, accepted limitations — do not file these as bugs

- Wayland: window positioning and the global hotkey require XWayland; a compositor without XWayland support won't work (documented in README).
- "Stick to Window" can't see native-Wayland client windows (browsers/apps launched with `--ozone-platform=wayland`), only X11/XWayland ones.
- Tray menu separators render as plain gaps (no visible line) — the native desktop shell draws that menu, not our own styled `QMenu`.
- Some other apps' own global hotkeys can out-prioritize this app's hotkey grab; not fixable from our side.
