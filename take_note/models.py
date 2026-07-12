from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex


# Default color palette. All Material Design 200-weight pastels, for a
# consistent saturation/lightness across the set — expanded from the
# original 7 (yellow..grey) to 12 (user wanted 10-12 options) by adding
# the 5 that filled the biggest hue gaps: red, cyan, lime, teal, and a
# more blue-leaning purple than the existing one.
SWATCHES = [
    "#fff59d",  # yellow
    "#a5d6a7",  # green
    "#90caf9",  # blue
    "#f48fb1",  # pink
    "#ffcc80",  # orange
    "#ce93d8",  # purple
    "#eeeeee",  # grey/white
    "#ef9a9a",  # red
    "#80deea",  # cyan
    "#e6ee9c",  # lime
    "#80cbc4",  # teal
    "#b39ddb",  # deep purple / lavender
]
DEFAULT_COLOR = SWATCHES[0]
DEFAULT_HOTKEY = "Meta+Alt+N"
DEFAULT_NOTES_BROWSER_HOTKEY = "Meta+Alt+B"

# Separate, darker palette for text color: the pastel SWATCHES above read
# poorly as font color against the (also pastel) note backgrounds. Also
# expanded from 7 to 12 alongside SWATCHES; the 5 additions were checked
# via WCAG contrast against all 12 SWATCHES entries (same method as
# HYPERLINK_COLOR in note_window.py) and land in the same range as the
# original 7's own worst cases (e.g. dark orange's ~1.6:1 against the
# orange swatch) rather than a stricter bar — this is the user's own free
# choice of text color, not a forced/unavoidable one like a hyperlink.
FONT_SWATCHES = [
    "#000000",  # black
    "#5d4037",  # dark brown
    "#c62828",  # dark red
    "#2e7d32",  # dark green
    "#1565c0",  # dark blue
    "#6a1b9a",  # dark purple
    "#e65100",  # dark orange
    "#00695c",  # dark teal
    "#283593",  # dark navy/indigo
    "#424242",  # charcoal
    "#ad1457",  # dark magenta
    "#556b2f",  # dark olive
]

# Named transparency presets, mapped to a QWidget.setWindowOpacity() value.
# "Full" stops short of 0 so the note stays visible/clickable rather than
# vanishing entirely.
TRANSPARENCY_LEVELS = [
    ("None", 1.0),
    ("Low", 0.85),
    ("Medium", 0.70),
    ("High", 0.55),
    ("Full", 0.40),
]


@dataclass
class Note:
    id: str = field(default_factory=_new_id)
    title: str = ""
    html: str = ""
    color: str = DEFAULT_COLOR
    x: int = 100
    y: int = 100
    w: int = 220
    h: int = 220
    always_on_top: bool = True
    rolled_up: bool = False
    locked: bool = False
    opacity: float = 1.0
    board_id: str | None = None
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)
    modified_at: str = field(default_factory=_now_iso)
    # None means "not in Trash". Deliberately left independent of
    # board_id — trashing a note never touches board_id, so a restored
    # note goes right back to whichever board it came from (or stays
    # unfiled if it never had one). Set only via NoteManager.trash_note().
    deleted_at: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Note":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class Board:
    id: str = field(default_factory=_new_id)
    name: str = "Notepad"
    color: str = "#e0e0e0"
    x: int = 150
    y: int = 150
    w: int = 400
    h: int = 300
    created_at: str = field(default_factory=_now_iso)
    modified_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Board":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class Settings:
    default_color: str = DEFAULT_COLOR
    randomize_new_note_color: bool = False
    default_always_on_top: bool = True
    default_font_size: int = 12
    default_font_color: str = "#000000"
    launch_at_login: bool = False
    # None means "no hotkey configured" (explicitly cleared via Settings'
    # Clear button) — distinct from the non-None string default a fresh
    # install starts with. Only ever becomes None through deliberate user
    # action, never a fallback/unset-on-disk state.
    hotkey: str | None = DEFAULT_HOTKEY
    notes_browser_hotkey: str | None = DEFAULT_NOTES_BROWSER_HOTKEY
    # No default combo for these three, unlike the two above — explicit
    # user call: these are opt-in, left for each user to pick their own
    # (or not bother), not something a fresh install grabs automatically.
    show_hide_all_notes_hotkey: str | None = None
    roll_all_notes_hotkey: str | None = None
    bring_all_notes_to_front_hotkey: str | None = None
    spell_check_enabled: bool = False

    # None until the Notes Manager has actually been moved/resized once —
    # lets it fall back to NotesManagerWindow's own built-in default
    # geometry on first run rather than every user starting at (0, 0).
    notes_browser_x: int | None = None
    notes_browser_y: int | None = None
    notes_browser_w: int | None = None
    notes_browser_h: int | None = None

    # Same pattern as notes_browser_x/y/w/h above, for SettingsDialog.
    settings_dialog_x: int | None = None
    settings_dialog_y: int | None = None
    settings_dialog_w: int | None = None
    settings_dialog_h: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Settings":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})
