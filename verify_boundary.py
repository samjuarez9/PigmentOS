import os
import sys
import time
from datetime import datetime
from unittest.mock import patch, MagicMock

sys.path.append(os.getcwd())
from run import refresh_gamma_logic, CACHE

def test_market_boundary():
    print("🧪 Testing Market Boundary Logic (9:00 AM vs 9:30 AM)...")
    
    with patch('run.datetime') as mock_datetime:
        mock_now = MagicMock()
        mock_now.date.return_value.weekday.return_value = 4 # Friday
        mock_datetime.now.return_value = mock_now
        mock_datetime.side_effect = datetime
        
        with patch('run.get_cached_price', return_value=500.0), \
             patch('run.fetch_options_chain_polygon', return_value=None): # Mock polygon to avoid calls
            
            # Case 1: 9:15 AM (Should be PREMARKET)
            mock_now.hour = 9
            mock_now.minute = 15
            refresh_gamma_logic("SPY")
            data = CACHE.get("gamma_SPY", {}).get("data")
            print(f"⏰ 9:15 AM -> Period: {data.get('time_period')}, Source: {data.get('source')}")
            
            if data.get('time_period') != 'pre_market':
                print("❌ FAILURE: 9:15 AM should be pre_market")
            else:
                print("✅ SUCCESS: 9:15 AM is pre_market")

            # Clear Cache before next test
            CACHE["gamma_SPY"] = {}
            
            # Case 2: 9:30 AM (Should be MARKET)
            mock_now.hour = 9
            mock_now.minute = 30
            refresh_gamma_logic("SPY")
            data = CACHE.get("gamma_SPY", {}).get("data")
            
            # If Polygon failed (as expected due to mock), data might be None or empty
            # But we know it shouldn't be 'premarket_wait'
            
            print(f"⏰ 9:30 AM -> Source: {data.get('source') if data else 'None (Polygon Failed)'}") 
            
            if data and data.get('source') == 'premarket_wait':
                print("❌ FAILURE: 9:30 AM should NOT be premarket_wait")
            else:
                print("✅ SUCCESS: 9:30 AM exited premarket block")

if __name__ == "__main__":
    test_market_boundary()
