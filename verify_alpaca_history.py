import requests
import json
import os
from datetime import datetime, timedelta

# Credentials provided by user
API_KEY = "PKD66OSCNTGDQ2ORIX4RGSKGI5"
SECRET_KEY = "9eSKSK2CchHQbFFwMYr1tnwZgu8MNZEMNfdXqVYwyF5M"
DATA_URL = "https://data.alpaca.markets/v1beta1/options"

def test_alpaca_history(symbol):
    print(f"\nTesting Alpaca Historical Quotes for {symbol}...")
    
    headers = {
        "APCA-API-KEY-ID": API_KEY,
        "APCA-API-SECRET-KEY": SECRET_KEY,
        "Accept": "application/json"
    }
    
    # Define a time range (e.g., yesterday around noon)
    # 2025-12-31 is the date we saw data for.
    start_time = "2025-12-31T12:00:00Z"
    end_time = "2025-12-31T12:05:00Z"
    
    # Endpoint: /v1beta1/options/quotes?symbols={symbol}&start={start}&end={end}
    history_url = f"{DATA_URL}/quotes"
    params = {
        "symbols": symbol,
        "start": start_time,
        "end": end_time,
        "limit": 5
    }
    
    print(f"Requesting Historical Quotes ({start_time} to {end_time})...")
    try:
        resp = requests.get(history_url, headers=headers, params=params, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            quotes = data.get("quotes", {}).get(symbol, [])
            
            if quotes:
                print(f"✅ Success! Received {len(quotes)} historical quotes.")
                print(f"   Sample: {quotes[0]}")
                return True
            else:
                print("⚠️  Response valid (200 OK) but returned NO quotes for this time range.")
                print("   (This might mean no trading happened, or history is restricted).")
                return False
        elif resp.status_code == 403:
            print("❌ Access Denied (403). Plan likely does not include Historical Options Data.")
            return False
        elif resp.status_code == 422:
            print(f"❌ Invalid Parameter (422): {resp.text}")
            return False
        else:
            print(f"❌ Error {resp.status_code}: {resp.text}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

# Use the same valid symbol
test_symbol = "SPY260102C00500000" 
test_alpaca_history(test_symbol)
