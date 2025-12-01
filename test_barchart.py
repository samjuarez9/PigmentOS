import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_barchart():
    print("--- TESTING BARCHART SCRAPER ---")
    
    # 1. Setup Headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://www.barchart.com/options/unusual-activity/stocks"
    }

    try:
        # 2. Get Cookies (XSRF)
        print("1. Fetching Main Page for Cookies...")
        session = requests.Session()
        page_resp = session.get("https://www.barchart.com/options/unusual-activity/stocks", headers=headers, verify=False, timeout=10)
        print(f"   Status: {page_resp.status_code}")
        
        xsrf = session.cookies.get_dict().get("XSRF-TOKEN")
        if xsrf:
            print("   ✅ Found XSRF Token")
            headers["X-XSRF-TOKEN"] = requests.utils.unquote(xsrf)
        else:
            print("   ❌ No XSRF Token found (might fail)")

        # 3. Request API
        print("2. Fetching API Data...")
        api_url = "https://www.barchart.com/proxies/core-api/v1/quotes/get"
        params = {
            "list": "options.unusual_activity.stocks",
            "fields": "symbol,baseSymbol,strikePrice,expirationDate,putCall,volume,openInterest,tradeTime,lastPrice,priceChange,percentChange",
            "orderBy": "volume",
            "orderDir": "desc",
            "limit": "10",
            "meta": "field.shortName,field.type,field.description"
        }

        api_resp = session.get(api_url, headers=headers, params=params, verify=False, timeout=10)
        print(f"   Status: {api_resp.status_code}")
        
        if api_resp.status_code == 200:
            data = api_resp.json()
            count = data.get('total', 0)
            results = data.get('data', [])
            print(f"   ✅ Success! Found {len(results)} items (Total: {count})")
            
            for i, item in enumerate(results[:5]):
                print(f"   [{i+1}] {item.get('symbol')} | Vol: {item.get('volume')} | {item.get('tradeTime')}")
        else:
            print(f"   ❌ Failed: {api_resp.text[:200]}")

    except Exception as e:
        print(f"   ❌ Error: {e}")

if __name__ == "__main__":
    test_barchart()
