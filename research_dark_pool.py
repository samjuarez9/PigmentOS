import yfinance as yf
import pandas as pd

def check_large_trades(symbol):
    print(f"--- Checking {symbol} ---")
    ticker = yf.Ticker(symbol)
    
    # Check 1-minute history for volume spikes
    print("Fetching 1m history...")
    hist = ticker.history(period="1d", interval="1m")
    
    if hist.empty:
        print("No history found.")
        return

    # Calculate average volume
    avg_vol = hist['Volume'].mean()
    print(f"Average 1m Volume: {avg_vol:,.0f}")
    
    # Find "Block Trades" (e.g., > 10x average)
    large_blocks = hist[hist['Volume'] > (avg_vol * 10)]
    
    if not large_blocks.empty:
        print(f"Found {len(large_blocks)} potential block trades:")
        print(large_blocks[['Close', 'Volume']].tail())
    else:
        print("No significant volume spikes found.")

    # Check for other info
    # print("Info keys:", ticker.info.keys())

check_large_trades("SPY")
check_large_trades("NVDA")
