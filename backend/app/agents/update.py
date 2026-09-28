"""One short call that writes a delta note. It does not re-run the council."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.app.utils.llm import call_llm_with_retry
from backend.app.utils.parse import extract_and_parse_json

UPDATE_SYSTEM = """You are the Update Analyst. You read an old brief and only what changed since it was written.
You do not re-analyze the whole company. You answer whether the new facts change the thesis.

Output ONLY valid JSON:
{
  "thesis_changed": false,
  "note": "two or three sentences on what changed and whether it matters",
  "verdict": "STRONG BUY | BUY | HOLD | AVOID | STRONG AVOID",
  "conviction": 1-10,
  "summary": "two sentences a reader can use as the new brief"
}

If the packet does not show a material change, keep the old verdict and set thesis_changed to false.
Do not invent a filing, a price, or a metric that is not in the packet.
Do not recommend a portfolio percentage."""


def update_packet(report: dict[str, Any], status: dict[str, Any]) -> str:
    sell_if = report.get("sell_if") or []
    lines = [
        f"Ticker: {report.get('ticker')}",
        f"Brief date: {report.get('generated_at')}",
        f"Old verdict: {report.get('verdict')} conviction {report.get('conviction')}",
        f"Old summary: {report.get('summary')}",
        f"Price at the brief: {report.get('last_price')}",
        f"Bear / base / bull: {report.get('price_target_bear')} / {report.get('price_target_base')} / {report.get('price_target_bull')}",
        f"Change check: {status.get('banner') or 'No material price move, new filing, or tripped condition.'}",
    ]
    if status.get("price") is not None:
        lines.append(f"Price now: {status['price']}")
    filing = status.get("new_filing")
    if filing:
        lines.append(f"New filing: {filing.get('form')} filed {filing.get('filed')}")
    if sell_if:
        lines.append("Checkable conditions written on the old brief:")
        for condition in sell_if:
            lines.append(f"- {condition.get('label')}")
    tripped = status.get("tripped") or []
    if tripped:
        lines.append("Conditions that are true now: " + "; ".join(item.get("label") or "" for item in tripped))
    return "\n".join(lines)


def apply_update(report: dict[str, Any], parsed: dict[str, Any], status: dict[str, Any], old_id: str) -> dict[str, Any]:
    verdict = str(parsed.get("verdict") or report.get("verdict") or "HOLD").upper()
    try:
        conviction = int(parsed.get("conviction") or report.get("conviction") or 5)
    except (TypeError, ValueError):
        conviction = int(report.get("conviction") or 5)
    conviction = max(1, min(10, conviction))
    updated = dict(report)
    updated["verdict"] = verdict
    updated["conviction"] = conviction
    updated["summary"] = str(parsed.get("summary") or report.get("summary") or "")
    updated["title"] = report.get("title") or "Update"
    updated["update_note"] = str(parsed.get("note") or "").strip()
    updated["thesis_changed"] = bool(parsed.get("thesis_changed"))
    updated["kind"] = "update"
    updated["supersedes"] = old_id
    updated["generated_at"] = datetime.now(timezone.utc).isoformat()
    updated["last_price"] = status.get("price") or report.get("last_price")
    updated.pop("id", None)
    return updated


async def run_update(report: dict[str, Any], status: dict[str, Any], old_id: str, llm_opts: dict) -> dict[str, Any]:
    raw = await call_llm_with_retry(
        UPDATE_SYSTEM,
        update_packet(report, status),
        500,
        options=llm_opts,
    )
    parsed = extract_and_parse_json(raw) or {}
    if not parsed and raw:
        parsed = {"note": raw.strip()[:800], "thesis_changed": False}
    updated = apply_update(report, parsed, status, old_id)
    note = updated.get("update_note") or ""
    round1 = {
        "update": {
            "agent_id": "update",
            "agent_name": "Update Analyst",
            "tag": "Delta note",
            "output": note,
            "conviction": updated["conviction"],
            "stance": updated["verdict"],
            "timestamp": updated["generated_at"],
        }
    }
    return {"report": updated, "round1": round1, "raw": raw}
