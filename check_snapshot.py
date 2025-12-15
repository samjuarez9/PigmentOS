import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")

symbol = "SPY"
url = f"https://api.polygon.io/v2/last/trade/{symbol}"
print(f"Requesting {url}...")

resp = requests.get(url, params={"apiKey": POLYGON_API_KEY}, timeout=10)
print(f"Status: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    print(f"Data keys: {data.keys()}")
    if "ticker" in data:
        print(f"Ticker data: {data['ticker']}")
    else:
        print("No 'ticker' key in response")
else:
    print(f"Error: {resp.text}")
