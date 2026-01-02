import os
import requests
import json

# Load API Key
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

API_KEY = os.getenv("POLYGON_API_KEY")

if not API_KEY:
    print("❌ Error: POLYGON_API_KEY not found.")
    exit(1)

# Fetch a snapshot for a highly active ticker (SPY) to ensure we get data
symbol = "SPY"
print(f"Fetching Options Snapshot for {symbol}...")

url = f"https://api.polygon.io/v3/snapshot/options/{symbol}"
params = {
    "apiKey": API_KEY,
    "limit": 5, # Get a few to find one with quotes
    "strike_price.gte": 500
}

try:
    resp = requests.get(url, params=params, timeout=15)
    if resp.status_code == 200:
        data = resp.json()
        results = data.get("results", [])
        
        if results:
            print(f"✅ Found {len(results)} contracts.")
            
            # Find one with 'last_quote' if possible
            sample = None
            for item in results:
                if "last_quote" in item:
                    sample = item
                    break
            
            if not sample:
                print("⚠️ No contracts had 'last_quote' field. Showing first result:")
                sample = results[0]
            else:
                print("✅ Found contract with 'last_quote'!")

            # Print the structure clearly
            print(json.dumps(sample, indent=2))
            
            # Check timestamps
            day = sample.get("day", {})
            quote = sample.get("last_quote", {})
            
            trade_ts = day.get("last_updated")
            quote_ts = quote.get("time") # Polygon usually uses 'time' or 'sip_timestamp'
            
            print("\n--- TIMESTAMPS ---")
            print(f"Trade Last Updated: {trade_ts}")
            print(f"Quote Time:         {quote_ts}")
            
            if trade_ts and quote_ts:
                diff = abs(trade_ts - quote_ts) / 1_000_000_000 # nanoseconds? usually ms or ns
                # Polygon timestamps are usually nanoseconds (19 digits) or milliseconds (13 digits)
                # Let's check length
                print(f"Diff: {diff} seconds (approx)")
                
        else:
            print("❌ No results in snapshot.")
    else:
        print(f"❌ Error {resp.status_code}: {resp.text}")

except Exception as e:
    print(f"❌ Exception: {e}")
