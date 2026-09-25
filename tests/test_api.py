from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def client(tmp_path: Path) -> TestClient:
    settings = Settings(database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}", scheduler_enabled=False)
    return TestClient(create_app(settings))


def workflow_payload():
    return {
        "name": "Lead Router",
        "description": "Qualifies inbound leads",
        "steps": [
            {"name": "Score", "action": "calculate", "params": {"path": "result.score", "expression": "size + budget", "variables": {"size": "lead.size", "budget": "lead.budget"}}},
            {"name": "Note", "action": "template", "params": {"path": "result.note", "template": "{{lead.name}} scored {{result.score}}"}}
        ]
    }


def test_workflow_create_run_idempotency_webhook_and_metrics(tmp_path):
    c = client(tmp_path)
    created = c.post("/api/workflows", json=workflow_payload())
    assert created.status_code == 201
    workflow = created.json()
    workflow_id = workflow["id"]

    body = {"payload": {"lead": {"name": "Acme", "size": 50, "budget": 20}}}
    first = c.post(f"/api/workflows/{workflow_id}/run", json=body, headers={"Idempotency-Key": "abc-123"})
    second = c.post(f"/api/workflows/{workflow_id}/run", json=body, headers={"Idempotency-Key": "abc-123"})
    assert first.status_code == 200
    assert first.json()["status"] == "SUCCEEDED"
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["output"]["result"]["score"] == 70

    webhook = c.post(f"/api/webhooks/{workflow_id}/{workflow['webhook_token']}", json={"lead": {"name": "Beta", "size": 5, "budget": 7}})
    assert webhook.status_code == 200
    assert webhook.json()["trigger_type"] == "webhook"

    metrics = c.get("/api/metrics").json()
    assert metrics["workflows"] == 1
    assert metrics["runs"] == 2
    assert metrics["successful_runs"] == 2
    assert metrics["success_rate"] == 100.0


def test_schedule_create_and_manual_tick(tmp_path):
    c = client(tmp_path)
    workflow = c.post("/api/workflows", json=workflow_payload()).json()
    schedule = c.post(f"/api/workflows/{workflow['id']}/schedules", json={"name": "Every minute", "interval_minutes": 1, "payload": {"lead": {"name": "Schedule", "size": 1, "budget": 2}}})
    assert schedule.status_code == 201
    assert c.get("/api/schedules").json()[0]["interval_minutes"] == 1
    tick = c.post("/api/scheduler/tick")
    assert tick.status_code == 200
    assert tick.json()["executed"] == 0
