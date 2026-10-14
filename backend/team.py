"""Build and run the fully connected Campus Customs agent team."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic_ai import Agent, RunContext, UsageLimits

from .accounting import build_accounting_agent
from .audit import DEFAULT_AUDIT_PATH, record_event, summarize
from .boss import build_boss_agent
from .customer_service import build_customer_service_agent
from .facilities import build_facilities_agent
from .inventory import build_inventory_agent
from .models import AgentRole, TeamDeps, TeamRunResult
from .runtime import MODEL_NAME, build_mcp_toolset, build_model


async def _delegate(ctx: RunContext[TeamDeps], target: AgentRole, task: str) -> str:
    """Run another role while retaining the same audit trail and MCP toolset."""
    deps = ctx.deps
    if target == deps.current_agent:
        return "Do not delegate to yourself; continue with the evidence already collected."
    if deps.remaining_hops <= 0:
        return "Delegation limit reached; answer using the evidence already collected."
    agent = deps.agents.get(target.value)
    if agent is None:
        return f"The {target.value} agent is unavailable."

    start_step = deps.next_step()
    record_event(
        run_id=deps.run_id,
        agent=deps.current_agent,
        step=start_step,
        event="delegation_start",
        action="delegate",
        input_value=task,
        delegated_to=target,
        path=deps.audit_path,
    )
    try:
        child_result = await agent.run(
            task,
            deps=deps.child(target),
            usage_limits=_usage_limits(deps),
        )
        output = str(child_result.output)
        end_step = deps.next_step()
        record_event(
            run_id=deps.run_id,
            agent=deps.current_agent,
            step=end_step,
            event="delegation_complete",
            action="delegate",
            input_value=task,
            output_value=output,
            delegated_to=target,
            path=deps.audit_path,
        )
        return output
    except Exception as exc:
        end_step = deps.next_step()
        record_event(
            run_id=deps.run_id,
            agent=deps.current_agent,
            step=end_step,
            event="delegation_error",
            action="delegate",
            input_value=task,
            output_value=repr(exc),
            delegated_to=target,
            path=deps.audit_path,
        )
        raise


async def delegate_to_inventory(ctx: RunContext[TeamDeps], task: str) -> str:
    """Ask Inventory to investigate stock, replenishment, or vendor shipping."""
    return await _delegate(ctx, AgentRole.INVENTORY, task)


async def delegate_to_boss(ctx: RunContext[TeamDeps], task: str) -> str:
    """Escalate an unresolved decision or conflict to Boss."""
    return await _delegate(ctx, AgentRole.BOSS, task)


async def delegate_to_accounting(ctx: RunContext[TeamDeps], task: str) -> str:
    """Ask Accounting to investigate cash, invoices, leases, or payment readiness."""
    return await _delegate(ctx, AgentRole.ACCOUNTING, task)


async def delegate_to_facilities(ctx: RunContext[TeamDeps], task: str) -> str:
    """Ask Facilities to investigate the lease, rent timing, or shop space."""
    return await _delegate(ctx, AgentRole.FACILITIES, task)


async def delegate_to_customer_service(ctx: RunContext[TeamDeps], task: str) -> str:
    """Ask Customer Service to prepare a board-only customer or organization draft."""
    return await _delegate(ctx, AgentRole.CUSTOMER_SERVICE, task)


DELEGATION_TOOLS = [
    delegate_to_boss,
    delegate_to_inventory,
    delegate_to_accounting,
    delegate_to_facilities,
    delegate_to_customer_service,
]


def _usage_limits(deps: TeamDeps) -> UsageLimits:
    """Apply request and token ceilings to every model call in the team."""
    return UsageLimits(
        request_limit=deps.max_model_requests,
        input_tokens_limit=12000,
        output_tokens_limit=4000,
        total_tokens_limit=16000,
    )


@dataclass
class AgentTeam:
    """Five connected agents sharing one model, MCP toolset, and audit trail."""

    agents: dict[str, Agent[Any, str]]
    toolset: Any
    model: Any
    audit_path: Path = DEFAULT_AUDIT_PATH
    model_name: str = MODEL_NAME

    @property
    def boss(self) -> Agent[Any, str]:
        return self.agents[AgentRole.BOSS.value]

    async def run(self, objective: str, *, max_rounds: int = 3, max_hops: int = 4) -> TeamRunResult:
        """Run a bounded Boss loop; each round may delegate to any specialist."""
        if not 1 <= max_rounds <= 3:
            raise ValueError("max_rounds must be between 1 and 3")
        if not 0 <= max_hops <= 6:
            raise ValueError("max_hops must be between 0 and 6")

        run_id = str(uuid4())
        deps = TeamDeps(
            run_id=run_id,
            agents=self.agents,
            audit_path=self.audit_path,
            remaining_hops=max_hops,
            current_agent=AgentRole.BOSS,
        )
        prompt = objective
        output = ""
        rounds_completed = 0
        for round_number in range(1, max_rounds + 1):
            rounds_completed = round_number
            loop_step = deps.next_step()
            record_event(
                run_id=run_id,
                agent=AgentRole.BOSS,
                step=loop_step,
                event="loop_start",
                action=f"boss_round_{round_number}",
                input_value=prompt,
                path=self.audit_path,
            )
            try:
                result = await self.boss.run(
                    prompt,
                    deps=deps,
                    usage_limits=_usage_limits(deps),
                )
                output = str(result.output)
            except Exception as exc:
                record_event(
                    run_id=run_id,
                    agent=AgentRole.BOSS,
                    step=deps.next_step(),
                    event="loop_error",
                    action=f"boss_round_{round_number}",
                    input_value=prompt,
                    output_value=repr(exc),
                    path=self.audit_path,
                )
                raise

            record_event(
                run_id=run_id,
                agent=AgentRole.BOSS,
                step=deps.next_step(),
                event="loop_complete",
                action=f"boss_round_{round_number}",
                input_value=prompt,
                output_value=output,
                path=self.audit_path,
            )
            if "NO FURTHER DELEGATION" in output.upper() or "RESOLUTION COMPLETE" in output.upper():
                break
            prompt = (
                "Continue the bounded review of the same objective. Reconcile this prior Boss report "
                "with fresh MCP evidence, delegate only unresolved questions, and end with a clear plan:\n\n"
                + summarize(output)
            )

        return TeamRunResult(run_id=run_id, output=output, rounds=rounds_completed)


def build_team() -> AgentTeam:
    """Construct all five roles with the same gpt-6-luna model and MCP server."""
    model = build_model()
    toolset = build_mcp_toolset()
    agents: dict[str, Agent[Any, str]] = {}
    agents[AgentRole.BOSS.value] = build_boss_agent(model, toolset, DELEGATION_TOOLS)
    agents[AgentRole.INVENTORY.value] = build_inventory_agent(model, toolset, DELEGATION_TOOLS)
    agents[AgentRole.ACCOUNTING.value] = build_accounting_agent(model, toolset, DELEGATION_TOOLS)
    agents[AgentRole.FACILITIES.value] = build_facilities_agent(model, toolset, DELEGATION_TOOLS)
    agents[AgentRole.CUSTOMER_SERVICE.value] = build_customer_service_agent(model, toolset, DELEGATION_TOOLS)
    return AgentTeam(agents=agents, toolset=toolset, model=model)
