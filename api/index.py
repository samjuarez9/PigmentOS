from http.server import BaseHTTPRequestHandler
import json
import requests

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 1. Setup Headers to look like a real browser (CRITICAL)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json",
            "Referer": "https://www.barchart.com/options/unusual-activity/stocks"
        }

        try:
            # 2. First, get the main page to grab the necessary cookies (XSRF token)
            session = requests.Session()
            page_resp = session.get("https://www.barchart.com/options/unusual-activity/stocks", headers=headers)

            # 3. Extract the XSRF token from cookies
            xsrf_token = session.cookies.get_dict().get("XSRF-TOKEN")
            if xsrf_token:
                headers["X-XSRF-TOKEN"] = requests.utils.unquote(xsrf_token)

            # 4. Request the internal API data
            api_url = "https://www.barchart.com/proxies/core-api/v1/quotes/get"
            params = {
                "list": "options.unusual_activity.stocks",
                "fields": "symbol,baseSymbol,strikePrice,expirationDate,putCall,volume,openInterest,tradeTime",
                "orderBy": "volume",
                "orderDir": "desc",
                "limit": "30",
                "meta": "field.shortName,field.type,field.description"
            }

            api_resp = session.get(api_url, headers=headers, params=params)
            data = api_resp.json()

            # 5. Send JSON back to Frontend
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')  # Enable CORS
            self.end_headers()
            self.wfile.write(json.dumps(data).encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            error_response = {"error": str(e)}
            self.wfile.write(json.dumps(error_response).encode('utf-8'))
