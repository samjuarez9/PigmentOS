import sys
import os
import time
from datetime import datetime, timedelta
import pytz

# Add project root to path
sys.path.append(os.path.abspath("/Users/newuser/PigmentOS"))

# Mock environment variables if needed
os.environ["ALPACA_API_KEY"] = "PK78229D29103" # Mock or real key if available
os.environ["ALPACA_SECRET_KEY"] = "sk_test_..." # Mock
os.environ["POLYGON_API_KEY"] = "mock_poly_key"

# Import the functions to test
# We need to mock requests to avoid actual API calls and control the data
from unittest.mock import MagicMock, patch
import run

def test_30dte_filter():
    print("🧪 Testing 30-Day DTE Filter...")
    
    # Mock current time
    tz_eastern = pytz.timezone('US/Eastern')
    now_et = datetime.now(tz_eastern)
    
    # 1. Test Polygon Scanner Logic
    print("\n--- Polygon Scanner Test ---")
    
    # Create mock trades with various expiries
    expiry_ok = (now_et + timedelta(days=15)).strftime("%Y-%m-%d")
    expiry_bad = (now_et + timedelta(days=45)).strftime("%Y-%m-%d")
    
    mock_poly_resp = {
        "results": [
            {
                "details": {
                    "ticker": "O:SPY250115C00500000",
                    "strike_price": 500,
                    "contract_type": "call",
                    "expiration_date": expiry_ok
                },
                "day": {"volume": 1000, "close": 5.0},
                "greeks": {"delta": 0.5}
            },
            {
                "details": {
                    "ticker": "O:SPY250215C00500000",
                    "strike_price": 500,
                    "contract_type": "call",
                    "expiration_date": expiry_bad
                },
                "day": {"volume": 1000, "close": 5.0},
                "greeks": {"delta": 0.5}
            }
        ],
        "_current_price": 500
    }
    
    with patch('run.fetch_unusual_options_polygon') as mock_fetch:
        mock_fetch.return_value = mock_poly_resp
        
        # Run scanner
        whales = run.scan_whales_polygon()
        
        print(f"Input trades: 2 (1 OK, 1 > 30 days)")
        print(f"Output trades: {len(whales)}")
        
        if len(whales) == 1 and whales[0]['expirationDate'] == expiry_ok:
            print("✅ Polygon Filter: PASSED")
        else:
            print("❌ Polygon Filter: FAILED")
            for w in whales:
                print(f"  - Got trade with expiry: {w['expirationDate']}")

    # 2. Test Alpaca Scanner Logic
    print("\n--- Alpaca Scanner Test ---")
    
    # Mock Alpaca response
    # Alpaca uses OCC symbols which contain the date
    # Format: SPY + YYMMDD + C/P + Strike
    
    def make_occ(date_obj):
        y = date_obj.year % 100
        m = date_obj.month
        d = date_obj.day
        return f"SPY{y:02d}{m:02d}{d:02d}C00500000"
        
    occ_ok = make_occ(now_et + timedelta(days=15))
    occ_bad = make_occ(now_et + timedelta(days=45))
    
    mock_alpaca_resp = {
        "snapshots": {
            occ_ok: {
                "dailyBar": {"v": 1000},
                "latestTrade": {"p": 5.0, "t": "2025-01-01T10:00:00Z"},
                "latestQuote": {"ap": 5.1, "bp": 4.9}
            },
            occ_bad: {
                "dailyBar": {"v": 1000},
                "latestTrade": {"p": 5.0, "t": "2025-01-01T10:00:00Z"},
                "latestQuote": {"ap": 5.1, "bp": 4.9}
            }
        }
    }
    
    with patch('requests.get') as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_alpaca_resp
        mock_get.return_value = mock_resp
        
        # Run scanner
        whales = run.scan_whales_alpaca()
        
        print(f"Input trades: 2 (1 OK, 1 > 30 days)")
        print(f"Output trades: {len(whales)}")
        
        # Note: scan_whales_alpaca parses the OCC symbol to get expiry
        # We need to check if it correctly filtered
        
        if len(whales) == 1:
             print("✅ Alpaca Filter: PASSED")
        else:
            print("❌ Alpaca Filter: FAILED")
            for w in whales:
                print(f"  - Got trade with expiry: {w['expirationDate']}")

if __name__ == "__main__":
    test_30dte_filter()
