import requests
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("POLYGON_API_KEY")
TICKER = "O:GOOG260123C00337500"

url = f"https://api.polygon.io/v2/aggs/ticker/{TICKER}/prev?apiKey={API_KEY}"

print(f"Fetching: {url}")
resp = requests.get(url)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.text}")
