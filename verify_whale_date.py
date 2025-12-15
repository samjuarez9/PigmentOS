import os
import sys
import time
import json
from datetime import datetime, date
from unittest.mock import patch, MagicMock

sys.path.append(os.getcwd())
from run import refresh_single_whale_polygon, CACHE, WHALE_HISTORY

def test_whale_date_filter():
    print("🧪 Testing Whale Stream Date Filtering (Today vs Yesterday)...")
    
    # Mock datetime to be 9:30 AM ET Today
    with patch('run.datetime') as mock_datetime:
        mock_now = MagicMock()
        # Set "Today" to a fixed date: 2024-01-05 (Friday)
        fixed_date = date(2024, 1, 5)
        mock_now.date.return_value = fixed_date
        mock_now.weekday.return_value = 4 # Friday
        mock_now.timestamp.return_value = 1704465000 # 9:30 AM ET
        mock_now.hour = 9
        mock_now.minute = 30
        
        # Configure now() to return our mock
        mock_datetime.now.return_value = mock_now
        mock_datetime.fromtimestamp.side_effect = datetime.fromtimestamp # Use real fromtimestamp
        mock_datetime.side_effect = datetime # Use real datetime for other calls
        
        # Mock fetch_unusual_options_polygon to return mixed data
        # 1. Trade from TODAY (9:29 AM)
        # 2. Trade from YESTERDAY (4:00 PM)
        
        today_ts = 1704464940 * 1_000_000_000 # 9:29 AM ET (in nanoseconds)
        yesterday_ts = 1704384000 * 1_000_000_000 # Yesterday 4:00 PM ET
        
        mock_data = {
            "results": [
                {
                    "details": {"ticker": "SPY", "strike_price": 470, "contract_type": "call", "expiration_date": "2024-01-05"},
                    "day": {"volume": 1000, "close": 2.5, "last_updated": today_ts},
                    "open_interest": 100
                },
                {
                    "details": {"ticker": "QQQ", "strike_price": 400, "contract_type": "put", "expiration_date": "2024-01-05"},
                    "day": {"volume": 2000, "close": 3.0, "last_updated": yesterday_ts},
                    "open_interest": 200
                }
            ],
            "_current_price": 470
        }
        
        with patch('run.fetch_unusual_options_polygon', return_value=mock_data):
            # Clear Cache first
            CACHE["whales"]["data"] = []
            WHALE_HISTORY.clear()
            
            # Run Logic
            refresh_single_whale_polygon("SPY")
            
            # Check Results
            whales = CACHE["whales"]["data"]
            print(f"🐋 Whales Found: {len(whales)}")
            
            found_spy = False
            found_qqq = False
            
            for w in whales:
                print(f"  - {w['symbol']} ({w['putCall']}) @ {w['tradeTime']}")
                if "SPY" in w['symbol']: found_spy = True
                if "QQQ" in w['symbol']: found_qqq = True
            
            if found_spy and not found_qqq:
                print("✅ SUCCESS: Only TODAY's trade (SPY) was included. Yesterday's trade (QQQ) was filtered out.")
            elif found_qqq:
                print("❌ FAILURE: Yesterday's trade (QQQ) was NOT filtered out.")
            else:
                print("❌ FAILURE: Today's trade (SPY) was NOT found.")

if __name__ == "__main__":
    test_whale_date_filter()
