"""Shared data types passed between Campus Customs agents and audit logging."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


class AgentRole(str, Enum):
    BOSS = "boss"
    INVENTORY = "inventory"
    ACCOUNTING = "accounting"
    FACILITIES = "facilities"
    CUSTOMER_SERVICE = "customer_service"


class AuditEvent(BaseModel):
    """One append-only event in the team audit trail."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    run_id: str
    agent: AgentRole
    step: int = Field(ge=0)
    event: str
    action: str
    input_summary: str = ""
    output_summary: str = ""
    delegated_to: Optional[AgentRole] = None
    model: str = "gpt-6-luna"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TeamRunResult(BaseModel):
    """Structured result returned by the top-level team loop."""

    run_id: str
    output: str
    rounds: int
    model: str = "gpt-6-luna"


class PaymentApprovalRequest(BaseModel):
    """A human-approved outgoing payment or purchase."""

    kind: Literal["invoice", "lease", "purchase"]
    ref_id: int = Field(gt=0)
    amount: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False)
    account: str = Field(default="checking", min_length=1, max_length=80)
    approved_by: str = Field(min_length=1, max_length=120)


@dataclass
class TeamDeps:
    """Runtime dependencies shared by every agent in one team run."""

    run_id: str
    agents: Dict[str, Any]
    audit_path: Any
    remaining_hops: int = 4
    max_model_requests: int = 8
    step_counter: list[int] = field(default_factory=lambda: [0])
    current_agent: AgentRole = AgentRole.BOSS

    def child(self, role: AgentRole) -> "TeamDeps":
        return replace(
            self,
            remaining_hops=self.remaining_hops - 1,
            current_agent=role,
        )

    def next_step(self) -> int:
        self.step_counter[0] += 1
        return self.step_counter[0]
