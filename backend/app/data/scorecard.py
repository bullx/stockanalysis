"""Forward scorecard. Horizons stay blank until the calendar date has passed.

Prices before the call are never used as the outcome. The stored last price is
the entry. Later closes come from the daily history. Old call files are not rewritten.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timezone
from typing import Any

HORIZONS = (("1m", 1), ("3m", 3), ("6m", 6), ("12m", 12))

_BEAR_WORDS = (
    "strong sell",
    "strong avoid",
    "avoid",
    "overvalued",
    "bear",
    "headwind",
    "declining",
    "sell",
)
_BULL_WORDS = (
    "strong buy",
    "buy",
    "undervalued",
    "bullish",
    "tailwind",
    "exceptional",
    "strong",
)
_NEUTRAL_WORDS = ("hold", "neutral", "fair", "moderate", "stable", "average", "narrow")


def parse_money(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).replace(",", "").replace("$", "").strip()
    if not text or text.upper() in {"N/A", "NA", "NONE"}:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if number > 0 else None


def call_day(report: dict[str, Any]) -> date | None:
    raw = report.get("generated_at") or (report.get("freshness") or {}).get("council_ran_at") or ""
    text = str(raw)[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def shift_months(day: date, months: int) -> date:
    month_index = day.month - 1 + months
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(day.day, last))


def _as_date(value: str) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def close_on_or_before(history: list[dict[str, Any]], day: date) -> float | None:
    found = None
    for row in history:
        row_day = _as_date(row.get("date") or "")
        if row_day is None or row_day > day or row.get("close") is None:
            continue
        found = float(row["close"])
    return found


def close_on_or_after(history: list[dict[str, Any]], day: date) -> tuple[str, float] | None:
    for row in history:
        row_day = _as_date(row.get("date") or "")
        if row_day is None or row_day < day or row.get("close") is None:
            continue
        return row_day.isoformat(), float(row["close"])
    return None


def _return(start: float | None, end: float | None) -> float | None:
    if start is None or end is None or start <= 0:
        return None
    return (end / start) - 1


def stayed_inside(
    history: list[dict[str, Any]],
    start: date,
    end: date,
    bear: float | None,
    bull: float | None,
) -> bool | None:
    if bear is None or bull is None or bear > bull:
        return None
    closes = []
    for row in history:
        row_day = _as_date(row.get("date") or "")
        if row_day is None or row_day <= start or row_day > end or row.get("close") is None:
            continue
        closes.append(float(row["close"]))
    if not closes:
        return None
    return all(bear <= price <= bull for price in closes)


def score_horizons(
    report: dict[str, Any],
    stock: list[dict[str, Any]],
    spy: list[dict[str, Any]],
    sector: list[dict[str, Any]],
    today: date | None = None,
) -> list[dict[str, Any]]:
    today = today or datetime.now(timezone.utc).date()
    opened = call_day(report)
    entry = parse_money(report.get("last_price"))
    bear = parse_money(report.get("price_target_bear"))
    bull = parse_money(report.get("price_target_bull"))
    rows = []
    for label, months in HORIZONS:
        if opened is None:
            rows.append({"horizon": label, "status": "no_date"})
            continue
        due = shift_months(opened, months)
        if today < due:
            rows.append({"horizon": label, "status": "not_due", "due": due.isoformat()})
            continue
        if entry is None:
            rows.append({"horizon": label, "status": "no_entry_price", "due": due.isoformat()})
            continue
        stock_hit = close_on_or_after(stock, due)
        spy_hit = close_on_or_after(spy, due)
        sector_hit = close_on_or_after(sector, due) if sector else None
        if stock_hit is None:
            rows.append({"horizon": label, "status": "no_price", "due": due.isoformat()})
            continue
        spy_entry = close_on_or_before(spy, opened)
        sector_entry = close_on_or_before(sector, opened) if sector else None
        stock_return = _return(entry, stock_hit[1])
        spy_return = _return(spy_entry, spy_hit[1] if spy_hit else None)
        sector_return = _return(sector_entry, sector_hit[1] if sector_hit else None)
        rows.append(
            {
                "horizon": label,
                "status": "scored",
                "due": due.isoformat(),
                "asof": stock_hit[0],
                "price": stock_hit[1],
                "stock_return": stock_return,
                "spy_return": spy_return,
                "sector_return": sector_return,
                "excess_spy": None if stock_return is None or spy_return is None else stock_return - spy_return,
                "excess_sector": None
                if stock_return is None or sector_return is None
                else stock_return - sector_return,
                "stayed_inside": stayed_inside(stock, opened, date.fromisoformat(stock_hit[0]), bear, bull),
            }
        )
    return rows


def seat_direction(stance: str) -> str | None:
    text = (stance or "").lower().strip()
    if not text or "incomplete" in text or text in {"unknown", "empty"}:
        return None
    if any(word in text for word in _BEAR_WORDS):
        return "bear"
    if "high" in text and "risk" in text:
        return "bear"
    if any(word in text for word in _BULL_WORDS):
        return "bull"
    if any(word in text for word in _NEUTRAL_WORDS):
        return "neutral"
    return None


def _longest_scored_return(horizons: list[dict[str, Any]]) -> float | None:
    scored = [row for row in horizons if row.get("status") == "scored" and row.get("stock_return") is not None]
    if not scored:
        return None
    return scored[-1]["stock_return"]


def seat_results(round1: dict[str, Any] | None, horizons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    outcome = _longest_scored_return(horizons)
    results = []
    for agent_id, record in (round1 or {}).items():
        if not isinstance(record, dict):
            continue
        direction = seat_direction(str(record.get("stance") or ""))
        aligned = None
        if outcome is not None and direction is not None:
            if outcome > 0.01 and direction == "bull":
                aligned = True
            elif outcome < -0.01 and direction == "bear":
                aligned = True
            elif abs(outcome) <= 0.01 and direction == "neutral":
                aligned = True
            else:
                aligned = False
        results.append(
            {
                "agent_id": agent_id,
                "agent_name": record.get("agent_name") or agent_id,
                "stance": record.get("stance") or "",
                "direction": direction,
                "aligned": aligned,
            }
        )
    return results


def link_calls(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mark later briefs as superseding earlier ones. Does not write the files."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        ticker = str((record.get("report") or {}).get("ticker") or "").upper()
        grouped.setdefault(ticker, []).append(record)
    linked = []
    for ticker, rows in grouped.items():
        rows.sort(key=lambda row: str((row.get("report") or {}).get("generated_at") or ""))
        for index, row in enumerate(rows):
            report = row.get("report") or {}
            linked.append(
                {
                    **row,
                    "ticker": ticker,
                    "supersedes": rows[index - 1]["id"] if index else report.get("supersedes"),
                    "superseded_by": rows[index + 1]["id"] if index + 1 < len(rows) else None,
                }
            )
    linked.sort(key=lambda row: str((row.get("report") or {}).get("generated_at") or ""), reverse=True)
    return linked


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def summarize(scored: list[dict[str, Any]]) -> dict[str, Any]:
    def bucket(key_fn) -> list[dict[str, Any]]:
        groups: dict[str, list[dict[str, Any]]] = {}
        for row in scored:
            groups.setdefault(key_fn(row), []).append(row)
        out = []
        for name, rows in sorted(groups.items()):
            excess = []
            inside = []
            due = 0
            for row in rows:
                for horizon in row.get("horizons") or []:
                    if horizon.get("status") != "scored":
                        continue
                    due += 1
                    if horizon.get("excess_spy") is not None:
                        excess.append(horizon["excess_spy"])
                    if horizon.get("stayed_inside") is not None:
                        inside.append(1.0 if horizon["stayed_inside"] else 0.0)
            out.append(
                {
                    "name": name,
                    "calls": len(rows),
                    "scored_horizons": due,
                    "avg_excess_spy": _mean(excess),
                    "stayed_inside_rate": _mean(inside),
                }
            )
        return out

    seats: dict[str, list[bool]] = {}
    for row in scored:
        for seat in row.get("seats") or []:
            if seat.get("aligned") is None:
                continue
            seats.setdefault(seat.get("agent_name") or seat.get("agent_id") or "seat", []).append(bool(seat["aligned"]))
    seat_rows = [
        {"name": name, "scored": len(flags), "aligned_rate": _mean([1.0 if flag else 0.0 for flag in flags])}
        for name, flags in sorted(seats.items())
    ]
    return {
        "by_verdict": bucket(lambda row: str((row.get("report") or {}).get("verdict") or "UNKNOWN")),
        "by_model": bucket(lambda row: str((row.get("report") or {}).get("provider_used") or "unknown")),
        "by_seat": seat_rows,
        "calls": len(scored),
        "forward_only": True,
    }


def public_call(row: dict[str, Any]) -> dict[str, Any]:
    report = row.get("report") or {}
    sheet = report.get("fact_sheet") or {}
    return {
        "id": row.get("id"),
        "ticker": row.get("ticker") or str(report.get("ticker") or "").upper(),
        "verdict": report.get("verdict"),
        "title": report.get("title"),
        "summary": report.get("summary"),
        "conviction": report.get("conviction"),
        "generated_at": report.get("generated_at"),
        "last_price": report.get("last_price"),
        "price_target_base": report.get("price_target_base"),
        "price_target_bull": report.get("price_target_bull"),
        "price_target_bear": report.get("price_target_bear"),
        "provider_used": report.get("provider_used"),
        "sector_etf": report.get("sector_etf") or sheet.get("sector_etf"),
        "kind": report.get("kind") or "council",
        "update_note": report.get("update_note"),
        "horizons": row.get("horizons") or [],
        "seats": row.get("seats") or [],
        "supersedes": row.get("supersedes"),
        "superseded_by": row.get("superseded_by"),
    }


async def build_scorecard(output_dir: str = "output") -> dict[str, Any]:
    from backend.app.data.cache import cache_get, cache_set
    from backend.app.data.prices import fetch_history
    from backend.app.utils.storage import load_all_reports

    linked = link_calls(load_all_reports(output_dir))
    if not linked:
        return {"summary": summarize([]), "calls": []}
    stamp = datetime.now(timezone.utc).date().isoformat()
    key = stamp + "_" + str(len(linked)) + "_" + "|".join(str(row.get("id")) for row in linked[:40])
    cached = cache_get("scorecard", key, ttl_s=6 * 3600, output_dir=output_dir)
    if isinstance(cached, dict) and cached.get("calls") is not None:
        return cached

    symbols = {"SPY"}
    for row in linked:
        ticker = str((row.get("report") or {}).get("ticker") or "").upper()
        if ticker:
            symbols.add(ticker)
        etf = (row.get("report") or {}).get("sector_etf") or ((row.get("report") or {}).get("fact_sheet") or {}).get(
            "sector_etf"
        )
        if etf:
            symbols.add(str(etf).upper())
    histories: dict[str, list] = {}
    for symbol in symbols:
        histories[symbol] = await fetch_history(symbol, "10y", output_dir=output_dir)

    scored = []
    for row in linked:
        report = row.get("report") or {}
        ticker = str(report.get("ticker") or "").upper()
        etf = str(report.get("sector_etf") or (report.get("fact_sheet") or {}).get("sector_etf") or "").upper()
        result = score_record(
            row,
            histories.get(ticker) or [],
            histories.get("SPY") or [],
            histories.get(etf) or [],
        )
        result["supersedes"] = row.get("supersedes")
        result["superseded_by"] = row.get("superseded_by")
        scored.append(result)
    payload = {"summary": summarize(scored), "calls": [public_call(row) for row in scored]}
    cache_set("scorecard", key, payload, output_dir=output_dir)
    return payload


def score_record(
    record: dict[str, Any],
    stock: list[dict[str, Any]],
    spy: list[dict[str, Any]],
    sector: list[dict[str, Any]],
    today: date | None = None,
) -> dict[str, Any]:
    report = record.get("report") or {}
    horizons = score_horizons(report, stock, spy, sector, today=today)
    return {
        "id": record.get("id"),
        "ticker": str(report.get("ticker") or "").upper(),
        "report": report,
        "horizons": horizons,
        "seats": seat_results(record.get("round1"), horizons),
        "supersedes": record.get("supersedes"),
        "superseded_by": record.get("superseded_by"),
    }
