import os
import sys
import time
import json
from datetime import datetime
from unittest.mock import patch, MagicMock

# Add current directory to path
sys.path.append(os.getcwd())

# Import the function to test
# We need to mock datetime to simulate premarket
from run import refresh_gamma_logic, CACHE

def test_premarket_logic():
    print("🧪 Testing Premarket Logic for Gamma Wall...")
    
    # Mock datetime to be 8:00 AM ET (Premarket)
    # 8:00 AM ET is 13:00 UTC (assuming standard time)
    # But run.py uses pytz.timezone('US/Eastern')
    
    with patch('run.datetime') as mock_datetime:
        # Create a mock datetime object that behaves like a real one
        # 2024-01-05 (Friday) 08:00:00 ET
        mock_now = MagicMock()
        mock_now.date.return_value.weekday.return_value = 4 # Friday
        mock_now.hour = 8
        mock_now.minute = 0
        
        # Configure now() to return our mock
        mock_datetime.now.return_value = mock_now
        mock_datetime.side_effect = datetime
        
        # Also need to mock get_cached_price to avoid network calls and return a dummy price
        with patch('run.get_cached_price', return_value=500.0):
            
            # Run the logic
            refresh_gamma_logic("SPY")
            
            # Check Cache
            cache_key = "gamma_SPY"
            data = CACHE.get(cache_key, {}).get("data")
            
            if not data:
                print("❌ No data in cache")
                return
            
            print(f"📊 Time Period: {data.get('time_period')}")
            print(f"📉 Strikes Count: {len(data.get('strikes'))}")
            print(f"🏷️ Source: {data.get('source')}")
            
            if data.get('time_period') == 'pre_market' and len(data.get('strikes')) == 0 and data.get('source') == 'premarket_wait':
                print("✅ SUCCESS: Premarket logic correctly returned empty strikes and 'premarket_wait' source.")
            else:
                print("❌ FAILURE: Logic did not return expected premarket state.")

if __name__ == "__main__":
    test_premarket_logic()
