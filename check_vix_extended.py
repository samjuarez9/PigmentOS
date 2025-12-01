import yfinance as yf

def check_vix():
    symbol = "^VIX"
    print(f"Fetching info for {symbol}...")
    t = yf.Ticker(symbol)
    
    print("\n--- fast_info ---")
    for key in ['last_price', 'previous_close']:
        try:
            val = getattr(t.fast_info, key)
            print(f"{key}: {val}")
        except:
            print(f"{key}: N/A")
            
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
    check_vix()
