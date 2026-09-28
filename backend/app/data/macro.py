"""FRED CSV series. No API key required for the graph CSV endpoint."""

from __future__ import annotations

from typing import Any

from backend.app.data.cache import cache_get, cache_set
from backend.app.data.http import get_text

SERIES = {
    "DGS10": "10-year Treasury yield",
    "FEDFUNDS": "Federal funds rate",
    "CPIAUCSL": "CPI (all urban, index)",
    "UNRATE": "Unemployment rate",
}


async def fetch_series(series_id: str, output_dir: str = "output") -> list[dict[str, Any]]:
    cached = cache_get("macro", series_id, ttl_s=24 * 3600, output_dir=output_dir)
    if cached is not None:
        return cached
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv"
    text = await get_text(url, headers={"User-Agent": "AureliaInvestments/1.0"}, params={"id": series_id})
    if not text:
        return []
    rows: list[dict[str, Any]] = []
    for line in text.splitlines()[1:]:
        parts = line.split(",")
        if len(parts) < 2:
            continue
        date, raw = parts[0].strip(), parts[1].strip()
        if raw in {"", ".", "NA"}:
            continue
        try:
            rows.append({"date": date, "value": float(raw)})
        except ValueError:
            continue
    if rows:
        cache_set("macro", series_id, rows, output_dir=output_dir)
    return rows


async def fetch_macro_snapshot(output_dir: str = "output") -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    for series_id, label in SERIES.items():
        rows = await fetch_series(series_id, output_dir=output_dir)
        if not rows:
            snapshot[series_id] = {"label": label, "value": None, "asof": None}
            continue
        last = rows[-1]
        snapshot[series_id] = {"label": label, "value": last["value"], "asof": last["date"]}
    return snapshot
