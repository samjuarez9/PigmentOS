import requests
import json
from datetime import datetime, timedelta

FMP_API_KEY = "imWDtUMcvZ9J6nXH4yCr01zMYLILhaeO"

def test_fmp_calendar():
    start_date = datetime.now().strftime('%Y-%m-%d')
    end_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
    
    url = f"https://financialmodelingprep.com/stable/economic-calendar?from={start_date}&to={end_date}&apikey={FMP_API_KEY}"
    
    print(f"Testing FMP API: {url}")
    try:
        response = requests.get(url, timeout=10)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Items received: {len(data)}")
            if data:
                print("Sample Item:", json.dumps(data[0], indent=2))
                
                # Check for High impact events
                high_impact = [item for item in data if item.get('impact') == 'High']
                print(f"High Impact Events: {len(high_impact)}")
                if high_impact:
                    print("Sample High Impact:", json.dumps(high_impact[0], indent=2))
        else:
            print("Response:", response.text[:500])
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_fmp_calendar()
