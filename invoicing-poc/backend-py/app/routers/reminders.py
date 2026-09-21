from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.auth import current_business, require_auth
from app.db import supabase
from app.jobs import overdue as overdue_job

router = APIRouter()


@router.get("/reminders/overdue")
def overdue_now(business_id: str = Depends(current_business)):
    """Dashboard banner data, computed from due_date - so it's right even before the daily job has run."""
    return (supabase.table("invoice").select("id, invoice_number, due_date, total_amount, amount_paid, customer(name)")
            .eq("business_id", business_id).in_("status", ["sent", "overdue"])
            .lt("due_date", datetime.now(timezone.utc).isoformat()).order("due_date").execute().data)


@router.post("/reminders/run")
def run_now(business_id: str = Depends(current_business)):
    """Manual 'send reminder now' - also the cut-list fallback if the cron proves flaky."""
    return overdue_job.run_overdue_job(business_id)


@router.get("/jobs/status", dependencies=[Depends(require_auth)])
def job_status():
    return {"lastRun": overdue_job.last_run}
