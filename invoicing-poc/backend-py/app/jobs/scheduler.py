import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.jobs.overdue import run_overdue_job

log = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None


def start_scheduler() -> None:
    global _scheduler
    if settings.disable_scheduler:
        log.info("[scheduler] disabled via DISABLE_SCHEDULER")
        return
    _scheduler = BackgroundScheduler(timezone=settings.timezone)
    # misfire_grace_time: if the process was busy/asleep at 08:00, still run when it wakes (up to 1h late)
    _scheduler.add_job(run_overdue_job, CronTrigger.from_crontab(settings.reminder_cron, timezone=settings.tz),
                       id="overdue", misfire_grace_time=3600, coalesce=True)
    _scheduler.start()
    log.info('[scheduler] overdue job scheduled "%s" (%s)', settings.reminder_cron, settings.timezone)
    # Catch-up run on boot (free hosts sleep idle servers). Safe to repeat: reminder_sent_at stops duplicate alerts.
    _scheduler.add_job(run_overdue_job, id="boot-catchup")


def stop_scheduler() -> None:
    if _scheduler:
        _scheduler.shutdown(wait=False)
