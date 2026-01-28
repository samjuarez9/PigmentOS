import requests
import json

def check():
    url = "https://gamma-api.polymarket.com/events?limit=5&active=true&closed=false&order=volume24hr&ascending=false"
    try:
        resp = requests.get(url, verify=False, timeout=10)
        data = resp.json()
        if data:
            print(f"Checking {len(data)} events...")
            for e in data:
                markets = e.get('markets', [])
                for m in markets:
                    print(f"--- {e.get('title', 'No Title')} ---")
                    print(f"oneDayPriceChange: {m.get('oneDayPriceChange')}")
                    print(f"oneHourPriceChange: {m.get('oneHourPriceChange')}")
                    print(f"volume24hr: {m.get('volume24hr')}")
                    print("-" * 20)
                    break # Just check one market per event
        else:
            print("No events found")
    except Exception as e:
        print(e)

if __name__ == "__main__":
    check()
