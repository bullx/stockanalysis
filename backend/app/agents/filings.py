"""Round 0 readers. They see the code diff and Exhibit 99.1 excerpts, never a full 10-K."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Awaitable, Callable

from backend.app.data.cache import cache_get, cache_set
from backend.app.utils.llm import _fatal_llm_error, call_llm_with_retry

Emit = Callable[[dict], Awaitable[None]]

READER_VERSION = "1"

FILINGS_SYSTEM = """You are the Filings Analyst. You read only the extracted diff in the user message. You do not browse and you do not recall other filings.

First line, exactly one of:
FILINGS: Improving
FILINGS: Stable
FILINGS: Deteriorating

Then at most six bullets. Each bullet cites the form, date, and section that appear in the packet (Risk Factors, MD&A, 8-K item, Form 4). Cover what changed, new risks, red flags, and insider net shares. If a section says it was not found, say that. Do not invent a quote, a number, or a filing that is not in the packet."""

EARNINGS_SYSTEM = """You are the Earnings Analyst. You read only the Exhibit 99.1 excerpts in the user message.

First line, exactly one of:
EARNINGS: Beat and raise
EARNINGS: In line
EARNINGS: Miss or cut
EARNINGS: Not stated

Use Beat and raise, In line, or Miss or cut only when the excerpts themselves compare results to a prior outlook or say guidance was raised, reaffirmed, or cut. If the excerpts only list a forward outlook with no comparison, use Not stated. If there are no excerpts, use Not stated.

Then at most five bullets. Quote the figure and the filing date from the packet. Do not invent a beat, a miss, or a consensus number."""


def _clip(text: str, limit: int = 1600) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "…"


def _clip_para(text: str, limit: int = 360) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    return text[:limit]


def filings_reader_packet(digest: dict[str, Any]) -> str:
    """Diff, red flags, 8-K codes, and Form 4 net. Full filing text is ignored."""
    lines = ["Use only the lines below. This is a diff, not the full filing."]
    latest = digest.get("latest_annual") or digest.get("latest_quarterly") or digest.get("latest_filing") or {}
    if latest:
        lines.append(
            f"Latest {latest.get('form')} filed {latest.get('filed')} accession {latest.get('accession')}"
        )
    for label, key in (("Risk Factors (Item 1A)", "risk_diff"), ("MD&A (Item 7)", "mda_diff")):
        block = digest.get(key) or {}
        lines.append(f"{label}:")
        if block.get("note"):
            lines.append(f"  note: {block['note']}")
        added = block.get("added") or []
        removed = block.get("removed") or []
        if not added and not removed and not block.get("note"):
            lines.append("  not found")
        for para in added[:4]:
            lines.append(f"  added: {_clip_para(para)}")
        for para in removed[:3]:
            lines.append(f"  removed: {_clip_para(para)}")
    flags = digest.get("red_flags") or []
    if flags:
        lines.append("Red-flag scan:")
        for flag in flags[:6]:
            lines.append(
                f"  [{flag.get('source')}] {flag.get('phrase')}: {_clip_para(flag.get('snippet') or '', 180)}"
            )
    else:
        lines.append("Red-flag scan: none of the watched phrases.")
    for event in (digest.get("eight_k") or [])[:6]:
        lines.append(f"8-K {event.get('filed')} items {event.get('items') or 'n/a'}")
    insider = digest.get("insider_90d") or {}
    lines.append(
        f"Form 4 sample ({insider.get('forms', 0)} filings): "
        f"bought {insider.get('bought', 0):,.0f} sold {insider.get('sold', 0):,.0f} "
        f"net {insider.get('net', 0):,.0f}"
    )
    return "\n".join(lines)


def earnings_reader_packet(digest: dict[str, Any]) -> str:
    lines = ["Use only the excerpts below. Do not add figures from memory."]
    earn = digest.get("earnings_8k") or {}
    if earn:
        lines.append(f"Item 2.02 8-K filed {earn.get('filed')} accession {earn.get('accession')}")
    if digest.get("guidance_source"):
        lines.append(f"Source: {digest['guidance_source']}")
    if digest.get("guidance_note"):
        lines.append(str(digest["guidance_note"]))
    excerpts = digest.get("guidance") or []
    if not excerpts:
        lines.append("No guidance excerpts were extracted.")
    for index, excerpt in enumerate(excerpts[:6], start=1):
        lines.append(f"{index}. {_clip_para(excerpt, 480)}")
    return "\n".join(lines)


def _has_diff(digest: dict[str, Any]) -> bool:
    for key in ("risk_diff", "mda_diff"):
        block = digest.get(key) or {}
        if block.get("added") or block.get("removed"):
            return True
    return False


def _packet_fingerprint(digest: dict[str, Any]) -> str:
    chunks: list[str] = []
    for key in ("risk_diff", "mda_diff"):
        block = digest.get(key) or {}
        chunks.extend(block.get("added") or [])
        chunks.extend(block.get("removed") or [])
    chunks.extend(digest.get("guidance") or [])
    raw = "\n".join(chunks)
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:12]


def _cache_key(digest: dict[str, Any], tier_name: str, model: str) -> str:
    latest = digest.get("latest_annual") or digest.get("latest_quarterly") or digest.get("latest_filing") or {}
    annual = latest.get("accession") or "none"
    earn = (digest.get("earnings_8k") or {}).get("accession") or "none"
    safe_model = re.sub(r"[^A-Za-z0-9._-]+", "_", model)[:80]
    return f"v{READER_VERSION}_{tier_name}_{safe_model}_{annual}_{earn}_{_packet_fingerprint(digest)}"


async def _read(system: str, user: str, max_tokens: int, llm_opts: dict) -> str:
    gate = llm_opts.get("gate")
    if gate:
        gate.raise_if_stopped()
    return await call_llm_with_retry(system, user, max_tokens, options=llm_opts)


async def run_filing_readers(
    digest: dict[str, Any] | None,
    ticker: str,
    tier_name: str,
    llm_opts: dict,
    emit: Emit,
    output_dir: str = "output",
) -> str:
    """Paste-ready notes for the other seats. Skips the model when there is nothing to read."""
    if not digest:
        return ""
    model = str(llm_opts.get("model") or "model")
    cached = cache_get("filings_reader", _cache_key(digest, tier_name, model), ttl_s=0, output_dir=output_dir)
    if isinstance(cached, str) and cached.strip():
        return cached

    want_filings = tier_name != "tier3" and _has_diff(digest)
    want_earnings = bool(digest.get("guidance"))
    if not want_filings and not want_earnings:
        lines = []
        if tier_name == "tier3":
            lines.append("FILINGS READER: skipped on a small model. Use the red-flag scan in the code digest.")
        else:
            lines.append(
                "FILINGS READER: no Risk Factors or MD&A diff was extracted, so the model was not asked to read a filing."
            )
        note = digest.get("guidance_note") or "No Exhibit 99.1 guidance excerpts were extracted."
        lines.append(f"EARNINGS READER: {note} The model was not asked to invent a beat or a miss.")
        return "\n\n".join(lines)

    await emit({"type": "filings.started", "ticker": ticker})
    parts: list[str] = []
    failed = False
    try:
        if tier_name == "tier3":
            parts.append("FILINGS READER: skipped on a small model. Use the red-flag scan in the code digest.")
        elif want_filings:
            try:
                raw = await _read(
                    FILINGS_SYSTEM,
                    f"Ticker: {ticker}\n\n{filings_reader_packet(digest)}",
                    500,
                    llm_opts,
                )
                parts.append(
                    "FILINGS READER (model, filing diff only — not a source document):\n" + _clip(raw)
                )
            except Exception as exc:  # noqa: BLE001
                if _fatal_llm_error(exc):
                    raise
                failed = True
                parts.append(f"FILINGS READER: model call failed ({exc}). Use the code digest.")
        else:
            parts.append(
                "FILINGS READER: no Risk Factors or MD&A diff was extracted, so the model was not asked to read a filing."
            )

        if want_earnings:
            try:
                raw = await _read(
                    EARNINGS_SYSTEM,
                    f"Ticker: {ticker}\n\n{earnings_reader_packet(digest)}",
                    450,
                    llm_opts,
                )
                parts.append(
                    "EARNINGS READER (model, Exhibit 99.1 excerpts only — not a source document):\n" + _clip(raw)
                )
            except Exception as exc:  # noqa: BLE001
                if _fatal_llm_error(exc):
                    raise
                failed = True
                parts.append(f"EARNINGS READER: model call failed ({exc}). Use the guidance excerpts above.")
        else:
            note = digest.get("guidance_note") or "No Exhibit 99.1 guidance excerpts were extracted."
            parts.append(f"EARNINGS READER: {note} The model was not asked to invent a beat or a miss.")
    finally:
        await emit({"type": "filings.ready", "ticker": ticker})

    text = "\n\n".join(parts).strip()
    if text and not failed:
        cache_set("filings_reader", _cache_key(digest, tier_name, model), text, output_dir=output_dir)
    return text
