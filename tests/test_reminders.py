from __future__ import annotations

from datetime import datetime, timedelta, timezone

from take_note.reminders import (
    format_reminder_for_display,
    is_reminder_due,
    local_datetime_to_utc_iso,
    utc_iso_to_local_datetime,
)


def test_utc_iso_to_local_datetime_round_trips_to_the_same_instant():
    original = datetime(2026, 3, 5, 14, 30, tzinfo=timezone.utc)
    iso = original.isoformat()

    local = utc_iso_to_local_datetime(iso)

    assert local.astimezone(timezone.utc) == original


def test_local_datetime_to_utc_iso_round_trips_to_the_same_instant():
    # Naive, as QDateTimeEdit.dateTime().toPython() would produce.
    naive_local = datetime(2026, 3, 5, 9, 15)

    iso = local_datetime_to_utc_iso(naive_local)

    # The naive value, tagged with the system's own local zone, must be
    # the same instant as what got stored.
    expected = naive_local.astimezone(timezone.utc)
    assert datetime.fromisoformat(iso) == expected


def test_local_datetime_to_utc_iso_does_not_treat_naive_value_as_already_utc():
    """Regression guard for the mirror-image of the notes_manager
    _format_modified bug: naive_dt.replace(tzinfo=timezone.utc) would
    silently skip the local->UTC conversion. Only meaningfully catches
    the bug when the test machine's local zone isn't UTC itself."""
    naive_local = datetime(2026, 3, 5, 9, 15)

    iso = local_datetime_to_utc_iso(naive_local)

    wrong_result = naive_local.replace(tzinfo=timezone.utc).isoformat()
    local_offset = datetime.now().astimezone().utcoffset()
    if local_offset and local_offset != timedelta(0):
        assert iso != wrong_result


def test_format_reminder_for_display_matches_the_project_convention():
    utc_iso = datetime(2026, 7, 10, 20, 56, tzinfo=timezone.utc).isoformat()

    formatted = format_reminder_for_display(utc_iso)

    expected = utc_iso_to_local_datetime(utc_iso).strftime("%B %d, %Y %I:%M %p")
    assert formatted == expected


def test_is_reminder_due_before_at_and_after_now():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    earlier = (now - timedelta(minutes=1)).isoformat()
    exact = now.isoformat()
    later = (now + timedelta(minutes=1)).isoformat()

    assert is_reminder_due(earlier, now) is True
    assert is_reminder_due(exact, now) is True
    assert is_reminder_due(later, now) is False


def test_is_reminder_due_defaults_now_to_the_current_time():
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

    assert is_reminder_due(past) is True
    assert is_reminder_due(future) is False
