import yfinance as yf
import time

def verify_movers():
    MOVERS_TICKERS = [
        "NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "META", "GOOGL",
        "AMD", "INTC", "AVGO", "MU", "QCOM", "ARM", "SMCI",
        "PLTR", "COIN", "MSTR", "GME", "AMC", "SOFI", "HOOD", "BBBY",
        "SNOW", "DDOG", "NET", "CRWD", "ZS", "SHOP", "ROKU", "UPST",
        "SQ", "PYPL", "AFRM",
        "NFLX", "DIS", "UBER", "DASH", "ABNB", "PTON", "NKE", "SBUX",
        "RIVN", "LCID", "NIO", "RKLB",
        "BA", "SNAP", "PINS", "SPOT",
        "SPY", "QQQ", "IWM", "DIA"
    ]
    
    print(f"Fetching data for {len(MOVERS_TICKERS)} tickers...")
    start_time = time.time()
    
    movers = []
    tickers_obj = yf.Tickers(" ".join(MOVERS_TICKERS))
    
    success_count = 0
    fail_count = 0
    
    for symbol in MOVERS_TICKERS:
        try:
            t = tickers_obj.tickers[symbol]
            # Mimic the backend logic exactly
            last = t.fast_info.last_price
            prev = t.fast_info.previous_close
            
            if last and prev:
                change = ((last - prev) / prev) * 100
                movers.append({
                    "symbol": symbol,
                    "change": round(change, 2),
                    "type": "gain" if change >= 0 else "loss",
                    "price": last
                })
                success_count += 1
                print(f"✅ {symbol}: {last:.2f} ({change:+.2f}%)")
            else:
                print(f"⚠️ {symbol}: Missing price data (last={last}, prev={prev})")
                fail_count += 1
        except Exception as e:
            print(f"❌ {symbol}: Error - {e}")
            fail_count += 1
            
    end_time = time.time()
    duration = end_time - start_time
    
    print(f"\nSummary:")
    print(f"Total Tickers: {len(MOVERS_TICKERS)}")
    print(f"Success: {success_count}")
    print(f"Failed: {fail_count}")
    print(f"Duration: {duration:.2f} seconds")
    
    if movers:
        movers.sort(key=lambda x: x['change'], reverse=True)
        print("\nTop 5 Gainers:")
        for m in movers[:5]:
            print(f"{m['symbol']}: {m['change']}%")
            
        print("\nTop 5 Losers:")
        for m in movers[-5:]:
            print(f"{m['symbol']}: {m['change']}%")
    else:
        print("\n❌ No data fetched!")

if __name__ == "__main__":
    verify_movers()
