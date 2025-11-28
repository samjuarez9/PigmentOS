import requests
import json

URL = "https://gamma-api.polymarket.com/events?closed=false&limit=10&order=volume&ascending=false"

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json'
}

print(f"Testing Polymarket API: {URL}")
try:
    response = requests.get(URL, headers=headers, timeout=10)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Items received: {len(data)}")
        if data:
            print("Sample Item:", json.dumps(data[0], indent=2))
    else:
        print("Response:", response.text[:500])
except Exception as e:
    print(f"Error: {e}")
