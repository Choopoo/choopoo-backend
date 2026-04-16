"""Forecaster service.

Runs a loop every FORECAST_INTERVAL seconds. For each catalog indicator that
has >=7 readings, fits an AutoETS model (via statsforecast) and writes a
`kind=forecast` insight to every (org, goal) pair that has linked the indicator
as `primary`.

Insights are written through the gateway using the SERVICE_SECRET auth path,
so RLS is enforced end-to-end just like user-initiated writes.

No Kafka in v1 — reads readings directly from Postgres (BYPASSRLS via the
pipeline role). Introducing `indicator.readings.v1` Kafka topic is a follow-up.
"""
from __future__ import annotations
import logging
import os
import time
import traceback

import httpx
import pandas as pd
import psycopg2
import psycopg2.extras

# statsforecast is heavy; import lazily after psycopg is up
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("forecaster")

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://gateway:8080")
SERVICE_SECRET = os.getenv("SERVICE_SECRET", "")
INTERVAL = int(os.getenv("FORECAST_INTERVAL", "300"))
HORIZON = int(os.getenv("FORECAST_HORIZON_DAYS", "7"))

DSN = (
    f"host={os.getenv('DB_HOST','postgres')} port={os.getenv('DB_PORT','5432')} "
    f"user={os.getenv('DB_USER','pipeline')} password={os.getenv('DB_PASSWORD','pipeline')} "
    f"dbname={os.getenv('DB_NAME','pipeline')}"
)


def _headers(org_id: int) -> dict:
    return {
        "X-Service-Secret": SERVICE_SECRET,
        "X-Org-Id": str(org_id),
        "X-User-Id": "0",
        "X-User-Role": "owner",
        "Content-Type": "application/json",
    }


def fetch_indicators(conn) -> list[dict]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT id, code, unit
              FROM catalog_indicator_template
             WHERE kind = 'price'
        """)
        return [dict(r) for r in cur.fetchall()]


def fetch_series(conn, indicator_id: int) -> pd.DataFrame | None:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT ts, value FROM global_indicator_readings
             WHERE indicator_id = %s ORDER BY ts
        """, (indicator_id,))
        rows = cur.fetchall()
    if len(rows) < 7:
        return None
    df = pd.DataFrame(rows, columns=["ds", "y"])
    df["ds"] = pd.to_datetime(df["ds"])
    df["y"] = df["y"].astype(float)
    df["unique_id"] = "series"
    return df[["unique_id", "ds", "y"]]


def fit_and_project(df: pd.DataFrame, horizon: int) -> tuple[float, float, float]:
    """Return (last_value, projected_value, trend_pct)."""
    from statsforecast import StatsForecast
    from statsforecast.models import AutoETS

    sf = StatsForecast(models=[AutoETS(season_length=1)], freq="D", n_jobs=1)
    try:
        fc = sf.forecast(df=df, h=horizon)
    except Exception as e:  # noqa: BLE001
        log.warning("statsforecast failed, using linear fallback: %s", e)
        # Linear fallback: last value + rolling mean trend
        y = df["y"].to_numpy()
        trend = (y[-1] - y[0]) / max(len(y), 1)
        proj = y[-1] + trend * horizon
        return float(y[-1]), float(proj), float((proj - y[-1]) / y[-1] * 100 if y[-1] else 0)
    last = float(df["y"].iloc[-1])
    proj_col = [c for c in fc.columns if c.startswith("AutoETS")][0]
    proj = float(fc[proj_col].iloc[-1])
    trend_pct = (proj - last) / last * 100 if last else 0
    return last, proj, trend_pct


def find_linked_goals(conn, indicator_id: int) -> list[dict]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT gil.org_id, gil.goal_id, gil.role, g.title
              FROM goal_indicator_links gil
              JOIN goals g ON g.id = gil.goal_id
             WHERE gil.indicator_kind = 'catalog'
               AND gil.indicator_id = %s
               AND gil.role = 'primary'
        """, (indicator_id,))
        return [dict(r) for r in cur.fetchall()]


def write_forecast(org_id: int, goal_id: int, indicator_code: str, indicator_id: int,
                   last: float, proj: float, trend_pct: float, unit: str) -> None:
    direction = "trending up" if trend_pct >= 0 else "trending down"
    arrow = "▲" if trend_pct >= 0 else "▼"
    body = (
        f"**{indicator_code}** {direction} over the next {HORIZON}d.\n\n"
        f"- Latest: `{last:,.0f} {unit}`\n"
        f"- Projected ({HORIZON}d): `{proj:,.0f} {unit}` {arrow} `{trend_pct:+.2f}%`\n"
        f"- Model: AutoETS (statsforecast)\n\n"
        f"*Projection is from a univariate trend model on recent readings. "
        f"Treat as a sanity check, not guidance on its own.*"
    )
    payload = {
        "goal_id": goal_id,
        "kind": "forecast",
        "title": f"{indicator_code} {HORIZON}d {arrow} {trend_pct:+.2f}%",
        "body_md": body,
        "ai_model": "forecaster:autoets",
        "evidence": [
            {"kind": "catalog_indicator", "catalog_indicator_id": indicator_id, "weight": 1.0},
        ],
    }
    with httpx.Client(timeout=10.0) as client:
        r = client.post(f"{GATEWAY_URL}/api/v2/insights", json=payload, headers=_headers(org_id))
        r.raise_for_status()
        log.info("wrote forecast org=%s goal=%s ind=%s trend=%.2f%%",
                 org_id, goal_id, indicator_code, trend_pct)


def tick() -> None:
    conn = psycopg2.connect(DSN)
    try:
        indicators = fetch_indicators(conn)
        log.info("tick: %d catalog price indicators", len(indicators))
        for ind in indicators:
            df = fetch_series(conn, ind["id"])
            if df is None:
                continue
            try:
                last, proj, trend = fit_and_project(df, HORIZON)
            except Exception as e:  # noqa: BLE001
                log.warning("forecast %s failed: %s", ind["code"], e)
                continue
            linked = find_linked_goals(conn, ind["id"])
            for link in linked:
                try:
                    write_forecast(
                        org_id=link["org_id"], goal_id=link["goal_id"],
                        indicator_code=ind["code"], indicator_id=ind["id"],
                        last=last, proj=proj, trend_pct=trend, unit=ind.get("unit") or "unit",
                    )
                except httpx.HTTPStatusError as e:
                    log.warning("insert failed: %s", e.response.text)
    finally:
        conn.close()


def main() -> None:
    log.info("forecaster started · interval=%ss · horizon=%sd", INTERVAL, HORIZON)
    while True:
        try:
            tick()
        except Exception:  # noqa: BLE001
            log.error("tick error:\n%s", traceback.format_exc())
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
