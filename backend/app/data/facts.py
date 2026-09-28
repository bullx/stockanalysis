"""Assemble a sourced fact sheet for one ticker."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.app.data.dcf import reverse_dcf_growth, scenario_prices
from backend.app.data.filings import build_filings_digest, format_filings_digest
from backend.app.data.peers import build_peer_table
from backend.app.data.macro import fetch_macro_snapshot
from backend.app.data.metrics import business_metrics, forensic_metrics, price_metrics, valuation_metrics
from backend.app.data.prices import fetch_history
from backend.app.data.sec import extract_fundamentals, fetch_companyfacts, fetch_submissions, resolve_cik
from backend.app.utils.market import fetch_quote

# SIC first-two-digits → sector ETF. Incomplete by design; unknown stays None.
SIC_TO_ETF = {
    "10": "XLE",
    "12": "XLE",
    "13": "XLE",
    "20": "XLP",
    "28": "XLV",
    "29": "XLE",
    "33": "XLB",
    "35": "XLI",
    "3571": "XLK",
    "3572": "XLK",
    "36": "XLK",
    "37": "XLY",
    "38": "XLV",
    "48": "XLC",
    "49": "XLU",
    "60": "XLF",
    "61": "XLF",
    "62": "XLF",
    "63": "XLF",
    "67": "XLRE",
    "73": "XLK",
}


def classify_coverage(ticker: str, cik: dict | None, quote: dict | None) -> str:
    qtype = (quote or {}).get("quote_type") or (quote or {}).get("type") or ""
    if qtype == "etf" or ticker.upper().endswith(("ETF",)):
        return "etf"
    if cik:
        return "us"
    return "non_us"


def _pct(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.{digits}f}%"


def _num(value: float | None, money: bool = False) -> str:
    if value is None:
        return "n/a"
    if money:
        abs_v = abs(value)
        if abs_v >= 1e12:
            return f"${value / 1e12:.2f}T"
        if abs_v >= 1e9:
            return f"${value / 1e9:.2f}B"
        if abs_v >= 1e6:
            return f"${value / 1e6:.2f}M"
        return f"${value:,.0f}"
    return f"{value:,.2f}"


def _stamp(metric: dict[str, Any], key: str) -> str:
    filed = metric.get(f"{key}_filed") or metric.get("revenue_filed")
    end = metric.get(f"{key}_end") or metric.get("revenue_end")
    bits = []
    if end:
        bits.append(f"period {end}")
    if filed:
        bits.append(f"filed {filed}")
    return f" ({', '.join(bits)})" if bits else ""


async def build_fact_sheet(
    ticker: str,
    output_dir: str = "output",
    include_filings: bool = True,
) -> dict[str, Any]:
    symbol = (ticker or "").strip().upper()
    quote = await fetch_quote(symbol)
    history = await fetch_history(symbol, output_dir=output_dir)
    cik = await resolve_cik(symbol, output_dir=output_dir)
    coverage = classify_coverage(symbol, cik, quote)

    facts = None
    submissions = None
    fund: dict[str, list] = {}
    filings_digest = None
    sic = None
    sic_desc = None
    entity = None

    if cik:
        facts = await fetch_companyfacts(cik["cik"], output_dir=output_dir)
        submissions = await fetch_submissions(cik["cik"], output_dir=output_dir)
        if facts:
            fund = extract_fundamentals(facts)
            entity = facts.get("entityName")
        if submissions:
            sic = submissions.get("sic")
            sic_desc = submissions.get("sicDescription")
            if include_filings:
                filings_digest = await build_filings_digest(cik["cik"], submissions, output_dir=output_dir)

    biz = business_metrics(fund) if fund else {}
    forensic = forensic_metrics(fund) if fund else {}
    price = price_metrics(history)
    last = (quote or {}).get("price") or price.get("last")
    val = valuation_metrics(fund, last) if fund else {}
    macro = await fetch_macro_snapshot(output_dir=output_dir)

    discount = 0.09
    ten_year = (macro.get("DGS10") or {}).get("value")
    if ten_year:
        discount = max(0.06, min(0.14, ten_year / 100 + 0.045))

    implied = None
    scenarios = None
    if val.get("fcf") and val["fcf"] > 0 and val.get("shares") and last:
        implied = reverse_dcf_growth(
            last,
            val["fcf"],
            val["shares"],
            discount,
            net_debt=biz.get("net_debt") or 0,
        )
        scenarios = scenario_prices(
            val["fcf"],
            biz.get("revenue_cagr_5y"),
            implied,
            discount,
            val["shares"],
            net_debt=biz.get("net_debt") or 0,
            last_price=last,
        )

    sector_etf = None
    if sic:
        code = str(sic)
        sector_etf = SIC_TO_ETF.get(code) or SIC_TO_ETF.get(code[:4]) or SIC_TO_ETF.get(code[:2])

    latest_filing = None
    if filings_digest:
        latest_filing = filings_digest.get("latest_filing")

    peers = []
    if include_filings and sic and cik:
        peers = await build_peer_table(
            symbol,
            sic,
            cik.get("cik"),
            biz,
            val,
            company=entity or (cik or {}).get("title") or "",
            output_dir=output_dir,
        )

    sheet = {
        "ticker": symbol,
        "company": entity or (cik or {}).get("title") or (quote or {}).get("name") or "",
        "coverage": coverage,
        "quote": quote,
        "history": history[-320:],  # ~1.2 years for the chart; full series stays in cache
        "history_points": len(history),
        "cik": cik,
        "sic": sic,
        "sic_description": sic_desc,
        "sector_etf": sector_etf,
        "business": biz,
        "forensic": forensic,
        "valuation": val,
        "price": price,
        "macro": macro,
        "dcf": {
            "discount_rate": discount,
            "implied_growth": implied,
            "scenarios": scenarios,
        },
        "filings": filings_digest,
        "peers": peers,
        "latest_filing": latest_filing,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "price": "Yahoo Finance chart (unofficial)",
            "fundamentals": "SEC EDGAR companyfacts" if facts else None,
            "filings": "SEC EDGAR submissions + documents" if filings_digest else None,
            "macro": "FRED",
        },
    }
    sheet["prompt"] = format_fact_sheet(sheet)
    return sheet


def format_fact_sheet(sheet: dict[str, Any]) -> str:
    coverage = sheet.get("coverage")
    lines = [
        "FACT SHEET — numbers below are computed in code from the named source.",
        "Do not invent a different last price, revenue, margin, or multiple.",
        "If a field is n/a, say so. Do not fill gaps from memory.",
        f"Coverage: {coverage} "
        + {
            "us": "(US filer — financials and filings are real)",
            "non_us": "(no SEC financials — price history only; do not invent fundamentals)",
            "etf": "(ETF — no company financials; price history only)",
        }.get(coverage, ""),
        f"Ticker: {sheet.get('ticker')}  Company: {sheet.get('company') or 'n/a'}",
    ]
    if sheet.get("sic"):
        lines.append(f"SIC {sheet['sic']} — {sheet.get('sic_description') or ''}  Sector ETF: {sheet.get('sector_etf') or 'n/a'}")

    q = sheet.get("quote") or {}
    p = sheet.get("price") or {}
    if q.get("price") is not None:
        lines.append(
            f"LAST PRICE (Yahoo, fact): ${q['price']:.2f} {q.get('currency', 'USD')} as of {q.get('asof')}"
        )
    if p:
        lines.append(
            f"PRICE HISTORY (Yahoo, {sheet.get('history_points', 0)} daily bars): "
            f"50DMA {_num(p.get('sma_50'))} · 200DMA {_num(p.get('sma_200'))} · "
            f"RSI(14) {_num(p.get('rsi_14'))} · 52w {_num(p.get('low_52w'))}–{_num(p.get('high_52w'))} · "
            f"max drawdown {_pct(p.get('max_drawdown'))} · vol {_pct(p.get('vol_1y'))}"
        )
        macd = p.get("macd") or {}
        if macd:
            lines.append(f"MACD: line {_num(macd.get('macd'))} / signal {_num(macd.get('signal'))} / hist {_num(macd.get('hist'))}")

    biz = sheet.get("business") or {}
    if biz.get("revenue") is not None:
        lines.append("BUSINESS (SEC companyfacts, annual, latest reported; first-filed kept if restated):")
        lines.append(
            f"- Revenue {_num(biz.get('revenue'), True)}{_stamp(biz, 'revenue')}  "
            f"YoY {_pct(biz.get('revenue_yoy'))}  5y CAGR {_pct(biz.get('revenue_cagr_5y'))}"
            + ("  [restated vs first filing]" if biz.get("revenue_restated") else "")
        )
        lines.append(
            f"- Margins: gross {_pct(biz.get('gross_margin'))} · operating {_pct(biz.get('operating_margin'))} · "
            f"net {_pct(biz.get('net_margin'))}"
        )
        lines.append(
            f"- FCF {_num(biz.get('fcf'), True)} (OCF minus |capex|) · FCF margin {_pct(biz.get('fcf_margin'))} · "
            f"net debt {_num(biz.get('net_debt'), True)}"
        )
        lines.append(
            f"- Returns: ROE {_pct(biz.get('roe'))} · ROA {_pct(biz.get('roa'))} · ROIC {_pct(biz.get('roic'))}"
        )
    elif coverage == "us":
        lines.append("BUSINESS: SEC facts downloaded but required tags were missing. Do not invent revenue or margins.")

    val = sheet.get("valuation") or {}
    if val.get("market_cap"):
        lines.append(
            f"VALUATION (price × diluted shares from SEC): cap {_num(val.get('market_cap'), True)} · "
            f"P/E {_num(val.get('pe'))} · EV/EBITDA {_num(val.get('ev_ebitda'))} · "
            f"FCF yield {_pct(val.get('fcf_yield'))}"
        )

    dcf = sheet.get("dcf") or {}
    if dcf.get("implied_growth") is not None:
        lines.append(
            f"WHAT THE PRICE IMPLIES (reverse DCF, code): "
            f"discount { _pct(dcf.get('discount_rate')) }. "
            f"Market price is consistent with ~{_pct(dcf['implied_growth'])} near-term FCF growth "
            f"fading to 3% over 5 years. History 5y revenue CAGR {_pct((sheet.get('business') or {}).get('revenue_cagr_5y'))}. "
            "State whether you believe that implied growth."
        )
        sc = dcf.get("scenarios") or {}
        if sc.get("base"):
            lines.append(
                "DCF SCENARIOS (code, from history CAGR ±, not a forecast): "
                + " · ".join(
                    f"{name} g={_pct((sc.get(name) or {}).get('growth'))} -> {_num((sc.get(name) or {}).get('price'), True)}"
                    for name in ("bear", "base", "bull")
                    if sc.get(name)
                )
            )

    forensic = sheet.get("forensic") or {}
    if forensic:
        lines.append(
            f"FORENSIC (code): cash/earnings {_num(forensic.get('cash_vs_earnings'))} · "
            f"SBC/revenue {_pct(forensic.get('sbc_pct_revenue'))} · "
            f"share-count YoY {_pct(forensic.get('share_count_yoy'))} · "
            f"receivables YoY minus sales YoY {_pct(forensic.get('receivables_yoy_minus_sales_yoy'))}"
        )
        if forensic.get("notes"):
            for n in forensic["notes"]:
                lines.append(f"  ! {n}")

    macro = sheet.get("macro") or {}
    bits = []
    for key in ("DGS10", "FEDFUNDS", "CPIAUCSL", "UNRATE"):
        row = macro.get(key) or {}
        if row.get("value") is not None:
            bits.append(f"{row['label']} {row['value']} as of {row.get('asof')}")
    if bits:
        lines.append("MACRO (FRED): " + " · ".join(bits))

    peers = sheet.get("peers") or []
    if len(peers) > 1:
        lines.append("PEERS (same SEC industry code, multiples computed in code — not a model guess):")
        for row in peers:
            lines.append(
                f"- {row.get('ticker')} P/E {_num(row.get('pe'))} · EV/EBITDA {_num(row.get('ev_ebitda'))} · "
                f"operating margin {_pct(row.get('operating_margin'))} · FCF yield {_pct(row.get('fcf_yield'))}"
            )
    elif sheet.get("sic"):
        lines.append("PEERS: no other same-SIC company was resolved. Do not invent a peer multiple.")

    if sheet.get("filings"):
        lines.append("")
        lines.append(format_filings_digest(sheet["filings"]))

    latest = sheet.get("latest_filing")
    built = sheet.get("built_at", "")[:10]
    lines.append(
        f"FRESHNESS: fact sheet built {built}; last price as of {(q or {}).get('asof') or 'n/a'}; "
        f"latest filing {(latest or {}).get('form', 'n/a')} {(latest or {}).get('filed', '')}"
    )
    return "\n".join(lines)
