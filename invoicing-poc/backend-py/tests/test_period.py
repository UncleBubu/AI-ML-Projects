from datetime import datetime, timezone

from app.dates import end_of_day_utc
from app.period import current_period, previous_period


def utc(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def test_week_starts_monday_midnight_lagos():
    assert current_period("week", utc("2026-09-19T15:00:00Z")).start == utc("2026-09-13T23:00:00Z")


def test_sunday_2330_utc_is_already_monday_in_lagos():
    # the classic midnight bug: a UTC-based week would still be the OLD week
    assert current_period("week", utc("2026-09-20T23:30:00Z")).start == utc("2026-09-20T23:00:00Z")


def test_month_starts_on_the_first_lagos_time():
    assert current_period("month", utc("2026-09-19T15:00:00Z")).start == utc("2026-08-31T23:00:00Z")


def test_previous_week_is_like_for_like():
    now = utc("2026-09-16T12:00:00Z")
    cur, prev = current_period("week", now), previous_period("week", now)
    assert prev.start == utc("2026-09-06T23:00:00Z")
    assert prev.end - prev.start == cur.end - cur.start


def test_previous_month_across_year_boundary():
    assert previous_period("month", utc("2027-01-10T10:00:00Z")).start == utc("2026-11-30T23:00:00Z")


def test_previous_window_never_overlaps_current():
    now = utc("2026-10-31T10:00:00Z")
    assert previous_period("month", now).end <= current_period("month", now).start


def test_due_date_is_end_of_day_lagos():
    assert end_of_day_utc("2026-10-01") == "2026-10-01T22:59:59+00:00"
