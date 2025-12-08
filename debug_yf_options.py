import yfinance as yf
import pandas as pd

print("Fetching SPY...")
ticker = yf.Ticker("SPY")

print("Fetching Options Dates...")
try:
    opts = ticker.options
    print(f"Options Dates: {opts}")
except Exception as e:
    print(f"Error fetching options: {e}")

if opts:
    print(f"Fetching Chain for {opts[0]}...")
    chain = ticker.option_chain(opts[0])
    print(f"Calls: {len(chain.calls)}")
    print(f"Puts: {len(chain.puts)}")
else:
    print("No options found.")
