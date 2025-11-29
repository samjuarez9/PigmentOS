import feedparser
import requests
import time
import calendar
from datetime import datetime
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CANDIDATE_URLS = [
    "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114", # CNBC Top News
    "http://feeds.marketwatch.com/marketwatch/topstories/", # MarketWatch
    "https://www.investing.com/rss/news.rss", # Investing.com (Benchmark)
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml", # WSJ Markets
    "https://finance.yahoo.com/news/rssindex" # Yahoo (Benchmark - Stale)
]

def check_feeds():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    for url in CANDIDATE_URLS:
        print(f"\n--- Checking {url} ---")
        try:
            response = requests.get(url, headers=headers, verify=False, timeout=5)
            feed = feedparser.parse(response.content)
            
            if not feed.entries:
                print("    ❌ NO ENTRIES FOUND")
                continue

            print(f"    Found {len(feed.entries)} entries")
            
            for i, entry in enumerate(feed.entries[:3]):
                title = entry.get('title', 'No Title')
                published = entry.get('published', 'No Published String')
                published_parsed = entry.get('published_parsed', None)
                
                print(f"    [{i}] {title[:60]}...")
                print(f"        Raw Date: {published}")
                
                if published_parsed:
                    ts = calendar.timegm(published_parsed)
                    dt = datetime.fromtimestamp(ts)
                    print(f"        Parsed: {dt} (TS: {ts})")
                    
                    # Check age
                    age = time.time() - ts
                    if age < 3600:
                        print(f"        ✅ FRESH (< 1h ago)")
                    elif age < 86400:
                        print(f"        ⚠️ RECENT (< 24h ago)")
                    else:
                        print(f"        ❌ STALE (> 24h ago)")
                else:
                    print(f"        ❌ FAILED TO PARSE DATE")

        except Exception as e:
            print(f"    Error: {e}")

if __name__ == "__main__":
    check_feeds()
