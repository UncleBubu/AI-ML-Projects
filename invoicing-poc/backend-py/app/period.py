"""Day 6: turn 'this week' / 'this month' into absolute UTC windows using the
business timezone. The database only ever receives absolute instants, so it can
never silently fall back to UTC.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from app.config import settings

Range = Literal["week", "month"]


@dataclass(frozen=True)
class Period:
    range: str
    start: datetime  # inclusive, tz-aware UTC
    end: datetime    # exclusive, tz-aware UTC
    timezone: str


def _midnight(d: date, tz: ZoneInfo) -> datetime:
    return datetime.combine(d, time.min, tzinfo=tz).astimezone(timezone.utc)


def _period_start_date(range_: str, local_day: date) -> date:
    if range_ == "week":
        return local_day - timedelta(days=local_day.weekday())  # weekday(): Monday == 0
    return local_day.replace(day=1)


def current_period(range_: Range, now: datetime | None = None, tz: ZoneInfo | None = None) -> Period:
    """Period-to-date: from the start of the week/month (00:00 business time) until now."""
    tz = tz or settings.tz
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    start = _midnight(_period_start_date(range_, now.astimezone(tz).date()), tz)
    return Period(range_, start, now, str(tz))


def previous_period(range_: Range, now: datetime | None = None, tz: ZoneInfo | None = None) -> Period:
    """Like-for-like window: the same elapsed time into the PREVIOUS period.

    Comparing Mon-Wed of this week with the whole of last week would always look
    like a collapse; Mon-Wed vs Mon-Wed is fair. Capped so it never overlaps the
    current period (e.g. the 31st vs a 30-day month).
    """
    tz = tz or settings.tz
    cur = current_period(range_, now, tz)
    day_before = cur.start.astimezone(tz).date() - timedelta(days=1)
    prev_start = _midnight(_period_start_date(range_, day_before), tz)
    prev_end = min(prev_start + (cur.end - cur.start), cur.start)
    return Period(range_, prev_start, prev_end, str(tz))
