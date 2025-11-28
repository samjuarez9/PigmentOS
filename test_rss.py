import feedparser
import requests
import time

URLS = [
    "https://techcrunch.com/feed/",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html"
]

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

print("Testing RSS Fetching...")
for url in URLS:
    try:
        print(f"Fetching {url}...")
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            feed = feedparser.parse(response.content)
            print(f"Entries: {len(feed.entries)}")
            if feed.entries:
                print(f"Top Title: {feed.entries[0].title}")
        else:
            print("Failed to fetch.")
    except Exception as e:
        print(f"Error: {e}")
