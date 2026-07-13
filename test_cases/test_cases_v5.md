# Take Note! — Manual Test Cases (v5)

Covers everything merged to `main` as of 2026-07-11. No branch-specific
setup needed — just run the app normally. Distinct from the automated
`pytest` suite in `tests/` — this is for exercising the real app by hand
under a real desktop (XWayland/KDE Plasma), where things like
window-manager interaction, real fonts, and compositor behavior actually
matter.

**v5 changes from v4:** the v4 pass itself found several real bugs, all
now fixed — the checkbox-glyph list-marker note from v4 is unrelated;
these are new, from the actual v4 pass results:

- **QFontDialog showed the wrong size on a note you'd never typed
  into** (§3.1) — right-clicking such a note silently reset its default
  font size before the dialog ever opened.
- **§3.13's "watch-for" is now a confirmed, fixed bug**, not a vague
  maybe: type a line, press Enter several times, then arrow **up** (not
  type) into one of the blank lines left in between and type there —
  the exact repro. Rewritten below as a normal pass/fail case.
- **A new note could land exactly on top of an old one right after a
  relaunch** (new case §2.1b) — the stagger counter always reset to 0 on
  launch.
- **The Delete Note confirmation dialog was too narrow** (§2.7) — text
  wrapped to two cramped lines.
- **The find bar's in-field clear (×) button was invisible** (§4.1) —
  present but rendered in a color indistinguishable from the field's
  white background.
- **A Notepad board window could render above notes regardless of their
  own always-on-top setting** (new case §7.20).
- **The spell-check-unavailable explanation (§12.9/§12.9a) went through
  several rounds**: contrast was fixed, then a follow-up found the text
  had also become too small and mis-aligned compared to the rest of the
  dialog, and clipped at the bottom of the dialog on first open — all
  fixed, wording below updated to match.

**New this version — a whole Tags feature (§13):** free-form tags,
assigned per note via the hamburger menu, visible and filterable in the
Notes Browser only (not on the note window itself yet — deliberately
deferred, see §13.1's note).

The "Known, accepted limitations" section at the bottom no longer lists
the grey-text item — it's a confirmed, fixed bug now, not an open one.

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
- Spell check's optional dependency is normally installed on this
  machine — `enchant2`/`hunspell`/`hunspell-en-US` at the OS level,
  `pyenchant` pip-installed into `.venv` — so §12 should be fully
  testable as-is. If you've uninstalled `pyenchant` from `.venv` to test
  the unavailable path (§12.9/§12.9a), remember to `pip install
  pyenchant` back into `.venv` afterward before the rest of §12.

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
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **1.2** Quit via tray icon → **Quit**. App exits cleanly — no crash
  dialog ("Service Crash for Python 3.14" or similar).
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
- [x] **1.5** Open the Notes Browser and note the **Date Modified** value
  for a couple of notes. Quit the app *without editing anything* and
  relaunch it. Open the Notes Browser again — those same notes' Date
  Modified should read identically, not bumped to "just now".
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues

## 2. Note creation & window basics

- [x] **2.1** Tray → **New Note** creates a note at a sensible default
  position/size, default color, always-on-top by default.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **2.1a** Create several new notes in a row — each appears slightly
  offset from the last rather than stacked exactly on top of each other.
  Keep creating a dozen or more — the stagger should wrap back around
  instead of drifting notes off-screen.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **2.1b** Quit and relaunch the app (with existing notes still near
  their original positions), then immediately create a new note (tray
  icon or hotkey) as the very first thing you do — it should **not**
  land exactly on top of an existing note. (Regression: the stagger
  counter always reset to 0 on launch, so the first post-relaunch note
  reused the exact same fixed default position as the first note of any
  session.)
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **2.2** Global hotkey (check Settings → Hotkey tab for the
  currently-configured combo — default is `Ctrl+Alt+N`) creates a new
  note from anywhere, even with no Take Note! window focused. Check the
  terminal for any stray error output while doing this.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
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
  the note up to just its header, and back down. Try this on a note
  **with a title set** (§4.5) specifically — the collapsed header should
  stay clean, not a squashed/garbled mess of overlapping text. Roll-up
  state and each note's position/size persist across a restart.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **2.7** Header `×` → confirmation dialog **"Delete this note
  permanently?"**, sized to read comfortably on one line, not cramped
  onto two; **Yes** deletes it, **No**/close leaves it untouched.
  - [ ] Pass
  - [ ] Fail
  - [x] Pass with Issues
    - Delete dialog appears at the very top of the screen and nowhere near the note being deleted. See screenshot.
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
- [x] **2.10** Insert a picture into a note (§3.8), then backspace it
  away completely back to an empty note, then type. The new text should
  read in the note's normal color, not faded/grey.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues

## 3. Rich text editing (right-click the note body)

- [ ] **3.1** **Font…** opens the native font-family/size/style picker;
  applies to the current selection (or becomes the typing default with
  no selection). Your system's default UI font is **Noto Sans** — that's
  what should show pre-selected on a fresh note. Specifically try this
  on a note you have **never typed into** — right-click it first (do
  nothing else), then open **Font…** — it should show your configured
  default size (Settings → General → Default font size), not some other
  size.
  - [ ] Pass
  - [ ] Fail
  - [x] Pass with Issues
    - Some text was bolded before the font size change, but was no longer bolded afterwards. Expected behavior? See screenshots.
- [x] **3.2** **Font Style** submenu: **Bold** (`Ctrl+B`), **Italic**
  (`Ctrl+I`), **Underline** (`Ctrl+U`), **Strikethrough** (`Ctrl+K`)
  each toggle correctly on a selection and via their shortcuts.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **3.2a** Select text that already has one or more of Bold/Italic/
  Underline/Strikethrough applied, open **Font Style** — the matching
  entries show a checked state. Select plain unformatted text — none are
  checked.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **3.3** **Font Style** → **Left/Center/Right** alignment applies
  to the current paragraph, and whichever one currently applies shows
  checked (a plain new paragraph should show **Left** checked, since
  that's the real default, not neither).
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **3.4** **Font Color…** swatch picker recolors selected text;
  picker itself has rounded corners and a visible border (not
  square/flat). Try it on a **list item** too, including one that's the
  only/last line in the note — the text should stay visible, not vanish.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **3.5** **Bullets && Numbering** submenu: each style (•, 1/2/3,
  a/b/c, A/B/C, i/ii/iii, I/II/III) applies correctly to a multi-line
  selection as **one shared list** (numbers should read 1, 2, 3… not
  "1." repeated on every line); **None** removes list formatting.
  Selection is exclusive.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **3.5a** Select 2+ list items spanning multiple lines and look
  closely at every line's marker, selected and unselected — all should
  show the real bullet/number. None should render as a small
  checkbox-outline glyph (☐). Try a nested list (mixed depths) and a
  numbered style too, not just the default bullet.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **3.6** **Increase Indent** / **Decrease Indent** nest/un-nest list
  items correctly, including across multi-line selections at different
  depths — each level should step over by a consistent, modest amount,
  not compound into an ever-widening indent.
  - [ ] Pass
  - [ ] Fail
  - [x] Pass with Issues
    - See screenshots. No further denting possible. Expected behavior?
- [x] **3.7** Tab / Shift+Tab inside a list item also indent/dedent (not
  just the menu items).
  - [ ] Pass
  - [ ] Fail
  - [x] Pass with Issues
    - See 3.6
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
  browser. Hovering shows a hand cursor + tooltip. The URL field in the
  dialog has a visible clear (×) button.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **3.11** Right-click **directly on top of** an existing link (not
  just with the caret already sitting inside it from an earlier click)
  → menu says **Edit Hyperlink…** and pre-fills the current URL.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **3.11a** Right-click on an existing link — menu also shows a
  **Remove Hyperlink** entry. Click it — the text reverts to plain,
  un-clickable text in the note's normal color, no underline.
  Right-click plain never-linked text — no **Remove Hyperlink** entry
  appears.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **3.11b** Type a plain URL directly into a note (not through the
  Hyperlink… dialog) — it stays plain, unstyled text as you type (no
  live reformatting-as-you-type). Right-click directly on it — it
  becomes a real clickable link immediately, and the menu already reads
  **Edit Hyperlink…**/shows **Remove Hyperlink** rather than plain
  **Hyperlink…**.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **3.11c** Right-click ordinary text containing a period that isn't
  a URL (e.g. "e.g." or "notes.txt") — does **not** get auto-linkified.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **3.12** Undo/Redo/Cut/Copy/Paste/Select All (Qt's built-in menu,
  shown above the app's own items) all work normally.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **3.13** Type a line of text, press Enter 5-6 times (leaving
  several blank paragraphs), then type something on the new last line.
  Now press the **Up arrow** (not click) to move the caret into one of
  the blank lines in between, and type there. The new text should read
  in the note's normal color, not faded/grey. (Confirmed root cause:
  purely moving the caret via the keyboard into certain blank lines
  desynced the "what color should I type in" state, with no text change
  to trigger the fix that already existed for the typing-only version of
  this bug.)
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues

## 4. Find, Lock, and Title

- [x] **4.1** `Ctrl+F` or right-click → **Find…** opens a small find bar
  between header and body. Typing searches live; **▲/▼** step through
  matches with wraparound; `×` (or Esc) closes it. The search field
  itself has a visible dark clear (×) button inside it once you've typed
  something — check this specifically, it was previously present but
  effectively invisible (same light color as the field's white
  background).
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **4.1a** With the find bar open and a search term entered, **F3**
  jumps to the next match and **Shift+F3** jumps to the previous match
  (same as ▼/▲). Close the find bar, then press F3 — nothing happens
  (shortcut only live while the bar is open).
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
  - [ ] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **4.5** `Shift+F2` (or ☰ → **Add Title…**) opens a dialog to set a
  title — wide enough to read its own window title comfortably, on
  either monitor. Once set, a bold title bar appears between header and
  body, and the menu item now reads **Edit Title…**. *(Not `Ctrl+F2` —
  that's bound on this exact machine to KWin's "Switch to Desktop 2",
  see §11.2.)* The title field itself has a visible clear (×) button.
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
  rounded corners and a visible thicker border — 12 swatches, checkmark
  on the currently-selected one, **readable regardless of how light the
  swatch is** (e.g. yellow) — dark checkmark on light swatches, white on
  dark ones.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
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
- [x] **6.2** After sticking, minimizing/restoring the target window
  hides/shows the note in sync. **Closing the target window** (not
  minimizing) should unstick the note and leave it visible again — check
  the terminal for any stray error output right as the target window
  closes, and confirm the ☰ menu goes back to reading **Stick to
  Window…** afterward (not still **Unstick from Window**).
  - [x] Pass
  - [ ] Fail
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
- [x] **7.2** Right-click empty canvas → **New Note on this Notepad**
  creates a note already attached to that board. Resize the board window
  bigger and smaller a few times afterward — no scrollbar should ever
  get stuck showing once the note comfortably fits, regardless of size.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **7.3** Right-click empty canvas → **Rename Notepad** lets you
  rename it via a dialog wide enough to read its own title (check on
  both monitors); the header label updates immediately. The name field
  has a visible clear (×) button.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **7.4** Right-click empty canvas → **Delete Notepad** →
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
  grey notch/artifact cut into it.
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
  scrollbar.
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
- [x] **7.17** Change a board-attached note's transparency (☰ → **Note
  Transparency**) — it should visibly blend with the board behind it,
  same as a standalone note does with its desktop background.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **7.18** Set a title on a board-attached note (§4.5) — the title
  bar strip should show the *note's* own color, not the board's
  background color showing through behind the title text.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **7.19** Open any dialog from a board-attached note (Add
  Title…/Font…/Hyperlink…/Add picture…/Stick to Window…/the note's own
  Delete confirmation) — each should render in the app's normal dark
  theme, not a washed-out grey matching the board's own background.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **7.20** Open a Notepad board window, then create several new
  standalone notes (tray icon, hotkey, or another note's `+`) so they
  land staggered near the board window — every new note should render
  **above** the board window, regardless of the notes' own always-on-top
  setting. (Regression: the board window used a window type that KWin
  keeps in a permanently elevated stacking layer above ordinary windows,
  independent of any state hints — same class of bug notes themselves
  had fixed in an earlier version, just never carried over to the board
  window.)
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues

## 8. Notes Browser

- [x] **8.1** Tray → **Notes Browser…** opens a single window titled
  "Notes Browser" (the OS/WM appends " — Take Note!" automatically, same
  as every other window — should read "Notes Browser — Take Note!", not
  a doubled-up "Take Note! — Notes Browser — Take Note!"). Opening it
  again while already open just raises/focuses the existing one (doesn't
  spawn a second).
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **8.2** Left tree shows **All Notes**, **Unfiled**, then one entry
  per existing board (by name) — should match whatever boards you
  actually have right now. (See §13 for the new **Tags** section that
  also appears here once any note has a tag.)
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **8.3** Selecting **All Notes** lists every note; **Unfiled** shows
  only notes with no board; a board name shows only that board's notes.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **8.4** Table has five columns: **Title**, **Preview**,
  **Notepad**, **Date Modified** (US format, e.g. "July 10, 2026 03:56
  PM"), **Tags** (new — see §13).
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **8.4a** Edit a note right now and check its **Date Modified** —
  should match your system clock's actual current local time, not be
  off by a fixed number of hours.
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
  "Month Day, Year" text). Sort by **Date Modified** a few times, then
  **Notepad** a few times, then **Preview** — the Preview column header
  should render in full ("Preview" plus the sort-arrow), not clipped to
  something like "review".
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
- [x] **9.7** Button row now reads **OK / Apply / Cancel**. Change a
  setting (e.g. Default font size), click **Apply** — takes effect
  immediately (e.g. a new note picks it up) without closing the dialog.
  Click **OK** afterward — no double-applied side effects.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **9.8** Move/resize the Settings dialog, click **OK**, reopen it —
  reopens at the exact position/size you left it at (matches the Notes
  Browser, §8.16). Try it again but click **Cancel** instead of OK after
  moving it — position is still remembered (window geometry isn't
  treated as a "setting" you're discarding by cancelling). Also: with no
  saved position/size at all (e.g. a fresh scratch profile, §1.1), the
  dialog should open at a size that comfortably fits all its content —
  no clipped controls at the bottom.
  - [ ] Pass
  - [ ] Fail
  - [x] Pass with Issues
    - See screenshot
- [x] **9.8a** **"Check spelling as you type"** checkbox at the bottom of
  the General tab, unchecked by default — see §12 for the full
  spell-check pass, this is just confirming it's present here.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues

### Hotkey tab

- [x] **9.9** Current global hotkey shows in the recorder field; typing
  a new combo and clicking **Test** reports **"✓ Available"** or **"✗
  Already in use by another app"** live, without committing it.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **9.10** Clicking **OK** actually commits a changed hotkey — the
  old combo stops creating notes, the new one does.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **9.11** *(Known gap)* This tab only configures the one global
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
- [x] **10.3** One **Show/Hide All Notes** item. With all notes visible,
  click it — all hide; click again — all reappear. With a mixed
  hidden/visible state, click it — converges to all-visible (matches
  Roll Up/Down Notes' convergent-toggle behavior), not a per-note
  toggle. Session-only — don't expect this to persist across a restart.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **10.3a** ☰ menu (or header right-click menu) on any note now has
  a **Hide Note** entry, above Delete Note — hides just that one note,
  others unaffected. Open the Notes Browser — the hidden note still
  shows up in the table; double-click its row to bring it back. Session-
  only, same as 10.3 (reappears on restart, not persisted).
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
  - [ ] Pass
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

## 12. Spell check (optional, off by default)

This dev machine normally has the optional dependency fully set up
(`enchant2`/`hunspell`/`hunspell-en-US` at the OS level, `pyenchant`
pip-installed into `.venv`) — every case below except §12.9/§12.9a should
be testable as-is.

- [x] **12.1** Settings → General shows a **"Check spelling as you
  type"** checkbox, unchecked by default.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **12.2** Check it, click **Apply** (or OK) — takes effect
  immediately on already-open notes, no need to close/reopen them.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **12.3** Type a misspelled word (e.g. "teh", "wrold", "recieve") —
  a red wavy underline appears under it shortly after you finish typing
  it. Correctly-spelled words never get underlined. Fix the typo — the
  underline disappears live as you correct it.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **12.4** Turn a URL into a link (§3.10/§3.11b), then type a
  misspelled word *inside* the link text — it does not get underlined
  (hyperlink text is skipped from checking entirely).
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **12.5** Right-click a misspelled (underlined) word — suggested
  corrections appear at the top of the context menu, above **Font…**.
  Click one — the word is replaced in place. Right-click a correctly-
  spelled word — no suggestions section appears.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **12.6** Right-click a badly garbled "word" with no close match —
  either a short suggestion list or a disabled **"(No suggestions)"**
  placeholder, not a crash or empty broken menu.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **12.7** Uncheck the setting and Apply, with notes open and
  underlines visible — they disappear immediately on all open notes.
  Right-clicking a misspelled-looking word now shows the normal menu,
  no suggestions.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **12.8** With spell-check on, quit and relaunch the app — your
  notes' "Date Modified" (check a couple in the Notes Browser before
  quitting, compare after) shouldn't have bumped just from being
  reopened.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **12.9** With the optional dependency unavailable (`pip uninstall
  pyenchant` from `.venv`, then relaunch), the checkbox is disabled and
  its explanation is a real, always-visible line of text right below
  it, not something you'd only see by hovering. **Both** the checkbox's
  own text and the explanation below it should be clearly legible (a
  medium grey, not washed-out/illegible) and the **same font size** as
  every other label in the dialog — not noticeably smaller. The
  explanation text should also start flush left under the checkbox, not
  indented to the right. **Remember to `pip install pyenchant` back into
  `.venv` afterward** so the rest of this section (and §3.13's repro,
  which now holds up with spell-check on) stays testable.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [ ] **12.9a** Same check, but switch your desktop to light mode first
  (§11.1) — that explanation text (and the checkbox) should still be
  clearly readable, not washed out against the lighter background.
  - [ ] Pass
  - [ ] Fail
  - [ ] Pass with Issues

## 13. Tags (new this version)

Free-form tags per note — no predefined list, any text you type becomes
a tag. Assigned per note via the hamburger menu; visible and filterable
in the Notes Browser only. **Deliberately no visual indicator on the
note window itself yet** — that's a separate, not-yet-started follow-up
(Future-backlog item 23), not a bug — the only way to see or search by
a note's tags right now is the Notes Browser.

- [x] **13.1** ☰ → **Tags…** opens a dialog with a single text field,
  labeled for comma-separated input. Type a few tags separated by
  commas (e.g. `work, urgent`) and click OK. Nothing visible changes on
  the note window itself (expected, see above).
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **13.2** Re-open ☰ → **Tags…** on the same note — the field
  pre-fills with the tags you just set, comma-separated (e.g.
  `work, urgent`).
  - [ ] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **13.3** Change the text but click **Cancel** instead of OK — the
  note's actual tags are unchanged (confirm by reopening the dialog
  again).
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **13.4** Open the dialog, clear the field completely, click OK —
  the note now has no tags (confirm via the Notes Browser's Tags column,
  §13.6 — it should be blank).
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **13.5** Type messy input — extra spaces, a trailing comma, the
  same tag twice (e.g. `  work ,, urgent, work `) — click OK, then
  reopen the dialog. The field should show a clean, deduplicated list
  (`work, urgent`), not the messy original.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **13.6** Tag a couple of different notes (some overlapping tags,
  some not), then open the Notes Browser — each tagged note shows its
  tags, comma-separated, in the new **Tags** column at the right of the
  table; an untagged note shows that column blank.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **13.7** In the Notes Browser's left tree, a **Tags** entry
  appears (below your boards, if any) once at least one note has a tag.
  Expand it — it lists every unique tag currently in use across all
  notes, alphabetically, with no duplicates.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **13.8** Click one of the tag names under **Tags** in the tree —
  the table narrows to only notes that have that exact tag. Click
  **All Notes** again to clear the filter.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **13.9** Click directly on the **Tags** parent item itself (not
  one of the tag names under it) — it should just expand/collapse, not
  act as a filter or select/highlight like All Notes/Unfiled/a board
  name do.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **13.10** Remove a tag from every note that currently has it (☰ →
  **Tags…** on each, delete that tag from the field, OK) — that tag
  should disappear from the Notes Browser's tree the next time it
  refreshes (within about half a second, same live-update behavior as
  §8.15 — no need to close/reopen the browser).
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
  the one global new-note hotkey is configurable. See §9.11.
- Spell check needs its optional dependency (`pyenchant` + a system
  Enchant/dictionary install) — the Settings checkbox is disabled with
  an explanatory label when it's missing, rather than silently doing
  nothing. See §12.
- The Notepad corkboard window's own chrome still looks visually plain/
  unpolished compared to note windows, and there's no tray listing of
  existing boards or a way to reopen one once its × is clicked except
  via the Notes Browser — not yet started, see §7.14/§7.16.
- Tags have no visual indicator on the note window itself yet — Notes
  Browser only. See §13's intro and Future-backlog item 23.
- No autocomplete in the Tags dialog — plain comma-separated free text,
  deliberately kept simple for this first version. See §13.
