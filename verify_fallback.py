import sys
import time
from unittest.mock import MagicMock, patch

# Mock dependencies before importing run
sys.modules['flask'] = MagicMock()
sys.modules['flask_cors'] = MagicMock()
sys.modules['flask_socketio'] = MagicMock()
sys.modules['yfinance'] = MagicMock()
sys.modules['requests'] = MagicMock()

# Import the function to test
# We need to load run.py but it has global execution code. 
# Ideally we'd import it, but it might start servers or connect to DBs.
# Let's read the file and extract the function or just rely on the fact that we modified it 
# and trust the logic. 
# Better: Create a script that imports run.py safely if possible, or just copies the function logic for testing?
# No, copying logic doesn't test the actual file.
# Let's try to import run.py but mock everything that causes side effects.

# Actually, run.py has `if __name__ == '__main__':` so it should be safe to import 
# IF we mock the global objects it initializes at top level.
# It initializes Flask app, etc.

# Let's just create a script that uses the modified run.py logic by importing it.
# But run.py imports `app` from `flask` etc.

# Alternative: We can just run a small script that imports `get_finnhub_price` from `run`
# assuming we can bypass the heavy imports.

# Let's try a simpler approach: 
# We will create a script that defines the SAME function structure and logic to verify the logic flow,
# OR we can just trust the code change since it was a simple insertion.
# But the user wants verification.

# Let's try to run a script that imports `run` and mocks `requests.get` to fail for Finnhub
# and mocks `yfinance.Ticker` to succeed.

import os
# Set dummy env vars to avoid errors
os.environ["FINNHUB_API_KEY"] = "dummy"
os.environ["POLYGON_API_KEY"] = "dummy"

# Mock yfinance
import yfinance as yf
mock_ticker = MagicMock()
mock_ticker.fast_info.last_price = 335.50
yf.Ticker = MagicMock(return_value=mock_ticker)

# Mock requests
import requests
def mock_get(url, timeout=5):
    mock_resp = MagicMock()
    if "finnhub" in url:
        print("Mocking Finnhub FAILURE")
        mock_resp.status_code = 403 # Fail
    elif "polygon" in url:
        print("Mocking Polygon SUCCESS (Should not be reached if yfinance works)")
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": [{"c": 331.00}]}
    return mock_resp
requests.get = MagicMock(side_effect=mock_get)

# Now import run
# We need to handle the fact that run.py creates a Flask app on import.
# That's fine as long as it doesn't run.
try:
    import run
except Exception as e:
    print(f"Import warning: {e}")

# Reset caches
run.FINNHUB_PRICE_CACHE = {}
run.PRICE_CACHE = {}

print("\n--- Testing Fallback Logic ---")
price = run.get_finnhub_price("GOOGL")
print(f"Returned Price: {price}")

if price == 335.50:
    print("✅ SUCCESS: Fell back to yfinance price (335.50)")
elif price == 331.00:
    print("❌ FAILURE: Fell back to Polygon price (331.00)")
else:
    print(f"❌ FAILURE: Returned unexpected price {price}")
