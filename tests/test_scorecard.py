import numpy as np
import pandas as pd
import pytest

from scorecard import (
    compute_indicators,
    latest_metrics,
    normalized_score,
    prepare_prices,
    recommendation,
    score_blocks,
    trend_momentum_block,
    valuation_block,
)

BEST_CASE = {
    'price': 110.0, 'ma50': 105.0, 'ma200': 100.0,
    'roc_20': 8.0, 'momentum_change': 0.5, 'win_rate': 65.0,
    'vol_trend': 20.0, 'roc_50': 15.0, 'price_position': 20.0,
    'vol_z_score': 0.0, 'vol_5d': 1_000_000, 'vol_50d': 900_000, 'daily_range': 1.0,
}

WORST_CASE = {
    'price': 90.0, 'ma50': 95.0, 'ma200': 100.0,
    'roc_20': -8.0, 'momentum_change': -0.5, 'win_rate': 30.0,
    'vol_trend': -20.0, 'roc_50': -15.0, 'price_position': 90.0,
    'vol_z_score': 2.0, 'vol_5d': 500_000, 'vol_50d': 900_000, 'daily_range': 3.0,
}

NEUTRAL_CASE = {
    'price': 100.0, 'ma50': 100.0, 'ma200': 100.0,
    'roc_20': 0.0, 'momentum_change': 0.0, 'win_rate': 50.0,
    'vol_trend': 0.0, 'roc_50': 0.0, 'price_position': 50.0,
    'vol_z_score': 0.0, 'vol_5d': 1_000_000, 'vol_50d': 1_000_000, 'daily_range': 1.0,
}


def make_prices(days=300, volume=None, seed=0):
    rng = np.random.default_rng(seed)
    close = 100 * np.cumprod(1 + rng.normal(0.001, 0.01, days))
    return pd.DataFrame({
        'date': pd.bdate_range('2024-01-01', periods=days),
        'open': close,
        'high': close * 1.01,
        'low': close * 0.99,
        'close': close,
        'volume': volume if volume is not None else np.full(days, 1_000_000.0),
    })


def test_all_favorable_signals_reach_plus_five():
    blocks = score_blocks(BEST_CASE, pe_ratio=10, market_pe=25)
    assert normalized_score(blocks) == pytest.approx(5.0)
    assert recommendation(normalized_score(blocks))[0] == "🟢 STRONG BUY"


def test_all_unfavorable_signals_reach_minus_five():
    blocks = score_blocks(WORST_CASE, pe_ratio=50, market_pe=25)
    assert normalized_score(blocks) == pytest.approx(-5.0)
    assert recommendation(normalized_score(blocks))[0] == "🔴 STRONG SELL"


def test_all_neutral_signals_score_zero():
    blocks = score_blocks(NEUTRAL_CASE, pe_ratio=20, market_pe=20)
    assert all(b.score == 0 for b in blocks)
    assert normalized_score(blocks) == 0
    assert recommendation(normalized_score(blocks))[0] == "🟡 HOLD / REDUCE TO 50%"


def test_block_ranges_match_signals():
    blocks = score_blocks(BEST_CASE, pe_ratio=10, market_pe=25)
    assert [b.max_up for b in blocks] == [3, 1, 2, 1, 0, 0]
    assert [b.max_down for b in blocks] == [3, 1, 2, 1, 1, 1]
    assert all(b.score == b.max_up for b in blocks)


def test_score_scale_is_asymmetric_but_reaches_both_ends():
    # One of seven possible positives is worth more than one of nine possible negatives
    up = score_blocks({**NEUTRAL_CASE, 'roc_50': 15.0}, pe_ratio=20, market_pe=20)
    down = score_blocks({**NEUTRAL_CASE, 'roc_50': -15.0}, pe_ratio=20, market_pe=20)
    assert normalized_score(up) == pytest.approx(5 / 7)
    assert normalized_score(down) == pytest.approx(-5 / 9)


def test_fading_momentum_on_rising_stock_does_not_say_down():
    block = trend_momentum_block({**BEST_CASE, 'roc_20': 12.0, 'momentum_change': -3.0})
    momentum = block.signals[1]
    assert momentum.score == -1
    assert "Down" not in momentum.message
    assert "Fading" in momentum.message


def test_falling_stock_message_has_no_double_negative():
    momentum = trend_momentum_block(WORST_CASE).signals[1]
    assert "Down 8.0%" in momentum.message


@pytest.mark.parametrize('pe', [None, 'Infinity', -5, 0, float('nan'), 'abc'])
def test_unusable_pe_is_neutral(pe):
    block = valuation_block(pe, 25)
    assert block.score == 0
    assert "not available" in block.signals[0].message


def test_missing_market_pe_falls_back_to_default():
    assert valuation_block(10, None).score == 1


def test_volume_trend_compares_consecutive_20_day_windows():
    volume = np.r_[np.full(280, 1_000_000.0), np.full(20, 2_000_000.0)]
    m = latest_metrics(compute_indicators(make_prices(volume=volume)))
    assert m['vol_trend'] == pytest.approx(100.0)


def test_zero_volume_does_not_produce_infinities():
    m = latest_metrics(compute_indicators(make_prices(volume=np.zeros(300))))
    blocks = score_blocks(m)
    assert pd.isna(m['vol_trend'])
    assert blocks[1].score == 0
    assert "nan" not in blocks[1].signals[0].message.lower()


def test_prepare_prices_flattens_yfinance_multiindex():
    flat = make_prices(days=5).set_index('date')
    flat.index.name = 'Date'
    flat.columns = pd.MultiIndex.from_product([[c.title() for c in flat.columns], ['AAPL']], names=['Price', 'Ticker'])
    df = prepare_prices(flat)
    assert list(df.columns) == ['date', 'open', 'high', 'low', 'close', 'volume']
    assert len(df) == 5
