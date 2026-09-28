"""Same-SIC peers. Multiples are computed from SEC facts and a Yahoo price."""

from __future__ import annotations

import re
from typing import Any

from backend.app.data.cache import cache_get, cache_set
from backend.app.data.http import get_text, sec_headers
from backend.app.data.metrics import business_metrics, valuation_metrics
from backend.app.data.sec import extract_fundamentals, fetch_companyfacts, load_ticker_map
from backend.app.settings import get_settings
from backend.app.utils.market import fetch_quote

_CIK_TAG = re.compile(r"<cik>\s*(\d{7,10})\s*</cik>", re.I)
_CIK_PARENS = re.compile(r"\((\d{7,10})\)")


def peer_ciks_from_feed(xml: str) -> list[int]:
    found: list[int] = []
    seen: set[int] = set()
    matches = list(_CIK_TAG.finditer(xml or "")) or list(_CIK_PARENS.finditer(xml or ""))
    for match in matches:
        cik = int(match.group(1))
        if cik in seen or cik == 0:
            continue
        seen.add(cik)
        found.append(cik)
    return found


def peer_row(ticker: str, name: str, business: dict[str, Any], valuation: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "name": name or "",
        "pe": valuation.get("pe"),
        "ev_ebitda": valuation.get("ev_ebitda"),
        "operating_margin": business.get("operating_margin"),
        "fcf_yield": valuation.get("fcf_yield"),
    }


def _ticker_by_cik(mapping: dict[str, dict[str, Any]]) -> dict[int, str]:
    out: dict[int, str] = {}
    for ticker, row in mapping.items():
        try:
            out[int(row["cik"])] = ticker
        except (KeyError, TypeError, ValueError):
            continue
    return out


async def build_peer_table(
    ticker: str,
    sic: str | int | None,
    self_cik: int | None,
    business: dict[str, Any],
    valuation: dict[str, Any],
    company: str = "",
    output_dir: str = "output",
    limit: int = 4,
) -> list[dict[str, Any]]:
    symbol = (ticker or "").strip().upper()
    if not sic or not symbol:
        return []
    cache_key = f"{symbol}_{sic}"
    cached = cache_get("peers", cache_key, ttl_s=12 * 3600, output_dir=output_dir)
    if isinstance(cached, list):
        return cached

    url = (
        "https://www.sec.gov/cgi-bin/browse-edgar"
        f"?action=getcompany&SIC={sic}&owner=include&count=40&output=atom"
    )
    feed = await get_text(url, headers=sec_headers(get_settings().sec_user_agent), timeout=30.0)
    mapping = await load_ticker_map(output_dir)
    by_cik = _ticker_by_cik(mapping)
    names = []
    for cik in peer_ciks_from_feed(feed or ""):
        if self_cik is not None and cik == int(self_cik):
            continue
        peer = by_cik.get(cik)
        if not peer or peer == symbol:
            continue
        names.append(peer)
        if len(names) >= limit:
            break

    rows = [peer_row(symbol, company, business, valuation)]
    for peer in names:
        facts = await fetch_companyfacts_for_ticker(peer, mapping, output_dir)
        if not facts:
            rows.append({"ticker": peer, "name": "", "pe": None, "ev_ebitda": None, "operating_margin": None, "fcf_yield": None})
            continue
        fund = extract_fundamentals(facts)
        biz = business_metrics(fund)
        quote = await fetch_quote(peer)
        price = (quote or {}).get("price")
        val = valuation_metrics(fund, price)
        rows.append(peer_row(peer, str(facts.get("entityName") or ""), biz, val))
    if len(rows) > 1:
        cache_set("peers", cache_key, rows, output_dir=output_dir)
    return rows


async def fetch_companyfacts_for_ticker(
    ticker: str,
    mapping: dict[str, dict[str, Any]],
    output_dir: str,
) -> dict[str, Any] | None:
    row = mapping.get(ticker.upper())
    if not row:
        return None
    return await fetch_companyfacts(row["cik"], output_dir=output_dir)
