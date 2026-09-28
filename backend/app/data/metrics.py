"""Computed metrics. Code does the math; nothing here invents a number."""

from __future__ import annotations

import math
from typing import Any


def _latest(series: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    if not series:
        return None
    return series[-1]


def _val(series: list[dict[str, Any]] | None, index: int = -1) -> float | None:
    if not series or abs(index) > len(series):
        return None
    try:
        return float(series[index]["val"])
    except (KeyError, TypeError, ValueError):
        return None


def cagr(start: float | None, end: float | None, years: float) -> float | None:
    if start is None or end is None or start <= 0 or end <= 0 or years <= 0:
        return None
    return (end / start) ** (1 / years) - 1


def yoy(series: list[dict[str, Any]] | None) -> float | None:
    if not series or len(series) < 2:
        return None
    prev, cur = _val(series, -2), _val(series, -1)
    if prev is None or cur is None or prev == 0:
        return None
    return (cur - prev) / abs(prev)


def ratio(num: float | None, den: float | None) -> float | None:
    if num is None or den is None or den == 0:
        return None
    return num / den


def sma(values: list[float], window: int) -> float | None:
    if len(values) < window or window <= 0:
        return None
    return sum(values[-window:]) / window


def rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    gains = 0.0
    losses = 0.0
    for i in range(-period, 0):
        delta = closes[i] - closes[i - 1]
        if delta >= 0:
            gains += delta
        else:
            losses -= delta
    if losses == 0:
        return 100.0
    rs = (gains / period) / (losses / period)
    return 100 - (100 / (1 + rs))


def macd(closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> dict[str, float] | None:
    if len(closes) < slow + signal:
        return None

    def ema(vals: list[float], span: int) -> list[float]:
        k = 2 / (span + 1)
        out = [vals[0]]
        for price in vals[1:]:
            out.append(price * k + out[-1] * (1 - k))
        return out

    fast_line = ema(closes, fast)
    slow_line = ema(closes, slow)
    macd_line = [a - b for a, b in zip(fast_line, slow_line)]
    signal_line = ema(macd_line, signal)
    hist = macd_line[-1] - signal_line[-1]
    return {"macd": macd_line[-1], "signal": signal_line[-1], "hist": hist}


def max_drawdown(closes: list[float]) -> float | None:
    if not closes:
        return None
    peak = closes[0]
    worst = 0.0
    for price in closes:
        peak = max(peak, price)
        if peak > 0:
            worst = min(worst, (price - peak) / peak)
    return worst


def realized_vol(closes: list[float], window: int = 252) -> float | None:
    if len(closes) < 2:
        return None
    sample = closes[-window:] if len(closes) > window else closes
    rets = []
    for i in range(1, len(sample)):
        if sample[i - 1] > 0:
            rets.append(math.log(sample[i] / sample[i - 1]))
    if len(rets) < 10:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(252)


def correlation(a: list[float], b: list[float]) -> float | None:
    n = min(len(a), len(b))
    if n < 20:
        return None
    a, b = a[-n:], b[-n:]
    ma = sum(a) / n
    mb = sum(b) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    if va <= 0 or vb <= 0:
        return None
    return cov / math.sqrt(va * vb)


def business_metrics(fund: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    rev = fund.get("revenue") or []
    gp = fund.get("gross_profit") or []
    oi = fund.get("operating_income") or []
    ni = fund.get("net_income") or []
    ocf = fund.get("operating_cash_flow") or []
    capex = fund.get("capex") or []
    assets = fund.get("total_assets") or []
    equity = fund.get("equity") or []
    cash = fund.get("cash") or []
    ltd = fund.get("long_term_debt") or []
    std = fund.get("short_term_debt") or []

    revenue = _val(rev)
    fcf = None
    if _val(ocf) is not None and _val(capex) is not None:
        fcf = _val(ocf) - abs(_val(capex) or 0)
    net_debt = None
    if _val(ltd) is not None or _val(std) is not None:
        net_debt = ( _val(ltd) or 0) + (_val(std) or 0) - (_val(cash) or 0)

    five_start = _val(rev, -min(6, len(rev))) if len(rev) >= 2 else None
    five_years = min(len(rev) - 1, 5) if len(rev) >= 2 else None

    return {
        "revenue": revenue,
        "revenue_filed": (_latest(rev) or {}).get("filed"),
        "revenue_end": (_latest(rev) or {}).get("end"),
        "revenue_yoy": yoy(rev),
        "revenue_cagr_5y": cagr(five_start, revenue, five_years or 0) if five_years else None,
        "gross_margin": ratio(_val(gp), revenue),
        "operating_margin": ratio(_val(oi), revenue),
        "net_margin": ratio(_val(ni), revenue),
        "fcf": fcf,
        "fcf_margin": ratio(fcf, revenue),
        "net_debt": net_debt,
        "roe": ratio(_val(ni), _val(equity)),
        "roa": ratio(_val(ni), _val(assets)),
        "roic": ratio(_val(oi), (_val(equity) or 0) + (net_debt or 0) if (_val(equity) is not None) else None),
        "net_income": _val(ni),
        "operating_cash_flow": _val(ocf),
        "shares_diluted": _val(fund.get("shares_diluted")),
        "sbc": _val(fund.get("sbc")),
        "receivables": _val(fund.get("receivables")),
        "revenue_restated": bool((_latest(rev) or {}).get("restated")),
    }


def forensic_metrics(fund: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    ni = _val(fund.get("net_income"))
    ocf = _val(fund.get("operating_cash_flow"))
    sbc = _val(fund.get("sbc"))
    rev = fund.get("revenue") or []
    recv = fund.get("receivables") or []
    shares = fund.get("shares_diluted") or []
    cash_vs_earnings = None
    if ni is not None and ocf is not None and ni != 0:
        cash_vs_earnings = ocf / ni
    accruals = None
    if ni is not None and ocf is not None:
        accruals = ni - ocf
    sbc_pct = ratio(sbc, _val(rev))
    recv_yoy = yoy(recv)
    rev_yoy = yoy(rev)
    recv_vs_sales = None
    if recv_yoy is not None and rev_yoy is not None:
        recv_vs_sales = recv_yoy - rev_yoy
    dilution = yoy(shares)
    return {
        "cash_vs_earnings": cash_vs_earnings,
        "accruals": accruals,
        "sbc_pct_revenue": sbc_pct,
        "receivables_yoy_minus_sales_yoy": recv_vs_sales,
        "share_count_yoy": dilution,
        "notes": [
            n
            for n in [
                "Operating cash flow below net income" if cash_vs_earnings is not None and cash_vs_earnings < 0.8 else None,
                "Receivables growing faster than sales" if recv_vs_sales is not None and recv_vs_sales > 0.05 else None,
                "Share count rising (dilution)" if dilution is not None and dilution > 0.02 else None,
            ]
            if n
        ],
    }


def price_metrics(history: list[dict[str, Any]]) -> dict[str, Any]:
    closes = [float(r["close"]) for r in history if r.get("close") is not None]
    if not closes:
        return {}
    last = closes[-1]
    year = closes[-252:] if len(closes) >= 252 else closes
    return {
        "last": last,
        "asof": history[-1]["date"],
        "sma_50": sma(closes, 50),
        "sma_200": sma(closes, 200),
        "rsi_14": rsi(closes, 14),
        "macd": macd(closes),
        "high_52w": max(year),
        "low_52w": min(year),
        "max_drawdown": max_drawdown(closes),
        "vol_1y": realized_vol(closes, 252),
        "above_200dma": (sma(closes, 200) is not None and last > sma(closes, 200)),
    }


def valuation_metrics(
    fund: dict[str, list[dict[str, Any]]],
    last_price: float | None,
    shares: float | None = None,
) -> dict[str, Any]:
    ni = _val(fund.get("net_income"))
    ocf = _val(fund.get("operating_cash_flow"))
    capex = _val(fund.get("capex"))
    fcf = (ocf - abs(capex)) if ocf is not None and capex is not None else None
    share_count = shares or _val(fund.get("shares_diluted")) or _val(fund.get("shares_outstanding"))
    market_cap = (last_price * share_count) if last_price and share_count else None
    pe = ratio(market_cap, ni) if ni and ni > 0 else None
    fcf_yield = ratio(fcf, market_cap)
    ebitda = _val(fund.get("ebitda"))
    if ebitda is None:
        oi = _val(fund.get("operating_income"))
        dep = _val(fund.get("depreciation"))
        if oi is not None and dep is not None:
            ebitda = oi + abs(dep)
    cash = _val(fund.get("cash")) or 0
    debt = (_val(fund.get("long_term_debt")) or 0) + (_val(fund.get("short_term_debt")) or 0)
    ev = (market_cap + debt - cash) if market_cap is not None else None
    ev_ebitda = ratio(ev, ebitda) if ebitda and ebitda > 0 else None
    return {
        "market_cap": market_cap,
        "shares": share_count,
        "pe": pe,
        "fcf_yield": fcf_yield,
        "ev": ev,
        "ev_ebitda": ev_ebitda,
        "fcf": fcf,
    }
