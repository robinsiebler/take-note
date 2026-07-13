from __future__ import annotations

from datetime import datetime, timezone


def utc_iso_to_local_datetime(iso_timestamp: str) -> datetime:
    """Note.reminder_at is a UTC-aware ISO-8601 string (same convention as
    created_at/modified_at). astimezone() with no argument converts an
    aware datetime to the system's local timezone — same fix already used
    by notes_manager._format_modified() for the identical bug class
    (naively formatting a UTC-offset datetime displays the wrong
    wall-clock hour, mislabeled as local)."""
    return datetime.fromisoformat(iso_timestamp).astimezone()


def local_datetime_to_utc_iso(local_dt: datetime) -> str:
    """The inverse: local_dt is what QDateTimeEdit.dateTime().toPython()
    returns — a *naive* datetime representing the user's local wall-clock
    pick, no tzinfo at all. astimezone() with no argument on a naive
    datetime assumes it's already in the system's local timezone and
    attaches that tzinfo (this is Python's documented behavior, not a
    guess) — only then is it safe to convert to UTC. Deliberately not
    local_dt.replace(tzinfo=timezone.utc): that would claim the naive
    value is already UTC and skip the conversion entirely, the
    mirror-image of the bug utc_iso_to_local_datetime() exists to avoid."""
    return local_dt.astimezone(timezone.utc).isoformat()


def format_reminder_for_display(iso_timestamp: str) -> str:
    """Same US date/time convention as notes_manager._format_modified(),
    reused rather than reinvented."""
    return utc_iso_to_local_datetime(iso_timestamp).strftime("%B %d, %Y %I:%M %p")


def is_reminder_due(iso_timestamp: str, now: datetime | None = None) -> bool:
    """Pure instant comparison — both sides stay UTC-aware, no local
    conversion needed just to compare two points in time. `now` is a
    parameter (not always datetime.now(timezone.utc) internally) purely
    so tests can pass a fixed value instead of depending on wall-clock
    time."""
    if now is None:
        now = datetime.now(timezone.utc)
    return datetime.fromisoformat(iso_timestamp) <= now
