"""Accounting agent factory."""

from collections.abc import Sequence
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.mcp import MCPToolset

from .models import TeamDeps
from .runtime import load_prompt


def build_accounting_agent(model: Any, toolset: MCPToolset, delegation_tools: Sequence[Any]) -> Agent[TeamDeps, str]:
    return Agent(
        model=model,
        name="accounting",
        deps_type=TeamDeps,
        instructions=load_prompt("accounting"),
        tools=list(delegation_tools),
        toolsets=[toolset],
        retries=1,
    )
