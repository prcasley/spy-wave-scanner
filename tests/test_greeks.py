"""Unit tests for Black-Scholes Greeks."""



from src.greeks import delta, probability_above, probability_itm


def test_atm_call_delta_near_half():
    d = delta(spot=100, strike=100, days_to_expiry=30, iv=0.20, option_type="call")
    assert 0.50 < d < 0.65


def test_atm_put_delta_near_minus_half():
    d = delta(spot=100, strike=100, days_to_expiry=30, iv=0.20, option_type="put")
    assert -0.55 < d < -0.40


def test_deep_itm_call_delta_near_one():
    d = delta(spot=120, strike=100, days_to_expiry=30, iv=0.20, option_type="call")
    assert d > 0.95


def test_deep_otm_put_delta_near_zero():
    d = delta(spot=120, strike=100, days_to_expiry=30, iv=0.20, option_type="put")
    assert -0.05 < d < 0.0


def test_probability_itm_in_zero_to_one():
    p = probability_itm(spot=100, strike=105, days_to_expiry=30, iv=0.25, option_type="call")
    assert 0.0 <= p <= 1.0


def test_probability_above_consistent():
    p1 = probability_above(spot=100, target=110, days_to_expiry=30, iv=0.25)
    p2 = probability_above(spot=100, target=120, days_to_expiry=30, iv=0.25)
    assert p1 > p2  # less likely to reach a farther target


def test_zero_dte_call_delta_collapses():
    d_itm = delta(spot=110, strike=100, days_to_expiry=0, iv=0.20, option_type="call")
    d_otm = delta(spot=90, strike=100, days_to_expiry=0, iv=0.20, option_type="call")
    assert d_itm == 1.0 and d_otm == 0.0
