from datetime import datetime, timezone
from typing import Any

import httpx


async def search_symbol(text: str) -> dict[str, Any] | None:
    """Resolve a company name or question to a ticker via Yahoo's search endpoint.

    Returns {"symbol", "name", "type"} for the best equity/ETF match, or None.
    Network failures return None so the caller can fall back to a heuristic.
    """
    query = (text or "").strip()
    if not query:
        return None
    url = "https://query1.finance.yahoo.com/v1/finance/search"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; AureliaInvestments/1.0)"}
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(
                url,
                params={"q": query, "quotesCount": 6, "newsCount": 0},
                headers=headers,
            )
            response.raise_for_status()
            quotes = (response.json() or {}).get("quotes") or []
    except Exception:  # noqa: BLE001
        return None

    def pick(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "symbol": (item.get("symbol") or "").upper(),
            "name": item.get("shortname") or item.get("longname") or "",
            "type": (item.get("quoteType") or "").lower(),
        }

    # Prefer a tradable equity or ETF over indices, currencies, futures, etc.
    for item in quotes:
        if (item.get("quoteType") or "").upper() in {"EQUITY", "ETF"} and item.get("symbol"):
            return pick(item)
    for item in quotes:
        if item.get("symbol"):
            return pick(item)
    return None


async def fetch_quote(ticker: str) -> dict[str, Any] | None:
    symbol = (ticker or "").strip().upper()
    if not symbol or symbol == "UNKNOWN":
        return None
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; AureliaInvestments/1.0)"}
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.get(
                url,
                params={"interval": "1d", "range": "5d"},
                headers=headers,
            )
            response.raise_for_status()
            result = (response.json().get("chart") or {}).get("result") or []
            if not result:
                return None
            meta = result[0].get("meta") or {}
            price = meta.get("regularMarketPrice") or meta.get("previousClose") or meta.get("chartPreviousClose")
            if price is None:
                return None
            prev = meta.get("previousClose") or meta.get("chartPreviousClose")
            change_pct = None
            if prev:
                change_pct = (float(price) - float(prev)) / float(prev) * 100
            instrument = (meta.get("instrumentType") or "").lower()
            asof = meta.get("regularMarketTime")
            if asof:
                asof_date = datetime.fromtimestamp(int(asof), tz=timezone.utc).date().isoformat()
            else:
                asof_date = datetime.now(timezone.utc).date().isoformat()
            return {
                "ticker": symbol,
                "price": round(float(price), 2),
                "previous_close": round(float(prev), 2) if prev else None,
                "change_pct": round(change_pct, 2) if change_pct is not None else None,
                "currency": meta.get("currency") or "USD",
                "name": meta.get("shortName") or meta.get("longName") or "",
                "exchange": meta.get("exchangeName") or "",
                "type": "etf" if instrument == "etf" else ("equity" if instrument == "equity" else instrument or None),
                "asof": asof_date,
            }
    except Exception:  # noqa: BLE001
        return None


def format_live_data(quote: dict[str, Any]) -> str:
    change = ""
    if quote.get("change_pct") is not None:
        change = f" ({quote['change_pct']:+.2f}% vs previous close)"
    name = f" — {quote['name']}" if quote.get("name") else ""
    return (
        f"LIVE QUOTE (authoritative — do not invent a different spot price):\n"
        f"{quote['ticker']}{name}\n"
        f"Last price: ${quote['price']:.2f} {quote.get('currency', 'USD')} as of {quote.get('asof')}"
        f"{change}\n"
        "All price targets and implied upside MUST be relative to this last price."
    )
