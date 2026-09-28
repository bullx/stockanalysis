import json
import re


def mock_completion(system_prompt: str, user_message: str) -> str:
    sys_l = system_prompt.lower()
    user_l = user_message.lower()
    ticker = _ticker(user_message)

    if "update analyst" in sys_l:
        return json.dumps(
            {
                "thesis_changed": False,
                "note": "The price move and filings in the packet do not break the original thesis.",
                "verdict": "BUY",
                "conviction": 6,
                "summary": "The original case still holds. This note only records what changed.",
            }
        )
    if "filings analyst" in sys_l:
        return (
            "FILINGS: Stable\n"
            "- Risk Factors vs the prior filing: no new material weakness is in the packet.\n"
            "- Form 4 net shares are the code sample, not a full tape."
        )
    if "earnings analyst" in sys_l:
        return (
            "EARNINGS: Not stated\n"
            "- The excerpts do not compare results with a prior outlook, so this is not a beat or a miss."
        )
    if "chief investment officer" in sys_l or "lead investment analyst" in sys_l or "output only valid json" in sys_l or "output only a json" in sys_l:
        return _cio(ticker, user_message)
    if "research director" in sys_l or "debate synthesis" in user_l or "consensus points" in sys_l:
        return _debate(ticker)
    if "permanent skeptic" in sys_l or "strongest possible bear" in sys_l or "you are a skeptic" in sys_l:
        return (
            f"{ticker} is priced for perfection. A 20% miss vs consensus growth would compress "
            f"the multiple sharply. Narrative risk is high if the product story cracks. "
            f"A realistic path to a 40% drawdown is a demand slowdown plus multiple mean-reversion.\n"
            f"BEAR CASE CONVICTION: 7/10\n"
            f"PRIMARY BEAR THESIS: Valuation already discounts flawless execution."
        )
    if "valuation specialist" in sys_l or "you are a valuation" in sys_l:
        return (
            f"{ticker} trades at a premium to its 5-year average P/E but in line with growth-adjusted peers. "
            f"EV/EBITDA is rich, not extreme. Implied growth is ambitious but not absurd.\n"
            f"CONVICTION: 6/10\nVALUATION: FAIRLY VALUED"
        )
    if "fundamental equity" in sys_l or "you are a financial analyst" in sys_l:
        return (
            f"{ticker} shows durable revenue quality with expanding operating leverage. "
            f"FCF conversion is healthy and the balance sheet can fund buybacks without stress. "
            f"ROIC remains above cost of capital on our directional estimates.\n"
            f"CONVICTION: 8/10\nFUNDAMENTAL STANCE: BUY"
        )
    if "growth equity" in sys_l or "you are a growth analyst" in sys_l:
        return (
            f"TAM still supports mid-teens expansion. Growth is more secular than cyclical. "
            f"Share gains plus pricing power are the two live vectors for {ticker}.\n"
            f"CONVICTION: 7/10\nGROWTH OUTLOOK: STRONG"
        )
    if "competitive strategy" in sys_l or "you are a competitive" in sys_l:
        return (
            f"{ticker} has a narrow-to-wide moat from brand and switching costs. "
            f"The advantage looks stable, not rapidly eroding. Main threat is a well-capitalized peer.\n"
            f"CONVICTION: 7/10\nMOAT: NARROW — STABLE"
        )
    if "macro strategist" in sys_l or "you are a macro" in sys_l:
        return (
            f"Rate path is a mild headwind for long-duration names. Cycle positioning is acceptable. "
            f"Inflation is less damaging if {ticker} retains pricing power.\n"
            f"CONVICTION: 5/10\nMACRO STANCE: NEUTRAL"
        )
    if "technical analyst" in sys_l or "you are a technical" in sys_l:
        return (
            f"Trend structure is a higher-high regime above the 200-day. Momentum is constructive, not overbought. "
            f"Relative strength vs the index is mildly positive.\n"
            f"CONVICTION: 6/10\nTECHNICAL BIAS: BULLISH\nSupport: ~$168 | Resistance: ~$198"
        )
    if "sentiment and microstructure" in sys_l or "you are a sentiment" in sys_l:
        return (
            f"Positioning is busy but not extreme. Short interest is moderate. "
            f"Estimate revisions have stabilized. Contrarian fuel is limited.\n"
            f"CONVICTION: 5/10\nSENTIMENT: NEUTRAL"
        )
    if "earnings-quality" in sys_l or "earnings quality" in sys_l or "forensic ratios" in sys_l:
        return (
            f"Cash conversion for {ticker} should be read from the forensic block. "
            f"If receivables outgrow sales, treat the earnings number as mixed until cash catches up.\n"
            f"CONVICTION: 6/10\nEARNINGS QUALITY: MIXED"
        )
    if "portfolio risk manager" in sys_l or "you are a risk manager" in sys_l:
        return (
            f"Top risks for {ticker}: multiple compression, competitive share loss, and a demand air-pocket. "
            f"Leverage looks manageable. A 40%+ permanent loss would need a structural demand break.\n"
            f"CONVICTION: 6/10\nRISK LEVEL: MODERATE"
        )
    if "esg" in sys_l:
        return (
            f"Governance is the most material ESG factor. Climate transition risk is moderate. "
            f"No red-flag governance pattern is obvious from public history.\n"
            f"CONVICTION: 6/10\nESG PROFILE: AVERAGE\nTOP ESG RISK: Regulatory and data-privacy exposure."
        )
    return f"Analysis of {ticker} complete.\nCONVICTION: 6/10\nSTANCE: HOLD"


def _ticker(user: str) -> str:
    labeled = re.search(
        r"Security(?: under analysis)?:\s*([A-Za-z]{1,5})",
        user,
        re.I,
    )
    if labeled:
        return labeled.group(1).upper()
    match = re.search(r"\b([A-Z]{2,5})(?:\.[A-Z]{1,2})?\b", user.upper())
    blocked = {"THE", "AND", "FOR", "THIS", "FROM", "WITH", "YOUR", "GIVE", "END"}
    if match and match.group(1) not in blocked:
        return match.group(1)
    return "TICKER"


def _debate(ticker: str) -> str:
    return f"""CONSENSUS POINTS
- {ticker} is a high-quality franchise with above-cost-of-capital returns
- Balance sheet risk is not the primary debate

KEY DISAGREEMENTS
- Valuation specialists see fair value; bulls argue the premium is earned
- Timing: technicals are constructive while macro is only neutral

STRONGEST BULL THESIS
Durable earnings power plus buybacks can grind the stock higher even if the multiple stays elevated.

STRONGEST BEAR THESIS
The market already prices near-flawless execution; any growth miss compresses both earnings and the multiple.

SWING FACTOR
Whether next-year growth lands inside consensus without a margin air-pocket.

UNRESOLVED QUESTIONS
- Near-term demand elasticity
- Peer pricing intensity

CONSENSUS SCORE: 7/10
7 bullish-leaning, 2 neutral, 1 structured bear — divided on valuation."""


def _cio(ticker: str, user: str) -> str:
    payload = {
        "ticker": ticker,
        "company_name": ticker,
        "sector": "Unknown",
        "type": "stock",
        "verdict": "BUY",
        "title": f"{ticker} earns a measured overweight",
        "summary": (
            f"{ticker} is a quality compounder at a full but not reckless price. "
            "Own it with size discipline; the bear case is valuation, not franchise collapse."
        ),
        "conviction": 7,
        "price_target_base": "$210",
        "price_target_bull": "$245",
        "price_target_bear": "$155",
        "implied_upside_base": "+12%",
        "risk_level": "Moderate",
        "risk_note": "Primary risk is multiple compression if growth slips.",
        "horizon": "Medium-term",
        "horizon_note": "12–24 months",
        "consensus_score": 7,
        "consensus_description": "Most specialists constructive; valuation and devil's advocate restrain size",
        "scenarios": [
            {
                "type": "bull",
                "label": "Bull case",
                "probability": "25%",
                "price_target": "$245",
                "thesis": "Growth beats and the premium multiple holds. Operating leverage drops through.",
            },
            {
                "type": "base",
                "label": "Base case",
                "probability": "50%",
                "price_target": "$210",
                "thesis": "Earnings grind higher; the stock follows cash flow more than narrative.",
            },
            {
                "type": "bear",
                "label": "Bear case",
                "probability": "25%",
                "price_target": "$155",
                "thesis": "Growth misses and the multiple mean-reverts together.",
            },
        ],
        "catalysts": [
            {
                "type": "positive",
                "label": "Next earnings print",
                "timeline": "Next 1–2 quarters",
                "detail": "A clean beat with stable margins would confirm the base case.",
            },
            {
                "type": "negative",
                "label": "Guide-down risk",
                "timeline": "12 months",
                "detail": "A demand air-pocket would force the valuation debate into the open.",
            },
            {
                "type": "neutral",
                "label": "Rate path",
                "timeline": "Ongoing",
                "detail": "Duration-sensitive names will track real-rate surprises.",
            },
        ],
        "risks": [
            {"name": "Multiple compression", "score": 7, "description": "Premium valuation leaves little room for a miss."},
            {"name": "Competitive intensity", "score": 6, "description": "Share loss would undermine the growth vector."},
            {"name": "Demand air-pocket", "score": 5, "description": "A cyclical pause would hit both earnings and sentiment."},
            {"name": "Macro duration shock", "score": 4, "description": "Higher real rates pressure long-duration cash flows."},
        ],
        "financial_health": [
            {"metric": "Revenue growth", "value": "12%", "assessment": "Good", "note": "Directional estimate from specialist panel."},
            {"metric": "FCF conversion", "value": "Solid", "assessment": "Strong", "note": "Cash generation supports buybacks."},
            {"metric": "Leverage", "value": "Moderate", "assessment": "Good", "note": "Balance sheet is not the swing factor."},
        ],
        "predictability_scores": [
            {"dimension": "Earnings visibility", "score": 7, "rationale": "Recurring demand with some cyclical overlay."},
            {"dimension": "Revenue consistency", "score": 7, "rationale": "History suggests mid-cycle stability."},
            {"dimension": "Margin stability", "score": 6, "rationale": "Operating leverage cuts both ways."},
            {"dimension": "Macro sensitivity", "score": 5, "rationale": "Lower score means more rate/cycle sensitivity."},
        ],
        "position_guidance": {
            "stance": "smaller than a typical holding",
            "note": "The case is a full price on a durable business. Size is the reader's decision, not a portfolio weight.",
        },
        "sell_if": [
            {"metric": "price", "operator": "<", "threshold": 155, "label": "Sell if price < 155"},
            {"metric": "operating_margin", "operator": "<", "threshold": 0.25, "label": "Sell if operating margin < 25%"},
        ],
        "investment_strategy": [
            "Scale in over 2–3 tranches rather than a single lump sum at a full multiple.",
            "Add on a 10–12% drawdown if the fundamental stance is unchanged.",
            "Re-evaluate if price breaks the bear target with deteriorating revisions.",
            "Watch next two earnings prints for margin and growth confirmation.",
            "Hold 12–24 months; refresh the council after a thesis-level event.",
        ],
        "thesis_invalidators": [
            "Two consecutive quarters of negative estimate revisions.",
            "Evidence the moat is eroding via share loss.",
            "Leverage rising while FCF conversion breaks down.",
        ],
        "data_quality_notes": "Demo provider — replace with Ollama or a cloud model for live inference.",
    }
    return json.dumps(payload)
