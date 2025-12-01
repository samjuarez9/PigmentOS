import yfinance as yf
import pandas as pd
import datetime

def test_yfinance_options():
    print("🐳 Testing Yahoo Finance Options Data...", flush=True)
    
    # List of active tickers to check
    tickers = ["NVDA", "TSLA", "AAPL", "AMD", "SPY", "QQQ", "IWM", "COIN", "MSTR"]
    
    found_trades = []
    
    for symbol in tickers:
        try:
            print(f"Checking {symbol}...", flush=True)
            ticker = yf.Ticker(symbol)
            
            # Get expiration dates
            expirations = ticker.options
            if not expirations:
                print(f"No options found for {symbol}")
                continue
                
            # Check first expiration
            first_expiry = expirations[0]
            print(f"  Expiry: {first_expiry}")
            
            opts = ticker.option_chain(first_expiry)
            calls = opts.calls
            puts = opts.puts
            
            # Filter for high volume/OI
            # Simple "unusual" criteria: Volume > 1000 and Volume > OI
            
            unusual_calls = calls[(calls['volume'] > 1000) & (calls['volume'] > calls['openInterest'])]
            unusual_puts = puts[(puts['volume'] > 1000) & (puts['volume'] > puts['openInterest'])]
            
            if not unusual_calls.empty:
                print(f"  Found {len(unusual_calls)} unusual calls")
                for _, row in unusual_calls.head(2).iterrows():
                    found_trades.append({
                        "symbol": symbol,
                        "type": "CALL",
                        "strike": row['strike'],
                        "expiry": first_expiry,
                        "volume": row['volume'],
                        "oi": row['openInterest'],
                        "lastPrice": row['lastPrice']
                    })
                    
            if not unusual_puts.empty:
                print(f"  Found {len(unusual_puts)} unusual puts")
                for _, row in unusual_puts.head(2).iterrows():
                    found_trades.append({
                        "symbol": symbol,
                        "type": "PUT",
                        "strike": row['strike'],
                        "expiry": first_expiry,
                        "volume": row['volume'],
                        "oi": row['openInterest'],
                        "lastPrice": row['lastPrice']
                    })
                    
        except Exception as e:
            print(f"  Error checking {symbol}: {e}")
            
    print(f"\nTotal Potential Whales Found: {len(found_trades)}")
    if found_trades:
        print("Sample Trade:")
        print(found_trades[0])

if __name__ == "__main__":
    test_yfinance_options()
