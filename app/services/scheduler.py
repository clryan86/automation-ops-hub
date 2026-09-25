from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from ..config import Settings
from ..models import Schedule, Workflow
from .engine import run_workflow


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def run_due_schedules(session_factory, settings: Settings) -> int:
    now = utc_now()
    count = 0
    with session_factory() as session:
        schedules = session.scalars(
            select(Schedule).where(Schedule.enabled.is_(True), Schedule.next_run_at <= now)
        ).all()
        for schedule in schedules:
            workflow = session.get(Workflow, schedule.workflow_id)
            if workflow and workflow.enabled:
                run_workflow(
                    session,
                    workflow,
                    json.loads(schedule.input_json),
                    settings,
                    trigger_type="schedule",
                    idempotency_key=f"schedule:{schedule.id}:{schedule.next_run_at.isoformat()}",
                )
                schedule.last_run_at = now
                schedule.next_run_at = now + timedelta(minutes=schedule.interval_minutes)
                session.commit()
                count += 1
    return count


class SchedulerThread:
    def __init__(self, session_factory, settings: Settings):
        self.session_factory = session_factory
        self.settings = settings
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._loop, name="automation-scheduler", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        self.thread.join(timeout=2)

    def _loop(self) -> None:
        while not self.stop_event.wait(self.settings.scheduler_poll_seconds):
            try:
                run_due_schedules(self.session_factory, self.settings)
            except Exception:
                # A production service would emit structured logs/telemetry here.
                continue
