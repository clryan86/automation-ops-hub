from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import Settings
from app.database import Base, build_engine, build_session_factory
from app.models import Schedule, Workflow

settings = Settings.from_env()
engine = build_engine(settings.database_url)
Base.metadata.create_all(engine)
Session = build_session_factory(engine)

with Session() as session:
    for path in sorted((ROOT / "sample_workflows").glob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        workflow = session.query(Workflow).filter_by(name=spec["name"]).first()
        if workflow is None:
            workflow = Workflow(
                name=spec["name"],
                description=spec["description"],
                definition_json=json.dumps({"steps": spec["steps"]}),
            )
            session.add(workflow)
            session.flush()
            print(f"Created workflow #{workflow.id}: {workflow.name}")
            if "Lead" in workflow.name:
                session.add(
                    Schedule(
                        workflow_id=workflow.id,
                        name="Hourly demo lead check",
                        interval_minutes=60,
                        input_json=json.dumps({
                            "lead": {
                                "name": "Sample Account",
                                "email": "ops@example.com",
                                "company_size": 250,
                                "budget": 40000,
                                "enterprise": True
                            }
                        }),
                        next_run_at=datetime.now(timezone.utc) + timedelta(minutes=60),
                    )
                )
        else:
            print(f"Workflow already exists: {workflow.name}")
    session.commit()
