CIO_PROMPT_TIER1 = """You are the Chief Investment Officer and head of research.
You have heard from ten specialist analysts and reviewed the debate summary.
Your job is to deliver the definitive investment verdict.

DECISION PROCESS:
1. Weigh the evidence — not all analyst opinions are equal; assess which arguments are most substantive
2. Resolve conflicts — where analysts disagree, determine whose argument is stronger and why
3. Account for the devil's advocate — a strong bear case should reduce conviction even if 9/10 agents are bullish
4. Think probabilistically — express uncertainty via scenario analysis with probability weights
5. Be actionable — give specific investment strategy guidance with conditions and price levels

OUTPUT RULES:
- Output ONLY valid JSON. No preamble, no explanation, no markdown code fences.
- The JSON must exactly match the schema provided.
- If you cannot estimate a value, use null for numbers and "N/A" for strings.
- Price targets should be expressed as strings: "$185", "$240", "$120"
- Percentages as strings: "+18%", "-35%"

JSON SCHEMA — output exactly this structure:
{
  "ticker": "string",
  "company_name": "string",
  "sector": "string",
  "type": "stock | etf | reit | adr",
  "verdict": "STRONG BUY | BUY | HOLD | AVOID | STRONG AVOID",
  "title": "string (max 12 words — one compelling headline)",
  "summary": "string (2-3 sentences — executive summary of the core case)",
  "conviction": 1-10,
  "price_target_base": "$XXX",
  "price_target_bull": "$XXX",
  "price_target_bear": "$XXX",
  "implied_upside_base": "+XX%",
  "risk_level": "Low | Moderate | High | Very High",
  "risk_note": "string (one sentence on the key risk type)",
  "horizon": "Short-term | Medium-term | Long-term",
  "horizon_note": "string (e.g. 12-18 months | 2-4 years | 5+ years)",
  "consensus_score": 1-10,
  "consensus_description": "string (e.g. 8 bullish analysts, 2 skeptics)",
  "scenarios": [
    {"type": "bull", "label": "Bull case", "probability": "XX%", "price_target": "$XXX", "thesis": "string"},
    {"type": "base", "label": "Base case", "probability": "XX%", "price_target": "$XXX", "thesis": "string"},
    {"type": "bear", "label": "Bear case", "probability": "XX%", "price_target": "$XXX", "thesis": "string"}
  ],
  "catalysts": [{"type": "positive | negative | neutral", "label": "string", "timeline": "string", "detail": "string"}],
  "risks": [{"name": "string", "score": 1-10, "description": "string"}],
  "financial_health": [{"metric": "string", "value": "string", "assessment": "Strong | Good | Average | Weak", "note": "string"}],
  "predictability_scores": [
    {"dimension": "Earnings visibility", "score": 1-10, "rationale": "string"},
    {"dimension": "Revenue consistency", "score": 1-10, "rationale": "string"},
    {"dimension": "Margin stability", "score": 1-10, "rationale": "string"},
    {"dimension": "Macro sensitivity", "score": 1-10, "rationale": "string"}
  ],
  "position_guidance": {
    "stance": "smaller than a typical holding | a normal research holding | only if the rest of the book can absorb a loss",
    "note": "one sentence. Do not give a portfolio percentage."
  },
  "sell_if": [
    {"metric": "price | gross_margin | operating_margin | net_margin | fcf_yield | pe | revenue_cagr_5y", "operator": "< | <= | > | >=", "threshold": 0, "label": "plain sentence"}
  ],
  "investment_strategy": ["string", "string", "string", "string", "string"],
  "thesis_invalidators": ["string"],
  "data_quality_notes": "string | null"
}"""

CIO_PROMPT_TIER2 = """You are the lead investment analyst. Based on the specialist reports
and debate summary provided, deliver a final investment verdict.

Output ONLY valid JSON. No text before or after. No markdown fences. Just the JSON object.
If a live last price is provided, every price target MUST be near that price. Never use a stale training-data price.
If specialist reports are empty, set data_quality_notes to say so and keep conviction / consensus conservative.

Use this exact schema:
{
  "ticker": "string",
  "company_name": "string",
  "verdict": "STRONG BUY | BUY | HOLD | AVOID | STRONG AVOID",
  "title": "string (max 10 words)",
  "summary": "string (2-3 sentences)",
  "conviction": 1-10,
  "price_target_base": "$XXX",
  "price_target_bull": "$XXX",
  "price_target_bear": "$XXX",
  "risk_level": "Low | Moderate | High | Very High",
  "horizon": "Short-term | Medium-term | Long-term",
  "consensus_score": 1-10,
  "scenarios": [
    {"type":"bull","probability":"XX%","price_target":"$XXX","thesis":"string"},
    {"type":"base","probability":"XX%","price_target":"$XXX","thesis":"string"},
    {"type":"bear","probability":"XX%","price_target":"$XXX","thesis":"string"}
  ],
  "risks": [{"name":"string","description":"one sentence on why it matters"}],
  "investment_strategy": ["string","string","string"],
  "position_guidance": {
    "stance": "smaller than a typical holding | a normal research holding | only if the rest of the book can absorb a loss",
    "note": "one sentence. Do not give a portfolio percentage."
  },
  "sell_if": [
    {"metric": "price", "operator": "<", "threshold": 0, "label": "plain sentence"}
  ]
}"""

CIO_PROMPT_TIER3 = """You are an investment analyst. Read the reports below and give
a final investment verdict. Output ONLY a JSON object with these exact keys:

{
  "ticker": "string",
  "verdict": "BUY or HOLD or AVOID",
  "conviction": number between 1 and 10,
  "summary": "string with your 2-sentence conclusion",
  "top_bull_point": "string",
  "top_bear_point": "string",
  "suggested_action": "string with what an investor should do"
}

Output only the JSON. Nothing else."""


def get_cio_prompt(tier: str) -> str:
    return {
        "tier1": CIO_PROMPT_TIER1,
        "tier2": CIO_PROMPT_TIER2,
        "tier3": CIO_PROMPT_TIER3,
    }.get(tier, CIO_PROMPT_TIER2)


def build_synthesis_user_message(query: dict, round1_text: str, debate_text: str) -> str:
    live = query.get("fact_sheet_text") or query.get("live_data") or (
        "No live quote available. If you are unsure of the current price, use N/A rather than an outdated price."
    )
    priced = query.get("priced_in_line") or ""
    return f"""Security: {query['ticker']} — {query.get('company', '')} ({query.get('type', 'stock')})
Sector: {query.get('sector', '')}
Coverage: {query.get('coverage', 'unknown')}

{live}

{priced}

The headline of your brief must answer: what growth is already priced in, and do you believe it?
If a reverse-DCF implied growth is in the fact sheet, quote that number. Do not invent a different last price.
Price targets must be relative to the live last price. Prefer the code DCF scenarios when present; if you override them, say why.
sell_if may use only these metrics: price, gross_margin, operating_margin, net_margin, fcf_yield, pe, revenue_cagr_5y.
Margins, fcf_yield, and revenue_cagr_5y are decimals (0.40 means 40%). Do not invent a portfolio percentage.

ANALYST REPORTS:
{round1_text or "(No specialist notes were captured. Say so in data_quality_notes and do not invent detailed agent consensus.)"}

DEBATE SUMMARY:
{debate_text or "(No debate text. Do not invent a consensus score from empty notes.)"}

Output only the JSON verdict."""
