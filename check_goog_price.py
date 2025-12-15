import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")

def check_price(symbol):
    print(f"\n🔍 Checking Price for {symbol}...")
    
    # 1. Try Snapshot (Expect 403, but good to verify)
    url_snap = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/{symbol}"
    try:
        resp = requests.get(url_snap, params={"apiKey": POLYGON_API_KEY}, timeout=5)
        print(f"  Snapshot Status: {resp.status_code}")
    except Exception as e:
        print(f"  Snapshot Error: {e}")

    # 2. Try Prev Close (The Fallback)
    url_prev = f"https://api.polygon.io/v2/aggs/ticker/{symbol}/prev"
    try:
        resp = requests.get(url_prev, params={"apiKey": POLYGON_API_KEY}, timeout=5)
        print(f"  Prev Close Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            if data.get("results"):
                print(f"  ✅ Prev Close Price: {data['results'][0].get('c')}")
            else:
                print("  ❌ Prev Close: No results found.")
        else:
            print(f"  ❌ Prev Close Error: {resp.text}")
            
    except Exception as e:
        print(f"  Prev Close Exception: {e}")

check_price("GOOGL")
check_price("GOOG")
