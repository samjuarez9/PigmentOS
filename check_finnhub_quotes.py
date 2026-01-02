import os
import requests
import json

# Load API Key
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

if not FINNHUB_API_KEY:
    print("❌ Error: FINNHUB_API_KEY not found.")
    exit(1)

def check_finnhub_quote(symbol):
    print(f"\nChecking Finnhub Quote for {symbol}...")
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            print(json.dumps(data, indent=2))
            # Finnhub Quote Format:
            # c: Current price
            # d: Change
            # dp: Percent change
            # h: High
            # l: Low
            # o: Open
            # pc: Previous close
            # t: Timestamp
            
            # Does it have Bid/Ask?
            if 'b' in data or 'a' in data:
                 print("✅ Found Bid/Ask data!")
            else:
                 print("⚠️  No Bid/Ask data in response.")
        else:
            print(f"❌ Error {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"❌ Exception: {e}")

# 1. Check Underlying (SPY)
check_finnhub_quote("SPY")

# 2. Check an Option Contract (if possible)
# Finnhub usually requires specific formatting for options, or doesn't support them on free tier.
# Common format: SPY260102C00500000 (OCC)
# Let's try a known active contract from previous steps if available, or just guess one.
# SPY 500 Call for Jan 2 2026 (from previous output: O:SPY260102C00500000)
# Finnhub format might be different. Let's try OCC.
check_finnhub_quote("O:SPY260102C00500000") # Polygon format
check_finnhub_quote("SPY260102C00500000")   # Standard OCC
