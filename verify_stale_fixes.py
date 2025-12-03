import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import pandas as pd
import pytz
from datetime import datetime, timedelta
import time

# Add current directory to path
sys.path.append(os.getcwd())

# Mock start_background_worker to avoid starting threads on import
with patch('run.start_background_worker'):
    import run

class TestStaleFixes(unittest.TestCase):
    
    def setUp(self):
        # Reset Cache
        run.CACHE = {
            "whales": {"data": [], "timestamp": 0},
            "gamma_SPY": {"data": None, "timestamp": 0}
        }

    @patch('run.yf.Ticker')
    def test_gamma_stale_volume(self, mock_ticker):
        print("\nTesting Gamma Stale Volume Logic...")
        
        # Setup Mock Data
        mock_t = MagicMock()
        mock_ticker.return_value = mock_t
        
        # Mock Price
        mock_t.fast_info.last_price = 500.0
        mock_t.options = ['2024-12-06']
        
        # Mock Option Chain
        mock_opts = MagicMock()
        mock_t.option_chain.return_value = mock_opts
        
        # Create DataFrame with OLD date
        tz_eastern = pytz.timezone('US/Eastern')
        yesterday = datetime.now(tz_eastern) - timedelta(days=1)
        
        data = {
            'strike': [500.0],
            'volume': [1000],
            'openInterest': [5000],
            'lastTradeDate': [yesterday]
        }
        df = pd.DataFrame(data)
        
        mock_opts.calls = df
        mock_opts.puts = df
        
        # Run Logic
        run.refresh_gamma_logic()
        
        # Check Cache
        gamma_data = run.CACHE.get("gamma_SPY", {}).get("data")
        self.assertIsNotNone(gamma_data)
        
        strikes = gamma_data['strikes']
        self.assertEqual(len(strikes), 1)
        
        # Volume should be 0 because date is yesterday
        self.assertEqual(strikes[0]['call_vol'], 0)
        self.assertEqual(strikes[0]['put_vol'], 0)
        
        # OI should be preserved
        self.assertEqual(strikes[0]['call_oi'], 5000)
        self.assertEqual(strikes[0]['put_oi'], 5000)
        print("✅ Gamma Stale Volume Test Passed (Volume=0, OI=5000)")

    @patch('run.yf.Ticker')
    def test_gamma_fresh_volume(self, mock_ticker):
        print("\nTesting Gamma Fresh Volume Logic...")
        
        # Setup Mock Data
        mock_t = MagicMock()
        mock_ticker.return_value = mock_t
        
        mock_t.fast_info.last_price = 500.0
        mock_t.options = ['2024-12-06']
        
        mock_opts = MagicMock()
        mock_t.option_chain.return_value = mock_opts
        
        # Create DataFrame with TODAY date
        tz_eastern = pytz.timezone('US/Eastern')
        today = datetime.now(tz_eastern)
        
        data = {
            'strike': [500.0],
            'volume': [1000],
            'openInterest': [5000],
            'lastTradeDate': [today]
        }
        df = pd.DataFrame(data)
        
        mock_opts.calls = df
        mock_opts.puts = df
        
        run.refresh_gamma_logic()
        
        gamma_data = run.CACHE.get("gamma_SPY", {}).get("data")
        strikes = gamma_data['strikes']
        
        # Volume should be 1000 because date is today
        self.assertEqual(strikes[0]['call_vol'], 1000)
        print("✅ Gamma Fresh Volume Test Passed (Volume=1000)")

    @patch('run.yf.Ticker')
    def test_whale_cache_clearing(self, mock_ticker):
        print("\nTesting Whale Cache Clearing...")
        
        # Pre-populate Cache with "Stale" data for NVDA
        run.CACHE["whales"]["data"] = [{
            "baseSymbol": "NVDA",
            "symbol": "NVDA_OLD",
            "timestamp": time.time() - 10000
        }]
        
        # Setup Mock to return NO whales
        mock_t = MagicMock()
        mock_ticker.return_value = mock_t
        mock_t.fast_info.last_price = 100.0
        mock_t.options = ['2024-12-06']
        
        mock_opts = MagicMock()
        mock_t.option_chain.return_value = mock_opts
        
        # Empty DataFrame (No unusual whales found)
        empty_df = pd.DataFrame(columns=['volume', 'openInterest', 'lastPrice', 'strike', 'type', 'impliedVolatility', 'contractSymbol', 'lastTradeDate'])
        mock_opts.calls = empty_df
        mock_opts.puts = empty_df
        
        # Run Logic for NVDA
        run.refresh_single_whale("NVDA")
        
        # Check Cache
        whales = run.CACHE["whales"]["data"]
        # Should be empty now
        self.assertEqual(len(whales), 0)
        print("✅ Whale Cache Clearing Test Passed (Cache Empty)")

if __name__ == '__main__':
    unittest.main()
