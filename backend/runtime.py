"""Shared PydanticAI model, prompt, and MCP wiring."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic_ai import RunContext
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from .audit import record_event, summarize
from .models import TeamDeps


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
MODEL_NAME = "gpt-6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"


def load_prompt(role: str) -> str:
    return (PROMPT_DIR / f"{role}.md").read_text(encoding="utf-8")


def build_model() -> OpenAIChatModel:
    """Build the sole allowed model through Portkey's OpenAI-compatible endpoint."""
    api_key = os.getenv("PORTKEY_API_KEY")
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY must be set before running the agent team")

    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=api_key,
        base_url=PORTKEY_BASE_URL,
        default_headers={"x-portkey-api-key": api_key},
    )
    provider = OpenAIProvider(openai_client=client)
    # Portkey's gpt-6-luna chat endpoint accepts function tools only when
    # reasoning is explicitly disabled. Keep the required model while avoiding
    # the unsupported default reasoning parameter in the OpenAI-compatible API.
    return OpenAIChatModel(
        MODEL_NAME,
        provider=provider,
        settings={"openai_reasoning_effort": "none"},
    )


async def audit_mcp_call(
    ctx: RunContext[TeamDeps],
    call_tool: Any,
    tool_name: str,
    tool_args: dict[str, Any],
) -> Any:
    """Audit and then execute every MCP call; no database access happens here."""
    deps = ctx.deps
    step = deps.next_step()
    record_event(
        run_id=deps.run_id,
        agent=deps.current_agent,
        step=step,
        event="mcp_call_start",
        action=tool_name,
        input_value=tool_args,
        path=deps.audit_path,
    )
    result = await call_tool(tool_name, tool_args)
    step = deps.next_step()
    record_event(
        run_id=deps.run_id,
        agent=deps.current_agent,
        step=step,
        event="mcp_call_complete",
        action=tool_name,
        input_value=tool_args,
        output_value=summarize(result),
        path=deps.audit_path,
    )
    return result


def build_mcp_toolset() -> MCPToolset:
    """Expose the existing FastMCP server directly to PydanticAI agents."""
    return MCPToolset(
        str(PROJECT_ROOT / "mcp_server" / "server.py"),
        process_tool_call=audit_mcp_call,
        tool_error_behavior="error",
        include_return_schema=True,
    )
