import yfinance as yf
import pandas as pd

def check_timestamps():
    print("Checking timestamps for NVDA options...", flush=True)
    ticker = yf.Ticker("NVDA")
    expiry = ticker.options[0]
    opts = ticker.option_chain(expiry)
    calls = opts.calls
    
    if not calls.empty:
        print("Sample Call Data:")
        sample = calls.iloc[0]
        print(f"Last Trade Date: {sample['lastTradeDate']}")
        print(f"Type: {type(sample['lastTradeDate'])}")
        
        # Check if we can sort
        sorted_calls = calls.sort_values(by='lastTradeDate', ascending=False)
        print("Top 3 Most Recent Calls:")
        print(sorted_calls[['contractSymbol', 'lastTradeDate', 'volume']].head(3))
    else:
        print("No calls found.")

if __name__ == "__main__":
    check_timestamps()
