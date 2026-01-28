import requests
import json

def inspect_polymarket():
    url = "https://gamma-api.polymarket.com/events?limit=5&active=true&closed=false&order=volume24hr&ascending=false"
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
    
    try:
        resp = requests.get(url, headers=headers, verify=False, timeout=10)
        if resp.status_code == 200:
            events = resp.json()
            if events:
                print(f"Found {len(events)} events.")
                first_event = events[0]
                print("\n=== Event Keys ===")
                print(json.dumps(list(first_event.keys()), indent=2))
                
                print("\n=== Sample Event Data ===")
                # Print a subset to avoid spam
                sample = {k: v for k, v in first_event.items() if k in ['title', 'volume', 'volume24hr', 'markets']}
                print(json.dumps(sample, indent=2))
                
                if 'markets' in first_event and first_event['markets']:
                    print("\n=== Market Keys (Inside Event) ===")
                    print(json.dumps(list(first_event['markets'][0].keys()), indent=2))
                    print("\n=== Sample Market Data ===")
                    print(json.dumps(first_event['markets'][0], indent=2))
            else:
                print("No events found.")
        else:
            print(f"Error: {resp.status_code}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    inspect_polymarket()
