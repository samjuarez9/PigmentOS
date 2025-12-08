import requests
import json

def inspect_polymarket():
    url = "https://gamma-api.polymarket.com/events?limit=5&active=true&closed=false&order=volume24hr&ascending=false"
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
    
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            events = resp.json()
            if events:
                # Print keys of the first event to see available fields
                print("Top-level keys in event object:")
                print(list(events[0].keys()))
                
                # Print full content of the first event to inspect values
                print("\nFull content of first event:")
                print(json.dumps(events[0], indent=2))
            else:
                print("No events found.")
        else:
            print(f"Error: {resp.status_code}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    inspect_polymarket()
