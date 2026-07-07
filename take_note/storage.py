from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path

from .models import Board, Note, Settings

logger = logging.getLogger(__name__)


def _default_path() -> Path:
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg_data_home) if xdg_data_home else Path.home() / ".local" / "share"
    return base / "take-note" / "notes.json"


def save_all(
    notes: list[Note],
    boards: list[Board],
    settings: Settings,
    path: Path | None = None,
) -> None:
    path = path or _default_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "notes": [n.to_dict() for n in notes],
        "boards": [b.to_dict() for b in boards],
        "settings": settings.to_dict(),
    }

    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2))
    os.replace(tmp_path, path)


def load_all(path: Path | None = None) -> tuple[list[Note], list[Board], Settings]:
    path = path or _default_path()

    if not path.exists():
        return [], [], Settings()

    try:
        payload = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        logger.warning("Corrupt notes file at %s, backing up and starting fresh", path)
        backup_path = path.with_suffix(path.suffix + ".bak")
        try:
            shutil.copy(path, backup_path)
        except OSError:
            pass
        return [], [], Settings()

    notes = [Note.from_dict(d) for d in payload.get("notes", [])]
    boards = [Board.from_dict(d) for d in payload.get("boards", [])]
    settings = Settings.from_dict(payload.get("settings", {}))
    return notes, boards, settings
