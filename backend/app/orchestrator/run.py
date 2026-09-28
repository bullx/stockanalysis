from datetime import datetime, timezone
from typing import Awaitable, Callable

from backend.app.agents.definitions import AGENT_DEFINITIONS, CORE_AGENT_IDS, FULL_DESK_IDS
from backend.app.agents.filings import run_filing_readers
from backend.app.agents.synthesis import get_cio_prompt, build_synthesis_user_message
from backend.app.config.model_tiers import detect_tier
from backend.app.orchestrator.normalize import normalize_query, ticker_search_candidates
from backend.app.orchestrator.rounds import run_round1, run_round2
from backend.app.data.facts import build_fact_sheet
from backend.app.data.validate import validate_round1
from backend.app.settings import Settings, get_settings, provider_is_local
from backend.app.utils.context import prepare_round3_context
from backend.app.utils.llm import call_llm_with_retry
from backend.app.utils.market import fetch_quote, format_live_data, search_symbol
from backend.app.utils.parse import extract_and_parse_json, implied_upside, normalize_report
from backend.app.utils.prompt_adapter import adapt_prompts_for_model
from backend.app.utils.storage import save_report

Emit = Callable[[dict], Awaitable[None]]


async def run_analysis(
    user_input: str,
    emit: Emit,
    company: str = "",
    sector: str = "",
    asset_type: str = "",
    overrides: dict | None = None,
    settings: Settings | None = None,
) -> dict:
    settings = settings or get_settings()
    overrides = overrides or {}
    model_name = overrides.get("model") or settings.llm_model
    provider_name = overrides.get("provider") or settings.llm_provider
    context_window = int(overrides.get("context_window") or settings.local_context_window)
    tier_name, tier = detect_tier(model_name)
    if provider_name in {"openai", "anthropic", "gemini"} and tier_name != "tier1":
        from backend.app.config.model_tiers import MODEL_TIERS

        tier_name, tier = "tier1", MODEL_TIERS["tier1"]

    # Locality must follow the effective provider, not just global .env, so a
    # provider picked on the form controls sequential-vs-parallel and the timeout.
    if overrides.get("provider"):
        is_local = provider_is_local(provider_name)
    else:
        is_local = settings.is_local

    llm_opts = {
        "provider": provider_name,
        "model": model_name,
        "api_key": overrides.get("api_key") or settings.llm_api_key,
        "context_window": context_window,
        "gate": overrides.get("gate"),
        "is_local": is_local,
    }
    sequential = is_local or provider_name == "mock"
    present = {agent["id"] for agent in AGENT_DEFINITIONS}
    # The full desk is the default. A short desk is only the four core seats.
    # A tiny model always uses the short desk.
    short_desk = tier_name == "tier3" or overrides.get("lenses") is False
    source = CORE_AGENT_IDS if short_desk else FULL_DESK_IDS
    agent_ids = [agent_id for agent_id in source if agent_id in present]

    await emit(
        {
            "type": "analysis.started",
            "provider": provider_name,
            "model": model_name,
            "tier": tier_name,
            "agent_count": len(agent_ids),
            "agent_ids": agent_ids,
            "rounds": tier["rounds_enabled"],
            "context_window": context_window,
        }
    )

    query = normalize_query(user_input, company=company, sector=sector, asset_type=asset_type)
    if query.get("needs_resolution"):
        for candidate in ticker_search_candidates(query["query_raw"]):
            hit = await search_symbol(candidate)
            if hit and hit.get("symbol"):
                query["ticker"] = hit["symbol"]
                if not query.get("company") and hit.get("name"):
                    query["company"] = hit["name"]
                if query.get("type") in (None, "", "unknown") and hit.get("type"):
                    query["type"] = hit["type"]
                break
    quote = await fetch_quote(query["ticker"])
    if quote:
        query["quote"] = quote
        query["live_data"] = format_live_data(quote)
        query["last_price"] = quote["price"]
        query["last_price_asof"] = quote["asof"]
        if not query.get("company") and quote.get("name"):
            query["company"] = quote["name"]
        if quote.get("type") and query.get("type") in (None, "", "unknown"):
            query["type"] = quote["type"]

    await emit({"type": "facts.started", "ticker": query["ticker"]})
    sheet = await build_fact_sheet(query["ticker"], output_dir=settings.output_dir)
    query["coverage"] = sheet.get("coverage")
    query["fact_sheet_text"] = sheet.get("prompt")
    query["sic_description"] = sheet.get("sic_description") or query.get("sector")
    if sheet.get("sic_description") and not query.get("sector"):
        query["sector"] = sheet["sic_description"]
    if sheet.get("company") and not query.get("company"):
        query["company"] = sheet["company"]
    dcf = sheet.get("dcf") or {}
    if dcf.get("implied_growth") is not None:
        hist = (sheet.get("business") or {}).get("revenue_cagr_5y")
        query["priced_in_line"] = (
            f"PRICED IN (code): last price implies ~{dcf['implied_growth'] * 100:.1f}% near-term FCF growth. "
            f"5y revenue CAGR is {hist * 100:.1f}%." if hist is not None else
            f"PRICED IN (code): last price implies ~{dcf['implied_growth'] * 100:.1f}% near-term FCF growth."
        )
    # Compact sheet for the saved brief (full history stays available via /api/facts).
    query["fact_sheet"] = {
        "coverage": sheet.get("coverage"),
        "company": sheet.get("company"),
        "sic": sheet.get("sic"),
        "sic_description": sheet.get("sic_description"),
        "sector_etf": sheet.get("sector_etf"),
        "business": sheet.get("business"),
        "forensic": sheet.get("forensic"),
        "valuation": sheet.get("valuation"),
        "price": sheet.get("price"),
        "dcf": sheet.get("dcf"),
        "macro": sheet.get("macro"),
        "latest_filing": sheet.get("latest_filing"),
        "peers": sheet.get("peers") or [],
        "filings": {
            "items_found": (sheet.get("filings") or {}).get("items_found") if sheet.get("filings") else [],
            "red_flags": (sheet.get("filings") or {}).get("red_flags") if sheet.get("filings") else [],
            "insider_90d": (sheet.get("filings") or {}).get("insider_90d") if sheet.get("filings") else None,
            "earnings_8k": (sheet.get("filings") or {}).get("earnings_8k") if sheet.get("filings") else None,
            "guidance": (sheet.get("filings") or {}).get("guidance") if sheet.get("filings") else None,
            "guidance_note": (sheet.get("filings") or {}).get("guidance_note") if sheet.get("filings") else None,
            "risk_diff": (sheet.get("filings") or {}).get("risk_diff") if sheet.get("filings") else None,
        } if sheet.get("filings") else None,
        "history": sheet.get("history"),
        "built_at": sheet.get("built_at"),
        "sources": sheet.get("sources"),
        "prompt": sheet.get("prompt"),
    }
    await emit({"type": "facts.ready", "coverage": sheet.get("coverage"), "query": query})
    if sheet.get("coverage") == "us" and sheet.get("filings"):
        reader_note = await run_filing_readers(
            sheet["filings"],
            query.get("ticker") or "",
            tier_name,
            llm_opts,
            emit,
            output_dir=settings.output_dir,
        )
        if reader_note:
            query["fact_sheet_text"] = (query.get("fact_sheet_text") or "") + "\n\n" + reader_note
            query["fact_sheet"]["prompt"] = query["fact_sheet_text"]
            query["fact_sheet"]["filing_readers"] = reader_note
    await emit({"type": "query.normalized", "query": query})

    start = datetime.now(timezone.utc)
    round1 = await run_round1(
        query, tier, sequential, settings.local_agent_delay_ms, emit, llm_opts, agent_ids=agent_ids
    )

    high = [r for r in round1.values() if not r.get("error") and r.get("conviction", 0) >= 9]
    if len(high) == len([r for r in round1.values() if not r.get("error")]) and round1:
        await emit({"type": "bias.guard", "message": "Unanimous high conviction — extra devil's advocate"})
        from backend.app.agents.definitions import AGENT_BY_ID
        from backend.app.orchestrator.normalize import build_agent_user_message
        from backend.app.utils.parse import parse_agent_output

        devil = AGENT_BY_ID["devil"]
        extra = await call_llm_with_retry(
            devil["system_prompt"],
            build_agent_user_message(devil, query)
            + "\n\nThe rest of the desk is unanimous. Sharpen the bear case.",
            tier["max_tokens_agent"],
            options=llm_opts,
        )
        parsed = parse_agent_output(extra)
        round1["devil"] = {
            "agent_id": "devil",
            "agent_name": devil["name"],
            "tag": devil["tag"],
            **parsed,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await emit({"type": "agent.completed", **round1["devil"]})

    round2 = await run_round2(query, round1, tier, emit, llm_opts)

    await emit({"type": "round3.started"})
    round1_text, debate_text = prepare_round3_context(round1, round2, context_window)
    cio_prompt = get_cio_prompt(tier_name)
    adapted = adapt_prompts_for_model(
        cio_prompt,
        build_synthesis_user_message(query, round1_text, debate_text),
        tier.get("system_prompt_mode") or "native",
    )
    synth_raw = await call_llm_with_retry(
        adapted["system"], adapted["user"], tier["max_tokens_cio"], options=llm_opts
    )
    report = normalize_report(extract_and_parse_json(synth_raw), query)
    elapsed = int((datetime.now(timezone.utc) - start).total_seconds())
    failures = [f"{r['agent_name']}: {r['error']}" for r in round1.values() if r.get("error")]
    empty = [r["agent_name"] for r in round1.values() if not (r.get("output") or "").strip()]
    mismatches = validate_round1(round1, sheet)
    latest = sheet.get("latest_filing") or {}
    notes = [
        "; ".join(failures) if failures else None,
        f"{len(empty)}/{len(round1)} specialist notes were empty — CIO brief may be unanchored"
        if empty
        else None,
        "Debate had no usable text" if not (round2.get("raw_text") or "").strip() else None,
        "No live quote; price targets may reflect stale model knowledge" if not quote else None,
        "Tier 3 model — reduced agent count and simplified schema" if tier_name == "tier3" else None,
        "Debate round skipped (Tier 3)" if 2 not in tier["rounds_enabled"] else None,
        "Coverage is price-only; fundamentals were not available from SEC" if sheet.get("coverage") != "us" else None,
        "; ".join(mismatches) if mismatches else None,
        report.get("data_quality_notes"),
    ]
    report["coverage"] = sheet.get("coverage")
    report["sector_etf"] = sheet.get("sector_etf")
    report["freshness"] = {
        "built_at": sheet.get("built_at"),
        "last_price": query.get("last_price"),
        "last_price_asof": query.get("last_price_asof"),
        "latest_filing_form": latest.get("form"),
        "latest_filing_date": latest.get("filed"),
        "council_ran_at": datetime.now(timezone.utc).isoformat(),
    }
    report["priced_in"] = dcf
    report["fact_sheet"] = query.get("fact_sheet")
    if sheet.get("sector"):
        report["sector"] = report.get("sector") or sheet.get("sic_description")
    if sheet.get("sic_description") and (not report.get("sector") or report.get("sector") == "Unknown"):
        report["sector"] = sheet["sic_description"]
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    report["provider_used"] = f"{provider_name}/{model_name} ({tier_name})"
    report["total_time_s"] = elapsed
    report["data_quality_notes"] = " | ".join(n for n in notes if n) or None
    report["tier"] = tier_name
    if quote:
        report["last_price"] = quote["price"]
        report["last_price_asof"] = quote["asof"]
        report["implied_upside_base"] = (
            implied_upside(quote["price"], report.get("price_target_base"))
            or report.get("implied_upside_base")
            or "N/A"
        )

    paths = save_report(settings.output_dir, query["ticker"], report, round1, round2)
    result = {"report": report, "round1": round1, "round2": round2, "paths": paths, "query": query}
    await emit({"type": "analysis.done", **result})
    return result
