from __future__ import annotations

import json
import time
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import AuditEvent, StepRun, Workflow, WorkflowRun
from .actions import execute_action, get_path


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_definition(workflow: Workflow) -> list[dict[str, Any]]:
    payload = json.loads(workflow.definition_json)
    return payload.get("steps", [])


def should_run(step: dict[str, Any], context: dict[str, Any]) -> bool:
    condition = step.get("when")
    if not condition:
        return True
    actual = get_path(context, str(condition.get("path", "")))
    operator = condition.get("operator", "equals")
    expected = condition.get("value")
    if operator == "equals":
        return actual == expected
    if operator == "not_equals":
        return actual != expected
    if operator == "truthy":
        return bool(actual)
    if operator == "exists":
        return actual is not None
    return False


def run_workflow(
    session: Session,
    workflow: Workflow,
    input_payload: dict[str, Any],
    settings: Settings,
    *,
    trigger_type: str,
    idempotency_key: str | None = None,
) -> WorkflowRun:
    if idempotency_key:
        existing = session.scalar(
            select(WorkflowRun).where(
                WorkflowRun.workflow_id == workflow.id,
                WorkflowRun.idempotency_key == idempotency_key,
            )
        )
        if existing:
            return existing

    run = WorkflowRun(
        workflow_id=workflow.id,
        trigger_type=trigger_type,
        idempotency_key=idempotency_key,
        status="RUNNING",
        input_json=json.dumps(input_payload),
    )
    session.add(run)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        return session.scalar(
            select(WorkflowRun).where(
                WorkflowRun.workflow_id == workflow.id,
                WorkflowRun.idempotency_key == idempotency_key,
            )
        )

    context = deepcopy(input_payload)
    context.setdefault("meta", {})
    context["meta"].update({"workflow_id": workflow.id, "run_id": run.id})
    started = time.perf_counter()

    try:
        for position, step in enumerate(parse_definition(workflow)):
            name = str(step.get("name") or f"Step {position + 1}")
            action = str(step.get("action") or "")
            max_attempts = max(1, min(int(step.get("max_attempts", 1)), 5))

            if not should_run(step, context):
                session.add(
                    StepRun(
                        run_id=run.id,
                        position=position,
                        step_name=name,
                        action=action,
                        status="SKIPPED",
                        attempts=0,
                    )
                )
                session.flush()
                continue

            step_started = time.perf_counter()
            last_error: Exception | None = None
            result: dict[str, Any] | None = None
            attempts = 0
            for attempts in range(1, max_attempts + 1):
                try:
                    result = execute_action(action, step.get("params", {}), context, settings)
                    last_error = None
                    break
                except Exception as exc:
                    last_error = exc
                    if attempts < max_attempts:
                        time.sleep(min(0.05 * attempts, 0.15))

            duration_ms = (time.perf_counter() - step_started) * 1000
            if last_error is not None:
                session.add(
                    StepRun(
                        run_id=run.id,
                        position=position,
                        step_name=name,
                        action=action,
                        status="FAILED",
                        attempts=attempts,
                        error=str(last_error),
                        duration_ms=duration_ms,
                    )
                )
                raise last_error

            session.add(
                StepRun(
                    run_id=run.id,
                    position=position,
                    step_name=name,
                    action=action,
                    status="SUCCEEDED",
                    attempts=attempts,
                    output_json=json.dumps(result),
                    duration_ms=duration_ms,
                )
            )
            session.flush()

        run.status = "SUCCEEDED"
        run.output_json = json.dumps(context)
    except Exception as exc:
        run.status = "FAILED"
        run.error = str(exc)
        run.output_json = json.dumps(context)
    finally:
        run.finished_at = utc_now()
        run.duration_ms = (time.perf_counter() - started) * 1000
        session.add(
            AuditEvent(
                event_type="workflow.run.finished",
                entity_type="workflow_run",
                entity_id=run.id,
                details_json=json.dumps({"status": run.status, "workflow_id": workflow.id, "trigger_type": trigger_type}),
            )
        )
        session.commit()
        session.refresh(run)

    return run
