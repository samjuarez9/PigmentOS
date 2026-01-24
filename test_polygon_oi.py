
import requests
import os
from dotenv import load_dotenv
import datetime

load_dotenv()
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")

# Contract: O:NVDA260130C00195000 (Exp Jan 30, 2026)
# Let's try to get data for yesterday (or last trading day)
contract = "O:NVDA260130C00195000"
date = "2026-01-23" # Friday

url = f"https://api.polygon.io/v1/open-close/{contract}/{date}"
params = {"apiKey": POLYGON_API_KEY, "adjusted": "true"}

print(f"Fetching {url}...")
resp = requests.get(url, params=params)

print(f"Status: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    print(f"Open: {data.get('open')}")
    print(f"Close: {data.get('close')}")
    print(f"Volume: {data.get('volume')}")
    print(f"Open Interest: {data.get('open_interest')}") # This is what we need
else:
    print(f"Error: {resp.text}")
