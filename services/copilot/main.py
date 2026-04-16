"""Choopoo copilot HTTP service.

Exposes:
  POST /converse  {message, ctx{user_id, org_id, role}, history?}
                  -> {text, tool_calls, history}
  GET  /health    -> {status, mode}

Anthropic SDK with native tool-use when ANTHROPIC_API_KEY is set; falls back
to a stub command parser otherwise so the structural path can be exercised
without API cost.
"""
from __future__ import annotations
import logging
import os
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("copilot")

SERVICE_SECRET = os.getenv("SERVICE_SECRET", "")
HAS_ANTHROPIC = bool(os.getenv("ANTHROPIC_API_KEY"))
MODE = "anthropic" if HAS_ANTHROPIC else "stub"

app = FastAPI(title="choopoo-copilot")


class Ctx(BaseModel):
    user_id: int
    org_id: int
    role: str = "owner"


class ConverseRequest(BaseModel):
    message: str
    ctx: Ctx
    history: list[dict] | None = None


@app.get("/health")
async def health():
    return {"status": "ok", "mode": MODE, "model": os.getenv("CLAUDE_MODEL", "claude-opus-4-7")}


@app.post("/converse")
async def converse(req: ConverseRequest, x_service_secret: str = Header(default="")):
    if SERVICE_SECRET and x_service_secret != SERVICE_SECRET:
        raise HTTPException(status_code=401, detail="bad service secret")
    ctx = req.ctx.model_dump()

    if HAS_ANTHROPIC:
        from anthropic_loop import run as run_anthropic
        log.info("anthropic mode dispatch user=%s org=%s", ctx["user_id"], ctx["org_id"])
        return await run_anthropic(req.message, ctx, req.history)

    from stub_loop import run as run_stub
    log.info("stub mode dispatch user=%s org=%s message=%r", ctx["user_id"], ctx["org_id"], req.message)
    return await run_stub(req.message, ctx, req.history)
