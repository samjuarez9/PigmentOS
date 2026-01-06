import requests
import json

API_KEY = "d56539pr01qu3qo8fk40d56539pr01qu3qo8fk4g"
SYMBOL = "AAPL"
URL = f"https://finnhub.io/api/v1/stock/filings?symbol={SYMBOL}&token={API_KEY}"

print(f"Fetching SEC filings for {SYMBOL}...")
try:
    response = requests.get(URL, timeout=10)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        if isinstance(data, list):
            print(f"Found {len(data)} filings.")
            if data:
                print("\nMost recent filing:")
                print(json.dumps(data[0], indent=2))
        else:
            print("Unexpected response format:")
            print(json.dumps(data, indent=2))
    else:
        print(f"Error: {response.text}")

except Exception as e:
    print(f"Exception: {e}")
