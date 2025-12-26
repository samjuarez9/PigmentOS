import requests
import json
from datetime import datetime, timedelta

FINNHUB_API_KEY = "d56539pr01qu3qo8fk40d56539pr01qu3qo8fk4g"

endpoints = [
    # Free endpoints
    ("Quote", f"https://finnhub.io/api/v1/quote?symbol=AAPL&token={FINNHUB_API_KEY}"),
    ("Company News", f"https://finnhub.io/api/v1/company-news?symbol=AAPL&from=2024-12-01&to=2024-12-24&token={FINNHUB_API_KEY}"),
    ("Market News", f"https://finnhub.io/api/v1/news?category=general&token={FINNHUB_API_KEY}"),
    ("Earnings Calendar", f"https://finnhub.io/api/v1/calendar/earnings?from=2024-12-24&to=2024-12-31&token={FINNHUB_API_KEY}"),
    ("IPO Calendar", f"https://finnhub.io/api/v1/calendar/ipo?from=2024-12-24&to=2024-12-31&token={FINNHUB_API_KEY}"),
    # Premium - Economic Calendar
    ("Economic Calendar (Premium)", f"https://finnhub.io/api/v1/calendar/economic?token={FINNHUB_API_KEY}"),
]

for name, url in endpoints:
    print(f"\n=== {name} ===")
    try:
        response = requests.get(url, timeout=10)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                print(f"Items: {len(data)}")
                if data:
                    print(f"Sample: {json.dumps(data[0], indent=2)[:300]}")
            elif isinstance(data, dict):
                print(f"Keys: {list(data.keys())}")
                print(f"Sample: {json.dumps(data, indent=2)[:300]}")
        else:
            print(f"Response: {response.text[:200]}")
    except Exception as e:
        print(f"Error: {e}")
