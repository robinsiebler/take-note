from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "take-note"


def _autostart_dir() -> Path:
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg_config_home) if xdg_config_home else Path.home() / ".config"
    return base / "autostart"


def _desktop_file_path() -> Path:
    return _autostart_dir() / f"{APP_NAME}.desktop"


def _executable_path() -> Path:
    """Path to the installed console-script entry point, which setuptools/
    hatchling install alongside the running Python interpreter (e.g. next
    to .venv/bin/python)."""
    return Path(sys.executable).parent / APP_NAME


def is_enabled() -> bool:
    return _desktop_file_path().exists()


def enable() -> None:
    autostart_dir = _autostart_dir()
    autostart_dir.mkdir(parents=True, exist_ok=True)
    content = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Take Note!\n"
        f"Exec={_executable_path()}\n"
        "X-GNOME-Autostart-enabled=true\n"
    )
    _desktop_file_path().write_text(content)


def disable() -> None:
    path = _desktop_file_path()
    if path.exists():
        path.unlink()
