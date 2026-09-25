from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, selectinload

from .config import Settings
from .database import Base, build_engine, build_session_factory
from .models import AuditEvent, Schedule, Workflow, WorkflowRun
from .schemas import MetricsResponse, RunRequest, RunResponse, ScheduleCreate, ScheduleResponse, StepRunResponse, WorkflowCreate, WorkflowResponse
from .services.engine import run_workflow
from .services.scheduler import SchedulerThread, run_due_schedules

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = Jinja2Templates(directory=str(ROOT / "templates"))


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    if settings.database_url.startswith("sqlite:///"):
        db_path = Path(settings.database_url.removeprefix("sqlite:///"))
        if not db_path.is_absolute():
            db_path = ROOT / db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)

    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)
    Base.metadata.create_all(engine)
    scheduler: SchedulerThread | None = None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal scheduler
        if settings.scheduler_enabled:
            scheduler = SchedulerThread(session_factory, settings)
            scheduler.start()
        yield
        if scheduler:
            scheduler.stop()

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description="Workflow orchestration, webhook automation, scheduling, retries, idempotency, and audit history.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")

    def get_session(request: Request):
        session = request.app.state.session_factory()
        try:
            yield session
        finally:
            session.close()

    @app.get("/healthz")
    def healthz():
        return {"ok": True, "service": settings.app_name, "scheduler_enabled": settings.scheduler_enabled}

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request, session: Session = Depends(get_session)):
        workflows = session.scalars(select(Workflow).order_by(Workflow.name)).all()
        runs = session.scalars(
            select(WorkflowRun).options(selectinload(WorkflowRun.workflow)).order_by(desc(WorkflowRun.created_at)).limit(12)
        ).all()
        schedules = session.scalars(select(Schedule).order_by(Schedule.next_run_at).limit(12)).all()
        metrics = _metrics(session)
        return TEMPLATES.TemplateResponse(
            request=request,
            name="index.html",
            context={"app_name": settings.app_name, "workflows": workflows, "runs": runs, "schedules": schedules, "metrics": metrics},
        )

    @app.get("/runs/{run_id}", response_class=HTMLResponse)
    def run_page(run_id: int, request: Request, session: Session = Depends(get_session)):
        run = session.scalar(select(WorkflowRun).options(selectinload(WorkflowRun.steps), selectinload(WorkflowRun.workflow)).where(WorkflowRun.id == run_id))
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        return TEMPLATES.TemplateResponse(request=request, name="run.html", context={"app_name": settings.app_name, "run": run, "output": json.loads(run.output_json or "{}")})

    @app.post("/api/workflows", response_model=WorkflowResponse, status_code=201)
    def create_workflow(payload: WorkflowCreate, session: Session = Depends(get_session)):
        if session.scalar(select(Workflow).where(Workflow.name == payload.name)):
            raise HTTPException(status_code=409, detail="Workflow name already exists")
        workflow = Workflow(name=payload.name, description=payload.description, definition_json=json.dumps({"steps": payload.steps}))
        session.add(workflow)
        session.flush()
        session.add(AuditEvent(event_type="workflow.created", entity_type="workflow", entity_id=workflow.id, details_json=json.dumps({"name": workflow.name})))
        session.commit(); session.refresh(workflow)
        return _workflow_response(workflow)

    @app.get("/api/workflows", response_model=list[WorkflowResponse])
    def list_workflows(session: Session = Depends(get_session)):
        return [_workflow_response(item) for item in session.scalars(select(Workflow).order_by(Workflow.name)).all()]

    @app.get("/api/workflows/{workflow_id}", response_model=WorkflowResponse)
    def get_workflow(workflow_id: int, session: Session = Depends(get_session)):
        workflow = session.get(Workflow, workflow_id)
        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")
        return _workflow_response(workflow)

    @app.post("/api/workflows/{workflow_id}/run", response_model=RunResponse)
    def manual_run(workflow_id: int, payload: RunRequest, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), session: Session = Depends(get_session)):
        workflow = session.get(Workflow, workflow_id)
        if not workflow or not workflow.enabled:
            raise HTTPException(status_code=404, detail="Workflow not found or disabled")
        run = run_workflow(session, workflow, payload.payload, settings, trigger_type="manual", idempotency_key=idempotency_key)
        return _run_response(run, session)

    @app.post("/api/webhooks/{workflow_id}/{webhook_token}", response_model=RunResponse)
    def webhook_run(workflow_id: int, webhook_token: str, payload: dict, session: Session = Depends(get_session)):
        workflow = session.get(Workflow, workflow_id)
        if not workflow or workflow.webhook_token != webhook_token or not workflow.enabled:
            raise HTTPException(status_code=404, detail="Webhook not found")
        run = run_workflow(session, workflow, payload, settings, trigger_type="webhook")
        return _run_response(run, session)

    @app.get("/api/runs", response_model=list[RunResponse])
    def list_runs(limit: int = 25, session: Session = Depends(get_session)):
        limit = max(1, min(limit, 100))
        runs = session.scalars(select(WorkflowRun).order_by(desc(WorkflowRun.created_at)).limit(limit)).all()
        return [_run_response(run, session) for run in runs]

    @app.get("/api/runs/{run_id}", response_model=RunResponse)
    def get_run(run_id: int, session: Session = Depends(get_session)):
        run = session.get(WorkflowRun, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        return _run_response(run, session)

    @app.post("/api/workflows/{workflow_id}/schedules", response_model=ScheduleResponse, status_code=201)
    def create_schedule(workflow_id: int, payload: ScheduleCreate, session: Session = Depends(get_session)):
        workflow = session.get(Workflow, workflow_id)
        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")
        schedule = Schedule(workflow_id=workflow_id,name=payload.name,interval_minutes=payload.interval_minutes,input_json=json.dumps(payload.payload),next_run_at=utc_now()+timedelta(minutes=payload.interval_minutes))
        session.add(schedule); session.commit(); session.refresh(schedule)
        return _schedule_response(schedule)

    @app.get("/api/schedules", response_model=list[ScheduleResponse])
    def list_schedules(session: Session = Depends(get_session)):
        return [_schedule_response(s) for s in session.scalars(select(Schedule).order_by(Schedule.next_run_at)).all()]

    @app.post("/api/scheduler/tick")
    def scheduler_tick(request: Request):
        count = run_due_schedules(request.app.state.session_factory, settings)
        return {"executed": count}

    @app.get("/api/metrics", response_model=MetricsResponse)
    def metrics(session: Session = Depends(get_session)):
        return _metrics(session)

    @app.get("/api/audit")
    def audit(limit: int = 50, session: Session = Depends(get_session)):
        events = session.scalars(select(AuditEvent).order_by(desc(AuditEvent.created_at)).limit(max(1, min(limit, 200)))).all()
        return [{"id": e.id, "event_type": e.event_type, "entity_type": e.entity_type, "entity_id": e.entity_id, "details": json.loads(e.details_json), "created_at": e.created_at} for e in events]

    return app


def _workflow_response(workflow: Workflow) -> WorkflowResponse:
    return WorkflowResponse(id=workflow.id,name=workflow.name,description=workflow.description,enabled=workflow.enabled,webhook_token=workflow.webhook_token,steps=json.loads(workflow.definition_json).get("steps", []),created_at=workflow.created_at)


def _run_response(run: WorkflowRun, session: Session) -> RunResponse:
    session.refresh(run)
    steps = sorted(run.steps, key=lambda s: s.position)
    return RunResponse(id=run.id,workflow_id=run.workflow_id,trigger_type=run.trigger_type,status=run.status,input=json.loads(run.input_json),output=json.loads(run.output_json) if run.output_json else None,error=run.error,duration_ms=run.duration_ms,created_at=run.created_at,finished_at=run.finished_at,steps=[StepRunResponse(position=s.position,step_name=s.step_name,action=s.action,status=s.status,attempts=s.attempts,output=json.loads(s.output_json) if s.output_json else None,error=s.error,duration_ms=s.duration_ms) for s in steps])


def _schedule_response(schedule: Schedule) -> ScheduleResponse:
    return ScheduleResponse(id=schedule.id,workflow_id=schedule.workflow_id,name=schedule.name,interval_minutes=schedule.interval_minutes,enabled=schedule.enabled,payload=json.loads(schedule.input_json),last_run_at=schedule.last_run_at,next_run_at=schedule.next_run_at)


def _metrics(session: Session) -> MetricsResponse:
    workflows = session.scalar(select(func.count(Workflow.id))) or 0
    runs = session.scalar(select(func.count(WorkflowRun.id))) or 0
    success = session.scalar(select(func.count(WorkflowRun.id)).where(WorkflowRun.status == "SUCCEEDED")) or 0
    failed = session.scalar(select(func.count(WorkflowRun.id)).where(WorkflowRun.status == "FAILED")) or 0
    schedules = session.scalar(select(func.count(Schedule.id))) or 0
    rate = round((success / runs) * 100, 2) if runs else 0.0
    return MetricsResponse(workflows=int(workflows),runs=int(runs),successful_runs=int(success),failed_runs=int(failed),success_rate=rate,schedules=int(schedules))


app = create_app()
