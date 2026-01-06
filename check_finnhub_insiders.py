import requests
import json

API_KEY = "d56539pr01qu3qo8fk40d56539pr01qu3qo8fk4g"
SYMBOL = "NVDA" # NVDA usually has activity
URL = f"https://finnhub.io/api/v1/stock/insider-transactions?symbol={SYMBOL}&token={API_KEY}"

print(f"Fetching Insider Transactions for {SYMBOL}...")
try:
    response = requests.get(URL, timeout=10)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        if isinstance(data, dict) and 'data' in data:
            transactions = data['data']
            print(f"Found {len(transactions)} transactions.")
            if transactions:
                print("\nMost recent transactions:")
                for t in transactions[:3]:
                    print(json.dumps(t, indent=2))
        else:
            print("Unexpected response format:")
            print(json.dumps(data, indent=2))
    else:
        print(f"Error: {response.text}")

except Exception as e:
    print(f"Exception: {e}")
