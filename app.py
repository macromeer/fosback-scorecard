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
### A Simple Tool to Evaluate Any Stock or ETF

Ever wonder if now is a good time to buy, hold, or sell? This app analyzes **7 key factors** that professional 
investors look at, then gives you a simple score from **-5 (Sell)** to **+5 (Buy)**.

**What makes this different?**
- ✅ Works for any stock or ETF ticker
- ✅ Uses real-time market data
- ✅ No complex jargon - clear explanations for each factor
- ✅ Based on Norman Fosback's proven framework from 1976, updated for today's algo-driven markets

**Perfect for:** Long-term investors, DIY portfolio managers, or anyone curious about market timing without the complexity.
""")

with st.expander("📖 How It Works (Click to Learn More)"):
    st.markdown("""
    The app evaluates **7 critical factors** and combines them into a single score:
    
    1. **Trend & Momentum** - Is the price moving up or down? Is it accelerating?
    2. **Breadth & Quality** - Are investors showing real interest (volume)?
    3. **Sentiment & Flows** - Is it overbought (risky) or oversold (opportunity)?
    4. **Valuation & Macro** - Is it expensive or cheap compared to the market?
    5. **Volatility Regime** - Is the market calm or stressed?
    6. **Liquidity** - Can you easily buy/sell without moving the price?
    
    Each factor gets scored, then everything combines into your **final recommendation**.
    
    **Note:** This is educational. Always do your own research and consult a financial advisor before investing.
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
            st.subheader("📈 Block 1: Trend & Momentum")
            with st.expander("ℹ️ What does this measure?"):
                st.markdown("""
                **In simple terms:** Is the stock going up or down, and how fast?
                
                - **Trend**: We compare current price to its 50-day and 200-day averages
                - **Momentum**: How much has it moved in the last 20 days?
                - **Consistency**: Does it have more "up days" than "down days"?
                
                **Why it matters:** You want to buy stocks moving up with strong momentum, not falling knives.
                """)
            
            block1_score = 0
            
            # Trend
            if current_price > ma50 and ma50 > ma200:
                trend_score = 1
                st.success("✓ **Uptrend Confirmed** - Price is above both moving averages")
            elif current_price < ma50 and ma50 < ma200:
                trend_score = -1
                st.error("✗ **Downtrend** - Price is below moving averages")
            else:
                trend_score = 0
                st.info("~ **Mixed Trend** - No clear direction")
            
            # Momentum
            if roc_20 > 5 and momentum_change > 0:
                momentum_score = 1
                st.success(f"✓ **Strong Momentum** - Up {roc_20:.1f}% in 20 days and accelerating")
            elif roc_20 < -5 or momentum_change < -2:
                momentum_score = -1
                st.error(f"✗ **Weak Momentum** - Down {roc_20:.1f}% and losing steam")
            else:
                momentum_score = 0
                st.info(f"~ **Neutral Momentum** - Sideways movement ({roc_20:+.1f}%)")
            
            # Win rate
            if win_rate > 60:
                consistency_score = 1
                st.success(f"✓ **High Consistency** - {win_rate:.1f}% of days are positive (reliable uptrend)")
            elif win_rate < 40:
                consistency_score = -1
                st.error(f"✗ **Low Consistency** - Only {win_rate:.1f}% of days are positive (choppy/weak)")
            else:
                consistency_score = 0
                st.info(f"~ **Moderate Consistency** - {win_rate:.1f}% positive days")
            
            block1_score = trend_score + momentum_score + consistency_score
            st.metric("Block 1 Score", f"{block1_score}/3")
            
            # BLOCK 2: Breadth & Quality
            st.subheader("📊 Block 2: Breadth & Quality")
            with st.expander("ℹ️ What does this measure?"):
                st.markdown("""
                **In simple terms:** Are lots of people buying/selling, or is it quiet?
                
                - **Volume Trend**: Is trading activity increasing or decreasing?
                
                **Why it matters:** Price moves with high volume are more reliable. Low volume = weak conviction.
                Think of it like a product going viral vs. one nobody talks about.
                """)
            
            block2_score = 0
            
            # Volume
            if vol_trend > 5:
                volume_score = 1
                st.success(f"✓ **Volume Expanding** - Trading activity up {vol_trend:+.1f}% (strong interest)")
            elif vol_trend < -10:
                volume_score = -1
                st.error(f"✗ **Volume Drying Up** - Activity down {vol_trend:.1f}% (losing interest)")
            else:
                volume_score = 0
                st.info(f"~ **Stable Volume** - Normal activity ({vol_trend:+.1f}%)")
            
            block2_score = volume_score
            st.metric("Block 2 Score", f"{block2_score}/3")
            
            # BLOCK 3: Sentiment & Flows
            st.subheader("🎯 Block 3: Sentiment & Flows")
            with st.expander("ℹ️ What does this measure?"):
                st.markdown("""
                **In simple terms:** Is this a good deal, or has it already run too far?
                
                - **Recent Performance**: How has it done over the last 50 days?
                - **52-Week Position**: Is it near its high (expensive) or low (cheap)?
                
                **Why it matters:** Buying near 52-week highs can be risky (might correct). 
                Buying near lows can be an opportunity (if fundamentals are intact).
                """)
            
            block3_score = 0
            
            # Performance
            if roc_50 > 10:
                performance_score = 1
                st.success(f"✓ **Strong Performance** - Up {roc_50:.1f}% over 50 days")
            elif roc_50 < -10:
                performance_score = -1
                st.error(f"✗ **Weak Performance** - Down {roc_50:.1f}% over 50 days")
            else:
                performance_score = 0
                st.info(f"~ **Neutral Performance** - Flat over 50 days ({roc_50:+.1f}%)")
            
            # Valuation sentiment
            if price_position > 75:
                valuation_sentiment_score = -1
                st.error(f"✗ **Overbought** - At {price_position:.0f}% of 52-week range (limited upside)")
            elif price_position < 25:
                valuation_sentiment_score = 1
                st.success(f"✓ **Oversold** - At {price_position:.0f}% of 52-week range (potential opportunity)")
            else:
                valuation_sentiment_score = 0
                st.info(f"~ **Fair Value** - At {price_position:.0f}% of 52-week range")
            
            block3_score = performance_score + valuation_sentiment_score
            st.metric("Block 3 Score", f"{block3_score}/3")
            
            # BLOCK 4: Valuation & Macro
            st.subheader("💰 Block 4: Valuation & Macro")
            with st.expander("ℹ️ What does this measure?"):
                st.markdown("""
                **In simple terms:** Is this expensive or cheap compared to the overall market (S&P 500)?
                
                - **Relative P/E Ratio**: We compare the stock's price-to-earnings to the S&P 500
                
                **Why it matters:** A stock trading at a big premium needs exceptional growth to justify it.
                A discount might indicate an opportunity (or a problem - needs more research!).
                """)
            
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
                            st.success(f"✓ **Attractive Valuation** - Trading {abs(relative_pe):.0f}% cheaper than S&P 500")
                        elif relative_pe > 25:
                            valuation_score = -1
                            st.error(f"✗ **Expensive** - Trading {relative_pe:.0f}% more expensive than S&P 500")
                        else:
                            valuation_score = 0
                            st.info(f"~ **Fair Value** - Trading {abs(relative_pe):.0f}% {'above' if relative_pe > 0 else 'below'} S&P 500 (reasonable)")
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
            st.subheader("📉 Block 6: Volatility Regime")
            with st.expander("ℹ️ What does this measure?"):
                st.markdown("""
                **In simple terms:** How wild are the price swings? Is the market calm or panicking?
                
                - **Volatility Z-Score**: Measures if price swings are normal, extreme, or suspiciously calm
                
                **Why it matters:** 
                - High volatility = stress/panic = risky but potential opportunities
                - Too low = complacency = danger (calm before the storm)
                - Normal = healthy market conditions
                """)
            
            if vol_z_score > 1.5:
                vol_regime_score = -1
                st.error(f"🔴 **High Stress** - Volatility {vol_z_score:.1f}x above normal (market fear/uncertainty)")
            elif vol_z_score < -1.0:
                vol_regime_score = 0
                st.warning(f"🔵 **Complacency Warning** - Volatility unusually low (risk of sudden reversal)")
            else:
                vol_regime_score = 1
                st.success(f"🟡 **Normal Regime** - Volatility at healthy levels (Z-score: {vol_z_score:.2f})")
            
            block6_score = vol_regime_score
            st.metric("Block 6 Score", f"{block6_score}/1")
            
            # BLOCK 7: Liquidity
            st.subheader("💧 Block 7: Liquidity Conditions")
            with st.expander("ℹ️ What does this measure?"):
                st.markdown("""
                **In simple terms:** How easy is it to buy or sell without affecting the price?
                
                - **Volume Trends**: Is trading activity stable or drying up?
                - **Price Stability**: Are prices jumping around erratically?
                
                **Why it matters:** Low liquidity means you might struggle to sell when you want, 
                or face big price swings. Good liquidity = smoother trading experience.
                """)
            
            if vol_trend > -3 and vol_5d > vol_50d * 0.9:
                liquidity_score = 1
                st.success("✓ **Healthy Liquidity** - Easy to trade, stable volume")
            elif vol_trend < -10 or (daily_range > 2.5 and win_rate < 40):
                liquidity_score = -1
                st.error("✗ **Liquidity Stress** - Low volume or erratic prices (be cautious)")
            else:
                liquidity_score = 0
                st.info("~ **Normal Liquidity** - Standard trading conditions")
            
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
                st.metric("Normalized Score", f"{normalized_score:+.2f}", help="Scale: -5 (Strong Sell) to +5 (Strong Buy)")
                # Add visual score bar
                score_percentage = ((normalized_score + 5) / 10) * 100
                st.progress(score_percentage / 100)
                st.caption("Scale: -5 (Sell) ← 0 (Neutral) → +5 (Buy)")
            with col2:
                st.markdown(f"**{recommendation}**")
            
            st.info(meaning)
            
            st.markdown("---")
            st.caption("""
            **💡 How to use this score:**
            - **Above +2**: Generally bullish - consider buying or holding
            - **Between -2 and +2**: Mixed signals - be cautious, wait for clarity
            - **Below -2**: Generally bearish - consider reducing position or staying out
            
            Remember: This is one tool among many. Always consider your personal financial situation, 
            risk tolerance, and investment timeline.
            """)
            
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
