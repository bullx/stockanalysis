from datetime import date

from backend.app.agents.update import apply_update
from backend.app.data.scorecard import link_calls, score_horizons, summarize
from backend.app.data.watch import banner_text, evaluate_conditions, normalize_conditions


def test_horizon_stays_blank_until_the_month_passes():
    report = {
        "generated_at": "2026-09-26T00:00:00+00:00",
        "last_price": 100,
        "price_target_bear": "$80",
        "price_target_bull": "$140",
    }
    rows = score_horizons(report, [], [], [], today=date(2026, 9, 27))
    assert [row["status"] for row in rows] == ["not_due", "not_due", "not_due", "not_due"]


def test_score_uses_the_stored_entry_and_later_closes_only():
    report = {
        "generated_at": "2025-01-15T00:00:00+00:00",
        "last_price": 100,
        "price_target_bear": "$80",
        "price_target_bull": "$140",
    }
    stock = [
        {"date": "2024-12-01", "close": 50},
        {"date": "2025-01-15", "close": 100},
        {"date": "2025-02-18", "close": 110},
        {"date": "2025-04-16", "close": 90},
        {"date": "2025-07-16", "close": 120},
        {"date": "2026-01-16", "close": 150},
    ]
    spy = [
        {"date": "2025-01-15", "close": 500},
        {"date": "2025-02-18", "close": 500},
        {"date": "2026-01-16", "close": 550},
    ]
    rows = score_horizons(report, stock, spy, [], today=date(2026, 9, 27))
    assert rows[0]["status"] == "scored"
    assert abs(rows[0]["stock_return"] - 0.1) < 1e-9
    assert rows[0]["price"] == 110
    assert rows[0]["stayed_inside"] is True
    assert rows[3]["price"] == 150
    assert rows[3]["stayed_inside"] is False
    assert rows[3]["excess_spy"] is not None


def test_later_brief_supersedes_without_erasing_the_first():
    first = {"id": "a", "report": {"ticker": "AAPL", "verdict": "BUY", "generated_at": "2026-01-01"}}
    second = {"id": "b", "report": {"ticker": "AAPL", "verdict": "HOLD", "generated_at": "2026-06-01"}}
    linked = link_calls([first, second])
    by_id = {row["id"]: row for row in linked}
    assert by_id["a"]["superseded_by"] == "b"
    assert by_id["b"]["supersedes"] == "a"
    assert first["report"]["verdict"] == "BUY"
    board = summarize(
        [
            {"report": first["report"], "horizons": [{"status": "not_due"}], "seats": []},
            {"report": second["report"], "horizons": [{"status": "not_due"}], "seats": []},
        ]
    )
    assert board["forward_only"] is True
    assert board["calls"] == 2


def test_sell_if_keeps_known_metrics_and_trips_a_percent_threshold():
    cleaned = normalize_conditions(
        [
            {"metric": "price", "operator": "<", "threshold": 10, "label": "Sell if price < 10"},
            {"metric": "vibes", "operator": "<", "threshold": 1, "label": "no"},
        ]
    )
    assert len(cleaned) == 1
    tripped = evaluate_conditions(
        [{"metric": "operating_margin", "operator": "<", "threshold": 40, "label": "Sell if operating margin < 40%"}],
        {"operating_margin": 0.25},
    )
    assert tripped and tripped[0]["label"].startswith("Sell if")


def test_banner_only_when_something_changed():
    text = banner_text(8, -0.12, {"form": "8-K", "filed": "2026-09-01"}, [{"label": "Sell if margin < 40%"}])
    assert "8 days old" in text
    assert "-12%" in text
    assert "8-K" in text
    assert "TRUE" in text
    assert text.endswith("Re-run?")
    assert banner_text(2, 0.01, None, []) == ""


def test_update_writes_a_new_brief_and_names_the_old_one():
    updated = apply_update(
        {"ticker": "AAPL", "verdict": "BUY", "conviction": 7, "summary": "Old.", "title": "Old title", "id": "old"},
        {"thesis_changed": False, "note": "Nothing material.", "verdict": "BUY", "conviction": 6, "summary": "Still holds."},
        {"price": 101},
        "old",
    )
    assert updated["supersedes"] == "old"
    assert updated["kind"] == "update"
    assert "id" not in updated
    assert updated["update_note"] == "Nothing material."
