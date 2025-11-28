import yfinance as yf
import pandas as pd
import sys
import json

def calculate_rsi(data, window=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_composite_score():
    response = {
        "score": 50,
        "rating": "Neutral",
        "mode": "COMPOSITE",
        "details": {}
    }

    try:
        # Fetch SPY (for RSI & Trend) and ^VIX (for Volatility)
        # We need enough history for 125-day MA
        tickers = yf.Tickers("SPY ^VIX")
        
        # Fetch 6 months to be safe for 125d MA
        hist = tickers.history(period="6mo")
        
        # === 1. Volatility (VIX) - 50% Weight ===
        vix_series = hist['Close']['^VIX']
        if vix_series.empty: raise Exception("No VIX data")
        current_vix = vix_series.iloc[-1]
        
        # VIX Score: 10-40 mapped to 100-0
        vix_score = 100 - ((current_vix - 10) / 30 * 100)
        vix_score = max(0, min(100, vix_score))
        
        # === 2. Momentum (RSI) - 25% Weight ===
        spy_series = hist['Close']['SPY']
        if spy_series.empty: raise Exception("No SPY data")
        
        rsi_series = calculate_rsi(spy_series)
        current_rsi = rsi_series.iloc[-1]
        
        # RSI Score: 30 (Fear) to 70 (Greed) mapped to 0-100
        # RSI 30 -> Score 0
        # RSI 70 -> Score 100
        rsi_score = (current_rsi - 30) / 40 * 100
        rsi_score = max(0, min(100, rsi_score))
        
        # === 3. Trend (Price vs 125d MA) - 25% Weight ===
        ma_125 = spy_series.rolling(window=125).mean().iloc[-1]
        current_price = spy_series.iloc[-1]
        
        # Trend Score:
        # > 5% above MA = 100 (Greed)
        # > 5% below MA = 0 (Fear)
        diff_pct = (current_price - ma_125) / ma_125
        # Map -0.05 to 0.05 -> 0 to 100
        trend_score = (diff_pct + 0.05) / 0.10 * 100
        trend_score = max(0, min(100, trend_score))
        
        # === Composite Calculation ===
        final_score = (vix_score * 0.50) + (rsi_score * 0.25) + (trend_score * 0.25)
        
        response["score"] = round(final_score)
        response["details"] = {
            "vix": round(current_vix, 2),
            "vix_score": round(vix_score),
            "rsi": round(current_rsi, 2),
            "rsi_score": round(rsi_score),
            "trend_diff": round(diff_pct * 100, 2),
            "trend_score": round(trend_score)
        }
        
    except Exception as e:
        # === FALLBACK MODE ===
        response["mode"] = "FALLBACK"
        response["error"] = str(e)
        
        try:
            # Try to get just VIX as last resort
            vix = yf.Ticker("^VIX")
            try:
                price = vix.fast_info['last_price']
            except:
                price = vix.history(period="1d")['Close'].iloc[-1]
            
            vix_score = 100 - ((price - 10) / 30 * 100)
            response["score"] = round(max(0, min(100, vix_score)))
            response["details"]["vix"] = round(price, 2)
            
        except Exception as fallback_error:
            response["error"] += f" | Fallback failed: {fallback_error}"
            response["score"] = 50 # Ultimate fallback

    # Determine Rating
    s = response["score"]
    if s >= 75: response["rating"] = "Extreme Greed"
    elif s >= 55: response["rating"] = "Greed"
    elif s >= 45: response["rating"] = "Neutral"
    elif s >= 25: response["rating"] = "Fear"
    else: response["rating"] = "Extreme Fear"

    print(json.dumps(response))

if __name__ == "__main__":
    get_composite_score()
