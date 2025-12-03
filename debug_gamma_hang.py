import time
import yfinance as yf
import pandas as pd
import socket

# Set timeout like in run.py
socket.setdefaulttimeout(5)

def refresh_gamma_logic():
    print("👾 Scanning Gamma (SPY)...", flush=True)
    
    symbol = "SPY"
    try:
        ticker = yf.Ticker(symbol)
        
        print("Getting price...", flush=True)
        # Get Current Price
        try:
            current_price = ticker.fast_info.last_price
        except:
            current_price = ticker.info.get('regularMarketPrice', 0)
        print(f"Price: {current_price}", flush=True)
            
        if not current_price:
            print(f"Gamma Scan Failed: No price for {symbol}")
            return
            
        print("Getting expirations...", flush=True)
        # Get Nearest Expiration
        expirations = ticker.options
        print(f"Expirations: {len(expirations)} found", flush=True)
        if not expirations:
            print(f"Gamma Scan Failed: No options for {symbol}")
            return
            
        # Use the first expiration (0DTE/Weekly)
        expiry = expirations[0]
        print(f"Using expiry: {expiry}", flush=True)
        
        print("Fetching chain...", flush=True)
        # Fetch Chain
        opts = ticker.option_chain(expiry)
        print("Chain fetched.", flush=True)
        calls = opts.calls
        puts = opts.puts
        
        print(f"Calls: {len(calls)}, Puts: {len(puts)}", flush=True)
        
    except Exception as e:
        print(f"Gamma Scan Failed: {e}")

if __name__ == "__main__":
    refresh_gamma_logic()
