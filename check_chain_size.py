import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
TICKER = "SPY"

def check_chain_size():
    if not POLYGON_API_KEY:
        print("Error: POLYGON_API_KEY not found.")
        return

    print(f"Checking option chain for {TICKER}...")
    
    # 1. Get Price (Mock or Fetch)
    # Just assume a price for speed or fetch simple
    price = 135.0 # Approx NVDA price
    try:
        url = f"https://api.polygon.io/v2/aggs/ticker/{TICKER}/prev?apiKey={POLYGON_API_KEY}"
        resp = requests.get(url).json()
        if resp.get('results'):
            price = resp['results'][0]['c']
            print(f"Price: ${price}")
    except:
        pass

    min_strike = price * 0.80
    max_strike = price * 1.20
    
    print(f"Strike Range: ${min_strike:.2f} - ${max_strike:.2f}")

    # 2. Fetch Snapshot
    url = f"https://api.polygon.io/v3/snapshot/options/{TICKER}"
    params = {
        "apiKey": POLYGON_API_KEY,
        "limit": 250,
        "strike_price.gte": min_strike,
        "strike_price.lte": max_strike,
        "order": "asc",
        "sort": "strike_price"
    }

    start_time = time.time()
    count = 0
    pages = 0
    
    while url:
        pages += 1
        print(f"Fetching page {pages}...")
        resp = requests.get(url, params=params)
        if resp.status_code != 200:
            print(f"Error: {resp.status_code}")
            break
        
        data = resp.json()
        results = data.get("results", [])
        count += len(results)
        
        url = data.get("next_url")
        if url:
            params = {"apiKey": POLYGON_API_KEY} # Only api key needed for next_url
        else:
            break
            
    end_time = time.time()
    duration = end_time - start_time
    
    print(f"\nTotal Contracts: {count}")
    print(f"Total Pages: {pages}")
    print(f"Time Taken: {duration:.2f} seconds")

if __name__ == "__main__":
    check_chain_size()
