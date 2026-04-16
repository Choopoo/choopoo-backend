"""Event extractor service.

Scans newly-crawled `pages` rows for supply-event keywords (maintenance,
shutdown, force majeure, 检修, 装置, 停车 …) and writes `kind=event` insights to
every (org, goal) that has the matched material linked.

v1 is rule-based regex matching. v2 would pass the page body to an LLM for
NER (plant name, event type, start/end dates, confidence).

Writes via the gateway service-secret path so RLS stays enforced.
No Kafka — polls `pages` since the last processed id.
"""
from __future__ import annotations
import logging
import os
import re
import time
import traceback

import httpx
import psycopg2
import psycopg2.extras

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("event-extractor")

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://gateway:8080")
SERVICE_SECRET = os.getenv("SERVICE_SECRET", "")
INTERVAL = int(os.getenv("EVENT_INTERVAL", "60"))

DSN = (
    f"host={os.getenv('DB_HOST','postgres')} port={os.getenv('DB_PORT','5432')} "
    f"user={os.getenv('DB_USER','pipeline')} password={os.getenv('DB_PASSWORD','pipeline')} "
    f"dbname={os.getenv('DB_NAME','pipeline')}"
)

# Supply-event lexicon. Categorised so insight body can describe WHICH kind.
LEXICON = {
    "maintenance": [r"\bmaintenance\b", r"\bturnaround\b", r"\bshutdown\b", r"\bshut-down\b",
                    r"检修", r"停车", r"装置动态", r"装置检修"],
    "force_majeure": [r"force\s+majeure", r"\bFM\b", r"不可抗力"],
    "explosion_fire": [r"\bexplosion\b", r"\bfire\b", r"\bleak\b", r"爆炸", r"火灾", r"泄漏"],
    "restart": [r"\brestart\b", r"\brestarting\b", r"back\s+online", r"重启", r"复产"],
    "regulation": [r"\bban\b", r"\btariff\b", r"\bsanction\b", r"关税", r"禁令", r"制裁"],
}
COMPILED = {k: re.compile("|".join(v), re.IGNORECASE) for k, v in LEXICON.items()}


def _headers(org_id: int) -> dict:
    return {
        "X-Service-Secret": SERVICE_SECRET,
        "X-Org-Id": str(org_id),
        "X-User-Id": "0",
        "X-User-Role": "owner",
        "Content-Type": "application/json",
    }


def classify(text: str) -> tuple[str, str] | None:
    """Return (category, excerpt) of the first matching keyword, or None."""
    for category, regex in COMPILED.items():
        m = regex.search(text)
        if m:
            start = max(0, m.start() - 40)
            end = min(len(text), m.end() + 60)
            excerpt = text[start:end].replace("\n", " ").strip()
            return category, excerpt
    return None


def fetch_new_pages(conn, since: int) -> list[dict]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT id, url, domain, title, meta_description, material, org_id
              FROM pages
             WHERE id > %s
               AND (title IS NOT NULL OR meta_description IS NOT NULL)
             ORDER BY id
             LIMIT 200
        """, (since,))
        return [dict(r) for r in cur.fetchall()]


def find_goals_for_material(conn, material_code: str) -> list[dict]:
    """All (org, goal) pairs that have `material_code`'s primary spot indicator linked."""
    spot_code = material_spot_code(material_code)
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT gil.org_id, gil.goal_id, g.title
              FROM goal_indicator_links gil
              JOIN goals g ON g.id = gil.goal_id
              JOIN catalog_indicator_template cit
                ON cit.id = gil.indicator_id
               AND gil.indicator_kind = 'catalog'
             WHERE cit.subject_kind = 'raw_material'
               AND cit.subject_code = %s
        """, (material_code,))
        return [dict(r) for r in cur.fetchall()]


def material_spot_code(mat: str) -> str:
    # helper mirrors the UI map; not strictly needed since the join is on subject_code
    return {
        "BRENT": "BRENT_SPOT", "HDI": "HDI_SPOT_CN", "IPDI": "IPDI_SPOT_CN",
        "DBTDL": "DBTDL_SPOT", "PPG_2000": "PPG2000_SPOT",
        "BAC": "BAC_SPOT", "PHENOL": "PHENOL_SPOT", "TOLUENE": "TOLUENE_SPOT",
    }.get(mat, f"{mat}_SPOT_EC")


def write_event(org_id: int, goal_id: int, material: str, category: str,
                page: dict, excerpt: str) -> None:
    pretty = {
        "maintenance": "scheduled maintenance",
        "force_majeure": "force majeure",
        "explosion_fire": "operational incident",
        "restart": "restart / recovery",
        "regulation": "regulatory action",
    }.get(category, category)
    body = (
        f"**{material} · {pretty}** detected in a crawled source.\n\n"
        f"- Source: `{page['domain']}`\n"
        f"- Title: *{page.get('title') or '—'}*\n"
        f"- Keyword match: `{category}`\n"
    )
    payload = {
        "goal_id": goal_id,
        "kind": "event",
        "title": f"{material} · {pretty}",
        "body_md": body,
        "ai_model": "event-extractor:regex",
        "evidence": [
            {"kind": "page", "page_id": page["id"], "weight": 1.0, "excerpt": excerpt},
        ],
    }
    with httpx.Client(timeout=10.0) as client:
        r = client.post(f"{GATEWAY_URL}/api/v2/insights", json=payload, headers=_headers(org_id))
        r.raise_for_status()


def tick(state: dict) -> None:
    conn = psycopg2.connect(DSN)
    try:
        pages = fetch_new_pages(conn, state["since"])
        if not pages:
            return
        processed = 0
        for p in pages:
            state["since"] = max(state["since"], p["id"])
            text = " ".join(filter(None, [p.get("title"), p.get("meta_description")]))
            hit = classify(text)
            if not hit:
                continue
            category, excerpt = hit
            material = p.get("material") or ""
            if not material:
                continue
            linked = find_goals_for_material(conn, material)
            for link in linked:
                try:
                    write_event(link["org_id"], link["goal_id"], material, category, p, excerpt)
                    processed += 1
                except httpx.HTTPStatusError as e:
                    log.warning("insert failed: %s", e.response.text)
        if processed:
            log.info("tick: %d new pages scanned, %d event insights written", len(pages), processed)
    finally:
        conn.close()


def main() -> None:
    state = {"since": 0}
    log.info("event-extractor started · interval=%ss", INTERVAL)
    while True:
        try:
            tick(state)
        except Exception:  # noqa: BLE001
            log.error("tick error:\n%s", traceback.format_exc())
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
