from backend.app.agents.definitions import AGENT_DEFINITIONS

DEBATE_SYSTEM_PROMPT = """You are the senior research director moderating an investment committee meeting.
Ten specialist analysts have each independently analyzed the same security.
Your job is to map the intellectual landscape — not to recommend, but to clarify where the team agrees,
where they conflict, and what the key unresolved questions are.

Your output MUST follow this exact structure with these exact headers:

CONSENSUS POINTS
- [2-3 bullet points where 7 or more analysts clearly agree]

KEY DISAGREEMENTS
- [2-3 bullet points where analysts fundamentally conflict and WHY they conflict]

STRONGEST BULL THESIS
[One paragraph: the single most compelling reason to own this security, synthesized from the most bullish analysts]

STRONGEST BEAR THESIS
[One paragraph: the single most compelling reason NOT to own this security, synthesized from the skeptics and devil's advocate]

SWING FACTOR
[One sentence: the single variable whose outcome will determine which side of the debate is right]

UNRESOLVED QUESTIONS
- [2-3 questions the committee cannot answer from available analysis alone — things to monitor]

CONSENSUS SCORE: [X]/10
[Brief description: e.g. "7 bullish, 2 neutral, 1 bear — divided on valuation"]"""


def build_debate_user_message(query: dict, round1: dict) -> str:
    reports = []
    for agent in AGENT_DEFINITIONS:
        out = round1.get(agent["id"]) or {}
        reports.append(
            f"=== {agent['name'].upper()} ({agent['tag']}) ===\n{out.get('output') or 'No output'}\n"
        )
    body = "\n".join(reports)
    return f"""Security under analysis: {query['ticker']} — {query.get('company', '')} ({query.get('type', 'unknown')})
Macro context: {query.get('context', '')}

Below are independent analyses from all specialist analysts.
Read all of them carefully, then produce the debate synthesis following your required structure.

{body}

Now produce the structured debate synthesis."""


def build_synthetic_debate(round1: dict) -> dict:
    outputs = [o for o in round1.values() if not o.get("error")]
    avg = sum(o.get("conviction", 5) for o in outputs) / (len(outputs) or 1)
    bulls = [o for o in outputs if o.get("conviction", 5) >= 7]
    bears = [o for o in outputs if o.get("conviction", 5) <= 4]
    devil = (round1.get("devil") or {}).get("output") or ""
    return {
        "consensus_points": ["Multiple analysts cited business quality as a positive factor"],
        "key_disagreements": ["Valuation assessment and timing differ across analysts"],
        "strongest_bull": (bulls[0].get("output") or "")[:200] if bulls else "See individual agent outputs",
        "strongest_bear": devil[:200] or "See risk manager output",
        "swing_factor": "Earnings growth vs. valuation multiple compression",
        "unresolved_questions": ["Current price vs. fair value", "Near-term catalyst timing"],
        "consensus_score": round(avg),
        "raw_text": (
            f"[SYNTHETIC] Average conviction: {avg:.1f}/10. "
            f"{len(bulls)} bullish agents, {len(bears)} bearish agents."
        ),
        "synthetic": True,
    }
