import yfinance as yf
import json

def check_premarket():
    symbol = "SPY"
    print(f"Fetching info for {symbol}...")
    t = yf.Ticker(symbol)
    
    # Check fast_info first (faster)
    print("\n--- fast_info ---")
    for key in ['last_price', 'previous_close', 'open', 'day_high', 'day_low']:
        try:
            val = getattr(t.fast_info, key)
            print(f"{key}: {val}")
        except:
            print(f"{key}: N/A")
            
    # Check full info (slower but more detailed)
    print("\n--- info (subset) ---")
    info = t.info
    keys_to_check = [
        'currentPrice', 'preMarketPrice', 'postMarketPrice', 
        'regularMarketPrice', 'regularMarketPreviousClose',
        'marketState'
    ]
    
    for k in keys_to_check:
        print(f"{k}: {info.get(k, 'N/A')}")

if __name__ == "__main__":
    check_premarket()
