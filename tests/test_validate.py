from backend.app.data.validate import validate_note


def test_flags_stale_price():
    sheet = {"quote": {"price": 190.0}}
    flags = validate_note("We assume a $40 share price going forward.", sheet)
    assert flags


def test_ignores_nearby_price():
    sheet = {"quote": {"price": 190.0}}
    flags = validate_note("The stock trades at $195.", sheet)
    assert flags == []
