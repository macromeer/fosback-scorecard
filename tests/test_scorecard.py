import numpy as np
import pandas as pd
import pytest

from scorecard import (
    breadth_block,
    compute_indicators,
    latest_metrics,
    liquidity_block,
    normalized_score,
    prepare_prices,
    recommendation,
    score_blocks,
    sentiment_block,
    trend_momentum_block,
    valuation_block,
    volatility_block,
)

BEST_CASE = {
    'price': 110.0, 'ma50': 105.0, 'ma200': 100.0,
    'roc_20': 8.0, 'momentum_change': 0.5, 'win_rate': 70.0,
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


@pytest.mark.parametrize('case, expected', [(BEST_CASE, 5.0), (WORST_CASE, -5.0)])
def test_missing_data_does_not_cap_the_score(case, expected):
    blocks = score_blocks({**case, 'vol_trend': float('nan'), 'vol_z_score': float('nan')}, pe_ratio=None)
    assert normalized_score(blocks) == pytest.approx(expected)


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


def test_volume_trend_only_counts_once():
    m = {**BEST_CASE, 'vol_trend': -20.0}
    assert breadth_block(m).score == -1
    assert liquidity_block(m).score == 0


def test_collapsing_recent_volume_is_liquidity_stress():
    assert liquidity_block({**NEUTRAL_CASE, 'vol_5d': 400_000, 'vol_50d': 1_000_000}).score == -1


def test_mid_range_position_is_not_called_fair_value():
    message = sentiment_block(NEUTRAL_CASE).signals[1].message
    assert "Mid-Range" in message
    assert "Fair Value" not in message


def test_flat_noisy_series_is_mixed_trend():
    rng = np.random.default_rng(1)
    close = 100 + rng.uniform(-0.05, 0.05, 300)
    df = make_prices()
    df = df.assign(open=close, high=close * 1.001, low=close * 0.999, close=close)
    trend = trend_momentum_block(latest_metrics(compute_indicators(df))).signals[0]
    assert "Mixed Trend" in trend.message


@pytest.mark.parametrize('price, ma50, ma200, expected', [
    (100.5, 100.0, 99.0, 0),   # price within 1% of MA50
    (102.0, 100.0, 99.5, 0),   # MA50 within 1% of MA200
    (102.0, 100.0, 98.0, 1),
    (99.5, 100.0, 101.0, 0),
    (98.0, 100.0, 102.0, -1),
])
def test_trend_needs_a_clear_gap_between_averages(price, ma50, ma200, expected):
    m = {**NEUTRAL_CASE, 'price': price, 'ma50': ma50, 'ma200': ma200}
    assert trend_momentum_block(m).signals[0].score == expected


def test_momentum_change_spans_five_sessions():
    df = compute_indicators(make_prices())
    expected = df['ROC_20d'] - df['ROC_20d'].shift(5)
    pd.testing.assert_series_equal(df['Momentum_Change'], expected, check_names=False)


@pytest.mark.parametrize('win_rate, expected', [(70, 1), (65, 0), (60, 0), (40, 0), (35, 0), (30, -1)])
def test_win_rate_neutral_band(win_rate, expected):
    assert trend_momentum_block({**NEUTRAL_CASE, 'win_rate': win_rate}).signals[2].score == expected


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
    assert (block.max_up, block.max_down) == (0, 0)
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
    assert not blocks[1].signals[0].available
    assert all("nan" not in s.message.lower() for b in blocks for s in b.signals)


def test_prepare_prices_keeps_rows_with_missing_volume():
    raw = make_prices(days=300).set_index('date')
    raw.loc[raw.index[-30], 'volume'] = np.nan
    raw.loc[raw.index[-60], 'close'] = np.nan
    df = prepare_prices(raw)
    assert len(df) == 299
    m = latest_metrics(compute_indicators(df))
    assert m['vol_trend'] == pytest.approx(0.0)


def test_prepare_prices_flattens_yfinance_multiindex():
    flat = make_prices(days=5).set_index('date')
    flat.index.name = 'Date'
    flat.columns = pd.MultiIndex.from_product([[c.title() for c in flat.columns], ['AAPL']], names=['Price', 'Ticker'])
    df = prepare_prices(flat)
    assert list(df.columns) == ['date', 'open', 'high', 'low', 'close', 'volume']
    assert len(df) == 5


@pytest.mark.parametrize('vol_trend, expected', [(5.1, 1), (5.0, 0), (-10.0, 0), (-10.1, -1)])
def test_breadth_thresholds(vol_trend, expected):
    assert breadth_block({**NEUTRAL_CASE, 'vol_trend': vol_trend}).score == expected


@pytest.mark.parametrize('roc_50, expected', [(10.1, 1), (10.0, 0), (-10.0, 0), (-10.1, -1)])
def test_sentiment_performance_thresholds(roc_50, expected):
    assert sentiment_block({**NEUTRAL_CASE, 'roc_50': roc_50}).signals[0].score == expected


@pytest.mark.parametrize('position, expected', [(75.1, -1), (75.0, 0), (25.0, 0), (24.9, 1)])
def test_sentiment_position_thresholds(position, expected):
    assert sentiment_block({**NEUTRAL_CASE, 'price_position': position}).signals[1].score == expected


@pytest.mark.parametrize('z, expected, tone', [
    (1.51, -1, 'error'), (1.5, 0, 'info'), (-1.0, 0, 'info'), (-1.01, 0, 'warning'),
])
def test_volatility_thresholds(z, expected, tone):
    signal = volatility_block({**NEUTRAL_CASE, 'vol_z_score': z}).signals[0]
    assert (signal.score, signal.tone) == (expected, tone)


@pytest.mark.parametrize('vol_5d, daily_range, win_rate, expected', [
    (499_000, 1.0, 50.0, -1),  # last week's volume below half the 50-day average
    (500_000, 1.0, 50.0, 0),
    (1_000_000, 2.6, 39.0, -1),  # wide ranges with mostly down days
    (1_000_000, 2.5, 39.0, 0),
    (1_000_000, 2.6, 40.0, 0),
])
def test_liquidity_thresholds(vol_5d, daily_range, win_rate, expected):
    m = {**NEUTRAL_CASE, 'vol_5d': vol_5d, 'daily_range': daily_range, 'win_rate': win_rate}
    assert liquidity_block(m).score == expected


def tiny_prices(close, high=None, low=None):
    close = np.asarray(close, dtype=float)
    return pd.DataFrame({
        'date': pd.bdate_range('2024-01-01', periods=len(close)),
        'open': close, 'close': close,
        'high': close if high is None else np.asarray(high, dtype=float),
        'low': close if low is None else np.asarray(low, dtype=float),
        'volume': np.full(len(close), 1000.0),
    })


def test_ma50_is_mean_of_last_50_closes():
    df = compute_indicators(tiny_prices(np.arange(1, 61)))
    assert df['MA50'].iloc[-1] == pytest.approx(np.mean(np.arange(11, 61)))
    assert pd.isna(df['MA50'].iloc[48])


def test_price_position_uses_52_week_high_and_low():
    close = np.full(300, 100.0)
    high, low = close + 1, close - 1
    high[30] = 200.0  # older than 252 sessions, ignored
    high[200] = 150.0
    low[250] = 50.0
    m = latest_metrics(compute_indicators(tiny_prices(close, high, low)))
    assert m['price_position'] == pytest.approx((100 - 50) / (150 - 50) * 100)


def test_volatility_is_annualized_percent():
    # Alternating +1% / -1% returns: sample std of the 20 returns times sqrt(252), in percent
    close = 100 * np.cumprod(np.r_[1.0, np.tile([1.01, 1 / 1.01], 15)])
    df = compute_indicators(tiny_prices(close))
    returns = pd.Series(close).pct_change().iloc[-20:]
    assert df['Volatility_20d'].iloc[-1] == pytest.approx(returns.std() * np.sqrt(252) * 100)
    assert df['Volatility_20d'].iloc[-1] == pytest.approx(16.21, abs=0.01)


def test_win_rate_counts_up_days_in_last_20():
    steps = np.r_[np.ones(10), np.full(13, -1.0), np.ones(7)]  # last 20 steps: 13 down, 7 up
    close = 100 + np.cumsum(np.r_[0.0, steps])
    df = compute_indicators(tiny_prices(close))
    last_20 = np.diff(close)[-20:]
    assert df['Win_Rate'].iloc[-1] == pytest.approx((last_20 > 0).sum() / 20 * 100)
    assert df['Win_Rate'].iloc[-1] == pytest.approx(35.0)
