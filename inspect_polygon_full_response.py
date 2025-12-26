import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")

def inspect_full_polygon_response():
    symbol = "SPY"
    # Use a standalone price to get the snapshot
    current_price = 595.0
    strike_low = int(current_price * 0.95)
    strike_high = int(current_price * 1.05)

    url = f"https://api.polygon.io/v3/snapshot/options/{symbol}"
    params = {
        "apiKey": POLYGON_API_KEY,
        "limit": 50, 
        "strike_price.gte": strike_low,
        "strike_price.lte": strike_high
    }

    print(f"Requesting {url}...")
    try:
        resp = requests.get(url, params=params, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("results"):
                # Find a result with greeks
                found_greeks = False
                for result in data["results"]:
                    if result.get("greeks"):
                        print("Found contract with Greeks:")
                        print(json.dumps(result, indent=2))
                        found_greeks = True
                        break
                
                if not found_greeks:
                    print("No contracts with Greeks found in the first 50 results.")
                    print("First result sample:")
                    print(json.dumps(data["results"][0], indent=2))
            else:
                print("No results found.")
        else:
            print(f"Error: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    inspect_full_polygon_response()
