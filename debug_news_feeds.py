import feedparser
import time
import calendar
from datetime import datetime
import requests
import ssl

# Disable SSL warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

RSS_URLS = [
    "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    "https://techcrunch.com/feed/"
]

def debug_feeds():
    print(f"Current System Time: {time.time()} ({datetime.fromtimestamp(time.time())})")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    for url in RSS_URLS:
        print(f"\n--- Fetching {url} ---")
        try:
            # Use requests first to handle headers and SSL
            response = requests.get(url, headers=headers, verify=False, timeout=10)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code != 200:
                print(f"❌ Failed to fetch: {response.status_code}")
                continue
                
            feed = feedparser.parse(response.content)
            print(f"Feed Title: {feed.feed.get('title', 'Unknown')}")
            print(f"Entries found: {len(feed.entries)}")
            
            if len(feed.entries) > 0:
                for i, entry in enumerate(feed.entries[:3]):
                    title = entry.get('title', 'No Title')
                    published = entry.get('published', 'No Published String')
                    published_parsed = entry.get('published_parsed', None)
                    
                    pub_ts = 0
                    if published_parsed:
                        pub_ts = int(calendar.timegm(published_parsed))
                    
                    print(f"[{i}] Title: {title}")
                    print(f"    Published: {published}")
                    print(f"    Parsed TS: {pub_ts}")
            else:
                print("❌ No entries found in parsed feed.")
                # Print first 500 chars of content to debug
                print(f"Raw Content Preview: {response.text[:500]}")

        except Exception as e:
            print(f"Error fetching {url}: {e}")

if __name__ == "__main__":
    debug_feeds()
