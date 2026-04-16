"""Goal-to-Data autopilot saga.

When a goal.created.v1 event arrives:
  1. plan the saga (extract material entities from the goal title)
  2. for each extracted entity:
       a. search catalog
       b. if found -> enable; if not -> create private
       c. find the default spot indicator for the subject; enable + link to goal
  3. compose a first-pass briefing insight with citations
  4. mark workflow_run as succeeded

If any step fails permanently, mark workflow_run.state='failed' and write
a short error into the steps_log. Compensation for v1 is "leave partially-
attached indicators" — acceptable because everything is additive.

Planning uses a simple regex extractor from the title. Real LLM planning is
a later drop-in — the step shape is unchanged.
"""
from __future__ import annotations
import json
import logging
import re
import time
from typing import Any

import psycopg2
import psycopg2.extras

from gateway_client import Gateway

log = logging.getLogger("saga")

# Known entity aliases so the extractor can find even casual mentions.
# Keyed by canonical catalog code; values are case-insensitive substrings.
KNOWN_ENTITIES: dict[str, list[str]] = {
    "TDI": ["tdi", "toluene diisocyanate"],
    "MDI": ["mdi"],
    "HDI": ["hdi"],
    "IPDI": ["ipdi"],
    "TOLUENE": ["toluene", "甲苯"],
    "PHENOL": ["phenol", "苯酚"],
    "BAC": ["butyl acetate", "醋酸丁酯"],
    "PPG_2000": ["ppg", "polyol", "多元醇"],
    "DBTDL": ["dbtdl", "tin catalyst", "二月桂"],
    "BRENT": ["brent", "crude"],
}

# Fallback "probably a material but not in our seed" extractor — single-token
# uppercase-ish words of length 4-15 that aren't obvious English verbs.
CANDIDATE_RE = re.compile(r"\b([A-Z][A-Za-z0-9]{3,15})\b")


def extract_entities(title: str) -> list[dict]:
    """Return list of {code, kind} where kind in {catalog, private}."""
    t = title.lower()
    found = []
    for code, aliases in KNOWN_ENTITIES.items():
        for a in aliases:
            if a in t:
                found.append({"code": code, "kind": "catalog", "evidence": a})
                break
    if found:
        return found
    # Fallback: try uppercase-like tokens. Used for things like "caprolactam"
    # that aren't in the catalog but are clearly material names.
    tokens = CANDIDATE_RE.findall(title)
    ignore = {"The", "This", "That", "With", "Watch", "Track", "Manage", "Supply", "Risk", "Demand", "Cost", "Lens"}
    tokens = [t for t in tokens if t not in ignore]
    return [{"code": t.upper(), "kind": "private", "evidence": t} for t in tokens[:2]]


def run_saga(db_conn, gateway: Gateway, event: dict) -> None:
    """Execute the Goal-to-Data autopilot saga for a goal.created event.

    event payload: {goal_id, title, lens, horizon_days, user_id}
    event header:  X-Org-Id identifies the tenant.
    """
    org_id = event["_org_id"]
    payload = event["payload"]
    goal_id = payload["goal_id"]
    title = payload.get("title", "")
    user_id = payload.get("user_id", 0)
    ctx = {"org_id": org_id, "user_id": user_id, "role": "owner"}

    # Step 0: create a workflow_runs row under this tenant's context.
    run_id = _create_workflow_run(db_conn, org_id, goal_id, title)

    steps_log: list[dict] = []
    try:
        # Plan
        entities = extract_entities(title)
        plan = {"entities": entities, "lens": payload.get("lens")}
        _update_run(db_conn, run_id, state="running", plan=plan)
        log.info("[run %s] planned: %s", run_id, plan)

        if not entities:
            raise RuntimeError("no raw-material entities extracted from title")

        # Fetch catalog once; subsequent lookups are O(1).
        catalog = {m["code"]: m for m in gateway.catalog_materials(ctx)}
        catalog_indicators = gateway.catalog_indicators(ctx)
        ind_by_subject: dict[str, list[dict]] = {}
        for ind in catalog_indicators:
            key = ind.get("subject_code") or ""
            ind_by_subject.setdefault(key, []).append(ind)

        attached_indicator_codes: list[str] = []
        attached_materials: list[dict] = []

        for i, ent in enumerate(entities):
            step = {"n": i + 1, "entity": ent, "actions": []}
            try:
                if ent["kind"] == "catalog" and ent["code"] in catalog:
                    cat_mat = catalog[ent["code"]]
                    gateway.enable_catalog_material(ctx, cat_mat["id"], nickname=None)
                    step["actions"].append({"enable_catalog_material": cat_mat["code"]})
                    attached_materials.append({"source": "catalog", **cat_mat})
                else:
                    # Private: create a placeholder material so the goal has something
                    # concrete to show. Real autopilot would also schedule a crawl here.
                    res = gateway.create_private_material(
                        ctx,
                        code=ent["code"],
                        name=ent["code"].title(),
                        category="macro",
                    )
                    step["actions"].append({"create_private_material": ent["code"], "id": res["id"]})
                    attached_materials.append({"source": "private", "code": ent["code"], "id": res["id"]})

                # Find a primary spot indicator for this subject, enable it + link to goal.
                candidates = ind_by_subject.get(ent["code"], [])
                spot_candidates = [c for c in candidates if c.get("kind") == "price"]
                if spot_candidates:
                    ind = spot_candidates[0]
                    gateway.enable_catalog_indicator(ctx, ind["id"], role="primary")
                    gateway.add_indicator_to_goal(ctx, goal_id, indicator_kind="catalog", indicator_id=ind["id"], role="primary")
                    attached_indicator_codes.append(ind["code"])
                    step["actions"].append({"link_indicator": ind["code"]})

                # Also attach the subject-level spread if available (e.g. TDI_TOLUENE_SPREAD).
                spread_candidates = [c for c in candidates if c.get("kind") in ("spread", "derived")]
                if spread_candidates:
                    ind = spread_candidates[0]
                    gateway.enable_catalog_indicator(ctx, ind["id"], role="driver")
                    gateway.add_indicator_to_goal(ctx, goal_id, indicator_kind="catalog", indicator_id=ind["id"], role="driver")
                    attached_indicator_codes.append(ind["code"])
                    step["actions"].append({"link_spread": ind["code"]})

                step["status"] = "ok"
            except Exception as e:  # noqa: BLE001
                step["status"] = "error"
                step["error"] = str(e)
                log.warning("[run %s] step %s failed: %s", run_id, i + 1, e)
            steps_log.append(step)
            _update_run(db_conn, run_id, current_step=i + 1, steps_log=steps_log)

        # Final step: write a SETUP-EVENT insight (kind=event) — this is an audit
        # receipt, NOT a market briefing. The summariser/forecaster produce the
        # real briefing+alert insights later, as data flows in.
        if attached_indicator_codes:
            body = _compose_setup_body(title, attached_materials, attached_indicator_codes)
            evidence = [
                {
                    "kind": "catalog_indicator",
                    "catalog_indicator_id": _find_indicator_id(catalog_indicators, code),
                    "weight": 1.0 / len(attached_indicator_codes),
                }
                for code in attached_indicator_codes
                if _find_indicator_id(catalog_indicators, code) is not None
            ]
            primary_subject = (attached_materials[0]["code"] if attached_materials else "goal")
            gateway.create_insight(
                ctx,
                goal_id=goal_id,
                kind="event",
                title=f"Autopilot setup · {primary_subject}",
                body_md=body,
                ai_model="autopilot:stub",
                evidence=evidence,
            )
            steps_log.append({"n": len(steps_log) + 1, "briefing": "created"})
        else:
            steps_log.append({"n": len(steps_log) + 1, "briefing": "skipped: no indicators attached"})

        _update_run(db_conn, run_id, state="succeeded", steps_log=steps_log, completed=True)
        log.info("[run %s] succeeded", run_id)

    except Exception as e:  # noqa: BLE001
        log.exception("[run %s] failed", run_id)
        steps_log.append({"error": str(e)})
        _update_run(db_conn, run_id, state="failed", error=str(e), steps_log=steps_log, completed=True)


def _compose_setup_body(title: str, materials: list[dict], indicator_codes: list[str]) -> str:
    lines = [
        f"Autopilot parsed *\"{title}\"* and set up the goal.",
        "",
        "**Materials attached:**",
    ]
    for m in materials:
        lines.append(f"- `{m['code']}` ({m['source']})")
    lines.append("")
    lines.append("**Indicators now driving this goal:**")
    for c in indicator_codes:
        lines.append(f"- `{c}`")
    lines.append("")
    lines.append("Readings will flow in as the pipeline ingests sources. You can add or drop indicators anytime via the copilot.")
    return "\n".join(lines)


def _find_indicator_id(indicators: list[dict], code: str) -> int | None:
    for ind in indicators:
        if ind.get("code") == code:
            return ind["id"]
    return None


def _create_workflow_run(conn, org_id: int, goal_id: int, title: str) -> int:
    """Insert a workflow_runs row via the BYPASSRLS pipeline connection, but
    scoped to org_id via explicit column. Reads from tenants still go through RLS."""
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO workflow_runs (org_id, kind, subject_ref, state)
               VALUES (%s, 'goal_to_data', %s::jsonb, 'planning')
               RETURNING id""",
            (org_id, json.dumps({"goal_id": goal_id, "title": title})),
        )
        run_id = cur.fetchone()[0]
    conn.commit()
    return run_id


def _update_run(
    conn,
    run_id: int,
    *,
    state: str | None = None,
    plan: Any | None = None,
    current_step: int | None = None,
    steps_log: list | None = None,
    error: str | None = None,
    completed: bool = False,
):
    fields: list[str] = []
    args: list[Any] = []
    if state is not None:
        fields.append("state = %s")
        args.append(state)
    if plan is not None:
        fields.append("plan = %s::jsonb")
        args.append(json.dumps(plan))
    if current_step is not None:
        fields.append("current_step = %s")
        args.append(current_step)
    if steps_log is not None:
        fields.append("steps_log = %s::jsonb")
        args.append(json.dumps(steps_log))
    if error is not None:
        fields.append("error = %s")
        args.append(error)
    if completed:
        fields.append("completed_at = NOW()")
    if not fields:
        return
    args.append(run_id)
    with conn.cursor() as cur:
        cur.execute(f"UPDATE workflow_runs SET {', '.join(fields)} WHERE id = %s", args)
    conn.commit()


def sleep_ms(ms: int):
    time.sleep(ms / 1000.0)
