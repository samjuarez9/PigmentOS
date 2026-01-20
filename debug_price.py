import os
import requests
import time
from dotenv import load_dotenv

load_dotenv()

FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "d56539pr01qu3qo8fk40d56539pr01qu3qo8fk4g")
POLYGON_API_KEY = os.environ.get("POLYGON_API_KEY")

print(f"Finnhub Key Present: {bool(FINNHUB_API_KEY)}")
print(f"Polygon Key Present: {bool(POLYGON_API_KEY)}")

def get_finnhub_price(symbol):
    print(f"Fetching {symbol} from Finnhub...")
    if not FINNHUB_API_KEY:
        print("No Finnhub Key")
        return None
    
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
        resp = requests.get(url, timeout=5)
        print(f"Finnhub Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"Finnhub Data: {data}")
            price = data.get("c")
            return price
    except Exception as e:
        print(f"Finnhub Error: {e}")
    
    return None

def get_polygon_fallback(symbol):
    print(f"Fetching {symbol} from Polygon Fallback...")
    if not POLYGON_API_KEY:
        print("No Polygon Key")
        return None

    try:
        url = f"https://api.polygon.io/v2/aggs/ticker/{symbol}/prev?apiKey={POLYGON_API_KEY}"
        resp = requests.get(url, timeout=5)
        print(f"Polygon Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"Polygon Data: {data}")
            if data.get("results"):
                price = data["results"][0].get("c")
                return price
    except Exception as e:
        print(f"Polygon Error: {e}")
    
    return None

symbol = "SPY"
price = get_finnhub_price(symbol)
if price:
    print(f"Final Price (Finnhub): {price}")
else:
    price = get_polygon_fallback(symbol)
    print(f"Final Price (Polygon): {price}")
