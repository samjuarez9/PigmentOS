import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
SYMBOL = "SPY"

def check_polygon_snapshot():
    if not POLYGON_API_KEY:
        print("No API Key found")
        return

    url = f"https://api.polygon.io/v3/snapshot/options/{SYMBOL}"
    params = {
        "apiKey": POLYGON_API_KEY,
        "limit": 10,
        "strike_price.gte": 400,
        "strike_price.lte": 600
    }
    
    print(f"Fetching snapshot for {SYMBOL}...")
    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            print(f"Found {len(results)} contracts.")
            
            for i, contract in enumerate(results[:5]):
                print(f"\n--- Contract {i+1} ---")
                details = contract.get("details", {})
                greeks = contract.get("greeks", {})
                print(f"Ticker: {details.get('ticker')}")
                print(f"Greeks: {json.dumps(greeks, indent=2)}")
                print(f"Delta: {greeks.get('delta')}")
        else:
            print(f"Error: {resp.status_code} - {resp.text}")
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    check_polygon_snapshot()
