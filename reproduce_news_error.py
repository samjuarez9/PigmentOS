
import feedparser
import calendar
import time
import json

def api_news():
    print("Starting api_news...")
    RSS_URLS = [
        "https://www.investing.com/rss/news.rss",
        "https://finance.yahoo.com/news/rssindex"
    ]
    
    all_news = []
    for url in RSS_URLS:
        print(f"Fetching {url}...")
        try:
            feed = feedparser.parse(url)
            print(f"Parsed {url}. Entries: {len(feed.entries)}")
            for entry in feed.entries[:5]:
                pub_ts = int(time.time())
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    try:
                        pub_ts = int(calendar.timegm(entry.published_parsed))
                    except Exception as e:
                        print(f"Error converting time: {e}")
                
                all_news.append({
                    "title": entry.get('title', ''),
                    "publisher": "Market Wire",
                    "link": entry.get('link', ''),
                    "time": pub_ts,
                    "ticker": "NEWS"
                })
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            continue
        
    print("Sorting news...")
    try:
        all_news.sort(key=lambda x: x['time'], reverse=True)
        print("Sorted news.")
    except Exception as e:
        print(f"Error sorting news: {e}")

    print(json.dumps(all_news, indent=2))

if __name__ == "__main__":
    api_news()
