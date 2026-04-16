"""Thin HTTP client that calls back into the gateway using the service-secret
auth path. Every call carries X-Org-Id / X-User-Id / X-User-Role so gateway's
resolveSession middleware sets app.org_id and RLS is enforced per row.
"""
from __future__ import annotations
import os
import httpx

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://gateway:8080")
SERVICE_SECRET = os.getenv("SERVICE_SECRET", "")


def _headers(ctx: dict) -> dict:
    return {
        "X-Service-Secret": SERVICE_SECRET,
        "X-Org-Id": str(ctx["org_id"]),
        "X-User-Id": str(ctx["user_id"]),
        "X-User-Role": ctx.get("role", "owner"),
        "Content-Type": "application/json",
    }


class Gateway:
    def __init__(self, client: httpx.Client | None = None):
        self._client = client or httpx.Client(timeout=15.0)

    def catalog_materials(self, ctx) -> list[dict]:
        r = self._client.get(GATEWAY_URL + "/api/v2/catalog/materials", headers=_headers(ctx))
        r.raise_for_status()
        return r.json()

    def catalog_indicators(self, ctx) -> list[dict]:
        r = self._client.get(GATEWAY_URL + "/api/v2/catalog/indicators", headers=_headers(ctx))
        r.raise_for_status()
        return r.json()

    def enable_catalog_material(self, ctx, catalog_id: int, nickname: str | None = None) -> dict:
        body = {"catalog_raw_material_id": catalog_id}
        if nickname:
            body["nickname"] = nickname
        r = self._client.post(GATEWAY_URL + "/api/v2/tenant/materials/enable", json=body, headers=_headers(ctx))
        r.raise_for_status()
        return r.json()

    def create_private_material(self, ctx, code: str, name: str, name_cn: str | None = None,
                                unit: str = "CNY/ton", category: str | None = None) -> dict:
        body = {"code": code, "name": name, "unit": unit}
        if name_cn:
            body["name_cn"] = name_cn
        if category:
            body["category"] = category
        r = self._client.post(GATEWAY_URL + "/api/v2/tenant/materials", json=body, headers=_headers(ctx))
        r.raise_for_status()
        return r.json()

    def enable_catalog_indicator(self, ctx, template_id: int, role: str | None = None) -> dict:
        body = {"catalog_indicator_template_id": template_id}
        if role:
            body["role"] = role
        r = self._client.post(GATEWAY_URL + "/api/v2/tenant/indicators/enable", json=body, headers=_headers(ctx))
        r.raise_for_status()
        return r.json()

    def add_indicator_to_goal(self, ctx, goal_id: int, indicator_kind: str, indicator_id: int, role: str = "driver") -> dict:
        body = {"indicator_kind": indicator_kind, "indicator_id": indicator_id, "role": role}
        r = self._client.post(GATEWAY_URL + f"/api/v2/goals/{goal_id}/indicators", json=body, headers=_headers(ctx))
        r.raise_for_status()
        return r.json()

    def create_insight(self, ctx, *, goal_id: int, kind: str, title: str, body_md: str,
                       ai_model: str | None = None, evidence: list[dict] | None = None) -> dict:
        body = {"goal_id": goal_id, "kind": kind, "title": title, "body_md": body_md}
        if ai_model:
            body["ai_model"] = ai_model
        if evidence:
            body["evidence"] = evidence
        r = self._client.post(GATEWAY_URL + "/api/v2/insights", json=body, headers=_headers(ctx))
        r.raise_for_status()
        return r.json()
