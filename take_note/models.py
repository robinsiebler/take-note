from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex


# Default color palette.
SWATCHES = [
    "#fff59d",  # yellow
    "#a5d6a7",  # green
    "#90caf9",  # blue
    "#f48fb1",  # pink
    "#ffcc80",  # orange
    "#ce93d8",  # purple
    "#eeeeee",  # grey/white
]
DEFAULT_COLOR = SWATCHES[0]
DEFAULT_HOTKEY = "Ctrl+Alt+N"

# Separate, darker palette for text color: the pastel SWATCHES above read
# poorly as font color against the (also pastel) note backgrounds.
FONT_SWATCHES = [
    "#000000",  # black
    "#5d4037",  # dark brown
    "#c62828",  # dark red
    "#2e7d32",  # dark green
    "#1565c0",  # dark blue
    "#6a1b9a",  # dark purple
    "#e65100",  # dark orange
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
    created_at: str = field(default_factory=_now_iso)
    modified_at: str = field(default_factory=_now_iso)

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
    default_always_on_top: bool = True
    launch_at_login: bool = False
    hotkey: str = DEFAULT_HOTKEY

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Settings":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})
