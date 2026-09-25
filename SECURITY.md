# Security Policy

## Reporting

Please report suspected vulnerabilities privately to the repository owner rather than opening a public issue.

## Security design

- Workflow calculation expressions are evaluated through a restricted AST walker; Python `eval` is not used.
- Outbound HTTP actions are disabled by default.
- An optional HTTP hostname allowlist restricts connector destinations.
- Webhook URLs include high-entropy generated tokens.
- Workflow idempotency prevents repeated client retries from duplicating a keyed execution.

## Production hardening

A public multi-user deployment should add authentication, authorization, encrypted connector secrets, CSRF protections for state-changing browser actions, rate limiting, structured logging, TLS termination, migration tooling, secret rotation, webhook token rotation, and network egress controls.
