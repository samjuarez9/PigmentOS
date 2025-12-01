import requests
import json

def test_barchart():
    print("🐳 Testing Barchart API...", flush=True)
    
    try:
        # 1. Setup Headers
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json",
            "Referer": "https://www.barchart.com/options/unusual-activity/stocks"
        }

        # 2. Get Cookies (XSRF)
        session = requests.Session()
        # First request to get cookies
        print("Getting cookies...", flush=True)
        resp1 = session.get("https://www.barchart.com/options/unusual-activity/stocks", headers=headers, timeout=10)
        print(f"Cookie Resp: {resp1.status_code}")
        
        xsrf = session.cookies.get_dict().get("XSRF-TOKEN")
        if xsrf:
            headers["X-XSRF-TOKEN"] = requests.utils.unquote(xsrf)
            print("Got XSRF Token")
        else:
            print("No XSRF Token found")

        # 3. Request API
        api_url = "https://www.barchart.com/proxies/core-api/v1/quotes/get"
        params = {
            "list": "options.unusual_activity.stocks",
            "fields": "symbol,baseSymbol,strikePrice,expirationDate,putCall,volume,openInterest,tradeTime,lastPrice,priceChange,percentChange",
            "orderBy": "volume",
            "orderDir": "desc",
            "limit": "50",
            "meta": "field.shortName,field.type,field.description"
        }

        print("Requesting API...", flush=True)
        api_resp = session.get(api_url, headers=headers, params=params, timeout=10)
        
        print(f"API Status: {api_resp.status_code}")
        if api_resp.status_code == 200:
            data = api_resp.json()
            results = data.get('data', [])
            print(f"Total Results: {len(results)}")
            if len(results) > 0:
                print("First Result Sample:")
                print(json.dumps(results[0], indent=2))
            else:
                print("Raw Response Data:")
                print(json.dumps(data, indent=2))
        else:
            print(f"Error Response: {api_resp.text}")
            
    except Exception as e:
        print(f"Barchart Test Failed: {e}")

if __name__ == "__main__":
    test_barchart()
