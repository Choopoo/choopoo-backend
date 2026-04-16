"""Stub tool-use loop — runs without ANTHROPIC_API_KEY.

Pattern-matches the user message to one or more tool calls. Crude on purpose:
the goal is to demo the *structural* path (tool-use loop, gateway dispatch,
RLS enforcement) without any LLM cost.

Recognised commands (case-insensitive):
  goal:<title> [lens=buy|sell|macro|mixed] [horizon=N]
       -> create_goal
  search:<kind>:<query>
       -> search_catalog where kind ∈ {material,product,indicator}
  enable:material:<id> [nickname=…]
       -> enable_catalog_material
  private:material:<code>:<name>
       -> create_private_material
  compose:<code>:<unit>:<formula_json>
       -> compose_indicator_formula  (subject_kind=raw_material default)
  link:<goal_id>:<catalog|tenant>:<indicator_id> [role=primary|driver|context]
       -> add_indicator_to_goal

Multiple commands separated by `;` are dispatched sequentially.
"""
from __future__ import annotations
import json
import re
from typing import Any
from tools import call_tool


async def run(user_message: str, ctx: dict, history=None) -> dict:
    history = list(history or [])
    tool_calls: list[dict] = []
    text_lines: list[str] = []

    for raw in user_message.split(";"):
        cmd = raw.strip()
        if not cmd:
            continue
        try:
            name, args = _parse(cmd)
            result = await call_tool(name, args, ctx)
            tool_calls.append({"name": name, "input": args, "result": result})
            text_lines.append(f"✓ {name} → {_one_line(result)}")
        except _StubError as e:
            text_lines.append(f"✗ {e}")
        except Exception as e:  # noqa: BLE001
            text_lines.append(f"✗ {cmd}: {e.__class__.__name__}: {e}")

    if not tool_calls:
        text_lines.append(
            "stub mode — try `goal:Watch TDI lens=buy` or `search:material:TDI`. "
            "Set ANTHROPIC_API_KEY for natural-language."
        )

    return {"text": "\n".join(text_lines), "tool_calls": tool_calls, "history": history}


class _StubError(Exception):
    pass


def _one_line(obj: Any) -> str:
    s = json.dumps(obj, ensure_ascii=False)
    return (s[:140] + "…") if len(s) > 140 else s


def _parse(cmd: str) -> tuple[str, dict]:
    head, _, rest = cmd.partition(":")
    head = head.strip().lower()
    rest = rest.strip()

    if head == "goal":
        # title + optional kv pairs separated by spaces (lens=…, horizon=…)
        parts = rest.split()
        title_parts: list[str] = []
        opts: dict[str, str] = {}
        for p in parts:
            if "=" in p:
                k, _, v = p.partition("=")
                opts[k.lower()] = v
            else:
                title_parts.append(p)
        title = " ".join(title_parts) or "Untitled goal"
        args = {"title": title, "lens": opts.get("lens", "buy")}
        if "horizon" in opts:
            args["horizon_days"] = int(opts["horizon"])
        return "create_goal", args

    if head == "search":
        kind, _, query = rest.partition(":")
        if not query:
            raise _StubError("search:<kind>:<query>")
        return "search_catalog", {"kind": kind.strip(), "query": query.strip()}

    if head == "enable":
        sub, _, args_str = rest.partition(":")
        if sub.strip() != "material":
            raise _StubError("enable:material:<id> [nickname=...]")
        m = re.match(r"(\d+)(?:\s+nickname=(.+))?", args_str.strip())
        if not m:
            raise _StubError("enable:material:<id> [nickname=...]")
        out: dict[str, Any] = {"catalog_raw_material_id": int(m.group(1))}
        if m.group(2):
            out["nickname"] = m.group(2)
        return "enable_catalog_material", out

    if head == "private":
        sub, _, args_str = rest.partition(":")
        if sub.strip() != "material":
            raise _StubError("private:material:<code>:<name>")
        code, _, name = args_str.partition(":")
        if not code or not name:
            raise _StubError("private:material:<code>:<name>")
        return "create_private_material", {"code": code.strip().upper(), "name": name.strip()}

    if head == "compose":
        # compose:<code>:<unit>:<formula_json>
        code, _, rem = rest.partition(":")
        unit, _, formula = rem.partition(":")
        if not code or not unit or not formula:
            raise _StubError("compose:<code>:<unit>:<formula_json>")
        return "compose_indicator_formula", {
            "code": code.strip().upper(),
            "subject_kind": "raw_material",
            "unit": unit.strip(),
            "formula_json": json.loads(formula.strip()),
        }

    if head == "link":
        # link:<goal_id>:<catalog|tenant>:<indicator_id> [role=...]
        parts = rest.split()
        if not parts:
            raise _StubError("link:<goal_id>:<kind>:<indicator_id> [role=...]")
        head_part = parts[0]
        opts = {p.split("=", 1)[0]: p.split("=", 1)[1] for p in parts[1:] if "=" in p}
        gid, kind, ind = head_part.split(":")
        return "add_indicator_to_goal", {
            "goal_id": int(gid),
            "indicator_kind": kind.strip(),
            "indicator_id": int(ind),
            "role": opts.get("role", "driver"),
        }

    raise _StubError(f"unknown stub command: {head}")
