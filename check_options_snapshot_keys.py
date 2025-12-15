import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")

symbol = "SPY"
# Use a standalone price to get the snapshot
current_price = 595.0
strike_low = int(current_price * 0.90)
strike_high = int(current_price * 1.10)

url = f"https://api.polygon.io/v3/snapshot/options/{symbol}"
params = {
    "apiKey": POLYGON_API_KEY,
    "limit": 1, # Just need 1 to check root keys
    "strike_price.gte": strike_low,
    "strike_price.lte": strike_high
}

print(f"Requesting {url}...")
resp = requests.get(url, params=params, timeout=10)

if resp.status_code == 200:
    data = resp.json()
    print(f"Root keys: {list(data.keys())}")
    # Check if underlying price is in there
    if "underlying_asset" in data:
        print(f"underlying_asset: {data['underlying_asset']}")
    else:
        print("No 'underlying_asset' key.")
else:
    print(f"Error: {resp.status_code} {resp.text}")
