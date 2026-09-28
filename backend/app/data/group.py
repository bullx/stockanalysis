"""Price co-movement among names the user is watching. Not a customer relationship."""

from __future__ import annotations

from typing import Any

from backend.app.data.prices import fetch_history


def daily_returns(history: list[dict[str, Any]]) -> dict[str, float]:
    returns: dict[str, float] = {}
    previous = None
    for row in history:
        close = row.get("close")
        day = row.get("date")
        if close is None or not day:
            continue
        if previous:
            returns[str(day)] = (float(close) / previous) - 1
        previous = float(close)
    return returns


def pearson(left: dict[str, float], right: dict[str, float]) -> tuple[float | None, int]:
    days = sorted(set(left) & set(right))
    if len(days) < 40:
        return None, len(days)
    xs = [left[day] for day in days]
    ys = [right[day] for day in days]
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x <= 0 or var_y <= 0:
        return None, n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    return cov / (var_x ** 0.5 * var_y ** 0.5), n


async def moves_together(tickers: list[str], output_dir: str = "output") -> list[dict[str, Any]]:
    symbols = []
    seen = set()
    for ticker in tickers:
        symbol = (ticker or "").strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        symbols.append(symbol)
    if len(symbols) < 2:
        return []
    series = {symbol: daily_returns(await fetch_history(symbol, "2y", output_dir=output_dir)) for symbol in symbols}
    pairs = []
    for i, left in enumerate(symbols):
        for right in symbols[i + 1 :]:
            corr, days = pearson(series[left], series[right])
            pairs.append(
                {
                    "a": left,
                    "b": right,
                    "correlation": None if corr is None else round(corr, 2),
                    "days": days,
                    "moves_together": corr is not None and corr >= 0.7,
                }
            )
    pairs.sort(key=lambda row: row["correlation"] if row["correlation"] is not None else -1, reverse=True)
    return pairs
