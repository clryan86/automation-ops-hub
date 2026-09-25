# API Guide

Interactive OpenAPI documentation is available at `/docs` while the service is running.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/healthz` | Runtime health |
| POST | `/api/workflows` | Create workflow |
| GET | `/api/workflows` | List workflows |
| GET | `/api/workflows/{id}` | Inspect workflow |
| POST | `/api/workflows/{id}/run` | Manual execution |
| POST | `/api/webhooks/{id}/{token}` | Event-driven execution |
| GET | `/api/runs` | Recent execution history |
| GET | `/api/runs/{id}` | Full run and step trace |
| POST | `/api/workflows/{id}/schedules` | Create interval schedule |
| GET | `/api/schedules` | List schedules |
| POST | `/api/scheduler/tick` | Execute currently due schedules |
| GET | `/api/metrics` | Workflow/run reliability metrics |
| GET | `/api/audit` | Audit event stream |

## Idempotency

Manual execution accepts an optional `Idempotency-Key` header. Reusing the same key for the same workflow returns the existing run rather than executing the workflow again.
