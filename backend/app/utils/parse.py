import json
import re
from typing import Any

from backend.app.data.watch import normalize_conditions


def extract_and_parse_json(raw_text: str) -> dict[str, Any]:
    text = (raw_text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    block = re.search(r"\{[\s\S]*\}", text)
    if block:
        try:
            return json.loads(block.group(0))
        except json.JSONDecodeError:
            pass

    stripped = re.sub(r"```json\s*", "", text, flags=re.I)
    stripped = re.sub(r"```\s*", "", stripped).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    candidate = (
        re.sub(r"```json", "", text, flags=re.I)
        .replace("```", "")
    )
    candidate = re.sub(r",\s*}", "}", candidate)
    candidate = re.sub(r",\s*]", "]", candidate)
    candidate = re.sub(
        r"(['\"]?)([A-Za-z_][A-Za-z0-9_]*)(['\"]?):",
        r'"\2":',
        candidate,
    )
    candidate = re.sub(r":\s*'([^']*)'", r': "\1"', candidate)
    candidate = candidate.replace("\n", " ")
    match = re.search(r"\{[\s\S]*\}", candidate)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return extract_key_value_fallback(text)


def extract_key_value_fallback(text: str) -> dict[str, Any]:
    def extract(pattern: str, default: str) -> str:
        m = re.search(pattern, text, re.I)
        return m.group(1).strip() if m else default

    return {
        "ticker": extract(r"ticker[:\s]+([A-Z]{1,5})", "UNKNOWN"),
        "company_name": extract(r"company[:\s]+(.+)", "Unknown"),
        "verdict": extract(
            r"verdict[:\s]+(STRONG BUY|BUY|HOLD|AVOID|STRONG AVOID)", "HOLD"
        ),
        "title": extract(r"title[:\s]+(.+)", "Analysis complete"),
        "summary": extract(r"summary[:\s]+(.{20,300})", text[:200]),
        "conviction": int(extract(r"conviction[:\s]+(\d+)", "5") or 5),
        "price_target_base": extract(r"(?:base|target)[:\s]+(\$[\d,]+)", "N/A"),
        "price_target_bull": extract(r"bull[:\s]+(\$[\d,]+)", "N/A"),
        "price_target_bear": extract(r"bear[:\s]+(\$[\d,]+)", "N/A"),
        "implied_upside_base": extract(r"upside[:\s]+([+-]?\d+%)", "N/A"),
        "risk_level": extract(r"risk level[:\s]+(Low|Moderate|High|Very High)", "Moderate"),
        "horizon": extract(r"horizon[:\s]+(Short-term|Medium-term|Long-term|Short|Medium|Long)", "Medium-term"),
        "consensus_score": int(extract(r"consensus[:\s]+(\d+)", "5") or 5),
        "scenarios": [],
        "catalysts": [],
        "risks": [],
        "financial_health": [],
        "predictability_scores": [],
        "position_sizing": {
            "aggressive_investor": "N/A",
            "moderate_investor": "N/A",
            "conservative_investor": "N/A",
            "sizing_rationale": "Extraction fallback — review manually",
        },
        "investment_strategy": [text[:500]],
        "thesis_invalidators": [],
        "data_quality_notes": (
            "WARNING: JSON extraction failed — key-value fallback used. "
            "Consider a Tier 1 or Tier 2 model."
        ),
    }


def strip_think(text: str) -> str:
    return re.sub(r"<think>[\s\S]*?</think>", "", text or "", flags=re.I).strip()


def unwrap_markup(text: str) -> str:
    cleaned = strip_think(text)
    cleaned = re.sub(r"\*\*(.+?)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"__(.+?)__", r"\1", cleaned)
    cleaned = re.sub(r"^#{1,3}\s*", "", cleaned, flags=re.M)
    return cleaned.strip()


def try_parse_object(text: str) -> dict[str, Any] | None:
    cleaned = strip_think(text)
    for candidate in (cleaned,):
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
    block = re.search(r"\{[\s\S]*\}", cleaned)
    if block:
        try:
            obj = json.loads(block.group(0))
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
    return None


def parse_price_number(value: Any) -> float | None:
    if value is None:
        return None
    match = re.search(r"[\d]+(?:\.\d+)?", str(value).replace(",", ""))
    if not match:
        return None
    try:
        number = float(match.group(0))
    except ValueError:
        return None
    return number if number > 0 else None


def implied_upside(last_price: Any, target: Any) -> str | None:
    last = parse_price_number(last_price)
    tgt = parse_price_number(target)
    if not last or not tgt:
        return None
    return f"{((tgt - last) / last) * 100:+.1f}%"


def parse_agent_output(text: str) -> dict[str, Any]:
    display = strip_think(text)
    raw = unwrap_markup(text)
    obj = try_parse_object(raw)
    if obj and any(k in obj for k in ("conviction", "stance", "analysis", "output", "note")):
        stance = (
            obj.get("stance")
            or obj.get("outlook")
            or obj.get("valuation")
            or obj.get("thesis")
            or "unknown"
        )
        body = obj.get("output") or obj.get("analysis") or obj.get("note") or display
        try:
            conviction = int(obj.get("conviction") or 5)
        except (TypeError, ValueError):
            conviction = 5
        return {
            "output": str(body).strip(),
            "conviction": max(1, min(10, conviction)),
            "stance": str(stance).strip().splitlines()[0][:80] or "unknown",
        }

    conviction_match = re.search(
        r"^(?:BEAR CASE )?CONVICTION\s*:?\s*(\d+)", raw, re.I | re.M
    ) or re.search(r"\b(\d{1,2})\s*/\s*10\b", raw)
    stance_match = re.search(
        r"^(?:BEAR CASE )?(STANCE|OUTLOOK|VALUATION|MOAT|BIAS|SENTIMENT|RISK LEVEL|ESG PROFILE|"
        r"MACRO STANCE|FUNDAMENTAL STANCE|GROWTH OUTLOOK|TECHNICAL BIAS)\s*:\s*(.+)$",
        raw,
        re.I | re.M,
    )
    stance = ""
    if stance_match:
        stance = re.sub(r"\*+", "", stance_match.group(2)).strip().splitlines()[0][:80]
    if not stance and re.search(r"^PRIMARY BEAR THESIS\s*:", raw, re.I | re.M):
        stance = "BEAR CASE"
    if not stance:
        prose = re.search(r"ESG PROFILE IS\s+\**([A-Za-z]+)", raw, re.I)
        if prose:
            stance = prose.group(1).strip()
    if not stance:
        stance = "incomplete"
    conviction = int(conviction_match.group(1)) if conviction_match else 5
    return {
        "output": display,
        "conviction": max(1, min(10, conviction)),
        "stance": stance,
    }


def debate_has_structure(debate: dict[str, Any] | None) -> bool:
    if not debate:
        return False
    return bool(
        debate.get("strongest_bull")
        or debate.get("strongest_bear")
        or debate.get("swing_factor")
        or debate.get("consensus_points")
        or debate.get("key_disagreements")
        or debate.get("unresolved_questions")
    )


def debate_is_empty(debate: dict[str, Any]) -> bool:
    return not debate_has_structure(debate) and not (debate.get("raw_text") or "").strip()


def parse_debate_output(raw: str) -> dict[str, Any]:
    original = strip_think(raw)
    text = unwrap_markup(raw)
    obj = try_parse_object(text)
    if obj and any(
        k in obj for k in ("consensus_points", "strongest_bull", "strongest_bear", "swing_factor")
    ):
        return {
            "consensus_points": list(obj.get("consensus_points") or [])[:5],
            "key_disagreements": list(obj.get("key_disagreements") or [])[:5],
            "strongest_bull": str(obj.get("strongest_bull") or "").strip(),
            "strongest_bear": str(obj.get("strongest_bear") or "").strip(),
            "swing_factor": str(obj.get("swing_factor") or "").strip().split("\n")[0],
            "unresolved_questions": list(obj.get("unresolved_questions") or [])[:5],
            "consensus_score": int(obj.get("consensus_score") or 5),
            "raw_text": original,
        }

    markers = [
        "CONSENSUS POINTS",
        "KEY DISAGREEMENTS",
        "STRONGEST BULL THESIS",
        "STRONGEST BEAR THESIS",
        "SWING FACTOR",
        "UNRESOLVED QUESTIONS",
        "CONSENSUS SCORE",
    ]
    lookahead = "|".join(re.escape(m) for m in markers)

    def section(header: str) -> str:
        m = re.search(
            rf"{re.escape(header)}\s*:?\s*\n([\s\S]*?)(?=\n(?:{lookahead})\b|$)",
            text,
            re.I,
        )
        return (m.group(1) if m else "").strip()

    def bullets(block: str) -> list[str]:
        items = []
        for ln in block.splitlines():
            cleaned = re.sub(r"^[-*\d.)\s]+", "", ln).strip()
            if cleaned and cleaned.upper() not in markers:
                items.append(cleaned)
        return items

    score = re.search(r"CONSENSUS SCORE\s*:?\s*(\d+)", text, re.I)
    return {
        "consensus_points": bullets(section("CONSENSUS POINTS"))[:5],
        "key_disagreements": bullets(section("KEY DISAGREEMENTS"))[:5],
        "strongest_bull": section("STRONGEST BULL THESIS"),
        "strongest_bear": section("STRONGEST BEAR THESIS"),
        "swing_factor": section("SWING FACTOR").split("\n")[0] if section("SWING FACTOR") else "",
        "unresolved_questions": bullets(section("UNRESOLVED QUESTIONS"))[:5],
        "consensus_score": int(score.group(1)) if score else 5,
        "raw_text": original,
    }


def hydrate_debate(debate: dict[str, Any] | None) -> dict[str, Any] | None:
    if not debate:
        return debate
    if debate_has_structure(debate):
        return debate
    raw = debate.get("raw_text") or ""
    if not raw.strip():
        return debate
    parsed = parse_debate_output(raw)
    return {**debate, **parsed, "raw_text": raw}


def hydrate_agent(record: dict[str, Any]) -> dict[str, Any]:
    output = record.get("output") or ""
    if not output or record.get("error"):
        return record
    parsed = parse_agent_output(output)
    return {**record, "stance": parsed["stance"], "conviction": parsed["conviction"]}


def _normalize_risk(item: Any) -> dict[str, Any]:
    if isinstance(item, str):
        return {"name": item.strip(), "score": None, "description": ""}
    name = str(item.get("name") or item.get("label") or "Risk").strip()
    description = str(item.get("description") or item.get("detail") or "").strip()
    if description.casefold() == name.casefold():
        description = ""
    score = item.get("score")
    try:
        score = int(score) if score is not None and score != "" else None
    except (TypeError, ValueError):
        score = None
    return {"name": name, "score": score, "description": description}


def _position_guidance(report: dict[str, Any], sizing: dict[str, Any]) -> dict[str, str]:
    guide = report.get("position_guidance") if isinstance(report.get("position_guidance"), dict) else {}
    stance = str((guide or {}).get("stance") or "").strip()[:160]
    note = str((guide or {}).get("note") or sizing.get("sizing_rationale") or "").strip()[:400]
    return {"stance": stance, "note": note}


def normalize_report(report: dict[str, Any], query: dict[str, Any]) -> dict[str, Any]:
    sizing = report.get("position_sizing") or {}
    if "aggressive" in sizing and "aggressive_investor" not in sizing:
        sizing = {
            "aggressive_investor": sizing.get("aggressive", "N/A"),
            "moderate_investor": sizing.get("moderate", "N/A"),
            "conservative_investor": sizing.get("conservative", "N/A"),
            "sizing_rationale": sizing.get("sizing_rationale", ""),
        }

    risks = [_normalize_risk(r) for r in (report.get("risks") or [])]
    if not risks and report.get("top_risks"):
        risks = [_normalize_risk(r) for r in report["top_risks"]]

    scenarios = report.get("scenarios") or []
    for s in scenarios:
        s.setdefault("label", s.get("type", "case").title() + " case")
        s.setdefault("thesis", "")

    horizon = str(report.get("horizon") or "Medium-term")
    if horizon in {"Short", "Medium", "Long"}:
        horizon = f"{horizon}-term"

    return {
        "ticker": report.get("ticker") or query.get("ticker"),
        "company_name": report.get("company_name") or query.get("company") or query.get("ticker"),
        "sector": report.get("sector") or query.get("sector") or "Unknown",
        "type": report.get("type") or query.get("type") or "stock",
        "verdict": str(report.get("verdict") or "HOLD").upper(),
        "title": report.get("title") or "Investment analysis",
        "summary": report.get("summary")
        or report.get("suggested_action")
        or "See specialist reports.",
        "conviction": int(report.get("conviction") or 5),
        "price_target_base": report.get("price_target_base") or "N/A",
        "price_target_bull": report.get("price_target_bull") or "N/A",
        "price_target_bear": report.get("price_target_bear") or "N/A",
        "implied_upside_base": implied_upside(
            query.get("last_price") or (query.get("quote") or {}).get("price"),
            report.get("price_target_base"),
        )
        or report.get("implied_upside_base")
        or "N/A",
        "last_price": (query.get("quote") or {}).get("price") or query.get("last_price"),
        "last_price_asof": (query.get("quote") or {}).get("asof") or query.get("last_price_asof"),
        "risk_level": report.get("risk_level") or "Moderate",
        "risk_note": report.get("risk_note") or report.get("top_bear_point") or "",
        "horizon": horizon,
        "horizon_note": report.get("horizon_note") or "",
        "consensus_score": int(report.get("consensus_score") or 5),
        "consensus_description": report.get("consensus_description") or "",
        "scenarios": scenarios,
        "catalysts": report.get("catalysts") or [],
        "risks": risks,
        "financial_health": report.get("financial_health") or [],
        "predictability_scores": report.get("predictability_scores") or [],
        "position_sizing": sizing
        or {
            "aggressive_investor": "N/A",
            "moderate_investor": "N/A",
            "conservative_investor": "N/A",
            "sizing_rationale": "",
        },
        "position_guidance": _position_guidance(report, sizing),
        "sell_if": normalize_conditions(report.get("sell_if")),
        "investment_strategy": report.get("investment_strategy") or [],
        "thesis_invalidators": report.get("thesis_invalidators") or [],
        "data_quality_notes": report.get("data_quality_notes"),
        "top_bull_point": report.get("top_bull_point"),
        "top_bear_point": report.get("top_bear_point"),
        "suggested_action": report.get("suggested_action"),
    }
