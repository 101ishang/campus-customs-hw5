"""Append-only audit trail support for agent loops and MCP calls."""

from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Lock
from typing import Any, Mapping, Optional

from .models import AgentRole, AuditEvent


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT_PATH = PROJECT_ROOT / "output" / "audit_trail.json"
_AUDIT_LOCK = Lock()


def summarize(value: Any, limit: int = 2000) -> str:
    """Return bounded text suitable for an audit record without exposing secrets."""
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, sort_keys=True, default=str)
        except TypeError:
            text = repr(value)
    return text if len(text) <= limit else text[:limit] + "…"


def append_audit_event(event: AuditEvent, path: Optional[Path] = None) -> None:
    """Append one event while preserving every prior event in the JSON array."""
    target = path or DEFAULT_AUDIT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with _AUDIT_LOCK:
        if target.exists():
            raw = target.read_text(encoding="utf-8").strip()
            existing = json.loads(raw) if raw else []
            if not isinstance(existing, list):
                raise ValueError(f"Audit trail must contain a JSON list: {target}")
        else:
            existing = []
        existing.append(event.model_dump(mode="json"))
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, target)


def record_event(
    *,
    run_id: str,
    agent: AgentRole,
    step: int,
    event: str,
    action: str,
    input_value: Any = "",
    output_value: Any = "",
    delegated_to: Optional[AgentRole] = None,
    metadata: Optional[Mapping[str, Any]] = None,
    path: Optional[Path] = None,
) -> None:
    append_audit_event(
        AuditEvent(
            run_id=run_id,
            agent=agent,
            step=step,
            event=event,
            action=action,
            input_summary=summarize(input_value),
            output_summary=summarize(output_value),
            delegated_to=delegated_to,
            metadata=dict(metadata or {}),
        ),
        path=path,
    )
