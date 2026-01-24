import requests
import os
from dotenv import load_dotenv
import json

load_dotenv()

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")

def verify_aggs_vwap():
    # Use a known option contract (SPY Jan 17 2025 500 Call - likely to have volume)
    # Note: Adjust date range to be recent as options expire
    ticker = "O:SPY250117C00500000" 
    # Use recent dates
    from datetime import datetime, timedelta
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{start_date}/{end_date}"
    params = {
        "apiKey": POLYGON_API_KEY,
        "adjusted": "true",
        "sort": "asc",
        "limit": 5
    }
    
    print(f"Fetching aggs for {ticker}...")
    resp = requests.get(url, params=params)
    
    if resp.status_code == 200:
        data = resp.json()
        results = data.get("results", [])
        if results:
            first_bar = results[0]
            print("First bar keys:", first_bar.keys())
            if 'vw' in first_bar:
                print(f"✅ VWAP found: {first_bar['vw']}")
            else:
                print("❌ VWAP NOT found in aggs")
            
            print("Full bar sample:", json.dumps(first_bar, indent=2))
        else:
            print("No results found")
    else:
        print(f"Error: {resp.status_code} - {resp.text}")

if __name__ == "__main__":
    verify_aggs_vwap()
