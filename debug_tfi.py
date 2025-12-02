import yfinance as yf
import time

def calculate_tfi():
    print("Fetching Data...")
    
    # 1. VIX
    vix = yf.Ticker("^VIX")
    try:
        vix_val = vix.fast_info['last_price']
    except:
        vix_val = vix.history(period="1d")['Close'].iloc[-1]
    
    print(f"VIX Value: {vix_val}")
    
    # Old Formula
    vix_score = 100 - ((vix_val - 10) / 30 * 100)
    print(f"VIX Score (Raw): {vix_score}")
    vix_score = max(0, min(100, vix_score))
    print(f"VIX Score (Clamped): {vix_score}")

    # 2. Momentum
    spy = yf.Ticker("SPY")
    hist = spy.history(period="30d")
    current_price = hist['Close'].iloc[-1]
    ma_5 = hist['Close'].tail(5).mean()
    ma_20 = hist['Close'].tail(20).mean()
    
    print(f"SPY Price: {current_price}")
    print(f"SPY 5d MA: {ma_5}")
    print(f"SPY 20d MA: {ma_20}")
    
    pct_diff_5 = (current_price - ma_5) / ma_5
    pct_diff_20 = (current_price - ma_20) / ma_20
    
    print(f"Pct Diff (5d): {pct_diff_5*100:.2f}%")
    print(f"Pct Diff (20d): {pct_diff_20*100:.2f}%")
    
    mom_score_5 = 50 + (pct_diff_5 * 2500)
    mom_score_5 = max(0, min(100, mom_score_5))
    
    mom_score_20 = 50 + (pct_diff_20 * 2500)
    mom_score_20 = max(0, min(100, mom_score_20))
    
    print(f"Momentum Score (5d): {mom_score_5}")
    print(f"Momentum Score (20d): {mom_score_20}")

    # 3. Composite
    final_score = (vix_score * 0.5) + (mom_score * 0.5)
    print(f"\nFINAL SCORE: {final_score}")

if __name__ == "__main__":
    calculate_tfi()
