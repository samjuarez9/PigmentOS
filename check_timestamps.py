import feedparser
import requests
import time
import calendar
from datetime import datetime
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

RSS_URLS = [
    "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
    "https://techcrunch.com/feed/",
    "https://www.investing.com/rss/news.rss",
    "https://finance.yahoo.com/news/rssindex"
]

def check_timestamps():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    for url in RSS_URLS:
        print(f"\n--- Checking {url} ---")
        try:
            response = requests.get(url, headers=headers, verify=False, timeout=5)
            feed = feedparser.parse(response.content)
            
            for i, entry in enumerate(feed.entries[:3]):
                title = entry.get('title', 'No Title')
                published = entry.get('published', 'No Published String')
                published_parsed = entry.get('published_parsed', None)
                
                print(f"[{i}] {title[:50]}...")
                print(f"    Raw Date: {published}")
                
                if published_parsed:
                    ts = calendar.timegm(published_parsed)
                    print(f"    Parsed TS: {ts} ({datetime.fromtimestamp(ts)})")
                else:
                    print(f"    ❌ FAILED TO PARSE DATE")

        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    check_timestamps()
