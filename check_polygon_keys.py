import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")

def check_polygon_snapshot():
    if not POLYGON_API_KEY:
        print("No API Key")
        return

    symbol = "SPY"
    # Get a few contracts
    url = f"https://api.polygon.io/v3/snapshot/options/{symbol}"
    params = {
        "apiKey": POLYGON_API_KEY,
        "limit": 1
    }
    
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        
        if "results" in data and len(data["results"]) > 0:
            first_result = data["results"][0]
            print("Keys in Polygon Result:", first_result.keys())
            if "last_quote" in first_result:
                print("Found last_quote:", first_result["last_quote"])
            else:
                print("No last_quote found.")
        else:
            print("No results found.")
            
    except Exception as e:
        print(e)

if __name__ == "__main__":
    check_polygon_snapshot()
