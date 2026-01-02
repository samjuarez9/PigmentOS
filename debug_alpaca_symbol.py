import os
import requests
from dotenv import load_dotenv

load_dotenv()

ALPACA_API_KEY = "PKD66OSCNTGDQ2ORIX4RGSKGI5"
ALPACA_SECRET_KEY = "9eSKSK2CchHQbFFwMYr1tnwZgu8MNZEMNfdXqVYwyF5M"
ALPACA_DATA_URL = "https://data.alpaca.markets/v1beta1/options"

def test_symbol(symbol):
    print(f"\nTesting symbol: {symbol}")
    headers = {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
        "Accept": "application/json"
    }
    url = f"{ALPACA_DATA_URL}/snapshots"
    params = {"symbols": symbol}
    
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            snapshot = data.get("snapshots", {}).get(symbol)
            if snapshot:
                print("✅ Success! Snapshot found.")
                print(f"Quote: {snapshot.get('latestQuote')}")
            else:
                print("❌ Response 200 but no snapshot data for this symbol.")
                print(f"Response keys: {data.keys()}")
                if 'snapshots' in data:
                    print(f"Snapshots keys: {data['snapshots'].keys()}")
        else:
            print(f"❌ Error: {resp.text}")
    except Exception as e:
        print(f"❌ Exception: {e}")

# Test cases based on user logs
# Log: O:NVDA260102C00190000
symbol_with_prefix = "O:NVDA260102C00190000"
symbol_clean = "NVDA260102C00190000"

test_symbol(symbol_with_prefix)
test_symbol(symbol_clean)
