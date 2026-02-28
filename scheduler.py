"""APScheduler setup for background jobs."""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

import config

_scheduler = None


def get_scheduler():
    """Get or create the singleton scheduler."""
    global _scheduler
    if _scheduler is None:
        db_path = config.DATA_DIR / "scheduler.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        jobstores = {
            "default": SQLAlchemyJobStore(url=f"sqlite:///{db_path}")
        }

        _scheduler = BackgroundScheduler(jobstores=jobstores)
        _scheduler.start()
    return _scheduler


def init_scheduler():
    """Initialize scheduled jobs on app startup."""
    scheduler = get_scheduler()

    # Channel scan every 4 hours
    scheduler.add_job(
        func="channel_scanner:scan_channels",
        trigger="interval",
        hours=config.SCAN_INTERVAL_HOURS,
        id="channel_scan",
        replace_existing=True,
    )

    # News generation at midnight UTC
    scheduler.add_job(
        func="news_generator:generate_daily_news",
        trigger="cron",
        hour=config.NEWS_GENERATION_HOUR,
        id="news_generation",
        replace_existing=True,
    )
