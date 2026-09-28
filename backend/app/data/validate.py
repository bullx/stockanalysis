"""Flag numbers in specialist notes that disagree with the fact sheet."""

from __future__ import annotations

import re
from typing import Any


def _sheet_numbers(sheet: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    q = sheet.get("quote") or {}
    if q.get("price"):
        out["last_price"] = float(q["price"])
    biz = sheet.get("business") or {}
    for key in ("gross_margin", "operating_margin", "net_margin", "revenue_yoy", "roe"):
        if biz.get(key) is not None:
            out[key] = float(biz[key])
    val = sheet.get("valuation") or {}
    if val.get("pe") is not None:
        out["pe"] = float(val["pe"])
    return out


def _extract_percents(text: str) -> list[float]:
    found = []
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*%", text):
        found.append(float(m.group(1)) / 100)
    return found


def _extract_multiples(text: str) -> list[float]:
    found = []
    for m in re.finditer(r"(?:P/?E|multiple)\D{0,12}(\d+(?:\.\d+)?)", text, re.I):
        found.append(float(m.group(1)))
    return found


def validate_note(text: str, sheet: dict[str, Any]) -> list[str]:
    """Return human-readable mismatch notes. Empty means nothing obvious clashed."""
    if not text or not sheet:
        return []
    flags: list[str] = []
    nums = _sheet_numbers(sheet)
    last = nums.get("last_price")
    if last:
        for m in re.finditer(r"\$\s?(\d{2,5}(?:\.\d+)?)", text):
            price = float(m.group(1))
            if price > 5 and (price / last < 0.4 or price / last > 2.5):
                flags.append(
                    f"Note cites ${price:.2f} vs fact-sheet last ${last:.2f} — likely a stale training-data price."
                )
                break
    for label, key in (("gross margin", "gross_margin"), ("operating margin", "operating_margin")):
        actual = nums.get(key)
        if actual is None:
            continue
        for pct in _extract_percents(text):
            if abs(pct - actual) > 0.15 and 0.01 < pct < 0.95:
                # Only flag if the sentence mentions the same margin type nearby — cheap heuristic.
                if label.split()[0] in text.lower():
                    flags.append(
                        f"{label.title()} in the note (~{pct:.0%}) is far from the fact sheet ({actual:.0%})."
                    )
                    break
    actual_pe = nums.get("pe")
    if actual_pe and 1 < actual_pe < 200:
        for pe in _extract_multiples(text):
            if 3 < pe < 200 and (pe / actual_pe < 0.5 or pe / actual_pe > 2):
                flags.append(f"P/E cited around {pe:.1f} vs fact-sheet {actual_pe:.1f}.")
                break
    return flags


def validate_round1(round1: dict[str, Any], sheet: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    for record in (round1 or {}).values():
        if record.get("error"):
            continue
        hits = validate_note(record.get("output") or "", sheet)
        if hits:
            name = record.get("agent_name") or record.get("agent_id")
            for h in hits:
                notes.append(f"{name}: {h}")
    return notes
