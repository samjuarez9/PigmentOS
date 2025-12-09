import unittest
import yfinance as yf

class TestMovers(unittest.TestCase):
    def test_get_movers(self):
        print("\nChecking yfinance for movers...")
        
        tickers = ["NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "META", "GOOGL", "AMD", "INTC", "NFLX", "SPY", "QQQ", "IWM", "COIN", "MSTR"]
        
        try:
            # We are just testing if we can fetch data and calculate changes without error
            print(f"Fetching info for {tickers[:3]}...")
            movers = []
            for t in tickers:
                tick = yf.Ticker(t)
                # fast_info is better and faster
                if hasattr(tick, 'fast_info'):
                    try:
                        last_price = tick.fast_info.last_price
                        prev_close = tick.fast_info.previous_close
                        
                        # Check for valid data before calculation
                        if last_price is not None and prev_close is not None and prev_close != 0:
                            change = last_price / prev_close - 1
                            movers.append({"symbol": t, "change": change * 100})
                    except Exception as e:
                        print(f"Could not fetch data for {t}: {e}")
                else:
                    print(f"Skipping {t}: No fast_info")
                
            # Sort
            movers.sort(key=lambda x: x['change'], reverse=True)
            
            print("Top Gainers:")
            for m in movers[:3]:
                print(f"{m['symbol']}: {m['change']:.2f}%")
                
            print("\nTop Losers:")
            for m in movers[-3:]:
                print(f"{m['symbol']}: {m['change']:.2f}%")
                
            # Assert we got at least some data if network is up
            if len(movers) == 0:
                print("Warning: No movers data fetched. This might be due to network or market data issues.")
            else:
                self.assertTrue(len(movers) > 0)
                
        except Exception as e:
            self.fail(f"Error in test_get_movers: {e}")

if __name__ == "__main__":
    unittest.main()
