# Take Note! — Manual Test Cases (v4)

Covers everything merged to `main` as of 2026-07-12 (`future-backlog`
and `feature/spell-check` are both fully merged in and deleted — no
branch-specific setup needed anymore, just run the app normally).
Distinct from the automated `pytest` suite in `tests/` — this is for
exercising the real app by hand under a real desktop (XWayland/KDE
Plasma), where things like window-manager interaction, real fonts, and
compositor behavior actually matter.

**v4 changes from v3:** every case's result line now spells out
**Pass**/**Fail**/**Pass with Issues** in full instead of the abbreviated
`P`/`F`/`PwI` checkboxes v3 used (line-space is no longer a constraint,
per explicit request). Content changes, all from work done after v3 was
written: the checkbox-glyph list-marker paint bug (§3.5) is fixed — its
"known issue" caveat is gone, replaced with a real pass/fail case;
Settings gained an Apply button and now remembers its window position
(§9.7/§9.8, previously flagged as known gaps); a single note can now be
hidden, not just all-or-nothing (§10.3a, previously a known gap
mentioned in §10.3); Show All/Hide All Notes collapsed into one
toggling tray item (§10.3); the Font Style submenu now shows which
styles the current selection already has, bold/italic/underline/
strikethrough **and** alignment (§3.2a); a **Remove Hyperlink** action
exists (§3.11a); plain-text URLs auto-detect as links at right-click
time (§3.11b/§3.11c); every text input field in the app has a clear
(×) button (scattered across §3/§4/§7); the find bar supports
F3/Shift+F3 (§4.1a); new notes stagger instead of stacking exactly on
top of each other (§2.1a); and a whole new optional spell-check
feature (§12, off by default).

**Also from a second round of live testing, after the above was
already merged:** two real regressions found and fixed —
`modified_at`/"Date Modified" used to bump on every single app launch
even with zero edits (§1.5, §12.8), and the Notes Browser displayed
UTC time mislabeled as local (§8.4a, off by several hours). The
spell-check-unavailable explanation was also changed from a tooltip
(reported hard to discover) to a visible label under the checkbox
(§12.9). One issue from that same round — text occasionally reading
faded/grey right after typing, in a note with spell check on — was
**not** successfully reproduced after several attempts and is not yet
fixed; flagged in §3.13 as something to watch for, not silently
dropped.

The "Known, accepted limitations" section at the bottom is updated to
match — several items that used to live there are now real test cases
instead.

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
- Spell check's optional dependency is already installed on this
  machine — `enchant2`/`hunspell`/`hunspell-en-US` at the OS level,
  `pyenchant` pip-installed into `.venv` — so §12 should be fully
  testable as-is, no extra setup needed.

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
  - [ ] Pass
  - [ ] Fail
  - [x] Pass with Issues
    New note was not staggered.
- [x] **1.5** Open the Notes Browser and note the **Date Modified** value
  for a couple of notes. Quit the app *without editing anything* and
  relaunch it. Open the Notes Browser again — those same notes' Date
  Modified should read identically, not bumped to "just now". (Regression:
  simply loading a note from disk — restoring its saved position/size/
  content — used to count as an edit and silently overwrite its real
  Date Modified on every single launch.)
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
  permanently?"**; **Yes** deletes it, **No**/close leaves it untouched.
  - [ ] Pass
  - [ ] Fail
  - [x] Pass with Issues
    See screenshot: Delete dialog needs to be wider.png
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
- [x] **3.2a** Select text that already has one or more of Bold/Italic/
  Underline/Strikethrough applied, open **Font Style** — the matching
  entries show a checked state (previously gave no indication at all).
  Select plain unformatted text — none are checked.
  - [ ] Pass
  - [ ] Fail
  - [x] Pass with Issues
    This test is wrong; there is no "plain text" option.
- [x] **3.3** **Font Style** → **Left/Center/Right** alignment applies
  to the current paragraph, and — same checked-state treatment as
  3.2a, added as a follow-up — whichever one currently applies shows
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
- [x] **3.5a** *(Previously a known issue, now fixed — markers are
  hand-drawn instead of trusting Qt's native paint.)* Select 2+ list
  items spanning multiple lines and look closely at every line's
  marker, selected and unselected — all should show the real
  bullet/number. None should render as a small checkbox-outline glyph
  (☐). Try a nested list (mixed depths) and a numbered style too, not
  just the default bullet.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **3.6** **Increase Indent** / **Decrease Indent** nest/un-nest list
  items correctly, including across multi-line selections at different
  depths — each level should step over by a consistent, modest amount,
  not compound into an ever-widening indent.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
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
  **Remove Hyperlink** entry (previously no way to remove a link once
  inserted). Click it — the text reverts to plain, un-clickable text in
  the note's normal color, no underline. Right-click plain never-linked
  text — no **Remove Hyperlink** entry appears.
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
- [x] **3.13** *(Watch-for, not a confirmed repro yet)* Text occasionally
  read faded/grey right after typing, seen once during spell-check
  testing (not confirmed related to spell check itself) — could not be
  reproduced afterward despite trying several concrete sequences
  (typing after clicking a spell-check suggestion, after toggling
  spell-check off, backspacing at various points including all the way
  to the very start of the note). **If this happens, mark Fail and note
  the exact sequence of keystrokes/clicks that led to it right here**
  — ideally including whether spell-check was on, before/after
  screenshots, and roughly how long you'd been typing in that note —
  those specifics are what's needed to actually chase this down. Pass
  just means you didn't see it this pass.
  - [ ] Pass
  - [x] Fail
    Exact repo steps provided in chat.
  - [ ] Pass with Issues

## 4. Find, Lock, and Title

- [x] **4.1** `Ctrl+F` or right-click → **Find…** opens a small find bar
  between header and body. Typing searches live; **▲/▼** step through
  matches with wraparound; `×` (or Esc) closes it. The search field
  itself has a visible clear (×) button.
  - [ ] Pass
  - [ ] Fail
  - [x] Pass with Issues
    See screenshot: Find clear button not visible on white background.png
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
  - [ ] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **4.4** Header padlock icon toggles lock too — white/unlocked vs.
  amber/locked. A single click toggles once; a double-click also
  toggles exactly once (not twice/net-no-op).
  - [x] Pass
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
- [ ] **7.5** From an existing standalone note, ☰ → **Add to Notepad**
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
- [x] **8.4a** Edit a note right now and check its **Date Modified** —
  should match your system clock's actual current local time, not be
  off by a fixed number of hours. (Regression: this displayed raw UTC
  time mislabeled as local — e.g. showed "07:11 PM" when the real local
  time was 12:33 PM.)
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
  - [ ] Pass
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
  treated as a "setting" you're discarding by cancelling).
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **9.8a** New **"Check spelling as you type"** checkbox at the
  bottom of the General tab, unchecked by default — see §12 for the full
  spell-check pass, this is just confirming it's present here.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues

### Hotkey tab

- [x] **9.9** Current global hotkey shows in the recorder field; typing
  a new combo and clicking **Test** reports **"✓ Available"** or **"✗
  Already in use by another app"** live, without committing it.
  - [ ] Pass
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
- [x] **10.3** One **Show/Hide All Notes** item (previously two separate
  "Show All Notes"/"Hide All Notes" items). With all notes visible,
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

## 12. Spell check (optional, off by default)

This dev machine already has the optional dependency fully set up
(`enchant2`/`hunspell`/`hunspell-en-US` at the OS level, `pyenchant`
pip-installed into `.venv`) — every case below should be testable as-is.

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
  reopened. Same underlying fix as §1.5 (which isn't spell-check-
  specific), confirmed here again since this is exactly the scenario
  the fix needs to hold up under.
  - [x] Pass
  - [ ] Fail
  - [ ] Pass with Issues
- [x] **12.9** With the optional dependency unavailable (§B6 in the
  temporary branch test doc covered how to actually trigger this, if
  you still have it — uninstalling `pyenchant` from `.venv`), the
  checkbox's explanation is a real, always-visible line of text right
  below it, not something you'd only see by hovering.
  - [ ] Pass
  - [x] Fail
    See screenshot: TC 12.9 - Tooltip not visible.png
  - [ ] Pass with Issues
- [x] **12.9a** Same check, but switch your desktop to light mode first
  (§11.1) — that explanation text should still be clearly readable, not
  washed out against the lighter background.
  - [ ] Pass
  - [x] Fail
    See screenshot: TC 12.9 - Tooltip not visible 2.png
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
- Occasional faded/grey text right after typing, not yet reproduced on
  demand — see §3.13. Not "accepted", just still open; report exact
  repro steps if you catch it.
