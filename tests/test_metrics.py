from backend.app.data.dcf import dcf_value, default_growth_path, reverse_dcf_growth
from backend.app.data.metrics import cagr, correlation, max_drawdown, ratio, rsi, sma, yoy


def test_cagr_doubles_in_seven_years():
    # Rule of 72-ish: 10% for 7 years is about 1.95x
    g = cagr(100, 194.87, 7)
    assert g is not None
    assert abs(g - 0.10) < 0.002


def test_cagr_rejects_bad_inputs():
    assert cagr(0, 100, 5) is None
    assert cagr(100, 110, 0) is None


def test_yoy_and_ratio():
    series = [{"val": 100}, {"val": 110}]
    assert abs((yoy(series) or 0) - 0.10) < 1e-9
    assert ratio(25, 100) == 0.25
    assert ratio(1, 0) is None


def test_sma_and_rsi_bounds():
    closes = [float(i) for i in range(1, 30)]
    assert sma(closes, 5) == sum(closes[-5:]) / 5
    value = rsi(closes, 14)
    assert value is not None
    assert 50 < value <= 100  # a straight climb is overbought


def test_max_drawdown():
    assert abs((max_drawdown([100, 120, 60, 90]) or 0) - (-0.5)) < 1e-9


def test_correlation_perfect():
    a = [float(i) for i in range(30)]
    assert abs((correlation(a, a) or 0) - 1.0) < 1e-9


def test_dcf_higher_growth_higher_price():
    low = dcf_value(10, default_growth_path(0.05), 0.03, 0.09, 1.0, 0)
    high = dcf_value(10, default_growth_path(0.15), 0.03, 0.09, 1.0, 0)
    assert low and high
    assert high["price"] > low["price"]


def test_reverse_dcf_recovers_growth():
    target = dcf_value(10, default_growth_path(0.12), 0.03, 0.09, 2.0, 0)
    assert target
    implied = reverse_dcf_growth(target["price"], 10, 2.0, 0.09)
    assert implied is not None
    assert abs(implied - 0.12) < 0.015
