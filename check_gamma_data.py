import yfinance as yf
import pandas as pd
import datetime

def check_spy_options():
    print(f"Checking SPY options at {datetime.datetime.now()}")
    try:
        ticker = yf.Ticker("SPY")
        
        # Check price
        try:
            price = ticker.fast_info.last_price
            print(f"SPY Price: {price}")
        except:
            print("Could not get fast_info price")

        # Check expirations
        exps = ticker.options
        if not exps:
            print("No expirations found!")
            return

        print(f"Found {len(exps)} expirations. First: {exps[0]}")
        
        # Check chain
        opts = ticker.option_chain(exps[0])
        calls = opts.calls
        puts = opts.puts
        
        print(f"Calls: {len(calls)}, Puts: {len(puts)}")
        
        if not calls.empty:
            print("Sample Call:")
            print(calls.iloc[0][['strike', 'volume', 'openInterest', 'lastPrice']])
            
            total_vol = calls['volume'].sum() + puts['volume'].sum()
            print(f"Total Volume for {exps[0]}: {total_vol}")
            
            if total_vol == 0:
                print("WARNING: Total volume is 0. Data might be delayed or market just opened.")
            else:
                print("Data seems populated.")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_spy_options()
