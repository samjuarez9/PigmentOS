import requests
import json

def test_tickers_endpoint():
    try:
        response = requests.get('http://localhost:5000/api/whales/tickers')
        if response.status_code == 200:
            data = response.json()
            print("✅ Endpoint /api/whales/tickers returned 200 OK")
            print(f"Tickers found: {data.get('tickers')}")
        else:
            print(f"❌ Endpoint returned {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"❌ Failed to connect: {e}")

if __name__ == "__main__":
    test_tickers_endpoint()
