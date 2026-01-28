import requests
import json

def verify():
    url = "http://127.0.0.1:8081/api/polymarket"
    try:
        resp = requests.get(url, timeout=5)
        data = resp.json()
        if 'data' in data:
            markets = data['data']
            print(f"Fetched {len(markets)} markets.")
            print("\nTop 5 Markets:")
            for i, m in enumerate(markets[:5]):
                print(f"{i+1}. {m.get('event')} | Volatile: {m.get('is_volatile')} | Delta: {m.get('delta')}")
            
            # Check if any have is_volatile=True
            volatile_count = sum(1 for m in markets if m.get('is_volatile'))
            print(f"\nTotal Volatile Markets: {volatile_count}")
        else:
            print("No data field in response")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    verify()
