"""Characterization tests for the model-output parser.

parse.py turns messy LLM text into structured records; it is the most
fragile code in the backend, so these lock in current behavior.
"""

from backend.app.utils.parse import (
    extract_and_parse_json,
    implied_upside,
    normalize_report,
    parse_agent_output,
    parse_debate_output,
    parse_price_number,
    strip_think,
    unwrap_markup,
)


def test_parse_price_number_handles_currency_and_commas():
    assert parse_price_number("$1,234.50") == 1234.5
    assert parse_price_number(187) == 187.0


def test_parse_price_number_rejects_nonpositive_and_missing():
    assert parse_price_number("N/A") is None
    assert parse_price_number("0") is None
    assert parse_price_number(None) is None


def test_implied_upside():
    assert implied_upside(100, "$110") == "+10.0%"
    assert implied_upside(100, "$80") == "-20.0%"
    assert implied_upside(None, "$110") is None
    assert implied_upside(100, "N/A") is None


def test_strip_think_and_unwrap_markup():
    assert strip_think("<think>reasoning</think>Answer") == "Answer"
    assert unwrap_markup("**bold** and __under__") == "bold and under"


def test_parse_agent_output_reads_conviction_and_stance_lines():
    text = "CONVICTION: 8/10\nFUNDAMENTAL STANCE: BUY\nGreat business with strong cash flow."
    out = parse_agent_output(text)
    assert out["conviction"] == 8
    assert out["stance"].upper().startswith("BUY")
    assert "cash flow" in out["output"]


def test_parse_agent_output_clamps_conviction():
    out = parse_agent_output("CONVICTION: 99/10\nSTANCE: BUY\nx")
    assert out["conviction"] == 10


def test_parse_agent_output_accepts_json_object():
    out = parse_agent_output('{"conviction": 7, "stance": "HOLD", "output": "balanced"}')
    assert out["conviction"] == 7
    assert out["stance"] == "HOLD"
    assert out["output"] == "balanced"


def test_parse_agent_output_missing_markers_is_incomplete():
    out = parse_agent_output("Some prose with no labels at all.")
    assert out["stance"] == "incomplete"
    assert out["conviction"] == 5


def test_parse_debate_output_structured_headers():
    text = (
        "CONSENSUS POINTS\n- Quality is high\n"
        "KEY DISAGREEMENTS\n- Valuation is contested\n"
        "STRONGEST BULL THESIS\nDurable compounder.\n"
        "STRONGEST BEAR THESIS\nPriced for perfection.\n"
        "SWING FACTOR\nWhether margins hold.\n"
        "UNRESOLVED QUESTIONS\n- Can growth persist\n"
        "CONSENSUS SCORE: 6\n"
    )
    d = parse_debate_output(text)
    assert d["strongest_bull"] == "Durable compounder."
    assert d["strongest_bear"] == "Priced for perfection."
    assert d["swing_factor"] == "Whether margins hold."
    assert d["consensus_score"] == 6
    assert d["consensus_points"] == ["Quality is high"]


def test_extract_and_parse_json_plain_and_fenced():
    assert extract_and_parse_json('{"verdict": "BUY"}')["verdict"] == "BUY"
    fenced = "```json\n{\"verdict\": \"HOLD\"}\n```"
    assert extract_and_parse_json(fenced)["verdict"] == "HOLD"


def test_normalize_report_fills_defaults():
    report = normalize_report({}, {"ticker": "AAA"})
    assert report["ticker"] == "AAA"
    assert report["verdict"] == "HOLD"
    assert report["conviction"] == 5
    assert report["risks"] == []


def test_normalize_report_expands_short_horizon():
    report = normalize_report({"horizon": "Long"}, {"ticker": "AAA"})
    assert report["horizon"] == "Long-term"
