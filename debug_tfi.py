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
    
    # Consensus Tuning (Aggressive)
    # VIX 12->100, VIX 22->0
    vix_score = 100 - ((vix_val - 12) * 10)
    print(f"VIX Score (Raw): {vix_score}")
    vix_score = max(0, min(100, vix_score))
    print(f"VIX Score (Clamped): {vix_score}")

    # 2. Momentum
    spy = yf.Ticker("SPY")
    hist = spy.history(period="10d")
    current_price = hist['Close'].iloc[-1]
    ma_5 = hist['Close'].tail(5).mean()
    
    print(f"SPY Price: {current_price}")
    print(f"SPY 5d MA: {ma_5}")
    
    pct_diff = (current_price - ma_5) / ma_5
    print(f"Pct Diff: {pct_diff*100:.2f}%")
    
    # Aggressive Momentum
    mom_score = 50 + (pct_diff * 5000)
    print(f"Momentum Score (Raw): {mom_score}")
    mom_score = max(0, min(100, mom_score))
    print(f"Momentum Score (Clamped): {mom_score}")

    # 3. Composite
    final_score = (vix_score * 0.5) + (mom_score * 0.5)
    print(f"\nFINAL SCORE: {final_score}")

if __name__ == "__main__":
    calculate_tfi()
