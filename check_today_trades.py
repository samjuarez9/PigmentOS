import os
import requests
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv

load_dotenv()

ALPACA_API_KEY = os.environ.get("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY")

headers = {
    "APCA-API-KEY-ID": ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
    "Accept": "application/json"
}

tz_eastern = pytz.timezone('US/Eastern')
now_et = datetime.now(tz_eastern)
today_str = now_et.strftime("%Y-%m-%d")

print(f"DEBUG: Checking Alpaca for TODAY's trades ({today_str})")
print(f"Current time (ET): {now_et.strftime('%H:%M:%S')}")

# Check multiple high-volume symbols
symbols = ["NVDA", "TSLA", "SPY", "AAPL"]

for symbol in symbols:
    print(f"\n=== {symbol} ===")
    
    # Get snapshots with high volume today
    snapshot_url = f"https://data.alpaca.markets/v1beta1/options/snapshots/{symbol}"
    params = {"feed": "indicative", "limit": 50}
    
    resp = requests.get(snapshot_url, headers=headers, params=params, timeout=15)
    if resp.status_code != 200:
        print(f"  Error: {resp.status_code}")
        continue
    
    snapshots = resp.json().get("snapshots", {})
    
    # Find contracts with today's volume > 0
    active_contracts = []
    for contract, data in snapshots.items():
        day_data = data.get("day", {})
        volume = day_data.get("v", 0) or 0
        if volume > 0:
            active_contracts.append((contract, volume))
    
    active_contracts.sort(key=lambda x: -x[1])
    
    print(f"  Contracts with today's volume: {len(active_contracts)}")
    
    if active_contracts:
        top_contract, top_vol = active_contracts[0]
        print(f"  Top contract: {top_contract} (Vol: {top_vol})")
        
        # Fetch trades for top contract
        trades_url = "https://data.alpaca.markets/v1beta1/options/trades"
        trades_params = {
            "symbols": top_contract,
            "start": f"{today_str}T00:00:00Z",
            "limit": 10
        }
        
        trades_resp = requests.get(trades_url, headers=headers, params=trades_params, timeout=15)
        if trades_resp.status_code == 200:
            trades = trades_resp.json().get("trades", {}).get(top_contract, [])
            print(f"  Trades fetched today: {len(trades)}")
            if trades:
                print(f"  Sample: {trades[0].get('t')} @ {trades[0].get('p')} x {trades[0].get('s')}")
    else:
        print("  No contracts with today's volume found.")
