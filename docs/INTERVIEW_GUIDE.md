# Interview Guide

## 30-second explanation

> Automation Ops Hub is a FastAPI workflow orchestration service I built to model the reliability concerns behind real business automation. Workflows are stored as JSON definitions, can be triggered manually, by webhook, or on an interval, and every run stores step-level status, retries, duration, input, and output. I also implemented database-backed idempotency and a safe AST-based calculation engine instead of using `eval`.

## What problem does it solve?

A one-off script can automate a task, but operational automation needs visibility and control. This project adds execution history, retries, idempotency, validation, conditional logic, scheduling, webhook triggers, and audit trails around the automation logic.

## Strong technical talking points

### Why a custom engine?

The goal was to demonstrate the mechanics of orchestration instead of hiding them behind a workflow framework. The core loop explicitly evaluates conditions, applies retries, records each step, handles failure, and persists the final run.

### Why database-backed idempotency?

API clients often retry requests after timeouts. Without idempotency, a retry could duplicate a payment, email, order, or other business side effect. The `(workflow_id, idempotency_key)` unique constraint makes duplicate manual requests resolve to the same execution.

### How is arbitrary-code execution avoided?

Calculations are parsed into a Python AST. Only numeric constants, variable names, and selected arithmetic operators are allowed. Calls, attribute access, imports, and arbitrary Python syntax are rejected.

### How are HTTP actions protected?

They are disabled by default. An operator must explicitly enable them, and can configure a hostname allowlist. This reduces accidental network access and SSRF exposure.

### What would change at scale?

- distributed queue workers
- PostgreSQL
- Alembic migrations
- versioned workflows
- secret management
- dead-letter queues
- durable timers / cron
- RBAC
- metrics/tracing
- connector SDK

## Resume bullets

- Built a FastAPI workflow-orchestration platform supporting manual, webhook, and scheduled triggers with persistent run/step audit history.
- Implemented database-backed idempotency, bounded retries, conditional execution, safe AST arithmetic, templating, validation, and guarded HTTP actions.
- Added automated unit/API tests, Docker packaging, GitHub Actions CI, execution metrics, and recruiter-focused architecture/security documentation.
