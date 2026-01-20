import requests
import os
from datetime import datetime, timedelta

def load_env():
    try:
        with open('.env', 'r') as f:
            for line in f:
                if line.startswith('POLYGON_API_KEY='):
                    return line.strip().split('=')[1]
    except:
        pass
    return os.environ.get('POLYGON_API_KEY')

api_key = load_env()
if not api_key:
    print("Error: POLYGON_API_KEY not found.")
    exit(1)

ticker = "O:NVDA250117C00140000"
# Get last 10 days
to_date = "2025-01-10"
from_date = "2025-01-01"

url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{from_date}/{to_date}"
params = {"apiKey": api_key}

print(f"Fetching {url}...")
resp = requests.get(url, params=params)

if resp.status_code == 200:
    data = resp.json()
    print("Response keys:", data.keys())
    if 'results' in data:
        print(f"Got {len(data['results'])} bars")
        for bar in data['results']:
            print(f"Date: {datetime.fromtimestamp(bar['t']/1000).date()}, Vol: {bar.get('v')}, OI: {bar.get('oi')}") # Check for 'oi' key just in case
    else:
        print("No results found.")
    print("Full Data Sample:", data)
else:
    print(f"Error: {resp.status_code} - {resp.text}")
