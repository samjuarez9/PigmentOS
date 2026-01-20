import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")

def check_trade_data():
    # Use a ticker we know exists or might exist. 
    # Try a SPY option that is likely active.
    # SPY price is approx 590-600.
    # Let's try to find one via snapshot first to be sure.
    
    print("--- Finding Active Contract ---")
    snapshot_url = f"https://api.polygon.io/v3/snapshot/options/SPY?apiKey={POLYGON_API_KEY}&limit=1"
    try:
        r = requests.get(snapshot_url)
        if r.status_code != 200:
            print("Failed to get snapshot.")
            return
            
        res = r.json().get("results", [])
        if not res:
            print("No options found.")
            return
            
        ticker = res[0]["details"]["ticker"]
        print(f"Testing with: {ticker}")
        
        # Now fetch trades
        print(f"\n--- Fetching Trades for {ticker} ---")
        # Correct Endpoint: v3/trades/{ticker}
        trades_url = f"https://api.polygon.io/v3/trades/{ticker}"
        params = {
            "apiKey": POLYGON_API_KEY,
            "limit": 5,
            "sort": "timestamp",
            "order": "desc" # Get most recent
        }
        
        tr = requests.get(trades_url, params=params)
        if tr.status_code == 200:
            trades = tr.json().get("results", [])
            print(f"Fetched {len(trades)} trades.")
            for t in trades:
                print(json.dumps(t, indent=2))
        else:
            print(f"Failed to fetch trades: {tr.status_code}")
            print(tr.text)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_trade_data()
