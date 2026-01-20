import requests
import os
from dotenv import load_dotenv

load_dotenv()

# Use a known ticker and date for testing
# Ideally one that has passed so we can see Day 2 data
# Example: NVDA Call from a few days ago
TICKER = "O:NVDA240119C00500000" # Example ticker, might need a real one
# Let's try to find a real ticker from the snapshot endpoint first if possible, 
# or just use a dummy one if we can't easily get one.
# Actually, let's just use a recent date and a common ticker format.
# NVDA $140 Call expiring Jan 17 2025
# Symbol format: O:NVDA250117C00140000
TICKER = "O:NVDA250117C00140000"
DATE = "2025-01-10" # Friday

url = f"http://localhost:8001/api/whales/conviction?ticker={TICKER}&date={DATE}&initial_oi=500"


try:
    print(f"Testing URL: {url}")
    resp = requests.get(url)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.json()}")
except Exception as e:
    print(f"Error: {e}")
