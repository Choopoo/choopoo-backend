"""Tool definitions exposed to the LLM.

Each tool maps to a gateway endpoint. The dispatcher (`call_tool`) makes the
HTTP request to the gateway using the per-conversation service headers so RLS
is enforced as if the user themselves were calling.

Add a new tool:
1. Add a JSON-schema entry to TOOL_SCHEMAS
2. Add the corresponding (method, path, body-builder) to TOOL_DISPATCH
"""
from __future__ import annotations
import os
from typing import Any
import httpx

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://gateway:8080")
SERVICE_SECRET = os.getenv("SERVICE_SECRET", "")

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "search_catalog",
        "description": "Search the global catalog for raw materials, finished products, or indicator templates by free-text query. Use this BEFORE create_private_* if the user mentions something that might already exist (e.g. 'TDI', 'caprolactam').",
        "input_schema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["material", "product", "indicator"]},
                "query": {"type": "string", "description": "Free-text query to substring-match against code, name, or name_cn"},
            },
            "required": ["kind", "query"],
        },
    },
    {
        "name": "create_goal",
        "description": "Create a new business goal for the owner.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "lens": {"type": "string", "enum": ["buy", "sell", "macro", "mixed"]},
                "horizon_days": {"type": "integer"},
            },
            "required": ["title", "lens"],
        },
    },
    {
        "name": "enable_catalog_material",
        "description": "Enable a catalog raw material for this tenant. Use this when the user wants to start tracking something already in the catalog.",
        "input_schema": {
            "type": "object",
            "properties": {
                "catalog_raw_material_id": {"type": "integer"},
                "nickname": {"type": "string", "description": "Optional local rename for this material"},
            },
            "required": ["catalog_raw_material_id"],
        },
    },
    {
        "name": "create_private_material",
        "description": "Create a NEW private raw material specific to this tenant. Use only after search_catalog returns no match.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "name": {"type": "string"},
                "name_cn": {"type": "string"},
                "unit": {"type": "string", "default": "CNY/ton"},
                "category": {"type": "string"},
            },
            "required": ["code", "name"],
        },
    },
    {
        "name": "compose_indicator_formula",
        "description": "Create a new private composite indicator from a JSON formula expression. Operators: subtract, add, divide, multiply. Operands are {indicator_code: '...'} or scalars.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "subject_kind": {"type": "string", "enum": ["raw_material", "finished_product", "region", "macro_series"]},
                "unit": {"type": "string"},
                "formula_json": {"type": "object"},
                "description": {"type": "string"},
            },
            "required": ["code", "subject_kind", "unit", "formula_json"],
        },
    },
    {
        "name": "add_indicator_to_goal",
        "description": "Link an indicator to an existing goal so the owner sees it on the goal's drill page.",
        "input_schema": {
            "type": "object",
            "properties": {
                "goal_id": {"type": "integer"},
                "indicator_kind": {"type": "string", "enum": ["catalog", "tenant"]},
                "indicator_id": {"type": "integer"},
                "role": {"type": "string", "enum": ["primary", "driver", "context"], "default": "driver"},
            },
            "required": ["goal_id", "indicator_kind", "indicator_id"],
        },
    },
]


def _service_headers(ctx: dict) -> dict[str, str]:
    """Build the X-Service-* headers gateway uses for trust + identity."""
    return {
        "X-Service-Secret": SERVICE_SECRET,
        "X-Org-Id": str(ctx["org_id"]),
        "X-User-Id": str(ctx["user_id"]),
        "X-User-Role": ctx.get("role", "owner"),
        "Content-Type": "application/json",
    }


async def call_tool(name: str, args: dict, ctx: dict) -> dict:
    """Dispatch a tool call to the gateway HTTP API. Returns the parsed JSON."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        if name == "search_catalog":
            kind = args["kind"]
            query = args["query"].lower()
            path_map = {
                "material": "/api/v2/catalog/materials",
                "product": "/api/v2/catalog/products",
                "indicator": "/api/v2/catalog/indicators",
            }
            r = await client.get(GATEWAY_URL + path_map[kind], headers=_service_headers(ctx))
            r.raise_for_status()
            rows = r.json()
            # Substring filter on code/name/name_cn — keep concise; surface top 10.
            def matches(row):
                hay = " ".join(
                    str(row.get(k, "") or "") for k in ("code", "name", "name_cn", "description")
                ).lower()
                return query in hay
            return {"matches": [r for r in rows if matches(r)][:10]}

        if name == "create_goal":
            r = await client.post(
                GATEWAY_URL + "/api/v2/goals",
                json={"title": args["title"], "lens": args["lens"], "horizon_days": args.get("horizon_days")},
                headers=_service_headers(ctx),
            )
            r.raise_for_status()
            return r.json()

        if name == "enable_catalog_material":
            body = {"catalog_raw_material_id": args["catalog_raw_material_id"]}
            if args.get("nickname"):
                body["nickname"] = args["nickname"]
            r = await client.post(GATEWAY_URL + "/api/v2/tenant/materials/enable", json=body, headers=_service_headers(ctx))
            r.raise_for_status()
            return r.json()

        if name == "create_private_material":
            body = {k: v for k, v in args.items() if v is not None}
            r = await client.post(GATEWAY_URL + "/api/v2/tenant/materials", json=body, headers=_service_headers(ctx))
            r.raise_for_status()
            return r.json()

        if name == "compose_indicator_formula":
            body = {
                "code": args["code"],
                "kind": "derived",
                "subject_kind": args["subject_kind"],
                "unit": args["unit"],
                "formula_json": args["formula_json"],
            }
            if args.get("description"):
                body["description"] = args["description"]
            r = await client.post(GATEWAY_URL + "/api/v2/tenant/indicators", json=body, headers=_service_headers(ctx))
            r.raise_for_status()
            return r.json()

        if name == "add_indicator_to_goal":
            goal_id = args["goal_id"]
            body = {
                "indicator_kind": args["indicator_kind"],
                "indicator_id": args["indicator_id"],
                "role": args.get("role", "driver"),
            }
            r = await client.post(GATEWAY_URL + f"/api/v2/goals/{goal_id}/indicators", json=body, headers=_service_headers(ctx))
            r.raise_for_status()
            return r.json()

        return {"error": f"unknown tool: {name}"}
