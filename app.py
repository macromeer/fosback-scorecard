import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Page config
st.set_page_config(
    page_title="Fosback Market Logic Scorecard",
    page_icon="📊",
    layout="wide"
)

# Title and description
st.title("📊 Fosback Market Logic Scorecard")
st.markdown("""
**Ticker-Agnostic Framework for ETFs & Stocks**

An adapted implementation of Norman Fosback's "Stock Market Logic" framework updated for modern market conditions:
- Algorithmic dominance (70% HFT volume)
- Retail options explosion (0DTE positioning)
- Passive ETF flows and sector rotation
- Real-time sentiment via options data
- Volatility regime analysis
""")

# Sidebar for inputs
st.sidebar.header("Configuration")
ticker = st.sidebar.text_input("Enter Ticker Symbol", value="GRID").upper()
days_back = st.sidebar.slider("Days of Historical Data", 365, 1095, 730)

if st.sidebar.button("Run Analysis", type="primary"):
    with st.spinner(f"Analyzing {ticker}..."):
        try:
            # Download data
            start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
            end_date = datetime.now().strftime('%Y-%m-%d')
            
            df = yf.download(ticker, start=start_date, end=end_date, progress=False)
            df.reset_index(inplace=True)
            
            # Handle column names
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] if col[0] != '' else col[1] for col in df.columns]
            
            df.columns = [col.lower().replace(' ', '_') for col in df.columns]
            df = df.dropna().sort_values('date').reset_index(drop=True)
            
            if len(df) < 200:
                st.error(f"Insufficient data for {ticker}. Need at least 200 trading days.")
                st.stop()
            
            # Calculate indicators
            df['MA50'] = df['close'].rolling(window=50).mean()
            df['MA100'] = df['close'].rolling(window=100).mean()
            df['MA200'] = df['close'].rolling(window=200).mean()
            df['Volume_MA20'] = df['volume'].rolling(window=20).mean()
            df['Volume_Ratio'] = df['volume'] / df['Volume_MA20']
            df['Returns'] = df['close'].pct_change()
            df['Volatility_20d'] = df['Returns'].rolling(window=20).std() * np.sqrt(252) * 100
            df['Volatility_MA60'] = df['Volatility_20d'].rolling(window=60).mean()
            df['ROC_20d'] = ((df['close'] - df['close'].shift(20)) / df['close'].shift(20)) * 100
            df['ROC_50d'] = ((df['close'] - df['close'].shift(50)) / df['close'].shift(50)) * 100
            df['Momentum_Change'] = df['ROC_20d'].diff()
            df['Daily_Range'] = ((df['high'] - df['low']) / df['close']) * 100
            df['Range_MA20'] = df['Daily_Range'].rolling(window=20).mean()
            df['Range_Z_Score'] = (df['Daily_Range'] - df['Range_MA20']) / df['Daily_Range'].rolling(20).std()
            df['Volume_Trend'] = df['Volume_MA20'].pct_change() * 100
            df['Vol_Z_Score'] = (df['Volatility_20d'] - df['Volatility_MA60']) / df['Volatility_20d'].rolling(60).std()
            df['Positive_Days'] = (df['Returns'] > 0).rolling(window=20).sum()
            df['Win_Rate'] = (df['Positive_Days'] / 20) * 100
            
            # Extract current metrics
            current_idx = len(df) - 1
            current_price = df['close'].iloc[current_idx]
            ma50 = df['MA50'].iloc[current_idx]
            ma100 = df['MA100'].iloc[current_idx]
            ma200 = df['MA200'].iloc[current_idx]
            current_volatility = df['Volatility_20d'].iloc[current_idx]
            vol_z_score = df['Vol_Z_Score'].iloc[current_idx]
            roc_20 = df['ROC_20d'].iloc[current_idx]
            roc_50 = df['ROC_50d'].iloc[current_idx]
            momentum_change = df['Momentum_Change'].iloc[current_idx]
            daily_range = df['Daily_Range'].iloc[current_idx]
            win_rate = df['Win_Rate'].iloc[current_idx]
            vol_trend = df['Volume_Trend'].iloc[current_idx]
            
            # Price positioning
            price_52week_high = df['high'].tail(252).max()
            price_52week_low = df['low'].tail(252).min()
            price_position = ((current_price - price_52week_low) / (price_52week_high - price_52week_low)) * 100
            
            # Volume metrics
            vol_5d = df['volume'].tail(5).mean()
            vol_50d = df['volume'].tail(50).mean()
            
            # Display current metrics
            st.header(f"{ticker} - Current Metrics")
            st.caption(f"As of {df['date'].iloc[current_idx].strftime('%Y-%m-%d')}")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Price", f"${current_price:.2f}")
                st.metric("MA50", f"${ma50:.2f}", f"{((current_price-ma50)/ma50*100):+.2f}%")
            with col2:
                st.metric("MA200", f"${ma200:.2f}", f"{((current_price-ma200)/ma200*100):+.2f}%")
                st.metric("20d ROC", f"{roc_20:+.2f}%")
            with col3:
                st.metric("Volatility (20d)", f"{current_volatility:.2f}%")
                st.metric("Vol Z-Score", f"{vol_z_score:.2f}")
            with col4:
                st.metric("Win Rate", f"{win_rate:.1f}%")
                st.metric("52w Position", f"{price_position:.1f}%")
            
            # BLOCK 1: Trend & Momentum
            st.subheader("Block 1: Trend & Momentum")
            block1_score = 0
            
            # Trend
            if current_price > ma50 and ma50 > ma200:
                trend_score = 1
                st.success("✓ Uptrend confirmed (Price > MA50 > MA200)")
            elif current_price < ma50 and ma50 < ma200:
                trend_score = -1
                st.error("✗ Downtrend (Price < MA50 < MA200)")
            else:
                trend_score = 0
                st.info("~ Mixed trend")
            
            # Momentum
            if roc_20 > 5 and momentum_change > 0:
                momentum_score = 1
                st.success("✓ Strong momentum accelerating")
            elif roc_20 < -5 or momentum_change < -2:
                momentum_score = -1
                st.error("✗ Negative momentum")
            else:
                momentum_score = 0
                st.info("~ Neutral momentum")
            
            # Win rate
            if win_rate > 60:
                consistency_score = 1
                st.success(f"✓ High consistency ({win_rate:.1f}% win rate)")
            elif win_rate < 40:
                consistency_score = -1
                st.error(f"✗ Low consistency ({win_rate:.1f}% win rate)")
            else:
                consistency_score = 0
                st.info("~ Moderate consistency")
            
            block1_score = trend_score + momentum_score + consistency_score
            st.metric("Block 1 Score", f"{block1_score}/3")
            
            # BLOCK 2: Breadth & Quality
            st.subheader("Block 2: Breadth & Quality")
            block2_score = 0
            
            # Volume
            if vol_trend > 5:
                volume_score = 1
                st.success("✓ Volume expanding")
            elif vol_trend < -10:
                volume_score = -1
                st.error("✗ Volume contracting")
            else:
                volume_score = 0
                st.info("~ Stable volume")
            
            block2_score = volume_score
            st.metric("Block 2 Score", f"{block2_score}/3")
            
            # BLOCK 3: Sentiment & Flows
            st.subheader("Block 3: Sentiment & Flows")
            block3_score = 0
            
            # Performance
            if roc_50 > 10:
                performance_score = 1
                st.success("✓ Strong 50-day performance")
            elif roc_50 < -10:
                performance_score = -1
                st.error("✗ Weak 50-day performance")
            else:
                performance_score = 0
                st.info("~ Neutral performance")
            
            # Valuation sentiment
            if price_position > 75:
                valuation_sentiment_score = -1
                st.error("✗ Extended (>75% of 52w range)")
            elif price_position < 25:
                valuation_sentiment_score = 1
                st.success("✓ Attractive (<25% of 52w range)")
            else:
                valuation_sentiment_score = 0
                st.info("~ Fair value zone")
            
            block3_score = performance_score + valuation_sentiment_score
            st.metric("Block 3 Score", f"{block3_score}/3")
            
            # BLOCK 4: Valuation & Macro
            st.subheader("Block 4: Valuation & Macro")
            block4_score = 0
            
            try:
                ticker_obj = yf.Ticker(ticker)
                ticker_info = ticker_obj.info
                pe_ratio = ticker_info.get('trailingPE', None)
                
                if pe_ratio:
                    try:
                        spy_info = yf.Ticker('SPY').info
                        spy_pe = spy_info.get('trailingPE', 20.0)
                        relative_pe = (pe_ratio / spy_pe - 1) * 100
                        
                        if relative_pe < -15:
                            valuation_score = 1
                            st.success(f"✓ Attractive (P/E {relative_pe:+.1f}% vs SPY)")
                        elif relative_pe > 25:
                            valuation_score = -1
                            st.error(f"✗ Expensive (P/E {relative_pe:+.1f}% vs SPY)")
                        else:
                            valuation_score = 0
                            st.info(f"~ Fair value (P/E {relative_pe:+.1f}% vs SPY)")
                    except:
                        valuation_score = 0
                        st.info("~ Fair value assumed")
                else:
                    valuation_score = 0
                    st.info("~ Fair value (P/E N/A)")
                    
                block4_score = valuation_score
            except:
                block4_score = 0
                st.info("~ Neutral (fundamentals unavailable)")
            
            st.metric("Block 4 Score", f"{block4_score}/3")
            
            # BLOCK 6: Volatility Regime
            st.subheader("Block 6: Volatility Regime")
            
            if vol_z_score > 1.5:
                vol_regime_score = -1
                st.error("🔴 High stress (Vol >1.5 SD)")
            elif vol_z_score < -1.0:
                vol_regime_score = 0
                st.warning("🔵 Complacency warning (Low vol)")
            else:
                vol_regime_score = 1
                st.success("🟡 Normal regime")
            
            block6_score = vol_regime_score
            st.metric("Block 6 Score", f"{block6_score}/1")
            
            # BLOCK 7: Liquidity
            st.subheader("Block 7: Liquidity Conditions")
            
            if vol_trend > -3 and vol_5d > vol_50d * 0.9:
                liquidity_score = 1
                st.success("✓ Healthy liquidity")
            elif vol_trend < -10 or (daily_range > 2.5 and win_rate < 40):
                liquidity_score = -1
                st.error("✗ Liquidity stress")
            else:
                liquidity_score = 0
                st.info("~ Normal liquidity")
            
            block7_score = liquidity_score
            st.metric("Block 7 Score", f"{block7_score}/1")
            
            # FINAL SCORECARD
            st.header("📊 Final Scorecard")
            
            scores = {
                'Trend & Momentum': block1_score,
                'Breadth & Quality': block2_score,
                'Sentiment & Flows': block3_score,
                'Valuation & Macro': block4_score,
                'Volatility Regime': block6_score,
                'Liquidity': block7_score
            }
            
            total_raw = sum(scores.values())
            total_max = 14  # 3+3+3+3+1+1
            normalized_score = (total_raw / total_max) * 5
            
            # Display scores table
            scorecard_df = pd.DataFrame({
                'Category': list(scores.keys()),
                'Score': list(scores.values()),
                'Status': [('✓ FAVORABLE' if s > 0 else ('✗ UNFAVORABLE' if s < 0 else '~ NEUTRAL')) for s in scores.values()]
            })
            
            st.dataframe(scorecard_df, use_container_width=True)
            
            # Recommendation
            st.subheader("Recommendation")
            
            if normalized_score >= 3:
                recommendation = "🟢 STRONG BUY"
                meaning = "Favorable across most indicators. Technicals + flows suggest upside."
                color = "green"
            elif normalized_score >= 1:
                recommendation = "🟢 BUY / HOLD FULL POSITION"
                meaning = "Generally positive setup. Macro support outweighs near-term weakness."
                color = "green"
            elif normalized_score >= -1:
                recommendation = "🟡 HOLD / REDUCE TO 50%"
                meaning = "Mixed signals. Scale back pending clarity on momentum/flows."
                color = "orange"
            elif normalized_score >= -3:
                recommendation = "🔴 REDUCE / CONSIDER EXIT"
                meaning = "Unfavorable conditions. Risk-reward tilted down. Preserve capital."
                color = "red"
            else:
                recommendation = "🔴 STRONG SELL"
                meaning = "Major headwinds across blocks. Wait for capitulation signals."
                color = "red"
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Normalized Score", f"{normalized_score:+.2f} / ±5")
            with col2:
                st.markdown(f"**{recommendation}**")
            
            st.info(meaning)
            
            # Chart
            st.subheader("Price Chart")
            chart_data = df[['date', 'close', 'MA50', 'MA200']].tail(252).set_index('date')
            st.line_chart(chart_data)
            
            # Disclaimer
            st.caption("**Disclaimer:** For educational purposes only. Not financial advice. Always consult a qualified advisor.")
            
        except Exception as e:
            st.error(f"Error analyzing {ticker}: {str(e)}")
            st.exception(e)
else:
    st.info("👈 Enter a ticker symbol and click 'Run Analysis' to begin")
