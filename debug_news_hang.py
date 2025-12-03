import time
import requests
import feedparser
import calendar
import ssl

# Mock CACHE
CACHE = {"news": {"data": [], "timestamp": 0}}

def refresh_news_logic():
    print("📰 Fetching News...", flush=True)
    
    RSS_FEEDS = [
        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664", # Finance
        "https://techcrunch.com/feed/", # Tech
        "https://www.investing.com/rss/news.rss" # General Markets
    ]
    
    all_news = []
    current_time = time.time()
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        for url in RSS_FEEDS:
            print(f"Fetching {url}...", flush=True)
            try:
                # Polite Delay
                time.sleep(1)
                
                # Use requests to handle headers and SSL
                response = requests.get(url, headers=headers, verify=False, timeout=5)
                print(f"Response: {response.status_code}", flush=True)
                if response.status_code != 200: continue
                
                feed = feedparser.parse(response.content)
                print(f"Parsed {len(feed.entries)} entries", flush=True)
                
                for entry in feed.entries[:5]:
                    pub_ts = int(time.time())
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        pub_ts = int(calendar.timegm(entry.published_parsed))
                    
                    # Determine publisher from URL or Feed Title
                    publisher = "Market Wire"
                    if "cnbc" in url: publisher = "CNBC"
                    elif "techcrunch" in url: publisher = "TechCrunch"
                    elif "investing.com" in url: publisher = "Investing.com"
                    
                    all_news.append({
                        "title": entry.get('title', ''),
                        "publisher": publisher,
                        "link": entry.get('link', ''),
                        "time": pub_ts,
                        "ticker": "NEWS"
                    })
            except Exception as e:
                print(f"Feed Error {url}: {e}")
                continue
            
        all_news.sort(key=lambda x: x['time'], reverse=True)
        print(f"📰 News Updated ({len(all_news)} items)", flush=True)
            
    except Exception as e:
        print(f"News Update Failed: {e}")

if __name__ == "__main__":
    refresh_news_logic()
