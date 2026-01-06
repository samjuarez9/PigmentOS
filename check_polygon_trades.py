import os
import requests
import datetime
import pytz
from dotenv import load_dotenv
import json

load_dotenv()

POLYGON_API_KEY = os.environ.get("POLYGON_API_KEY")
if not POLYGON_API_KEY:
    print("⚠️ POLYGON_API_KEY not found")
    exit(1)

SYMBOL = "SPY"
print(f"DEBUG: Checking Polygon Trades for {SYMBOL}")

# 1. Find an active contract
print("Fetching active contracts...")
url = f"https://api.polygon.io/v3/reference/options/contracts?underlying_ticker={SYMBOL}&expired=false&limit=10&apiKey={POLYGON_API_KEY}"
resp = requests.get(url)
if resp.status_code != 200:
    print(f"Error fetching contracts: {resp.status_code}")
    exit(1)

contracts = resp.json().get("results", [])
if not contracts:
    print("No contracts found")
    exit(1)

target_contract = contracts[0]["ticker"]
print(f"Analyzing Contract: {target_contract}")

# 2. Fetch Trades
print("Fetching trades...")
# Use v3 trades endpoint
trades_url = f"https://api.polygon.io/v3/trades/{target_contract}?limit=10&apiKey={POLYGON_API_KEY}"
resp = requests.get(trades_url)

if resp.status_code != 200:
    print(f"Error fetching trades: {resp.status_code} {resp.text}")
    exit(1)

trades = resp.json().get("results", [])
print(f"Found {len(trades)} trades")

if trades:
    print("\n--- Sample Trade Data ---")
    # Print first trade in full to see fields
    print(json.dumps(trades[0], indent=2))
    
    print("\n--- Field Analysis ---")
    for t in trades:
        price = t.get("price")
        size = t.get("size")
        conditions = t.get("conditions")
        sip_timestamp = t.get("sip_timestamp")
        
        # Check for aggressor side or similar
        # Polygon sometimes puts this in 'conditions' or specific fields
        print(f"Price: {price} | Size: {size} | Cond: {conditions} | TS: {sip_timestamp}")

else:
    print("No trades found for this contract today/recently.")
