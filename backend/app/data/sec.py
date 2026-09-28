"""SEC EDGAR: ticker→CIK, companyfacts (as-filed), submissions list."""

from __future__ import annotations

from typing import Any

from backend.app.data.cache import cache_get, cache_set
from backend.app.data.http import get_json, sec_data_headers, sec_headers
from backend.app.settings import get_settings

# Preferred tags in order. Companies pick different US-GAAP names for the same idea.
CONCEPTS: dict[str, list[str]] = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
    ],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"],
    "eps_diluted": ["EarningsPerShareDiluted", "EarningsPerShareBasic"],
    "cogs": ["CostOfRevenue", "CostOfGoodsAndServicesSold"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PurchaseOfPropertyAndEquipment",
    ],
    "total_assets": ["Assets"],
    "total_liabilities": ["Liabilities"],
    "equity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsAndShortTermInvestments"],
    "long_term_debt": ["LongTermDebtNoncurrent", "LongTermDebt"],
    "short_term_debt": ["LongTermDebtCurrent", "ShortTermBorrowings", "CommercialPaper"],
    "current_assets": ["AssetsCurrent"],
    "current_liabilities": ["LiabilitiesCurrent"],
    "shares_diluted": [
        "WeightedAverageNumberOfDilutedSharesOutstanding",
        "CommonStockSharesOutstanding",
    ],
    "shares_outstanding": ["CommonStockSharesOutstanding", "EntityCommonStockSharesOutstanding"],
    "sbc": ["ShareBasedCompensation"],
    "receivables": ["AccountsReceivableNetCurrent", "AccountsReceivableNet"],
    "inventory": ["InventoryNet"],
    "interest_expense": ["InterestExpense"],
    "ebitda": ["EarningsBeforeInterestTaxesDepreciationAndAmortization"],
    "depreciation": ["DepreciationDepletionAndAmortization", "Depreciation"],
}


def _ua() -> str:
    return get_settings().sec_user_agent


def pad_cik(cik: int | str) -> str:
    return str(int(cik)).zfill(10)


async def load_ticker_map(output_dir: str = "output") -> dict[str, dict[str, Any]]:
    cached = cache_get("sec", "company_tickers", ttl_s=24 * 3600, output_dir=output_dir)
    if cached is not None:
        return cached
    data = await get_json(
        "https://www.sec.gov/files/company_tickers.json",
        headers=sec_headers(_ua()),
        timeout=30.0,
    )
    mapping: dict[str, dict[str, Any]] = {}
    if isinstance(data, dict):
        for row in data.values():
            ticker = str(row.get("ticker") or "").upper()
            if ticker:
                mapping[ticker] = {
                    "cik": int(row["cik_str"]),
                    "cik_padded": pad_cik(row["cik_str"]),
                    "title": row.get("title") or "",
                    "ticker": ticker,
                }
    if mapping:
        cache_set("sec", "company_tickers", mapping, output_dir=output_dir)
    return mapping


async def resolve_cik(ticker: str, output_dir: str = "output") -> dict[str, Any] | None:
    symbol = (ticker or "").strip().upper()
    if not symbol:
        return None
    mapping = await load_ticker_map(output_dir)
    return mapping.get(symbol)


def _unit_rows(concept: dict[str, Any]) -> list[dict[str, Any]]:
    units = concept.get("units") or {}
    # Prefer USD, then USD/shares, then anything numeric.
    preferred = []
    for key in ("USD", "USD/shares", "shares", "pure"):
        if key in units:
            preferred.extend(units[key])
    if preferred:
        return preferred
    for rows in units.values():
        preferred.extend(rows)
    return preferred


def _is_annual(row: dict[str, Any]) -> bool:
    form = (row.get("form") or "").upper()
    fp = (row.get("fp") or "").upper()
    return form in {"10-K", "20-F", "40-F"} or fp == "FY"


def extract_series(facts: dict[str, Any], tags: list[str], annual: bool = True) -> list[dict[str, Any]]:
    """Return observations for the first tag that has data, stamped as-filed.

    Each item: {end, val, filed, form, fy, fp, accn, tag, first_filed, restated}.
    For a given period end we keep the earliest filing (first-reported) and the
    latest filing. The `val` is the latest reported number (useful for a live
    decision). `first_val` is what was first filed; restated is True when they differ.
    """
    us_gaap = ((facts.get("facts") or {}).get("us-gaap")) or {}
    dei = ((facts.get("facts") or {}).get("dei")) or {}
    chosen_tag = None
    raw: list[dict[str, Any]] = []
    for tag in tags:
        concept = us_gaap.get(tag) or dei.get(tag)
        if not concept:
            continue
        rows = _unit_rows(concept)
        if not rows:
            continue
        chosen_tag = tag
        raw = rows
        break
    if not raw:
        return []

    by_end: dict[str, list[dict[str, Any]]] = {}
    for row in raw:
        end = row.get("end")
        if not end or row.get("val") is None:
            continue
        if annual and not _is_annual(row):
            continue
        if not annual and _is_annual(row):
            continue
        by_end.setdefault(end, []).append(row)

    series: list[dict[str, Any]] = []
    for end, rows in sorted(by_end.items()):
        rows_sorted = sorted(rows, key=lambda r: r.get("filed") or "")
        first = rows_sorted[0]
        latest = rows_sorted[-1]
        first_val = float(first["val"])
        latest_val = float(latest["val"])
        series.append(
            {
                "end": end,
                "val": latest_val,
                "first_val": first_val,
                "filed": latest.get("filed"),
                "first_filed": first.get("filed"),
                "form": latest.get("form"),
                "fy": latest.get("fy"),
                "fp": latest.get("fp"),
                "accn": latest.get("accn"),
                "tag": chosen_tag,
                "restated": abs(first_val - latest_val) > max(1.0, abs(first_val) * 0.001),
            }
        )
    return series


async def fetch_companyfacts(cik: str | int, output_dir: str = "output") -> dict[str, Any] | None:
    padded = pad_cik(cik)
    cached = cache_get("sec", f"facts_{padded}", ttl_s=24 * 3600, output_dir=output_dir)
    if cached is not None:
        return cached
    data = await get_json(
        f"https://data.sec.gov/api/xbrl/companyfacts/CIK{padded}.json",
        headers=sec_data_headers(_ua()),
        timeout=40.0,
    )
    if not isinstance(data, dict):
        return None
    cache_set("sec", f"facts_{padded}", data, output_dir=output_dir)
    return data


async def fetch_submissions(cik: str | int, output_dir: str = "output") -> dict[str, Any] | None:
    padded = pad_cik(cik)
    cached = cache_get("sec", f"sub_{padded}", ttl_s=12 * 3600, output_dir=output_dir)
    if cached is not None:
        return cached
    data = await get_json(
        f"https://data.sec.gov/submissions/CIK{padded}.json",
        headers=sec_data_headers(_ua()),
        timeout=30.0,
    )
    if not isinstance(data, dict):
        return None
    cache_set("sec", f"sub_{padded}", data, output_dir=output_dir)
    return data


def list_filings(submissions: dict[str, Any], forms: set[str] | None = None, limit: int = 40) -> list[dict[str, Any]]:
    recent = (submissions.get("filings") or {}).get("recent") or {}
    names = recent.get("form") or []
    out: list[dict[str, Any]] = []
    wanted = {f.upper() for f in forms} if forms else None
    for i, form in enumerate(names):
        if wanted and form.upper() not in wanted and not any(form.upper().startswith(w) for w in wanted):
            continue
        accession = (recent.get("accessionNumber") or [""])[i]
        primary = (recent.get("primaryDocument") or [""])[i]
        out.append(
            {
                "form": form,
                "filed": (recent.get("filingDate") or [""])[i],
                "report_date": (recent.get("reportDate") or [""])[i],
                "accession": accession,
                "accession_nodash": accession.replace("-", ""),
                "primary": primary,
                "items": (recent.get("items") or [""])[i],
                "description": (recent.get("primaryDocDescription") or [""])[i],
            }
        )
        if len(out) >= limit:
            break
    return out


def extract_fundamentals(facts: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {name: extract_series(facts, tags, annual=True) for name, tags in CONCEPTS.items()}
