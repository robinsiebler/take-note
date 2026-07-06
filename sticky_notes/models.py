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
    name: str = "Memoboard"
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
