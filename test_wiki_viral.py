import requests
from datetime import datetime, timedelta

# Ticker -> Wiki Page Mapping
MAPPING = {
    "TSLA": "Tesla, Inc.",
    "NVDA": "Nvidia",
    "AAPL": "Apple Inc.",
    "PLTR": "Palantir Technologies",
    "MSFT": "Microsoft",
    "GOOG": "Google",
    "META": "Meta Platforms"
}

def get_pageviews(article):
    # Wikipedia Pageviews API (Daily)
    # Endpoint: /metrics/pageviews/per-article/{project}/{access}/{agent}/{article}/{granularity}/{start}/{end}
    
    today = datetime.now()
    start_date = (today - timedelta(days=5)).strftime("%Y%m%d")
    end_date = (today - timedelta(days=1)).strftime("%Y%m%d") # Data is usually 1 day delayed
    
    url = f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/{article}/daily/{start_date}/{end_date}"
    
    headers = {'User-Agent': 'PigmentOS/1.0 (pigment@example.com)'} # Wiki requires User-Agent
    
    try:
        resp = requests.get(url, headers=headers)
        data = resp.json()
        
        if 'items' in data:
            views = [item['views'] for item in data['items']]
            print(f"\n--- {article} ---")
            print(f"Views (Last 5 Days): {views}")
            
            if len(views) >= 2:
                latest = views[-1]
                avg = sum(views[:-1]) / len(views[:-1])
                spike = (latest - avg) / avg * 100
                print(f"Latest: {latest}, Avg: {avg:.0f}, Spike: {spike:.1f}%")
                
                if spike > 50:
                    print("🔥 VIRAL SPIKE DETECTED")
        else:
            print(f"Error for {article}: {data}")
            
    except Exception as e:
        print(f"Exception for {article}: {e}")

print("Testing Wikipedia Viral Index...")
for ticker, page in MAPPING.items():
    get_pageviews(page)
