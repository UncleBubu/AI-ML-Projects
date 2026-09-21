"""Timezone-aware date helpers. Python's zoneinfo does the hard part for us."""
from datetime import date, datetime, time, timezone

from app.config import settings


def _parse(iso_date: str) -> date:
    return date.fromisoformat(iso_date)


def end_of_day_utc(iso_date: str) -> str:
    """'2026-10-01' -> last instant of Oct 1 in the BUSINESS timezone, as UTC ISO.

    Treating a bare date as UTC midnight would make an invoice overdue ~a day
    early for a Lagos business.
    """
    return datetime.combine(_parse(iso_date), time(23, 59, 59), tzinfo=settings.tz).astimezone(timezone.utc).isoformat()


def noon_utc(iso_date: str) -> str:
    """Noon of that day in the business timezone: safely inside its own calendar day."""
    return datetime.combine(_parse(iso_date), time(12, 0), tzinfo=settings.tz).astimezone(timezone.utc).isoformat()
