# Changelog

All notable changes to Take Note! are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.3.0] - 2026-07-13

### Added
- Reminders: set a one-shot reminder on any note (☰ → Set/Edit
  Reminder…) with a date/time picker; a header bell icon shows when
  one's set. When it comes due, the note raises itself to the front
  (unrolling/restoring it if needed) — no desktop notification, no
  repeat. A reminder missed while the app was closed fires immediately
  on next launch; a reminder on a trashed note is skipped, not fired.

### Fixed
- A fired reminder could fail to visibly raise its note at all when
  the note wasn't Always-on-Top and was buried behind other windows —
  KWin's focus-stealing prevention silently denied the raise/activate
  request since it came from a background timer, not a direct click.
- A note stuck to another window could still briefly flash into the
  taskbar (with the same Vorta-icon mislabeling worked around
  elsewhere) during rapid minimize/restore cycling, even with the
  existing taskbar-hidden reassertion in place.

## [1.2.0] - 2026-07-13

### Added
- Trash: deleting a note now moves it to a Trash view in the Notes
  Manager instead of deleting it outright — Restore brings it back
  (including onto its original Notepad if it had one), or permanently
  delete it from there when ready.
- Configurable global hotkeys for Show/Hide All Notes, Roll Up/Down All
  Notes, and Bring Notes to Front (previously tray-menu-only), alongside
  New Note and the Notes Manager's own hotkey. The Hotkey tab scrolls
  instead of overflowing the screen, and a hint explains combos that
  don't register at all (already grabbed by a system shortcut).
- Configurable default note/notepad size — Small/Medium/Large/Extra
  Large presets in Settings.

### Changed
- Notes Browser renamed to Notes Manager, reflecting what it does now
  (Trash, bulk actions, filtering), not just browsing.

### Fixed
- Settings' OK/Apply could commit two hotkey fields to the same combo
  with no warning; only one could ever hold the real X11 grab, so the
  other silently stopped working.
- Reopening a minimized note, notepad, or the Notes Manager did nothing
  instead of restoring it.
- The Settings dialog showed up in the taskbar with the wrong icon, and
  opened a second copy if it was already open.
- A note stuck to another window (or hidden via Show/Hide All Notes)
  lost its taskbar-hidden state after being hidden and shown again.
- The Delete Notepad confirmation dialog could appear behind the
  board's own always-on-top notes.

## [1.1.0] - 2026-07-12

### Added
- Spell check: Ignore (session-only) and Add to Dictionary (permanent,
  via Enchant's own personal word list) alongside existing correction
  suggestions. Either clears the squiggly underline immediately on
  every open note containing the word, not just the one right-clicked.

## [1.0.0] - 2026-07-12

First tagged release. Highlights:

- Colored, resizable sticky notes with rich text: fonts, bold/italic/
  underline/strikethrough, alignment, bullets & numbering, font color,
  hyperlinks, and embedded images.
- Always-on-top, adjustable transparency, roll-up, and a global
  new-note hotkey.
- Notes Browser: a sortable, searchable table of every note, filterable
  by board or tag.
- Free-form tags per note, with a header icon indicator on the note
  itself.
- Notepads: group notes onto a shared corkboard-style window.
- Lock Note, in-note Find, optional spell check (via `pyenchant`).
- System tray for quick actions (new note/board, Notes Browser,
  Settings, bulk show/hide/roll).

[1.3.0]: https://github.com/robinsiebler/take-note/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/robinsiebler/take-note/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/robinsiebler/take-note/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/robinsiebler/take-note/releases/tag/v1.0.0
