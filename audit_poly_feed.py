import re
import os
import requests
import json
import math

def audit_feed():
    url = "https://gamma-api.polymarket.com/events?closed=false&limit=200&order=volume24hr&ascending=false"
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
        
        # --- NEW LOGIC START ---
        
        KEYWORDS = {
            "GEOPOL": ['war', 'invasion', 'strike', 'china', 'russia', 'israel', 'iran', 'taiwan', 'ukraine', 'gaza', 'border', 'military', 'ceasefire', 'capture', 'regime', 'clash', 'peace', 'khamenei', 'hezbollah', 'venezuela'],
            "MACRO": ['fed', 'rate', 'inflation', 'cpi', 'jobs', 'recession', 'gdp', 'fomc', 'powell', 'gold', 'reserve', 'ipo'],
            "CRYPTO": ['bitcoin', 'crypto', 'btc', 'eth', 'nft'],
            "TECH": ['apple', 'nvidia', 'microsoft', 'google', 'meta', 'tesla', 'amazon', 'ai', 'tech', 'openai', 'gemini'],
            "CULTURE": ['tweet', 'youtube', 'subscriber', 'mrbeast', 'logan paul', 'ksi', 'spotify', 'taylor swift', 'beyonce', 'film', 'movie', 'box office'],
            "SCIENCE": ['space', 'nasa', 'spacex', 'mars', 'moon', 'cancer', 'climate', 'temperature', 'fda', 'medicine']
        }

        BLACKLIST = ['nfl', 'nba', 'super bowl', 'sport', 'football', 'basketball', 'soccer', 'tennis', 'golf', 'searched', 'election', 'solana', 'microstrategy', 'mstr']
        
        candidates = []
        seen_stems = {}

        def get_title_stem(t):
            # Lowercase first
            s = t.lower()
            # Remove currency amounts (e.g. $100k, $95,000)
            s = re.sub(r'\$[\d,]+(\.\d+)?[kKmM]?', '', s)
            # Remove years (2024-2029)
            s = re.sub(r'\b202[4-9]\b', '', s)
            # Remove specific date patterns: "on December 5", "by Jan 1", "in March"
            # Matches: on/by/in + optional space + Month + optional space + optional Day
            months = r"(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)"
            s = re.sub(r'\b(on|by|in)?\s*' + months + r'\s*(\d{1,2})?(st|nd|rd|th)?\b', '', s)
            # Remove "above" or "below" if followed by space (common in price targets)
            s = re.sub(r'\b(above|below|hit|reach)\b', '', s)
            # Remove placeholders
            s = s.replace("___", "")
            # Collapse whitespace and non-alphanumeric (keep only letters for strict topic matching)
            s = re.sub(r'[^a-z\s]', '', s)
            return ' '.join(s.split())

        for event in events:
            title = event.get('title', '')
            title_lower = title.lower()

            # 1. Blacklist Check
            if any(bad in title_lower for bad in BLACKLIST): continue
            
            # 2. Determine Category
            category = "OTHER"
            for cat, keys in KEYWORDS.items():
                if any(re.search(r'\b' + re.escape(k) + r'\b', title_lower) for k in keys):
                    category = cat
                    break
            
            if category == "OTHER": continue

            # 3. Market Data Extraction
            markets = event.get('markets', [])
            if not markets: continue
            
            # Find best market (highest volume or main)
            m = markets[0] # Default
            
            # Calculate Metrics
            vol = float(m.get('volume', 0))
            delta = float(m.get('oneDayPriceChange', 0))
            
            # 4. Deduplication Logic
            stem = get_title_stem(title)
            
            # If we've seen this stem, only keep the one with higher volume
            if stem in seen_stems:
                existing_idx = seen_stems[stem]
                if vol > candidates[existing_idx]['volume']:
                    # Replace existing with this one (mark existing as skipped)
                    candidates[existing_idx]['skip'] = True
                    seen_stems[stem] = len(candidates) # Update pointer
                else:
                    continue # Skip this one, existing is better
            else:
                seen_stems[stem] = len(candidates)

            # 5. Weighted Score
            # Score = log(volume) * abs(delta)
            # This balances "Big News" (high vol) with "Fast Moving" (high delta)
            # Add 1 to volume to avoid log(0)
            score = math.log(vol + 1) * (abs(delta) * 100)
            
            candidates.append({
                "title": title,
                "category": category,
                "volume": vol,
                "delta": delta,
                "score": score,
                "skip": False
            })

        # Filter out skipped
        final_list = [c for c in candidates if not c['skip']]
        
        # Sort by Score
        final_list.sort(key=lambda x: x['score'], reverse=True)
        
        print("\n✅ FINAL FEED (Top 20):")
        print(f"{'SCORE':<8} | {'VOL':<8} | {'DELTA':<6} | {'CAT':<8} | {'TITLE'}")
        print("-" * 80)
        for c in final_list[:20]:
            print(f"{c['score']:<8.2f} | {c['volume']:<8.0f} | {c['delta']:<6.2f} | {c['category']:<8} | {c['title']}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    audit_feed()
