# Take Note! — Manual Test Cases (v2)

Covers everything built as of commit `5fae3b4` on `main` (2026-07-10).
Distinct from the automated `pytest` suite in `tests/` — this is for
exercising the real app by hand under a real desktop (XWayland/KDE
Plasma), where things like window-manager interaction, real fonts, and
compositor behavior actually matter.

**v2 changes from v1:** personalized to this system (Robin's machine) —
concrete paths instead of generic ones, since this doc only has one
tester. No test cases removed; a few tightened up with exact values to
check against.

## Your system

- Repo: `/home/robinsiebler/Code/take_note`
- Launch: `/home/robinsiebler/Code/take_note/.venv/bin/take-note`
  (or `cd` into the repo and run `.venv/bin/take-note`)
- Python 3.14.6, PySide6 6.11.1
- Desktop: KDE Plasma, running through XWayland (`QT_QPA_PLATFORM=xcb`,
  forced by `__main__.py`)
- `XDG_DATA_HOME`/`XDG_CONFIG_HOME` are **unset** on this machine, so the
  app uses the plain `~/.local/share` / `~/.config` fallbacks below.

Each case is a checkbox. Check it off as `[x]` once verified. If a case
fails, note the actual behavior next to it rather than just leaving it
unchecked, so a re-test later doesn't have to rediscover the same bug.

---

## 1. App lifecycle

- [x] **1.1** Your real data lives at
  `/home/robinsiebler/.local/share/take-note/notes.json` — confirm it
  exists and has your actual notes/boards in it (`cat` it or just check
  the file's there). To test the *fresh-install* path (auto-creates one
  default note) without touching your real data, either back up that
  file first (`mv notes.json notes.json.bak`, restore after) or run once
  with an isolated scratch dir:
  `XDG_DATA_HOME=/tmp/take-note-scratch /home/robinsiebler/Code/take_note/.venv/bin/take-note`.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **1.2** Quit via tray icon → **Quit**. App exits cleanly — no crash
  dialog ("Service Crash for Python 3.14" or similar). *(Regression,
  fixed in commit `c7c81c2` — this used to crash on every quit on this
  exact system; confirm it stays fixed.)*
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **1.3** Relaunch after quitting. All notes/boards reappear exactly
  where they were left (position, size, color, content) — reading back
  from the real `notes.json` above.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **1.4** Click the tray icon directly (not right-click) → creates a
  new note, same as **New Note**.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues

## 2. Note creation & window basics

- [x] **2.1** Tray → **New Note** creates a note at a sensible default
  position/size, default color, always-on-top by default.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **2.2** Global hotkey (check Settings → Hotkey tab for the
  currently-configured combo — default is `Ctrl+Alt+N`) creates a new
  note from anywhere, even with no Take Note! window focused.
  - [ ] Pass
  - [ ] Fail
  - [x] Pass with Issues — Note: Testing/using Ctrl+Alt+N causes "Bad
    Access" error messages to appear in terminal.
- [x] **2.3** Note header's `+` button creates another new note.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **2.4** Drag a note by its header — moves smoothly, no lag/tearing.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **2.5** Resize a note by dragging its bottom-right corner grip.
  *(Only present on a standalone note — see §7 for board-attached
  behavior.)*
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **2.6** Header **▲/▼** button (or double-click the header) rolls
  the note up to just its header, and back down. Roll-up state and each
  note's position/size persist across a restart.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **2.7** Header `×` → confirmation dialog **"Delete this note
  permanently?"**; **Yes** deletes it, **No**/close leaves it untouched.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **2.8** A note stays on top of normal windows when **Always on
  Top** is checked (hamburger ☰ menu), and behaves like a normal window
  (can be covered) when unchecked.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **2.9** Note Transparency submenu (☰ → **Note Transparency**):
  **None/Low/Medium/High/Full** each visibly change opacity; selection
  is exclusive (only one checked at a time) and persists across restart.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues

## 3. Rich text editing (right-click the note body)

- [x] **3.1** **Font…** opens the native font-family/size/style picker;
  applies to the current selection (or becomes the typing default with
  no selection). Your system's default UI font is **Noto Sans** — that's
  what should show pre-selected on a fresh note.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **3.2** **Font Style** submenu: **Bold** (`Ctrl+B`), **Italic**
  (`Ctrl+I`), **Underline** (`Ctrl+U`), **Strikethrough** (`Ctrl+K`)
  each toggle correctly on a selection and via their shortcuts.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **3.3** **Font Style** → **Left/Center/Right** alignment applies
  to the current paragraph.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [ ] **3.4** **Font Color…** swatch picker recolors selected text;
  picker itself has rounded corners and a visible border (not
  square/flat).
  - [ ] Pass
  - [x] Fail — FAIL: Text disappeard when new font color was applied.
  - [ ] Pass with Issues
- [ ] **3.5** **Bullets && Numbering** submenu: each style (•, 1/2/3,
  a/b/c, A/B/C, i/ii/iii, I/II/III) applies correctly; **None** removes
  list formatting. Selection is exclusive.
  - [ ] Pass
  - [x] Fail — Note: Selecting multiple bulleted item causes a
    checkmark glyph while the text is seolected.
  - [ ] Pass with Issues
- [x] **3.6** **Increase Indent** / **Decrease Indent** nest/un-nest list
  items correctly, including across multi-line selections at different
  depths.
  - [ ] Pass
  - [ ] Fail
  - [x] Pass with Issues — Note: Too wide of an indent issue is back.
- [x] **3.7** Tab / Shift+Tab inside a list item also indent/dedent (not
  just the menu items).
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **3.8** **Add picture…** inserts an image inline; note grows to
  fit (width and height) rather than shrinking the image, capped at
  screen size for an oversized picture. Pick a real photo from wherever
  you keep them to test with an actually-large image.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **3.9** Right-click an inserted picture → menu now says **Replace
  picture…** instead of **Add picture…**; replacing it works.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **3.10** **Hyperlink…** on a selection (or typed URL) turns it
  into a clickable link. Plain click on a link just places the cursor
  (link text stays editable); `Ctrl+Click` opens it in your default
  browser. Hovering shows a hand cursor + tooltip.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [ ] **3.11** Right-click with the caret inside an existing link (no
  selection) → menu says **Edit Hyperlink…** and pre-fills the current
  URL.
  - [ ] Pass
  - [x] Fail — FAIL: Still reads "Hyperlink"; URL not pre-filled.
  - [ ] Pass with Issues
- [x] **3.12** Undo/Redo/Cut/Copy/Paste/Select All (Qt's built-in menu,
  shown above the app's own items) all work normally.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues

## 4. Find, Lock, and Title

- [x] **4.1** `Ctrl+F` or right-click → **Find…** opens a small find bar
  between header and body. Typing searches live; **▲/▼** step through
  matches with wraparound; `×` (or Esc) closes it.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **4.2** **Find…** is disabled (greyed out, not clickable) on a
  completely empty note, and becomes enabled the moment you type
  anything.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **4.3** ☰ → **Lock Note** makes the body read-only. Right-click
  menu collapses to just **Find…**. `Ctrl+B`/`I`/`U`/`K` no longer do
  anything while locked.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **4.4** Header padlock icon toggles lock too — white/unlocked vs.
  amber/locked. A single click toggles once; a double-click also
  toggles exactly once (not twice/net-no-op).
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **4.5** `Shift+F2` (or ☰ → **Add Title…**) opens a dialog to set a
  title. Once set, a bold title bar appears between header and body, and
  the menu item now reads **Edit Title…**. *(Not `Ctrl+F2` — that's
  bound on this exact machine to KWin's "Switch to Desktop 2", see
  §11.2.)*
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **4.6** Title's font (family + size) matches whatever the note
  body's font currently is, and stays bold. Change the note's font size
  (via **Font…**) and re-open/re-set the title — the title should scale
  with it.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **4.7** Clearing the title (empty string in the dialog) hides the
  title bar again and reverts the menu label to **Add Title…**.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **4.8** Cancelling the title dialog leaves the existing title
  unchanged.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues

## 5. Note color & appearance

- [x] **5.1** ☰ → **Change Note Color…** opens a swatch-grid popup with
  rounded corners and a visible thicker border (not the old square/flat
  look) — 12 swatches, checkmark on the currently-selected one.
  - [ ] Pass
  - [ ] Fail
  - [x] Pass with Issues — cl: White checkmark barely visible on yellow
    swatch.
- [x] **5.2** Picking a color updates the note (header/body/footer/
  find-bar tint) immediately and persists across restart.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **5.3** The in-note find bar's background tints toward the note's
  own color (a lighter blend), and updates live if you change the note
  color while the find bar is open.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **5.4** Every color swatch (in both the note-color and font-color
  pickers, and in Settings) has a visible border regardless of how
  light or dark the swatch itself is — no swatch blends invisibly into
  the popup background.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues

## 6. Stick to Window

- [x] **6.1** ☰ → **Stick to Window…** opens a picker listing other real
  windows on your desktop (not Take Note's own windows). Try it with
  something ordinary you have open, like Dolphin or a terminal.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [ ] **6.2** After sticking, minimizing/restoring the target window
  hides/shows the note in sync; closing the target window also
  hides/closes the association appropriately.
  - [ ] Pass
  - [x] Fail — FAIL: Closing the window did not make the note hide.
    Quiting the app broke the association, but the note still thinks it
    is stuck to that window.
  - [ ] Pass with Issues
- [x] **6.3** ☰ menu now shows **Unstick from Window** for a stuck note;
  using it detaches it.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **6.4** A native Wayland app (e.g. Chromium/Vivaldi launched with
  `--ozone-platform=wayland`, or many Electron apps) does **not** appear
  in the picker — expected limitation on this Wayland-with-XWayland
  setup, not a bug (see README).
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues

## 7. Notepad (the per-board corkboard window)

- [x] **7.1** Tray → **New Notepad** creates a small corkboard-style
  window titled with the board's name.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **7.2** Right-click empty canvas → **New Note on this Board**
  creates a note already attached to that board.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **7.3** Right-click empty canvas → **Rename Board** lets you
  rename it; the header label updates immediately.
  - [ ] Pass
  - [ ] Fail
  - [x] Pass with Issues — Note: THe rename dialog was too small.
- [x] **7.4** Right-click empty canvas → **Delete Board** →
  confirmation ("Delete this Notepad? Notes on it will be moved back to
  the desktop.") → notes previously on it reappear as standalone notes
  rather than being deleted.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **7.5** From an existing standalone note, ☰ → **Add to Notepad**
  submenu lists every existing board by name, plus **New Notepad…** at
  the bottom. Picking a board reparents the note onto it.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **7.6** Once attached, that note's ☰ menu now shows **Remove from
  Notepad** (no submenu) instead of **Add to Notepad**; using it pops
  the note back to the desktop.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **7.7** A note attached to a board has no visible resize grip in
  its footer, and its rounded bottom-right corner renders cleanly — no
  grey notch/artifact cut into it. *(Fixed in `77b52c2` — this used to
  show a rendering artifact on this exact system, and dragging the grip
  would've resized the whole board instead of the note.)*
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **7.8** A standalone (non-board) note **does** still have its
  resize grip, and dragging it resizes just that note.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **7.9** Detaching a note (7.6) brings its resize grip back.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **7.10** Drag a note's header to reposition it within the board
  canvas — moves smoothly, corner still renders cleanly afterward (no
  leftover artifact at the old or new position).
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **7.11** A near-empty board at its default size (400×300) shows no
  scrollbar. *(Fixed in `5fae3b4` — this used to show scrollbars
  unconditionally on this exact system, since the canvas was hardcoded
  to a 600×600 minimum regardless of content.)*
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **7.12** Grow the board window much bigger, then shrink it back
  down — no lingering/spurious scrollbar if your notes still comfortably
  fit at the smaller size.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **7.13** Drag a note far outside the board's currently-visible
  area — the canvas grows to keep it reachable (scrollbars appear as
  needed), rather than the note becoming permanently unreachable/
  clipped. Drag it back near the origin — the canvas shrinks back down
  and the scrollbar goes away again.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **7.14** Board header's `×` hides the board (doesn't delete it).
  *(Known gap: no in-app way to reopen it afterward except via the Notes
  Browser — see §8.9 — and it does **not** currently remember being
  closed across a restart; it'll reopen automatically next launch. Not a
  bug to file, just confirming current behavior.)*
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **7.15** Drag the board window's own bottom-right corner grip —
  resizes the whole board window (this one's supposed to affect the
  board, unlike 7.7's note-level grip). This is currently the *only* way
  to resize a board or note — there's no edge-dragging, since these are
  frameless windows with no OS-native resize border. Expected, not a
  bug.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **7.16** *(Known gap, not a bug)* The board window's own chrome
  (flat grey header/canvas, native scrollbars) still looks visually
  plain/unpolished compared to note windows — no fix expected yet.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues

## 8. Notes Browser

- [x] **8.1** Tray → **Notes Browser…** opens a single window titled
  "Take Note! — Notes Browser". Opening it again while already open
  just raises/focuses the existing one (doesn't spawn a second).
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **8.2** Left tree shows **All Notes**, **Unfiled**, then one entry
  per existing board (by name) — should match whatever boards you
  actually have right now.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **8.3** Selecting **All Notes** lists every note; **Unfiled** shows
  only notes with no board; a board name shows only that board's notes.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **8.4** Table has four columns: **Title**, **Preview**,
  **Notepad**, **Date Modified** (US format, e.g. "July 10, 2026 03:56
  PM").
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **8.5** An untitled note shows **(untitled)** in Title but a real
  snippet of its body text in **Preview** — enough to actually tell two
  untitled notes apart at a glance.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **8.6** A note attached to a board shows that board's name in the
  **Notepad** column; an unattached note shows that column blank.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **8.7** Typing in **Search notes…** filters live by both title
  *and* body text (e.g. searching a word that only appears in the body
  still finds it). The field has a visible clear (×) button once you've
  typed something.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **8.8** Clicking a column header sorts by that column; **Date
  Modified** sorts chronologically (not alphabetically by the displayed
  "Month Day, Year" text).
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **8.9** Double-clicking a note row raises/shows that real note
  window. Double-clicking a board row in the tree raises/shows that
  board window.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **8.10** Ctrl-click / Shift-click selects multiple rows. Toolbar
  **Delete** (or right-click → **Delete N Notes**) asks **one**
  confirmation for the whole selection and deletes them all.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **8.11** Right-click a single row → **Show Note**, **Remove from
  Notepad** (only if attached), **Delete Note**.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **8.12** Right-click a board in the tree → **Rename** / **Delete
  Notepad** (same effect as doing it from the board window itself).
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **8.13** Toolbar **New Note**: creates an unattached note when
  **All Notes**/**Unfiled** is selected, or attaches it to whichever
  board is currently selected in the tree.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **8.14** Toolbar **New Notepad** creates a new board, which
  immediately appears in the tree.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **8.15** Creating/deleting/renaming a note or board elsewhere in
  the app (not through this window) updates the browser's list live
  within about half a second, without needing to close/reopen it.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **8.16** Resize and/or move the Notes Browser window, then quit
  and relaunch the app — it reopens at the exact size/position you left
  it at.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues

## 9. Settings dialog (tray → Settings…)

### General tab

- [x] **9.1** **Launch at login** checkbox reflects real autostart-file
  state. Toggling it creates/removes
  `/home/robinsiebler/.config/autostart/take-note.desktop` — check with
  `ls /home/robinsiebler/.config/autostart/` after toggling to confirm
  it's really there/gone.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **9.2** **New notes stay on top by default** checkbox controls new
  notes' initial always-on-top state.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **9.3** **Default note color** swatch grid picks the color new
  notes start with (when randomize, below, is off).
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **9.4** **Randomize new note color** checkbox: when checked, the
  color swatch grid above visibly dims (not just stops responding —
  actually looks disabled), and new notes get a random color from the
  palette instead of the fixed default. Unchecking restores the
  fixed-default behavior.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **9.5** **Default font size** (6–72pt) and **Default font color**
  swatch grid apply to the first character typed into a brand-new empty
  note — not to notes that already have content.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **9.6** Clicking **OK** after changing *only* one setting doesn't
  silently reset unrelated settings (e.g. the Notes Browser's remembered
  window position/size from §8.16 should survive going through Settings
  and clicking OK).
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues

### Hotkey tab

- [x] **9.7** Current global hotkey shows in the recorder field; typing
  a new combo and clicking **Test** reports **"✓ Available"** or **"✗
  Already in use by another app"** live, without committing it.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **9.8** Clicking **OK** actually commits a changed hotkey — the
  old combo stops creating notes, the new one does.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **9.9** *(Known gap)* This tab only configures the one global
  "new note" hotkey — there's no way here to rebind in-app shortcuts
  like Bold/Italic/Add Title. Not a bug; a distinct, not-yet-started
  feature.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues

## 10. Tray menu (full pass)

- [x] **10.1** **New Note** / **New Notepad** / **Notes Browser…** each
  work as described above.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **10.2** **Bring Notes on Top** raises every open note above other
  windows.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **10.3** **Show All Notes** / **Hide All Notes** show/hide every
  note (session-only — don't expect this to persist across a restart).
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **10.4** **Roll Up/Down Notes**: if any note is currently
  expanded, rolls *all* of them up; if all are already rolled up,
  expands *all* of them — never leaves a mixed state.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **10.5** **Settings…** opens the dialog from §9.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **10.6** **Quit** exits cleanly (see §1.2).
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **10.7** *(Known gap, cosmetic)* Menu separators show as plain
  gaps, no visible line — KDE's native tray menu doesn't pick up the
  app's own stylesheet. Not fixable from our side; don't file it.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues

## 11. Cross-cutting / theme

- [x] **11.1** Switch your desktop between light and dark mode (System
  Settings → Appearance → Global Theme) — context menus and the
  color-picker popup adapt to match, but note colors themselves stay
  exactly as set regardless of theme.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **11.2** Confirmed on this machine:
  `~/.config/kglobalshortcutsrc` has
  `Switch to Desktop 2=Ctrl+F2\tMeta+F2` — a real, live conflict, not
  hypothetical. Confirm `Shift+F2` opens Add Title correctly and
  `Ctrl+F2` does *not* (it should switch your virtual desktop instead,
  which is KWin's normal behavior, not this app's).
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues

---

## Known, accepted limitations — do not file these as bugs

- Wayland: window positioning and the global hotkey require XWayland;
  this machine already runs through it, so this shouldn't actually bite
  you day-to-day — only relevant if you ever try running on a compositor
  without XWayland support.
- "Stick to Window" can't see native-Wayland client windows, only
  X11/XWayland ones.
- Tray menu separators render as plain gaps — see §10.7.
- Some other apps' own global hotkeys can out-prioritize this app's
  hotkey grab; not fixable from our side.
- Board/note windows only resize from the bottom-right corner grip — no
  edge-dragging, since these are frameless windows with no OS-native
  resize border.
- No per-action custom hotkeys yet (Bold/Italic/Add Title etc.) — only
  the one global new-note hotkey is configurable. See §9.9.
