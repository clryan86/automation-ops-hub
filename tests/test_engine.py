import json

from app.config import Settings
from app.database import Base, build_engine, build_session_factory
from app.models import Workflow
from app.services.engine import run_workflow


def make_session():
    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return build_session_factory(engine)()


def test_workflow_executes_steps_and_condition():
    session = make_session()
    workflow = Workflow(
        name="Test Workflow",
        description="",
        definition_json=json.dumps({"steps": [
            {"name": "Calc", "action": "calculate", "params": {"path": "result.total", "expression": "q * p", "variables": {"q": "order.qty", "p": "order.price"}}},
            {"name": "Label", "action": "set", "when": {"path": "order.vip", "operator": "equals", "value": True}, "params": {"path": "result.priority", "value": "high"}}
        ]})
    )
    session.add(workflow); session.commit()
    run = run_workflow(session, workflow, {"order": {"qty": 2, "price": 50, "vip": True}}, Settings(database_url="sqlite:///:memory:", scheduler_enabled=False), trigger_type="manual")
    assert run.status == "SUCCEEDED"
    output = json.loads(run.output_json)
    assert output["result"]["total"] == 100
    assert output["result"]["priority"] == "high"
    assert len(run.steps) == 2


def test_workflow_failure_is_recorded():
    session = make_session()
    workflow = Workflow(name="Failing", description="", definition_json=json.dumps({"steps": [{"name": "Guard", "action": "assert", "params": {"path": "missing", "operator": "truthy", "message": "Required"}, "max_attempts": 2}]}))
    session.add(workflow); session.commit()
    run = run_workflow(session, workflow, {}, Settings(database_url="sqlite:///:memory:", scheduler_enabled=False), trigger_type="manual")
    assert run.status == "FAILED"
    assert run.error == "Required"
    assert run.steps[0].attempts == 2
