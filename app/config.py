from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_url: str
    scheduler_enabled: bool = True
    scheduler_poll_seconds: int = 15
    allow_http_actions: bool = False
    http_host_allowlist: tuple[str, ...] = ()
    app_name: str = "Automation Ops Hub"

    @classmethod
    def from_env(cls) -> "Settings":
        root = Path(__file__).resolve().parents[1]
        database_url = os.getenv(
            "DATABASE_URL",
            f"sqlite:///{(root / 'data' / 'automation_ops.db').as_posix()}",
        )
        allowlist = tuple(
            item.strip().lower()
            for item in os.getenv("HTTP_HOST_ALLOWLIST", "").split(",")
            if item.strip()
        )
        return cls(
            database_url=database_url,
            scheduler_enabled=os.getenv("SCHEDULER_ENABLED", "true").lower() in {"1", "true", "yes"},
            scheduler_poll_seconds=max(2, int(os.getenv("SCHEDULER_POLL_SECONDS", "15"))),
            allow_http_actions=os.getenv("ALLOW_HTTP_ACTIONS", "false").lower() in {"1", "true", "yes"},
            http_host_allowlist=allowlist,
        )
