from typing import Literal

from fastapi import APIRouter, Depends

from app.auth import current_business
from app.analytics import build_summary
from app.period import current_period, previous_period

router = APIRouter()


@router.get("/reports/summary")
def summary(range: Literal["week", "month"] = "week", include_previous: bool = False,
            business_id: str = Depends(current_business)):
    """ONE call returns every number the dashboard and the AI agent need."""
    current = build_summary(business_id, current_period(range))
    if include_previous:  # Day 8: "up 12% vs last week"
        current["previous"] = build_summary(business_id, previous_period(range))
    return current
