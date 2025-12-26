import requests
import json
from datetime import datetime, timedelta

# FRED API Key - Get one free at https://fred.stlouisfed.org/docs/api/api_key.html
# For testing, we'll check if FRED allows anonymous access or requires a key
FRED_API_KEY = "9832f887b004951ec7d53cb78f1063a0"

def test_fred_releases():
    # Test upcoming release dates
    start_date = datetime.now().strftime('%Y-%m-%d')
    end_date = (datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d')
    
    url = f"https://api.stlouisfed.org/fred/releases/dates?api_key={FRED_API_KEY}&file_type=json&realtime_start={start_date}&realtime_end={end_date}&include_release_dates_with_no_data=true&limit=20"
    
    print(f"Testing FRED API: {url[:100]}...")
    try:
        response = requests.get(url, timeout=10)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Keys: {list(data.keys())}")
            if 'release_dates' in data:
                releases = data['release_dates']
                print(f"Releases found: {len(releases)}")
                for r in releases[:5]:
                    print(f"  - {r}")
        else:
            print(f"Response: {response.text[:500]}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_fred_releases()
