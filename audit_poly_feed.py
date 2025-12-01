import re
import os
import requests
import json

def audit_feed():
    url = "https://gamma-api.polymarket.com/events?closed=false&limit=100&order=volume24hr&ascending=false"
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
    
    # Use API Key if available (simulating prod)
    api_key = os.environ.get("POLYMARKET_API_KEY")
    if api_key:
        headers['Authorization'] = f"Bearer {api_key}"
        print("🔑 Using API Key")

    print(f"Fetching from: {url}")
    try:
        resp = requests.get(url, headers=headers, verify=False, timeout=10)
        events = resp.json()
        print(f"Total Events Fetched: {len(events)}")
        
        # EXACT LOGIC FROM run.py
        KEYWORDS = {
            "GEOPOL": ['war', 'invasion', 'strike', 'china', 'russia', 'israel', 'iran', 'taiwan', 'election', 'ukraine', 'gaza', 'border', 'military'],
            "MACRO": ['fed', 'rate', 'inflation', 'cpi', 'jobs', 'recession', 'gdp', 'fomc'],
            "CRYPTO": ['bitcoin', 'crypto', 'btc', 'eth', 'solana', 'nft'],
            "TECH": ['apple', 'nvidia', 'microsoft', 'google', 'meta', 'tesla', 'amazon', 'ai', 'tech']
        }

        BLACKLIST = ['nfl', 'nba', 'super bowl', 'box office', 'pop', 'music', 'song', 'artist', 'movie', 'film', 'grammy', 'oscar', 'sport', 'football', 'basketball', 'soccer', 'tennis', 'golf']
        
        passed = []
        rejected = []
        
        for event in events:
            title = event.get('title', '')
            title_lower = title.lower()

            # 1. Blacklist Check
            if any(bad in title_lower for bad in BLACKLIST): 
                rejected.append(f"[BLACKLIST] {title}")
                continue
            
            category = "OTHER"
            for cat, keys in KEYWORDS.items():
                # Match whole words only
                if any(re.search(r'\b' + re.escape(k) + r'\b', title_lower) for k in keys):
                    category = cat
                    break
            
            if category != "OTHER":
                passed.append(f"[{category}] {title}")
            else:
                rejected.append(f"[NO MATCH] {title}")
                
        print("\n✅ PASSED FILTER (What user sees):")
        for p in passed:
            print(p)
            
        print("\n❌ REJECTED (Noise/Missed Signal):")
        for r in rejected[:10]: # Show first 10 rejected
            print(r)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    audit_feed()
