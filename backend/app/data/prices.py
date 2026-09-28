"""Yahoo daily price history. The quote endpoint stays in utils/market.py."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from backend.app.data.cache import cache_get, cache_set
from backend.app.data.http import YAHOO_UA


async def fetch_history(
    ticker: str,
    range_code: str = "10y",
    output_dir: str = "output",
) -> list[dict[str, Any]]:
    """Return [{date, close, volume}] oldest-first. Empty on failure."""
    symbol = (ticker or "").strip().upper()
    if not symbol or symbol == "UNKNOWN":
        return []
    cached = cache_get("prices", f"{symbol}_{range_code}", ttl_s=6 * 3600, output_dir=output_dir)
    if cached is not None:
        return cached
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                url,
                params={"interval": "1d", "range": range_code, "events": "div,splits"},
                headers={"User-Agent": YAHOO_UA},
            )
            response.raise_for_status()
            result = ((response.json() or {}).get("chart") or {}).get("result") or []
    except Exception:  # noqa: BLE001
        return []
    if not result:
        return []
    timestamps = result[0].get("timestamp") or []
    quote = ((result[0].get("indicators") or {}).get("quote") or [{}])[0]
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []
    rows: list[dict[str, Any]] = []
    for i, ts in enumerate(timestamps):
        if i >= len(closes) or closes[i] is None:
            continue
        day = datetime.fromtimestamp(int(ts), tz=timezone.utc).date().isoformat()
        vol = volumes[i] if i < len(volumes) and volumes[i] is not None else None
        rows.append({"date": day, "close": round(float(closes[i]), 4), "volume": vol})
    cache_set("prices", f"{symbol}_{range_code}", rows, output_dir=output_dir)
    return rows


def last_close(history: list[dict[str, Any]]) -> float | None:
    if not history:
        return None
    return float(history[-1]["close"])
