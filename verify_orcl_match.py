import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")

def verify_orcl_match():
    if not ALPACA_API_KEY or not POLYGON_API_KEY:
        print("Missing API Keys")
        return

    symbol = "ORCL"
    print(f"🔍 Fetching Alpaca Snapshot for {symbol}...")
    
    # 1. Get Alpaca Snapshot
    url = f"https://data.alpaca.markets/v1beta1/options/snapshots/{symbol}"
    headers = {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY
    }
    params = {"limit": 5} # Just get a few
    
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        data = resp.json()
        snapshots = data.get("snapshots", {})
        
        if not snapshots:
            print("No Alpaca data found.")
            return

        # Pick the first one
        occ_symbol = list(snapshots.keys())[0]
        alpaca_data = snapshots[occ_symbol]
        print(f"✅ Alpaca Found: {occ_symbol}")
        print(f"   - Latest Trade: {alpaca_data.get('latestTrade', {}).get('p')}")
        print(f"   - Bid/Ask: {alpaca_data.get('latestQuote', {}).get('bp')} / {alpaca_data.get('latestQuote', {}).get('ap')}")

        # 2. Fetch Polygon Data for SAME Symbol
        print(f"\n🔍 Fetching Polygon Data for {occ_symbol}...")
        
        # Polygon expects "O:" prefix sometimes, or just the symbol. 
        # Let's try exact match first.
        poly_symbol = f"O:{occ_symbol}" # e.g. O:ORCL250117C...
        
        # Extract underlying for v3 endpoint
        # v3/snapshot/options/{underlying}/{contract}
        underlying = "ORCL" 
        
        poly_url = f"https://api.polygon.io/v3/snapshot/options/{underlying}/{poly_symbol}"
        poly_params = {"apiKey": POLYGON_API_KEY}
        
        poly_resp = requests.get(poly_url, params=poly_params, timeout=10)
        poly_data = poly_resp.json()
        
        if "results" in poly_data:
            res = poly_data["results"]
            print(f"✅ Polygon Found: {res.get('details', {}).get('ticker')}")
            print(f"   - Open Interest: {res.get('open_interest')}")
            print(f"   - Strike: {res.get('details', {}).get('strike_price')}")
            print(f"   - Expiry: {res.get('details', {}).get('expiration_date')}")
            
            print("\n🎉 MATCH CONFIRMED!")
            print("We can successfully link Alpaca Trade Data with Polygon OI Data using the OCC Symbol.")
        else:
            print("❌ Polygon data not found for this symbol.")
            print(poly_data)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    verify_orcl_match()
