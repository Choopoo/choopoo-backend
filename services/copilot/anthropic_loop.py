"""Anthropic SDK tool-use loop.

Iterates through the assistant's tool_use blocks, dispatches each via tools.call_tool,
and feeds the tool_result back to the model until it produces a final text response.

Disabled when ANTHROPIC_API_KEY is unset — caller falls back to stub_loop.
"""
from __future__ import annotations
import os
from typing import Any
import anthropic
from tools import TOOL_SCHEMAS, call_tool

MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-7")
MAX_TURNS = 14

SYSTEM_PROMPT = """\
You are Choopoo's procurement & GTM copilot for a Chinese PU SME owner.
You can compose business goals, enable catalog materials, create private materials,
override indicators, compose new indicators from formulas, and link indicators to goals.

Rules:
- Always check the catalog with search_catalog before creating a private entity.
- Be brief in your text responses — the owner is busy.
- After completing a task, confirm what you did in 1-2 sentences with concrete IDs.
- If the user is ambiguous, ask one focused clarifying question instead of guessing.
- Composite indicator formulas use {op, left, right} where left/right are
  either {indicator_code: "..."} or {scalar: <number>}.
"""


async def run(user_message: str, ctx: dict, history: list[dict] | None = None) -> dict:
    """Drive a multi-turn conversation with tool-use. Returns {text, tool_calls, history}."""
    client = anthropic.AsyncAnthropic()
    if history is None:
        history = []
    messages = list(history) + [{"role": "user", "content": user_message}]
    tool_calls: list[dict] = []

    for _ in range(MAX_TURNS):
        resp = await client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )
        # Append the assistant turn to messages.
        messages.append({"role": "assistant", "content": resp.content})

        # Find any tool_use blocks; if none, we're done.
        tool_use_blocks = [b for b in resp.content if getattr(b, "type", None) == "tool_use"]
        if not tool_use_blocks:
            text_blocks = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
            return {"text": "\n".join(text_blocks), "tool_calls": tool_calls, "history": messages}

        # Dispatch each tool call.
        tool_results: list[dict[str, Any]] = []
        for tu in tool_use_blocks:
            try:
                result = await call_tool(tu.name, dict(tu.input), ctx)
                tool_calls.append({"name": tu.name, "input": dict(tu.input), "result": result})
                tool_results.append({"type": "tool_result", "tool_use_id": tu.id, "content": str(result)})
            except Exception as e:
                tool_calls.append({"name": tu.name, "input": dict(tu.input), "error": str(e)})
                tool_results.append({"type": "tool_result", "tool_use_id": tu.id, "content": f"error: {e}", "is_error": True})

        messages.append({"role": "user", "content": tool_results})

    return {"text": "(reached max tool-use turns)", "tool_calls": tool_calls, "history": messages}
