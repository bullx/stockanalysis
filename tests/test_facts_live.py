"""Live check against Yahoo + SEC. Uses the on-disk cache after the first run."""

import asyncio

from backend.app.data.facts import build_fact_sheet


def test_aapl_fact_sheet_has_sourced_revenue():
    sheet = asyncio.run(build_fact_sheet("AAPL", include_filings=False))
    assert sheet["coverage"] == "us"
    assert sheet["business"].get("revenue") and sheet["business"]["revenue"] > 1e11
    assert sheet["business"].get("revenue_filed")
    assert sheet["quote"] and sheet["quote"].get("price")
    assert sheet["history_points"] > 200
