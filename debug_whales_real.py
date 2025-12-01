import yfinance as yf
import pandas as pd
import pytz
from datetime import datetime

def debug_nvda():
    ticker = "NVDA"
    print(f"--- DEBUGGING {ticker} OPTIONS ---")
    
    stock = yf.Ticker(ticker)
    exps = stock.options
    if not exps:
        print("No expirations found!")
        return

    expiry = exps[0]
    print(f"Expiry: {expiry}")
    
    chain = stock.option_chain(expiry)
    calls = chain.calls
    
    print(f"Total Calls: {len(calls)}")
    
    # Check dates
    ny_tz = pytz.timezone('America/New_York')
    today_ny = datetime.now(ny_tz).date()
    print(f"Today (NY): {today_ny}")
    
    if not calls.empty:
        sample = calls.iloc[0]
        ts = sample['lastTradeDate']
        print(f"Sample Trade Date (Raw): {ts}")
        
        if hasattr(ts, 'to_pydatetime'): dt = ts.to_pydatetime()
        else: dt = ts
        if dt.tzinfo is None: dt = pytz.utc.localize(dt)
        trade_date = dt.astimezone(ny_tz).date()
        
        print(f"Sample Trade Date (Converted): {trade_date}")
        print(f"Days Diff: {(today_ny - trade_date).days}")
        
        # Check logic
        is_recent = (today_ny - trade_date).days <= 4
        print(f"Is Recent? {is_recent}")

if __name__ == "__main__":
    debug_nvda()
