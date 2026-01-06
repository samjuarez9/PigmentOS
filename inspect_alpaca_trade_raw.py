import os
import requests
import json
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz

load_dotenv()

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")

def inspect_raw():
    headers = {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
        "Accept": "application/json"
    }
    
    # Use a known active contract
    symbol = "NVDA260109C00090000" 
    
    print(f"--- Inspecting Raw Trade Data for {symbol} ---")
    
    trades_url = "https://data.alpaca.markets/v1beta1/options/trades"
    
    # Get trades from today
    tz_eastern = pytz.timezone('US/Eastern')
    now_et = datetime.now(tz_eastern)
    start_date = now_et.strftime("%Y-%m-%dT00:00:00Z")
    
    params = {
        "symbols": symbol,
        "start": start_date,
        "limit": 5
    }
    
    resp = requests.get(trades_url, headers=headers, params=params)
    
    if resp.status_code == 200:
        data = resp.json()
        trades = data.get("trades", {}).get(symbol, [])
        
        if trades:
            print(f"Found {len(trades)} trades. Showing raw JSON for the first one:")
            print(json.dumps(trades[0], indent=4))
            
            print("\nField Legend (Standard Alpaca):")
            print("t: Timestamp")
            print("x: Exchange Code")
            print("p: Price")
            print("s: Size")
            print("c: Condition Code")
            print("i: Trade ID")
            print("z: Tape")
        else:
            print("No trades found for today.")
    else:
        print(f"Error: {resp.status_code} - {resp.text}")

if __name__ == "__main__":
    inspect_raw()
