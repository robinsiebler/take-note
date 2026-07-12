# Take Note! — Features

- Colored sticky notes with rounded corners, rich text (a "Font…" action
  opens the native font-family/size/style dialog; plus quick bold/italic/
  underline/strikethrough, alignment, and bullets & numbering with
  indent/dedent via a right-click menu — Font Style and Bullets &
  Numbering both show which style the current selection already has),
  plus a "Font Color…" swatch picker (including black) for selected
  text, always-on-top (toggleable per note), adjustable transparency,
  freely movable and resizable, collapsible to just the header ("roll
  up"), persisted across restarts. New notes stagger slightly instead of
  stacking exactly on top of each other.
  Hyperlinks: "Hyperlink…" turns the selection (or a typed URL) into a
  clickable link, or edits an existing one in place (pre-filling its
  current URL) if invoked with just the caret inside it rather than a
  new selection — hover shows a hand cursor and tooltip, Ctrl+Click opens
  it, a plain click still just places the cursor for editing. Plain-text
  URLs also auto-detect as links the moment you right-click them, and
  "Remove Hyperlink" strips a link back to plain text.
- Spell check (optional, off by default — see below): a red squiggly
  underline under misspelled words as you type, with suggested
  corrections in the right-click menu, plus "Ignore" (this session only)
  and "Add to Dictionary" (persists across restarts) for words that
  aren't actually misspelled.
- Right-click the note body for text-formatting actions only; whole-note
  actions (color, transparency, always-on-top, Notepad, delete, hide)
  live in the header's right-click menu and the hamburger (☰) button
  instead.
- System tray icon: create notes/boards, open the Notes Browser, open
  Settings, quit.
- Five global hotkeys, all user-configurable in Settings: create a new
  note (default `Meta+Alt+N`), open the Notes Browser (default
  `Meta+Alt+B`), and — with no default combo, opt-in only — show/hide
  all notes, roll up/down all notes, and bring all notes to front,
  mirroring the tray menu's own bulk actions below.
- Notes Browser (tray → "Notes Browser…", or its own global hotkey
  above): a sortable, searchable table of every note (Title/Preview/
  Notepad/Date Modified/Tags columns) plus a tree of boards, tags, and
  Trash to filter by, for finding a note (including a hidden one)
  without hunting across the desktop. Deliberately excluded from the
  taskbar, pager, and Alt-Tab switcher — reachable only via the tray or
  its hotkey — since it was the one Take Note! window a real, unrelated
  KDE Task Manager bug (confirmed not caused by this app) could
  mislabel with another app's icon.
- Trash: deleting a note (its × button, hamburger menu, or the Notes
  Browser) now moves it to Trash instead of deleting it outright —
  still shows a confirmation, just without the old scarier "permanently"
  wording. A note's Notepad attachment is remembered while trashed, so
  restoring one puts it right back where it was; if that Notepad itself
  gets deleted first, the note just becomes unfiled instead. The Notes
  Browser's **Trash** node (always present, next to Tags) is the only
  place to **Restore** a note or **Delete Permanently** — real,
  irreversible deletion is no longer reachable anywhere else.
- Tags: free-form, per-note tags (no predefined list) assigned via the
  hamburger (☰) menu's "Tags…" dialog. Visible and filterable in the
  Notes Browser, plus a small ribbon icon in the note's own header
  (next to the lock icon) whenever it has at least one tag — hover it
  for the full tag list, click it to open the Tags… dialog directly.
- Settings dialog (tray → Settings…): launch at login, default note
  color/font size/color, whether new notes start always-on-top, optional
  spell check, and a hotkey recorder (one for each global hotkey above,
  each with its own Clear button to unbind it entirely) that live-tests
  a combo for conflicts — with this app's own other live hotkeys, or
  anything else already holding it — before committing to it. The
  Hotkey tab scrolls rather than growing the whole dialog to fit, and
  starts with a note that a combo already grabbed by a system-level
  shortcut (KWin's own global shortcuts, etc.) won't register in the
  field at all — not something the app can reliably detect ahead of
  time. Has Apply (try a setting without closing the dialog) alongside
  OK/Cancel, and
  remembers its own window position across restarts.
- Notepads: group notes onto a shared corkboard-style window that shows,
  hides, and moves as one unit.
- Context menus and the color picker adapt to your system's light/dark
  theme; note colors themselves stay as you set them regardless of theme.
- Embedded images: right-click → "Add picture…" (or "Replace picture…"
  when one is already selected) inserts a picture inline, persisted
  directly in the note's saved HTML so it survives a restart. The note
  grows in width and height to fit the picture rather than shrinking it,
  capped at the screen's available size.
- In-note Find (Ctrl+F, or the context menu's "Find…" — disabled on an
  empty note): a small non-modal find bar with Next/Previous
  (F3/Shift+F3 also work while it's open) and wrap-around search. Find,
  Title, and Hyperlink text fields all have a clear (×) button.
- Lock Note (hamburger ☰ menu): makes the note read-only — the
  text-formatting context menu collapses to just Find…, and Ctrl+B/I/U/K
  stop working too, so a locked note can't be edited from the keyboard
  either.
- Note title (hamburger ☰ menu's first item, or Shift+F2): shows as a bold
  line above the note body, only when set.
- Tray menu bulk actions (each also has its own optional global hotkey,
  see above): Bring Notes on Top, Show/Hide All Notes (collapses to one
  item, converging to all-shown or all-hidden), and Roll Up/Down Notes
  (rolls every note up if any are expanded, otherwise expands them
  all — one consistent end state for the whole batch rather than
  flipping each note independently). A single note can also be hidden
  on its own via the header/hamburger menu — session-only, same as the
  bulk actions, and still listed (and reopenable) in the Notes Browser
  while hidden.
