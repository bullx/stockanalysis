"""Live, code-only check of a saved brief against price, filings, and sell-if lines."""

from __future__ import annotations

from typing import Any

from backend.app.data.sec import fetch_submissions, list_filings, resolve_cik
from backend.app.data.watch import (
    age_days,
    banner_text,
    evaluate_conditions,
    load_watchlist,
    metric_values,
    push_alert,
)
from backend.app.utils.market import fetch_quote
from backend.app.utils.storage import load_report


async def inspect_report(report: dict[str, Any], output_dir: str = "output") -> dict[str, Any]:
    ticker = str(report.get("ticker") or "").upper()
    quote = await fetch_quote(ticker) if ticker else None
    price = (quote or {}).get("price")
    entry = report.get("last_price")
    change = None
    try:
        if price is not None and entry:
            change = (float(price) / float(entry)) - 1
    except (TypeError, ValueError, ZeroDivisionError):
        change = None

    new_filing = None
    prior = str((report.get("freshness") or {}).get("latest_filing_date") or "")
    if ticker:
        cik = await resolve_cik(ticker, output_dir)
        if cik:
            submissions = await fetch_submissions(cik["cik"], output_dir)
            recent = list_filings(submissions or {}, {"10-K", "10-Q", "8-K"}, limit=1)
            filed = (recent[0].get("filed") or "") if recent else ""
            if prior and filed and filed > prior:
                new_filing = {"form": recent[0].get("form"), "filed": filed}

    tripped = evaluate_conditions(report.get("sell_if") or [], metric_values(report, price))
    days = age_days(report.get("generated_at"))
    return {
        "banner": banner_text(days, change, new_filing, tripped),
        "age_days": days,
        "price": price,
        "price_change": change,
        "new_filing": new_filing,
        "tripped": tripped,
    }


async def run_watch_check(output_dir: str = "output") -> list[dict[str, Any]]:
    found = []
    for item in load_watchlist(output_dir):
        loaded = load_report(output_dir, str(item.get("report_id") or ""))
        report = (loaded or {}).get("report") or {}
        if not report:
            continue
        status = await inspect_report(report, output_dir)
        alert = push_alert(output_dir, str(item.get("ticker") or ""), str(item.get("report_id") or ""), status["banner"])
        if alert:
            found.append(alert)
    return found
