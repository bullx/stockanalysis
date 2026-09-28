"""Ticker normalization and question-to-subject resolution (Phase 0 bug fix)."""

from backend.app.orchestrator.normalize import (
    extract_ticker_from_text,
    normalize_query,
    ticker_search_candidates,
)


def test_clean_uppercase_ticker_is_trusted():
    q = normalize_query("AAPL")
    assert q["ticker"] == "AAPL"
    assert q["needs_resolution"] is False


def test_ticker_with_exchange_suffix_is_trusted():
    q = normalize_query("BRK.B")
    assert q["ticker"] == "BRK.B"
    assert q["needs_resolution"] is False


def test_lowercase_word_needs_resolution():
    # "aapl" could be a name typo; force resolution rather than trusting it.
    q = normalize_query("aapl")
    assert q["needs_resolution"] is True


def test_question_needs_resolution_and_does_not_pick_stopword():
    q = normalize_query("Is Tesla worth buying?")
    assert q["needs_resolution"] is True
    # The old bug returned "IS". The heuristic must never return a stopword.
    assert q["ticker"] != "IS"
    assert q["ticker"] == "TESLA"


def test_extract_skips_stopwords():
    assert extract_ticker_from_text("Should I buy Apple") == "APPLE"
    assert extract_ticker_from_text("Is Tesla worth buying?") == "TESLA"


def test_extract_prefers_explicit_uppercase_symbol():
    assert extract_ticker_from_text("is NVDA cheap right now") == "NVDA"


def test_company_is_not_polluted_with_question_text():
    q = normalize_query("Is Tesla worth buying?")
    assert q["company"] == ""


def test_search_candidates_narrow_to_subject():
    cands = ticker_search_candidates("Is Tesla worth buying?")
    # Raw first (so a literal name still works), then the isolated subject.
    assert cands[0] == "Is Tesla worth buying?"
    assert "Tesla" in cands
    # The isolated subject must come before the noisy full-token join.
    assert cands.index("Tesla") < cands.index("Tesla buying")


def test_search_candidates_lowercase_theme():
    cands = ticker_search_candidates("nvidia outlook")
    assert "nvidia" in cands
