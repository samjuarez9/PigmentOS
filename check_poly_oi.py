import requests
import os
from datetime import datetime, timedelta

# Mock env if needed, or rely on system env
# Assuming POLYGON_API_KEY is in env or I need to find it.
# I will try to read it from .env or just assume it's set in the environment where I run this.
# For now, I'll try to load from .env if present.

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

# Pick a recent option contract
# NVDA Call expiring soon?
# Let's try to find a valid ticker first or just guess one.
# NVDA 250117 C 140 (Example) -> O:NVDA250117C00140000
# Let's try to find a real one from the whales.html or run.py logs if possible, but guessing is faster if I know the format.
# Format: O:TickerYYMMDD[C/P]Price(8digits)

# Let's use a known recent date. Jan 10 2025 was a Friday.
# Ticker: NVDA
# Expiry: 2025-01-17
# Strike: 140
# Type: C
# Symbol: O:NVDA250117C00140000

ticker = "O:NVDA250117C00140000"
date = "2025-01-10"

url = f"https://api.polygon.io/v1/open-close/{ticker}/{date}"
params = {"apiKey": api_key}

print(f"Fetching {url}...")
resp = requests.get(url, params=params)

if resp.status_code == 200:
    data = resp.json()
    print("Response keys:", data.keys())
    print("Open Interest:", data.get('open_interest'))
    print("Volume:", data.get('volume'))
    print("Full Data:", data)
else:
    print(f"Error: {resp.status_code} - {resp.text}")
