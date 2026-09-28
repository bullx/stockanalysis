import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

import httpx

from backend.app.api.jobs import store
from backend.app.agents.definitions import AGENT_DEFINITIONS, CORE_AGENT_IDS
from backend.app.agents.update import run_update
from backend.app.config.model_tiers import detect_tier
from backend.app.config.providers import PROVIDERS
from backend.app.data.freshness import inspect_report
from backend.app.data.group import moves_together
from backend.app.data.scorecard import build_scorecard, link_calls
from backend.app.data.watch import add_watch, load_alerts, load_watchlist, mark_alerts_seen, remove_watch, save_watchlist
from backend.app.orchestrator.run import run_analysis
from backend.app.utils.llm import LlmStopped
from backend.app.settings import get_settings, provider_is_local
from backend.app.data.facts import build_fact_sheet
from backend.app.utils.market import fetch_quote
from backend.app.utils.parse import hydrate_agent, hydrate_debate
from backend.app.utils.storage import delete_report, load_all_reports, load_report, save_report

router = APIRouter(prefix="/api")


class AnalyzeRequest(BaseModel):
    query: str = Field(..., min_length=1)
    company: str = ""
    sector: str = ""
    asset_type: str = ""
    provider: str | None = None
    model: str | None = None
    api_key: str | None = None
    lenses: bool = True


async def model_ready(settings) -> bool:
    provider = (settings.llm_provider or "").lower()
    if provider == "mock":
        return True
    if provider == "ollama":
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                response = await client.get("http://127.0.0.1:11434/api/tags")
                return response.status_code < 500
        except Exception:  # noqa: BLE001
            return False
    if provider_is_local(provider):
        return True
    return bool(settings.llm_api_key)


@router.get("/health")
async def health():
    settings = get_settings()
    tier, _config = detect_tier(settings.llm_model)
    ready = await model_ready(settings)
    seat_count = len(CORE_AGENT_IDS) if tier == "tier3" else len(AGENT_DEFINITIONS)
    return {
        "ok": True,
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "tier": tier,
        "agent_count": seat_count,
        "is_local": settings.is_local,
        "demo": settings.llm_provider == "mock",
        "model_ready": ready,
    }


@router.get("/config")
async def config():
    settings = get_settings()
    tier, tcfg = detect_tier(settings.llm_model)
    return {
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "provider_type": settings.llm_provider_type,
        "context_window": settings.local_context_window,
        "timeout_ms": settings.local_llm_timeout_ms,
        "tier": tier,
        "providers": sorted(PROVIDERS.keys()),
        "agent_count": tcfg["agent_count"],
    }


@router.post("/analyze")
async def start_analysis(body: AnalyzeRequest):
    job = store.create()
    overrides = {
        k: v
        for k, v in {
            "provider": body.provider,
            "model": body.model,
            "api_key": body.api_key,
        }.items()
        if v
    }
    overrides["lenses"] = bool(body.lenses)
    overrides["gate"] = job.gate

    async def runner():
        async def emit(event: dict):
            await store.emit(job, event)

        try:
            await run_analysis(
                body.query,
                emit,
                company=body.company,
                sector=body.sector,
                asset_type=body.asset_type,
                overrides=overrides,
            )
        except LlmStopped as exc:
            await store.emit(job, {"type": "analysis.stopped", "error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            await job.gate.request_stop()
            await store.emit(job, {"type": "analysis.error", "error": str(exc)})

    asyncio.create_task(runner())
    return {"job_id": job.id, "status": job.status}


@router.post("/analyze/{job_id}/stop")
async def stop_analysis(job_id: str):
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status in {"done", "error", "stopped"}:
        return {"ok": True, "status": job.status}
    await job.gate.request_stop()
    return {"ok": True, "status": "stopping"}


@router.get("/analyze/{job_id}")
async def get_job(job_id: str):
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return store.snapshot(job)


@router.get("/analyze/{job_id}/stream")
async def stream_job(job_id: str):
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    queue: asyncio.Queue = asyncio.Queue()
    job.subscribers.append(queue)

    async def gen():
        for event in job.events:
            yield {"event": "message", "data": _dumps(event)}
        if job.status in {"done", "error", "stopped"}:
            return
        try:
            while True:
                event = await queue.get()
                yield {"event": "message", "data": _dumps(event)}
                if event.get("type") in {"analysis.done", "analysis.error", "analysis.stopped"}:
                    break
        finally:
            if queue in job.subscribers:
                job.subscribers.remove(queue)

    return EventSourceResponse(gen())


@router.get("/reports")
async def reports():
    linked = link_calls(load_all_reports(get_settings().output_dir))
    items = []
    for row in linked[:80]:
        report = row.get("report") or {}
        items.append(
            {
                "id": row.get("id"),
                "ticker": report.get("ticker"),
                "verdict": report.get("verdict"),
                "conviction": report.get("conviction"),
                "title": report.get("title"),
                "generated_at": report.get("generated_at"),
                "provider_used": report.get("provider_used"),
                "superseded_by": row.get("superseded_by"),
                "kind": report.get("kind") or "council",
            }
        )
    return {"items": items}


@router.get("/scorecard")
async def scorecard():
    return await build_scorecard(get_settings().output_dir)


@router.get("/tickers/{ticker}")
async def ticker_history(ticker: str):
    board = await build_scorecard(get_settings().output_dir)
    symbol = ticker.upper()
    calls = [row for row in board.get("calls") or [] if str(row.get("ticker")).upper() == symbol]
    return {"ticker": symbol, "calls": calls}


@router.get("/reports/{report_id}/status")
async def report_status(report_id: str):
    loaded = load_report(get_settings().output_dir, report_id)
    if not loaded:
        raise HTTPException(404, "Report not found")
    status = await inspect_report(loaded.get("report") or {}, get_settings().output_dir)
    watched = any(
        str(item.get("ticker")).upper() == str((loaded.get("report") or {}).get("ticker") or "").upper()
        for item in load_watchlist(get_settings().output_dir)
    )
    return {**status, "watching": watched}


@router.post("/reports/{report_id}/update")
async def update_report(report_id: str):
    settings = get_settings()
    loaded = load_report(settings.output_dir, report_id)
    if not loaded or not loaded.get("report"):
        raise HTTPException(404, "Report not found")
    status = await inspect_report(loaded["report"], settings.output_dir)
    result = await run_update(
        loaded["report"],
        status,
        report_id,
        {
            "provider": settings.llm_provider,
            "model": settings.llm_model,
            "api_key": settings.llm_api_key,
            "is_local": settings.is_local,
            "context_window": settings.local_context_window,
        },
    )
    saved = save_report(
        settings.output_dir,
        result["report"].get("ticker") or "UNKNOWN",
        result["report"],
        result["round1"],
        {"raw_text": result["report"].get("update_note") or "", "synthetic": True},
    )
    items = load_watchlist(settings.output_dir)
    changed = False
    for item in items:
        if item.get("report_id") == report_id:
            item["report_id"] = saved["id"]
            changed = True
    if changed:
        from backend.app.data.watch import save_watchlist

        save_watchlist(settings.output_dir, items)
    return {"id": saved["id"], "report": result["report"]}


@router.get("/watch/moves")
async def watch_moves():
    items = load_watchlist(get_settings().output_dir)
    pairs = await moves_together([item.get("ticker") or "" for item in items], get_settings().output_dir)
    return {"pairs": pairs}


@router.get("/watch")
async def watch_list():
    return {"items": load_watchlist(get_settings().output_dir)}


class WatchRequest(BaseModel):
    ticker: str
    report_id: str


@router.post("/watch")
async def watch_add(body: WatchRequest):
    items = add_watch(get_settings().output_dir, body.ticker, body.report_id)
    return {"items": items}


@router.delete("/watch/{ticker}")
async def watch_remove(ticker: str):
    return {"items": remove_watch(get_settings().output_dir, ticker)}


@router.get("/alerts")
async def alerts():
    return {"items": load_alerts(get_settings().output_dir)}


@router.post("/alerts/seen")
async def alerts_seen():
    mark_alerts_seen(get_settings().output_dir)
    return {"ok": True}


@router.post("/watch/check")
async def watch_check():
    from backend.app.data.freshness import run_watch_check

    found = await run_watch_check(get_settings().output_dir)
    return {"alerts": found}


@router.delete("/reports/{report_id}")
async def report_delete(report_id: str):
    settings = get_settings()
    if not delete_report(settings.output_dir, report_id):
        raise HTTPException(404, "Report not found")
    items = [item for item in load_watchlist(settings.output_dir) if item.get("report_id") != report_id]
    save_watchlist(settings.output_dir, items)
    return {"ok": True}


@router.get("/reports/{report_id}")
async def report_detail(report_id: str):
    data = load_report(get_settings().output_dir, report_id)
    if not data:
        raise HTTPException(404, "Report not found")
    if data.get("round2"):
        data["round2"] = hydrate_debate(data["round2"])
    if data.get("round1"):
        data["round1"] = {k: hydrate_agent(v) for k, v in data["round1"].items()}
    return data


@router.get("/quote/{ticker}")
async def quote(ticker: str):
    data = await fetch_quote(ticker)
    if not data:
        raise HTTPException(404, "Quote unavailable")
    return data


@router.get("/facts/{ticker}")
async def facts(ticker: str, filings: bool = True):
    sheet = await build_fact_sheet(ticker, output_dir=get_settings().output_dir, include_filings=filings)
    return sheet


def _dumps(event: dict) -> str:
    import json

    return json.dumps(event, default=str)
