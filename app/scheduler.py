from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .db import connect


class TaskScheduler:
    def __init__(self, runner):
        self.runner = runner
        self.scheduler = BackgroundScheduler(timezone="Asia/Shanghai")

    def start(self):
        self.scheduler.add_job(self.refresh, "interval", seconds=30, id="refresh", replace_existing=True)
        self.scheduler.start()
        self.refresh()

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def refresh(self):
        with connect() as db:
            rows = db.execute("SELECT id, schedule FROM tasks WHERE enabled=1 AND schedule IS NOT NULL AND schedule != ''").fetchall()
        current = {f"task-{row['id']}" for row in rows}
        for job in self.scheduler.get_jobs():
            if job.id != "refresh" and job.id not in current:
                self.scheduler.remove_job(job.id)
        for row in rows:
            job_id = f"task-{row['id']}"
            try:
                trigger = CronTrigger.from_crontab(row["schedule"], timezone="Asia/Shanghai")
            except ValueError:
                continue
            self.scheduler.add_job(self.runner, trigger=trigger, args=[row["id"]], id=job_id, replace_existing=True)
