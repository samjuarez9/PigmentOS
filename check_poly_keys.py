import requests
import json

def check():
    url = "https://gamma-api.polymarket.com/events?limit=1&active=true&closed=false&order=volume24hr&ascending=false"
    try:
        resp = requests.get(url, verify=False, timeout=10)
        data = resp.json()
        if data and len(data) > 0:
            markets = data[0].get('markets', [])
            if markets:
                print(json.dumps(list(markets[0].keys()), indent=2))
            else:
                print("No markets in event")
        else:
            print("No events found")
    except Exception as e:
        print(e)

if __name__ == "__main__":
    check()
