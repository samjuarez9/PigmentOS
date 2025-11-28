import yfinance as yf
import json

def get_movers():
    try:
        # yfinance doesn't have a direct "get_day_gainers" method on the Ticker object easily accessible 
        # without knowing the specific tickers. 
        # However, we can try to use the 'screener' or specific sector tickers if needed.
        # But actually, yfinance has a `Screen` or `Sector` or similar? No.
        # Let's check if we can get it via a specific "Day Gainers" symbol or similar, 
        # OR if we have to fetch a list of tickers and sort them.
        
        # Actually, yfinance has `yf.Tickers` but that requires a list.
        # Let's try to see if there is a known way or if we need to use a different approach.
        # Wait, yfinance might not have a direct "market movers" endpoint exposed easily.
        
        # Let's try to fetch a few popular tickers and see if we can sort them manually as a fallback
        # if a direct endpoint doesn't exist.
        
        # BUT, the user asked "does yahoofinance offer top movers".
        # Let's try to find if there is a specific module.
        
        print("Checking yfinance for movers...")
        
        # Attempt 1: Check if there's a sector or industry call that returns many tickers
        # This is inefficient.
        
        # Attempt 2: Use `yf.Search`? No.
        
        # Let's try to fetch a pre-defined list of popular stocks and calculate movers manually
        # This is often how it's done if the API doesn't give a "top list".
        
        tickers = ["NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "META", "GOOGL", "AMD", "INTC", "NFLX", "SPY", "QQQ", "IWM", "COIN", "MSTR"]
        data = yf.download(tickers, period="1d", interval="1d", progress=False)
        
        # Calculate % change
        # data['Close'] and data['Open'] (or previous close)
        
        # Actually, let's just get the 'regularMarketChangePercent' from info for a single ticker to see if it's there.
        
        print(f"Fetching info for {tickers[:3]}...")
        movers = []
        for t in tickers:
            tick = yf.Ticker(t)
            # info = tick.info # This is slow for many tickers
            # fast_info is better
            change = tick.fast_info.last_price / tick.fast_info.previous_close - 1
            movers.append({"symbol": t, "change": change * 100})
            
        # Sort
        movers.sort(key=lambda x: x['change'], reverse=True)
        
        print("Top Gainers:")
        for m in movers[:3]:
            print(f"{m['symbol']}: {m['change']:.2f}%")
            
        print("\nTop Losers:")
        for m in movers[-3:]:
            print(f"{m['symbol']}: {m['change']:.2f}%")
            
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    get_movers()
