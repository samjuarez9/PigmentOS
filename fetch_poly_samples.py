import requests
import json
import re

def fetch_poly_samples():
    url = "https://gamma-api.polymarket.com/events?limit=20&active=true&closed=false&order=volume24hr&ascending=false"
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
    
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            events = resp.json()
            
            print("--- POLYMARKET 'NEWS' CANDIDATES ---\n")
            
            for event in events:
                title = event.get('title', 'No Title')
                desc = event.get('description', '')
                vol = float(event.get('volume', 0))
                
                # Skip if description is empty or generic
                if not desc or len(desc) < 50: continue
                
                # Clean up description (remove links, extra whitespace)
                desc = re.sub(r'http\S+', '', desc)
                desc = ' '.join(desc.split())
                
                # Truncate for display
                if len(desc) > 200:
                    desc = desc[:200] + "..."
                
                print(f"TITLE: {title}")
                print(f"VOLUME: ${vol:,.0f}")
                print(f"SNIPPET: {desc}")
                print("-" * 40)
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fetch_poly_samples()
