from backend.app.agents.filings import earnings_reader_packet, filings_reader_packet
from backend.app.data.filings import (
    archive_names,
    diff_sections,
    extract_guidance,
    format_filings_digest,
    parse_form4_net,
    pick_exhibit_99_1,
    scan_red_flags,
    split_items,
    strip_html,
)


SAMPLE_10K = """
UNITED STATES SECURITIES AND EXCHANGE COMMISSION

Item 1. Business
We make widgets for industrial customers worldwide.

Item 1A. Risk Factors
Competition may intensify. We depend on a single supplier for a key input.

Item 7. Management’s Discussion and Analysis of Financial Condition and Results of Operations
Revenue grew because of price increases. Cash from operations funded buybacks.

Item 8. Financial Statements and Supplementary Data
See the consolidated statements.
"""


def test_strip_html_keeps_text():
    html = "<html><body><p>Hello <b>world</b></p><script>x</script></body></html>"
    text = strip_html(html)
    assert "Hello" in text and "world" in text
    assert "x" not in text or "script" not in text.lower()


def test_split_items_finds_risk_and_mda():
    sections = split_items(SAMPLE_10K)
    assert "1A" in sections
    assert "risk" in sections["1A"].lower()
    assert "7" in sections
    assert "Revenue grew" in sections["7"]


def test_split_items_ignores_a_cross_reference():
    text = """
Item 1. Business
We make devices for customers worldwide and have done so for many years.

Item 1A. Risk Factors
The following summarizes factors that could have a material adverse effect. We depend on a single supplier for a key part.

Item 7. Management's Discussion and Analysis of Financial Condition and Results of Operations
Item 1A of this Form 10-K under the heading "Risk Factors." As a result gross margins will be subject to volatility and downward pressure.
Operating Expenses
Operating expenses for 2025 were as follows and are discussed in the MD&A.
Revenue grew because of price increases. This item discusses the year just ended in detail.

Item 8. Financial Statements and Supplementary Data
See the consolidated statements included later in this report.
"""
    sections = split_items(text)
    assert "single supplier" in sections["1A"]
    assert "Operating expenses" not in sections["1A"]
    assert "Revenue grew" in sections["7"]


def test_red_flags_catch_going_concern():
    hits = scan_red_flags("There is substantial doubt about our ability to continue as a going concern.", "10-K")
    phrases = {h["phrase"] for h in hits}
    assert "substantial doubt" in phrases
    assert "going concern" in phrases


FORM4 = """<?xml version="1.0"?>
<ownershipDocument>
  <nonDerivativeTransaction>
    <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
    <transactionAmounts>
      <transactionShares><value>1000</value></transactionShares>
      <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
    </transactionAmounts>
  </nonDerivativeTransaction>
  <nonDerivativeTransaction>
    <transactionCoding><transactionCode>S</transactionCode></transactionCoding>
    <transactionAmounts>
      <transactionShares><value>200</value></transactionShares>
      <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
    </transactionAmounts>
  </nonDerivativeTransaction>
  <nonDerivativeTransaction>
    <transactionCoding><transactionCode>M</transactionCode></transactionCoding>
    <transactionAmounts>
      <transactionShares><value>5000</value></transactionShares>
      <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
    </transactionAmounts>
  </nonDerivativeTransaction>
</ownershipDocument>
"""


def test_form4_net_skips_option_exercise():
    parsed = parse_form4_net(FORM4)
    assert parsed["bought"] == 1000
    assert parsed["sold"] == 200
    assert parsed["net"] == 800


def test_diff_sections_keeps_only_the_new_sentence():
    shared = (
        "Competition may intensify if a well funded rival matches our price and our service levels across every region. "
    )
    old = "Item 1A. Risk Factors are as follows. " + (shared * 3)
    new = old + "We now depend on a single supplier for a key chip used in every unit we ship. "
    diff = diff_sections(old, new)
    assert any("single supplier" in part for part in diff["added"])
    assert all(shared.strip() not in part for part in diff["added"])


def test_extract_guidance_uses_the_outlook_and_skips_results():
    text = """
Results

Revenue was $10 billion.

Financial Outlook

The Company expects revenue between $90 billion and $93 billion.
Gross margin is expected to be between 46 percent and 47 percent.
We continue to invest in people and process every single day.
"""
    hits = extract_guidance(text)
    joined = " ".join(hits)
    assert "$90 billion" in joined
    assert "46 percent" in joined
    assert "$10 billion" not in joined
    assert "invest in people" not in joined


def test_pick_exhibit_99_1_prefers_the_press_release():
    assert pick_exhibit_99_1(["d8k.htm", "aapl-20250130xex99d1.htm", "chart.jpg"]) == "aapl-20250130xex99d1.htm"
    assert pick_exhibit_99_1(["press.htm", "exhibit99.htm"]) == "exhibit99.htm"
    assert pick_exhibit_99_1(["d8k.htm"]) is None


def test_archive_names_reads_the_index_list():
    payload = {
        "directory": {
            "item": [
                {"name": "index.html"},
                {"name": "d8k.htm"},
                {"name": "ex99d1.htm"},
            ]
        }
    }
    assert archive_names(payload) == ["d8k.htm", "ex99d1.htm"]


def test_format_digest_quotes_guidance():
    text = format_filings_digest(
        {
            "latest_annual": {"form": "10-K", "filed": "2025-11-01", "accession": "0001-25-000001"},
            "items_found": ["1A"],
            "risk_diff": {"added": [], "removed": [], "note": "Item 1A not found"},
            "mda_diff": {},
            "red_flags": [],
            "earnings_8k": {"filed": "2025-10-30", "accession": "0001-25-000099"},
            "guidance": ["The Company expects revenue between $90 billion and $93 billion."],
            "guidance_source": "ex99d1.htm from the Item 2.02 8-K filed 2025-10-30",
            "insider_90d": {"bought": 0, "sold": 0, "net": 0, "forms": 0},
        }
    )
    assert "$90 billion" in text
    assert "not parsed" not in text


def test_readers_skip_the_model_when_there_is_nothing_to_read(tmp_path):
    import asyncio

    from backend.app.agents.filings import run_filing_readers

    events = []

    async def emit(event):
        events.append(event["type"])

    text = asyncio.run(
        run_filing_readers(
            {
                "risk_diff": {"added": [], "removed": []},
                "mda_diff": {},
                "guidance": [],
                "guidance_note": "Item 2.02 8-K found. Exhibit 99.1 was not in the filing index.",
            },
            "AAPL",
            "tier1",
            {"model": "mock", "provider": "mock"},
            emit,
            output_dir=str(tmp_path),
        )
    )
    assert events == []
    assert "not asked to read a filing" in text
    assert "not asked to invent" in text


def test_reader_packets_omit_the_full_filing():
    digest = {
        "latest_annual": {"form": "10-K", "filed": "2025-11-01", "accession": "0001"},
        "risk_diff": {"added": ["New risk about a single supplier."], "removed": []},
        "mda_diff": {"added": [], "removed": [], "note": "Item 7 not found"},
        "red_flags": [],
        "eight_k": [{"filed": "2025-10-30", "items": "2.02"}],
        "insider_90d": {"bought": 10, "sold": 4, "net": 6, "forms": 1},
        "guidance": ["The Company expects revenue between $90 billion and $93 billion."],
        "guidance_source": "ex99d1.htm from the Item 2.02 8-K filed 2025-10-30",
        "earnings_8k": {"filed": "2025-10-30", "accession": "0009"},
        "full_10k": "SECRET WHOLE FILING TEXT SHOULD NOT APPEAR",
    }
    filings = filings_reader_packet(digest)
    earnings = earnings_reader_packet(digest)
    assert "SECRET WHOLE" not in filings
    assert "SECRET WHOLE" not in earnings
    assert "single supplier" in filings
    assert "Item 7 not found" in filings
    assert "$90 billion" in earnings
