import requests
import json

url = "https://gamma-api.polymarket.com/events?limit=200&active=true&closed=false&order=volume24hr&ascending=false"
try:
    r = requests.get(url)
    data = r.json()
    print(f"Fetched {len(data)} events")
    for i, event in enumerate(data):
        print(f"{i+1}. {event.get('title', 'No Title')} (Vol: {event.get('markets', [{}])[0].get('volume24hr', 0)})")
except Exception as e:
    print(f"Error: {e}")
