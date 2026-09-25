# Automation Ops Hub

[![CI](https://github.com/clryan86/automation-ops-hub/actions/workflows/ci.yml/badge.svg)](https://github.com/clryan86/automation-ops-hub/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-workflow%20API-009688)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.x-red)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED)
![License](https://img.shields.io/badge/license-MIT-green)

A production-minded **workflow orchestration and business automation platform** built with Python, FastAPI, SQLAlchemy, and a custom execution engine.

Automation Ops Hub lets teams define reusable workflows as JSON, trigger them by API or webhook, schedule recurring execution, apply conditional steps, retry failures, prevent duplicate processing with idempotency keys, and inspect step-level audit history from an operations dashboard.

> **Portfolio focus:** This project demonstrates backend engineering, workflow orchestration, API integration patterns, execution reliability, auditability, scheduling, testing, CI, and containerized deployment without depending on a paid SaaS platform.

## Why this project exists

Business automation is rarely just “run a script.” Reliable automation needs:

- repeatable workflow definitions,
- traceable execution history,
- safe retries,
- idempotency,
- conditional logic,
- scheduled and event-driven triggers,
- visibility into failures,
- and a clean integration boundary for external systems.

This project models those concerns directly.

## Core capabilities

### Workflow engine
- JSON-defined multi-step workflows
- ordered step execution
- conditional `when` clauses
- configurable retry attempts
- step-level timing and status
- context passed between steps
- success/failure persistence

### Built-in actions
- nested value assignment
- string templating
- safe arithmetic expressions
- regex extraction
- assertions / validation gates
- guarded outbound HTTP requests

### Triggers
- manual API execution
- secret webhook URL per workflow
- interval schedules
- explicit scheduler tick endpoint for deterministic operations/testing
- lightweight background scheduler in normal runtime

### Reliability
- `Idempotency-Key` support prevents duplicate manual runs
- workflow/run/step state persisted in SQL
- retries capped per step
- execution duration tracked
- failed step errors stored for diagnosis
- audit events recorded independently of run output

### Operations UI
- workflow inventory
- run counts and success rate
- recurring schedules
- recent run history
- step-by-step execution traces

## Architecture

```text
                 +--------------------+
API / Webhook -->|      FastAPI       |<-- Browser dashboard
                 +---------+----------+
                           |
                +----------v-----------+
                |   Workflow Engine    |
                | conditions / retry   |
                | idempotency / state  |
                +----+------------+----+
                     |            |
          +----------v--+      +--v----------------+
          | Built-in     |      | Scheduler         |
          | actions      |      | interval polling  |
          +------+-------+      +---------+----------+
                 |                        |
                 +-----------+------------+
                             |
                    +--------v--------+
                    |   SQLAlchemy    |
                    | SQLite / future |
                    | PostgreSQL      |
                    +-----------------+
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for more detail.

## Quick start

```bash
python -m venv .venv
```

Activate the environment:

```bash
# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# macOS/Linux
source .venv/bin/activate
```

Install dependencies and seed demo workflows:

```bash
pip install -r requirements-dev.txt
python scripts/seed_demo.py
uvicorn app.main:app --reload
```

Open:

- Dashboard: `http://127.0.0.1:8000`
- API docs: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/healthz`

## Example: create a workflow

```json
{
  "name": "Lead Router",
  "description": "Scores and routes inbound leads",
  "steps": [
    {
      "name": "Calculate score",
      "action": "calculate",
      "params": {
        "path": "result.score",
        "expression": "size * 0.5 + budget * 0.01",
        "variables": {
          "size": "lead.company_size",
          "budget": "lead.budget"
        }
      }
    },
    {
      "name": "Create note",
      "action": "template",
      "params": {
        "path": "result.note",
        "template": "{{lead.name}} scored {{result.score}}"
      }
    }
  ]
}
```

POST it to `/api/workflows`, then execute it with:

```json
{
  "payload": {
    "lead": {
      "name": "Acme Corp",
      "company_size": 500,
      "budget": 75000
    }
  }
}
```

Use the `Idempotency-Key` request header when retrying an execution from a client that must avoid duplicate processing.

## Tests

```bash
pytest
ruff check .
```

The automated suite covers:

- template rendering and nested context access,
- safe arithmetic evaluation,
- rejection of code-injection expressions,
- action composition,
- conditional workflow execution,
- failure and retry recording,
- API workflow creation,
- idempotent execution,
- webhook triggers,
- metrics,
- schedule creation,
- scheduler ticking.

## Docker

```bash
docker compose up --build
```

## Security model

Outbound `http_request` actions are **disabled by default**. They can be enabled with `ALLOW_HTTP_ACTIONS=true`, and production deployments should also define `HTTP_HOST_ALLOWLIST` so workflows cannot call arbitrary hosts.

The calculator uses a restricted Python AST evaluator rather than `eval`, preventing arbitrary code execution from workflow expressions.

See [SECURITY.md](SECURITY.md).

## Engineering highlights

- custom workflow engine rather than framework magic
- deterministic step state machine
- safe expression evaluation with AST whitelisting
- API/webhook/schedule trigger separation
- database-backed idempotency
- run + step audit trail
- background scheduler kept optional for deterministic tests
- provider-neutral HTTP integration boundary
- automatic OpenAPI documentation
- Docker and GitHub Actions

## Roadmap

- PostgreSQL deployment profile
- Alembic migrations
- authentication / RBAC
- encrypted credential vault for connectors
- queue-backed distributed workers
- dead-letter queue and replay UI
- cron expressions
- Slack / Gmail / GitHub connector adapters
- OpenTelemetry traces and Prometheus metrics
- workflow versioning
- drag-and-drop workflow builder

## Author

**Christopher Ryan**  
Python • Automation • Backend • Data & Applied AI

Built as part of a professional software-engineering portfolio focused on practical systems that automate real operational work.

## License

MIT
