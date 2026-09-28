"""Simple DCF and reverse DCF. Code owns the arithmetic."""

from __future__ import annotations

from typing import Any


def project_fcf(base_fcf: float, growth_rates: list[float]) -> list[float]:
    """Year-by-year FCF. growth_rates[i] is the growth into year i+1."""
    out = []
    fcf = base_fcf
    for g in growth_rates:
        fcf = fcf * (1 + g)
        out.append(fcf)
    return out


def dcf_value(
    base_fcf: float,
    growth_rates: list[float],
    terminal_growth: float,
    discount_rate: float,
    shares: float,
    net_debt: float = 0.0,
) -> dict[str, Any] | None:
    """Gordon-growth terminal value after the explicit forecast.

    Returns None when inputs cannot produce a finite positive value.
    """
    if base_fcf <= 0 or shares <= 0 or discount_rate <= terminal_growth:
        return None
    fcfs = project_fcf(base_fcf, growth_rates)
    pv = 0.0
    for i, fcf in enumerate(fcfs, start=1):
        pv += fcf / ((1 + discount_rate) ** i)
    last = fcfs[-1] if fcfs else base_fcf * (1 + (growth_rates[0] if growth_rates else 0))
    tv = last * (1 + terminal_growth) / (discount_rate - terminal_growth)
    pv += tv / ((1 + discount_rate) ** max(len(fcfs), 1))
    equity = pv - net_debt
    price = equity / shares
    if price <= 0 or not (price == price):  # NaN guard
        return None
    return {
        "enterprise_value": pv,
        "equity_value": equity,
        "price": price,
        "fcf_path": fcfs,
        "terminal_value": tv,
        "assumptions": {
            "base_fcf": base_fcf,
            "growth_rates": growth_rates,
            "terminal_growth": terminal_growth,
            "discount_rate": discount_rate,
            "shares": shares,
            "net_debt": net_debt,
        },
    }


def default_growth_path(near_growth: float, years: int = 5) -> list[float]:
    """Fade linear from near_growth to 3% over `years`."""
    terminal_near = 0.03
    if years <= 1:
        return [near_growth]
    step = (near_growth - terminal_near) / (years - 1)
    return [near_growth - step * i for i in range(years)]


def reverse_dcf_growth(
    price: float,
    base_fcf: float,
    shares: float,
    discount_rate: float,
    terminal_growth: float = 0.03,
    years: int = 5,
    net_debt: float = 0.0,
) -> float | None:
    """Find the constant near-term growth that makes DCF price match the market.

    Binary search over growth from -20% to +80%. Returns None if no root.
    """
    if price <= 0 or base_fcf <= 0 or shares <= 0:
        return None

    def implied(g: float) -> float | None:
        result = dcf_value(base_fcf, default_growth_path(g, years), terminal_growth, discount_rate, shares, net_debt)
        return result["price"] if result else None

    lo, hi = -0.20, 0.80
    plo, phi = implied(lo), implied(hi)
    if plo is None or phi is None:
        return None
    # Need the market price to sit between the two ends.
    if not (min(plo, phi) <= price <= max(plo, phi)):
        # Still return the closer bound as a flagged estimate.
        return hi if abs(phi - price) < abs(plo - price) else lo
    for _ in range(40):
        mid = (lo + hi) / 2
        pm = implied(mid)
        if pm is None:
            return None
        if (plo <= price <= pm) or (pm <= price <= plo):
            hi, phi = mid, pm
        else:
            lo, plo = mid, pm
    return (lo + hi) / 2


def sensitivity_grid(
    base_fcf: float,
    near_growth: float,
    terminal_growth: float,
    discount_rate: float,
    shares: float,
    net_debt: float = 0.0,
) -> list[dict[str, Any]]:
    """3x3 grid around growth and discount rate."""
    rows = []
    for g in (near_growth - 0.03, near_growth, near_growth + 0.03):
        for r in (discount_rate - 0.01, discount_rate, discount_rate + 0.01):
            result = dcf_value(base_fcf, default_growth_path(g), terminal_growth, r, shares, net_debt)
            rows.append(
                {
                    "growth": g,
                    "discount": r,
                    "price": result["price"] if result else None,
                }
            )
    return rows


def scenario_prices(
    base_fcf: float,
    history_cagr: float | None,
    implied_growth: float | None,
    discount_rate: float,
    shares: float,
    net_debt: float = 0.0,
    last_price: float | None = None,
) -> dict[str, Any]:
    """Bear / base / bull from explicit growth assumptions, not from the model."""
    hist = history_cagr if history_cagr is not None else 0.05
    implied = implied_growth if implied_growth is not None else hist
    cases = {
        "bear": max(-0.05, hist - 0.05),
        "base": hist,
        "bull": max(hist, implied) + 0.03,
    }
    out: dict[str, Any] = {}
    for name, g in cases.items():
        result = dcf_value(base_fcf, default_growth_path(g), 0.03, discount_rate, shares, net_debt)
        out[name] = {
            "growth": g,
            "price": result["price"] if result else None,
        }
    if last_price:
        out["last_price"] = last_price
    out["implied_growth"] = implied_growth
    out["history_cagr"] = history_cagr
    out["discount_rate"] = discount_rate
    return out
