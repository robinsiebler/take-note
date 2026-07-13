# Take Note! — Manual Test Cases (v3)

Covers everything built as of commit `279a89c` on `main` (2026-07-10).
Distinct from the automated `pytest` suite in `tests/` — this is for
exercising the real app by hand under a real desktop (XWayland/KDE
Plasma), where things like window-manager interaction, real fonts, and
compositor behavior actually matter.

**v3 changes from v2:** v2's own file got lost mid-export, so this is a
rebuild from the v2 PDF plus v1. Test case 1.1 had lost its actual test
*steps* somewhere between v1 and v2 (only the personalized paths
survived) — restored here. All v2 bugs found and fixed since then
(font color, hyperlink right-click, note-color swatch checkmark
contrast, Stick to Window close/crash, Rename Notepad dialog sizing,
and a batch more found through free-form testing beyond the v2
checklist — see new cases in §3, §7, and §9) are folded back into their
normal descriptions rather than called out as regressions, plus new
cases for each. Every case now has a result line underneath —
`[ ] P` `[ ] F` `[ ] PwI` — mark whichever applies instead of writing
free text unless it actually failed or passed with a caveat, in which
case note what happened next to the checkboxes.

## Your system

- Repo: `/home/robinsiebler/Code/take_note`
- Launch: `/home/robinsiebler/Code/take_note/.venv/bin/take-note`
  (or `cd` into the repo and run `.venv/bin/take-note`)
- Python 3.14.6, PySide6 6.11.1
- Desktop: KDE Plasma, running through XWayland (`QT_QPA_PLATFORM=xcb`,
  forced by `__main__.py`)
- Two monitors with **different scaling** — DP-1 (top, 1920×1080 @ 100%)
  and DP-3 (bottom/primary, effectively 3440×1440 @ 125%). A few dialog
  sizing bugs only showed up on the unscaled monitor — worth spot-checking
  dialogs on **both** if you notice anything cramped, not just the one
  you happen to be working on.
- `XDG_DATA_HOME`/`XDG_CONFIG_HOME` are **unset** on this machine, so the
  app uses the plain `~/.local/share` / `~/.config` fallbacks below.

Each case is a checkbox. Check it off as `[x]` once verified, and mark
the result line underneath. If a case fails or passes with an issue,
note the actual behavior right there rather than just leaving it
unchecked, so a re-test later doesn't have to rediscover the same bug.

---

## 1. App lifecycle

- [x] **1.1** Test the fresh-install path first, without touching your
  real data — run once with an isolated scratch dir:
  `XDG_DATA_HOME=/tmp/take-note-scratch /home/robinsiebler/Code/take_note/.venv/bin/take-note`.
  One default note should be created automatically. Quit it, then confirm
  your **real** data is untouched and still lives at
  `/home/robinsiebler/.local/share/take-note/notes.json` (`cat` it or
  just check the file's there).
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **1.2** Quit via tray icon → **Quit**. App exits cleanly — no crash
  dialog ("Service Crash for Python 3.14" or similar).
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **1.3** Relaunch after quitting. All notes/boards reappear exactly
  where they were left (position, size, color, content) — reading back
  from the real `notes.json` above.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **1.4** Click the tray icon directly (not right-click) → creates a
  new note, same as **New Note**.
  - [x] P
  - [ ] F
  - [ ] PwI

## 2. Note creation & window basics

- [x] **2.1** Tray → **New Note** creates a note at a sensible default
  position/size, default color, always-on-top by default.
  - [ ] P
  - [ ] F
  - [x] PwI
    Every new note appears in exactly the same place. This could confuse a user — let's make each new note appear slightly staggered, so it's obvious a new note was created. Less of an issue if random colors is selected. Add this to the backlog.
- [x] **2.2** Global hotkey (check Settings → Hotkey tab for the
  currently-configured combo — default is `Ctrl+Alt+N`) creates a new
  note from anywhere, even with no Take Note! window focused. Check the
  terminal for any stray error output while doing this.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **2.3** Note header's `+` button creates another new note.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **2.4** Drag a note by its header — moves smoothly, no lag/tearing.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **2.5** Resize a note by dragging its bottom-right corner grip.
  *(Only present on a standalone note — see §7 for board-attached
  behavior.)*
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **2.6** Header **▲/▼** button (or double-click the header) rolls
  the note up to just its header, and back down. Try this on a note
  **with a title set** (§4.5) specifically — the collapsed header should
  stay clean, not a squashed/garbled mess of overlapping text. Roll-up
  state and each note's position/size persist across a restart.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **2.7** Header `×` → confirmation dialog **"Delete this note
  permanently?"**; **Yes** deletes it, **No**/close leaves it untouched.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **2.8** A note stays on top of normal windows when **Always on
  Top** is checked (hamburger ☰ menu), and behaves like a normal window
  (can be covered) when unchecked.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **2.9** Note Transparency submenu (☰ → **Note Transparency**):
  **None/Low/Medium/High/Full** each visibly change opacity; selection
  is exclusive (only one checked at a time) and persists across restart.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **2.10** Insert a picture into a note (§3.8), then backspace it
  away completely back to an empty note, then type. The new text should
  read in the note's normal color, not faded/grey.
  - [x] P
  - [ ] F
  - [ ] PwI

## 3. Rich text editing (right-click the note body)

- [x] **3.1** **Font…** opens the native font-family/size/style picker;
  applies to the current selection (or becomes the typing default with
  no selection). Your system's default UI font is **Noto Sans** — that's
  what should show pre-selected on a fresh note.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **3.2** **Font Style** submenu: **Bold** (`Ctrl+B`), **Italic**
  (`Ctrl+I`), **Underline** (`Ctrl+U`), **Strikethrough** (`Ctrl+K`)
  each toggle correctly on a selection and via their shortcuts.
  - [ ] P
  - [ ] F
  - [x] PwI
    There's no indication of what style option(s) are in play. Can't remember if this was fixed or added to the backlog.
- [x] **3.3** **Font Style** → **Left/Center/Right** alignment applies
  to the current paragraph.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **3.4** **Font Color…** swatch picker recolors selected text;
  picker itself has rounded corners and a visible border (not
  square/flat). Try it on a **list item** too, including one that's the
  only/last line in the note — the text should stay visible, not vanish.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **3.5** **Bullets && Numbering** submenu: each style (•, 1/2/3,
  a/b/c, A/B/C, i/ii/iii, I/II/III) applies correctly to a multi-line
  selection as **one shared list** (numbers should read 1, 2, 3… not
  "1." repeated on every line); **None** removes list formatting.
  Selection is exclusive. **Known issue, already tracked (not yet
  fixed):** selecting 2+ list items and looking at the *unselected* line
  markers may show a checkbox glyph (☐) instead of the real
  bullet/number while the selection is active — purely a paint glitch,
  self-corrects on deselect, data is unaffected. Confirm it still
  matches that description; don't re-file it, just check the box below.
  - [ ] P
  - [x] F
    See reference screenshots: TC 3.5 - Sub-bullet color.png, TC 3.5 - Reset Bullets & Numbers to None.png
  - [ ] PwI
- [x] **3.6** **Increase Indent** / **Decrease Indent** nest/un-nest list
  items correctly, including across multi-line selections at different
  depths — each level should step over by a consistent, modest amount,
  not compound into an ever-widening indent.
  - [ ] P
  - [x] F
    Indent gets messed up (all bullet items selected). See reference screenshots: TC 3.6 - Before indent.png, TC 3.6 - After indent.png
  - [ ] PwI
- [x] **3.7** Tab / Shift+Tab inside a list item also indent/dedent (not
  just the menu items).
  - [ ] P
  - [x] F
    See 3.6 for screenshots.
  - [ ] PwI
- [x] **3.8** **Add picture…** inserts an image inline; note grows to
  fit (width and height) rather than shrinking the image, capped at
  screen size for an oversized picture. Pick a real photo from wherever
  you keep them to test with an actually-large image.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **3.9** Right-click an inserted picture → menu now says **Replace
  picture…** instead of **Add picture…**; replacing it works.
  - [ ] P
  - [ ] F
  - [ ] PwI
- [x] **3.10** **Hyperlink…** on a selection (or typed URL) turns it
  into a clickable link. Plain click on a link just places the cursor
  (link text stays editable); `Ctrl+Click` opens it in your default
  browser. Hovering shows a hand cursor + tooltip.
  - [ ] P
  - [x] F
    If you type a URL, place the caret inside it, and right-click directly (not from an earlier click), you get Hyperlink…, but selecting it does not pre-fill the URL — not sure if that's supposed to work.
  - [ ] PwI
- [x] **3.11** Right-click **directly on top of** an existing link (not
  just with the caret already sitting inside it from an earlier click)
  → menu says **Edit Hyperlink…** and pre-fills the current URL.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **3.12** Undo/Redo/Cut/Copy/Paste/Select All (Qt's built-in menu,
  shown above the app's own items) all work normally.
  - [x] P
  - [ ] F
  - [ ] PwI

## 4. Find, Lock, and Title

- [x] **4.1** `Ctrl+F` or right-click → **Find…** opens a small find bar
  between header and body. Typing searches live; **▲/▼** step through
  matches with wraparound; `×` (or Esc) closes it.
  - [ ] P
  - [ ] F
  - [x] PwI
    Feature enhancement: hotkey to jump to the next instance found (usually F3).
- [x] **4.2** **Find…** is disabled (greyed out, not clickable) on a
  completely empty note, and becomes enabled the moment you type
  anything.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **4.3** ☰ → **Lock Note** makes the body read-only. Right-click
  menu collapses to just **Find…**. `Ctrl+B`/`I`/`U`/`K` no longer do
  anything while locked.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **4.4** Header padlock icon toggles lock too — white/unlocked vs.
  amber/locked. A single click toggles once; a double-click also
  toggles exactly once (not twice/net-no-op).
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **4.5** `Shift+F2` (or ☰ → **Add Title…**) opens a dialog to set a
  title — wide enough to read its own window title comfortably, on
  either monitor. Once set, a bold title bar appears between header and
  body, and the menu item now reads **Edit Title…**. *(Not `Ctrl+F2` —
  that's bound on this exact machine to KWin's "Switch to Desktop 2",
  see §11.2.)*
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **4.6** Title's font (family + size) matches whatever the note
  body's font currently is, and stays bold. Change the note's font size
  (via **Font…**) and re-open/re-set the title — the title should scale
  with it.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **4.7** Clearing the title (empty string in the dialog) hides the
  title bar again and reverts the menu label to **Add Title…**.
  - [ ] P
  - [ ] F
  - [x] PwI
    Feature enhancement: if there's a title, add a clear button at the end of the input field. Do the same for Find and Edit Hyperlink (see reference screenshot: "clear button.png").
- [x] **4.8** Cancelling the title dialog leaves the existing title
  unchanged.
  - [x] P
  - [ ] F
  - [ ] PwI

## 5. Note color & appearance

- [x] **5.1** ☰ → **Change Note Color…** opens a swatch-grid popup with
  rounded corners and a visible thicker border — 12 swatches, checkmark
  on the currently-selected one, **readable regardless of how light the
  swatch is** (e.g. yellow) — dark checkmark on light swatches, white on
  dark ones.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **5.2** Picking a color updates the note (header/body/footer/
  find-bar tint) immediately and persists across restart.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **5.3** The in-note find bar's background tints toward the note's
  own color (a lighter blend), and updates live if you change the note
  color while the find bar is open.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **5.4** Every color swatch (in both the note-color and font-color
  pickers, and in Settings) has a visible border regardless of how
  light or dark the swatch itself is — no swatch blends invisibly into
  the popup background.
  - [x] P
  - [ ] F
  - [ ] PwI

## 6. Stick to Window

- [x] **6.1** ☰ → **Stick to Window…** opens a picker listing other real
  windows on your desktop (not Take Note's own windows). Try it with
  something ordinary you have open, like Dolphin or a terminal.
  - [x] P
    Note: neither Dolphin nor Konsole appear in the list; Winboat, Claude, and Perplexity do. Update the instructions.
  - [ ] F
  - [ ] PwI
- [x] **6.2** After sticking, minimizing/restoring the target window
  hides/shows the note in sync. **Closing the target window** (not
  minimizing) should unstick the note and leave it visible again — check
  the terminal for any stray error output right as the target window
  closes, and confirm the ☰ menu goes back to reading **Stick to
  Window…** afterward (not still **Unstick from Window**).
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **6.3** ☰ menu now shows **Unstick from Window** for a stuck note;
  using it detaches it.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **6.4** A native Wayland app (e.g. Chromium/Vivaldi launched with
  `--ozone-platform=wayland`, or many Electron apps) does **not** appear
  in the picker — expected limitation on this Wayland-with-XWayland
  setup, not a bug (see README).
  - [x] P
  - [ ] F
  - [ ] PwI

## 7. Notepad (the per-board corkboard window)

- [x] **7.1** Tray → **New Notepad** creates a small corkboard-style
  window titled with the board's name.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **7.2** Right-click empty canvas → **New Note on this Notepad**
  creates a note already attached to that board. Resize the board window
  bigger and smaller a few times afterward — no scrollbar should ever
  get stuck showing once the note comfortably fits, regardless of size.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **7.3** Right-click empty canvas → **Rename Notepad** lets you
  rename it via a dialog wide enough to read its own title (check on
  both monitors); the header label updates immediately.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **7.4** Right-click empty canvas → **Delete Notepad** →
  confirmation ("Delete this Notepad? Notes on it will be moved back to
  the desktop.") → notes previously on it reappear as standalone notes
  rather than being deleted.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **7.5** From an existing standalone note, ☰ → **Add to Notepad**
  submenu lists every existing board by name, plus **New Notepad…** at
  the bottom. Picking a board reparents the note onto it.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **7.6** Once attached, that note's ☰ menu now shows **Remove from
  Notepad** (no submenu) instead of **Add to Notepad**; using it pops
  the note back to the desktop.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **7.7** A note attached to a board has no visible resize grip in
  its footer, and its rounded bottom-right corner renders cleanly — no
  grey notch/artifact cut into it.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **7.8** A standalone (non-board) note **does** still have its
  resize grip, and dragging it resizes just that note.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **7.9** Detaching a note (7.6) brings its resize grip back.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **7.10** Drag a note's header to reposition it within the board
  canvas — moves smoothly, corner still renders cleanly afterward (no
  leftover artifact at the old or new position).
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **7.11** A near-empty board at its default size (400×300) shows no
  scrollbar.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **7.12** Grow the board window much bigger, then shrink it back
  down — no lingering/spurious scrollbar if your notes still comfortably
  fit at the smaller size.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **7.13** Drag a note far outside the board's currently-visible
  area — the canvas grows to keep it reachable (scrollbars appear as
  needed), rather than the note becoming permanently unreachable/
  clipped. Drag it back near the origin — the canvas shrinks back down
  and the scrollbar goes away again.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **7.14** Board header's `×` hides the board (doesn't delete it).
  *(Known gap: no in-app way to reopen it afterward except via the Notes
  Browser — see §8.9 — and it does **not** currently remember being
  closed across a restart; it'll reopen automatically next launch. Not a
  bug to file, just confirming current behavior.)*
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **7.15** Drag the board window's own bottom-right corner grip —
  resizes the whole board window (this one's supposed to affect the
  board, unlike 7.7's note-level grip). This is currently the *only* way
  to resize a board or note — there's no edge-dragging, since these are
  frameless windows with no OS-native resize border. Expected, not a
  bug.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **7.16** *(Known gap, not a bug)* The board window's own chrome
  (flat grey header/canvas, native scrollbars) still looks visually
  plain/unpolished compared to note windows — no fix expected yet.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **7.17** Change a board-attached note's transparency (☰ → **Note
  Transparency**) — it should visibly blend with the board behind it,
  same as a standalone note does with its desktop background.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **7.18** Set a title on a board-attached note (§4.5) — the title
  bar strip should show the *note's* own color, not the board's
  background color showing through behind the title text.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **7.19** Open any dialog from a board-attached note (Add
  Title…/Font…/Hyperlink…/Add picture…/Stick to Window…/the note's own
  Delete confirmation) — each should render in the app's normal dark
  theme, not a washed-out grey matching the board's own background.
  - [x] P
  - [ ] F
  - [ ] PwI

## 8. Notes Browser

- [x] **8.1** Tray → **Notes Browser…** opens a single window titled
  "Take Note! — Notes Browser". Opening it again while already open
  just raises/focuses the existing one (doesn't spawn a second).
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **8.2** Left tree shows **All Notes**, **Unfiled**, then one entry
  per existing board (by name) — should match whatever boards you
  actually have right now.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **8.3** Selecting **All Notes** lists every note; **Unfiled** shows
  only notes with no board; a board name shows only that board's notes.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **8.4** Table has four columns: **Title**, **Preview**,
  **Notepad**, **Date Modified** (US format, e.g. "July 10, 2026 03:56
  PM").
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **8.5** An untitled note shows **(untitled)** in Title but a real
  snippet of its body text in **Preview** — enough to actually tell two
  untitled notes apart at a glance.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **8.6** A note attached to a board shows that board's name in the
  **Notepad** column; an unattached note shows that column blank.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **8.7** Typing in **Search notes…** filters live by both title
  *and* body text (e.g. searching a word that only appears in the body
  still finds it). The field has a visible clear (×) button once you've
  typed something.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **8.8** Clicking a column header sorts by that column; **Date
  Modified** sorts chronologically (not alphabetically by the displayed
  "Month Day, Year" text).
  - [ ] P
  - [ ] F
  - [x] PwI
    See reference screenshot: TC 8.8 - Click Preview Column.png
- [x] **8.9** Double-clicking a note row raises/shows that real note
  window. Double-clicking a board row in the tree raises/shows that
  board window.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **8.10** Ctrl-click / Shift-click selects multiple rows. Toolbar
  **Delete** (or right-click → **Delete N Notes**) asks **one**
  confirmation for the whole selection and deletes them all.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **8.11** Right-click a single row → **Show Note**, **Remove from
  Notepad** (only if attached), **Delete Note**.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **8.12** Right-click a board in the tree → **Rename** / **Delete
  Notepad** (same effect as doing it from the board window itself).
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **8.13** Toolbar **New Note**: creates an unattached note when
  **All Notes**/**Unfiled** is selected, or attaches it to whichever
  board is currently selected in the tree.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **8.14** Toolbar **New Notepad** creates a new board, which
  immediately appears in the tree.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **8.15** Creating/deleting/renaming a note or board elsewhere in
  the app (not through this window) updates the browser's list live
  within about half a second, without needing to close/reopen it.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **8.16** Resize and/or move the Notes Browser window, then quit
  and relaunch the app — it reopens at the exact size/position you left
  it at.
  - [x] P
  - [ ] F
  - [ ] PwI

## 9. Settings dialog (tray → Settings…)

### General tab

- [x] **9.1** **Launch at login** checkbox reflects real autostart-file
  state. Toggling it creates/removes
  `/home/robinsiebler/.config/autostart/take-note.desktop` — check with
  `ls /home/robinsiebler/.config/autostart/` after toggling to confirm
  it's really there/gone.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **9.2** **New notes stay on top by default** checkbox controls new
  notes' initial always-on-top state.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **9.3** **Default note color** swatch grid picks the color new
  notes start with (when randomize, below, is off).
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **9.4** **Randomize new note color** checkbox: when checked, the
  color swatch grid above visibly dims (not just stops responding —
  actually looks disabled), and new notes get a random color from the
  palette instead of the fixed default. Unchecking restores the
  fixed-default behavior.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **9.5** **Default font size** (6–72pt) and **Default font color**
  swatch grid apply to the first character typed into a brand-new empty
  note — not to notes that already have content.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **9.6** Clicking **OK** after changing *only* one setting doesn't
  silently reset unrelated settings (e.g. the Notes Browser's remembered
  window position/size from §8.16 should survive going through Settings
  and clicking OK).
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **9.7** *(Known gap)* There's no **Apply** button — only **OK**
  (commits and closes) and **Cancel**. No way to try a setting without
  closing the dialog. Not a bug to file; tracked in the backlog.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **9.8** *(Known gap)* Move/resize the Settings dialog, close it,
  and reopen — it does **not** remember its position/size (unlike the
  Notes Browser, §8.16). Not a bug to file; tracked in the backlog.
  - [x] P
  - [ ] F
  - [ ] PwI

### Hotkey tab

- [x] **9.9** Current global hotkey shows in the recorder field; typing
  a new combo and clicking **Test** reports **"✓ Available"** or **"✗
  Already in use by another app"** live, without committing it.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **9.10** Clicking **OK** actually commits a changed hotkey — the
  old combo stops creating notes, the new one does.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **9.11** *(Known gap)* This tab only configures the one global
  "new note" hotkey — there's no way here to rebind in-app shortcuts
  like Bold/Italic/Add Title. Not a bug; a distinct, not-yet-started
  feature.
  - [x] P
  - [ ] F
  - [ ] PwI

## 10. Tray menu (full pass)

- [x] **10.1** **New Note** / **New Notepad** / **Notes Browser…** each
  work as described above.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **10.2** **Bring Notes on Top** raises every open note above other
  windows.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **10.3** **Show All Notes** / **Hide All Notes** show/hide every
  note (session-only — don't expect this to persist across a restart).
  There's currently no equivalent for hiding just *one* note — known
  gap, tracked in the backlog, not a bug to file.
  - [ ] P
  - [ ] F
  - [ ] PwI
- [x] **10.4** **Roll Up/Down Notes**: if any note is currently
  expanded, rolls *all* of them up; if all are already rolled up,
  expands *all* of them — never leaves a mixed state.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **10.5** **Settings…** opens the dialog from §9.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **10.6** **Quit** exits cleanly (see §1.2).
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **10.7** *(Known gap, cosmetic)* Menu separators show as plain
  gaps, no visible line — KDE's native tray menu doesn't pick up the
  app's own stylesheet. Not fixable from our side; don't file it.
  - [x] P
  - [ ] F
  - [ ] PwI

## 11. Cross-cutting / theme

- [x] **11.1** Switch your desktop between light and dark mode (System
  Settings → Appearance → Global Theme) — context menus and the
  color-picker popup adapt to match, but note colors themselves stay
  exactly as set regardless of theme.
  - [x] P
  - [ ] F
  - [ ] PwI
- [x] **11.2** Confirmed on this machine:
  `~/.config/kglobalshortcutsrc` has
  `Switch to Desktop 2=Ctrl+F2\tMeta+F2` — a real, live conflict, not
  hypothetical. Confirm `Shift+F2` opens Add Title correctly and
  `Ctrl+F2` does *not* (it should switch your virtual desktop instead,
  which is KWin's normal behavior, not this app's).
  - [x] P
  - [ ] F
  - [ ] PwI

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
  the one global new-note hotkey is configurable. See §9.11.
- No Settings dialog Apply button, and it doesn't remember its window
  position — both tracked in the backlog, see §9.7/§9.8.
- No way to hide a single note (only all-or-nothing via the tray) —
  tracked in the backlog, see §10.3.
- Selecting a multi-line list can show a checkbox-glyph paint glitch on
  the unselected lines — tracked, high priority, not yet fixed, see
  §3.5.
