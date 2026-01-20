import requests
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("POLYGON_API_KEY")
TICKER = "O:GOOG260123C00337500"
DATE = "2026-01-09" # Past date


url = f"https://api.polygon.io/v1/open-close/{TICKER}/{DATE}?apiKey={API_KEY}"

print(f"Fetching: {url}")
resp = requests.get(url)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.text}")
