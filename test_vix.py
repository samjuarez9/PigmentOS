import yfinance as yf
import requests

def check_vix():
    print("--- CHECKING VIX SOURCES ---")
    
    # 1. YFinance (^VIX)
    try:
        vix = yf.Ticker("^VIX")
        # Try fast_info first (real-time-ish)
        price = vix.fast_info['last_price']
        print(f"YFinance (^VIX) Fast Info: {price}")
    except Exception as e:
        print(f"YFinance Error: {e}")
        
    # 2. FRED (VIXCLS)
    try:
        FRED_KEY = "9832f887b004951ec7d53cb78f1063a0"
        url = f"https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&api_key={FRED_KEY}&file_type=json&sort_order=desc&limit=1"
        resp = requests.get(url, timeout=5)
        data = resp.json()
        val = data['observations'][0]['value']
        date = data['observations'][0]['date']
        print(f"FRED (VIXCLS): {val} (Date: {date})")
    except Exception as e:
        print(f"FRED Error: {e}")

if __name__ == "__main__":
    check_vix()
