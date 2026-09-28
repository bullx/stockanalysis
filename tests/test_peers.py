from backend.app.data.filings import extract_customer_concentration
from backend.app.utils.storage import delete_report, save_report
from backend.app.data.group import pearson
from backend.app.data.peers import peer_ciks_from_feed, peer_row
from backend.app.agents.definitions import CORE_AGENT_IDS, OPTIONAL_AGENT_IDS


def test_delete_report_removes_only_that_file(tmp_path):
    saved = save_report(str(tmp_path), "AAPL", {"ticker": "AAPL", "title": "x"}, {}, {})
    assert delete_report(str(tmp_path), saved["id"]) is True
    assert delete_report(str(tmp_path), "../secrets") is False
    assert delete_report(str(tmp_path), saved["id"]) is False


def test_core_desk_is_four_seats():
    assert CORE_AGENT_IDS == ["fundamental", "valuation", "quality", "devil"]
    assert "esg" in OPTIONAL_AGENT_IDS
    assert "quality" not in OPTIONAL_AGENT_IDS


def test_peer_feed_keeps_unique_ciks_in_order():
    xml = """
    <entry><title>10-K - APPLE INC (0000320193)</title></entry>
    <entry><title>10-Q - APPLE INC (0000320193)</title></entry>
    <entry><title>10-K - MICROSOFT CORP (0000789019)</title></entry>
    """
    assert peer_ciks_from_feed(xml) == [320193, 789019]


def test_peer_feed_reads_cik_tags():
    xml = "<entry><cik>0000861289</cik></entry><entry><cik>0000320193</cik></entry><entry><cik>0000861289</cik></entry>"
    assert peer_ciks_from_feed(xml) == [861289, 320193]


def test_peer_row_uses_only_computed_fields():
    row = peer_row("AAPL", "Apple", {"operating_margin": 0.3}, {"pe": 28.2, "ev_ebitda": None, "fcf_yield": 0.04})
    assert row["ticker"] == "AAPL"
    assert row["pe"] == 28.2
    assert row["operating_margin"] == 0.3


def test_customer_concentration_requires_a_percent():
    text = (
        "We sell to many customers around the world. "
        "One customer accounted for 18% of net sales in the year. "
        "No other customer is named here without a figure."
    )
    hits = extract_customer_concentration(text)
    assert len(hits) == 1
    assert "18%" in hits[0]
    assert extract_customer_concentration("We have customers.") == []


def test_correlation_needs_overlapping_days():
    left = {f"2024-01-{day:02d}": 0.01 for day in range(1, 10)}
    right = {f"2024-01-{day:02d}": 0.02 for day in range(1, 10)}
    corr, days = pearson(left, right)
    assert corr is None
    assert days == 9
    left = {f"2024-{month:02d}-01": 0.01 * month for month in range(1, 50)}
    right = {day: value * 2 for day, value in left.items()}
    corr, days = pearson(left, right)
    assert days == 49
    assert corr is not None and corr > 0.99
