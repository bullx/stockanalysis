import re
from datetime import datetime, timezone


TICKER_RE = re.compile(r"^[A-Z]{1,5}(\.[A-Z]{1,2})?$")


def get_current_macro_context() -> str:
    return "Macro figures are in the fact sheet when FRED is available. Do not invent rates or CPI."


# Common words that must never be mistaken for a ticker in the offline fallback.
_STOPWORDS = {
    "A", "AN", "THE", "IS", "ARE", "AM", "BE", "IT", "I", "DO", "DOES", "TO", "OF",
    "ON", "IN", "AT", "OR", "IF", "MY", "WE", "YOU", "AND", "FOR", "VS", "BUY",
    "SELL", "HOLD", "WORTH", "GOOD", "BAD", "NOW", "ABOUT", "WHAT", "WHY", "HOW",
    "SHOULD", "COULD", "WOULD", "STOCK", "STOCKS", "SHARE", "SHARES", "PRICE",
    "OUTLOOK", "INVEST", "INVESTING", "CHEAP", "EXPENSIVE", "OVER", "UNDER",
}


def extract_ticker_from_text(text: str) -> str:
    """Best-effort ticker guess used only when Yahoo search is unavailable."""
    original = text or ""
    # 1) An explicit ALL-CAPS token in the original is very likely the ticker.
    for tok in re.findall(r"\b[A-Z]{1,5}(?:\.[A-Z]{1,2})?\b", original):
        if tok.split(".")[0] not in _STOPWORDS:
            return tok.upper()
    # 2) Otherwise the first non-stopword word, uppercased.
    for tok in re.findall(r"\b[A-Za-z]{1,5}\b", original.upper()):
        if tok not in _STOPWORDS:
            return tok
    return original.strip()[:5].upper() or "UNKNOWN"


def ticker_search_candidates(raw: str) -> list[str]:
    """Ordered search strings for Yahoo, narrowing a question to its subject.

    Yahoo matches literally, so "Is Tesla worth buying?" finds nothing but
    "Tesla" resolves. We try the raw text, then capitalised proper nouns, then
    all non-stopword words, stopping at the first that resolves.
    """
    raw = (raw or "").strip()
    candidates: list[str] = []
    if raw:
        candidates.append(raw)
    proper = [w for w in re.findall(r"[A-Z][A-Za-z]+", raw) if w.upper() not in _STOPWORDS]
    if proper:
        candidates.append(" ".join(proper))
    tokens = [w for w in re.findall(r"[A-Za-z]+", raw) if w.upper() not in _STOPWORDS]
    if tokens:
        candidates.append(" ".join(tokens))
    seen: set[str] = set()
    ordered: list[str] = []
    for cand in candidates:
        key = cand.lower()
        if cand and key not in seen:
            seen.add(key)
            ordered.append(cand)
    return ordered


def normalize_query(user_input: str, company: str = "", sector: str = "", asset_type: str = "") -> dict:
    raw = (user_input or "").strip()
    # A clean ticker is only trusted when typed as-is (uppercase, no spaces),
    # e.g. "AAPL" or "BRK.B". Anything else ("aapl", "Tesla", a question) is
    # sent to Yahoo search by the orchestrator to resolve the real symbol.
    is_ticker = bool(TICKER_RE.match(raw))
    return {
        "query_raw": raw,
        "ticker": raw if is_ticker else extract_ticker_from_text(raw),
        "needs_resolution": not is_ticker,
        "company": company or "",
        "type": asset_type or "unknown",
        "sector": sector or "",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "context": get_current_macro_context(),
        "live_data": None,
    }


def build_agent_user_message(agent: dict, query: dict) -> str:
    live = query.get("fact_sheet_text") or ""
    if not live and query.get("live_data"):
        live = f"Live data context (use to supplement your analysis):\n{query['live_data']}"
    return (
        agent["user_template"]
        .replace("{ticker}", query.get("ticker") or "")
        .replace("{company}", query.get("company") or query.get("ticker") or "")
        .replace("{type}", query.get("type") or "unknown")
        .replace("{sector}", query.get("sector") or query.get("sic_description") or "")
        .replace("{context}", query.get("context") or "")
        .replace("{live_data_block}", live)
        + _seat_closer(agent.get("id") or "")
    )


def _seat_closer(agent_id: str) -> str:
    closer = (
        "\n\nCite fact-sheet numbers when you use a figure. If a field is n/a, say so. "
        "Do not invent revenue, margins, multiples, or RSI."
    )
    if agent_id in {"risk", "growth", "devil", "quality"}:
        closer += (
            " If a FILINGS READER or EARNINGS READER block is in the packet, "
            "use it for new risks, guidance, and insider activity, and cite the form and date it names. "
            "Do not quote a filing line that is not in that block or the code digest."
        )
    closer += (
        "\n\nThe first two lines of your reply must be the conviction line and the stance line, "
        "using the exact labels in your instructions. Write those before the analysis so a long note "
        "cannot cut them off."
    )
    return closer
