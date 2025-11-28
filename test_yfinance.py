import yfinance as yf
import time

def get_spy_put_volume():
    start_time = time.time()
    try:
        spy = yf.Ticker("SPY")
        # Get expiration dates
        exps = spy.options
        if not exps:
            print("No expirations found")
            return

        # Fetch nearest expiration chain
        chain = spy.option_chain(exps[0])
        puts = chain.puts
        
        total_vol = puts['volume'].sum()
        print(f"SPY Put Volume (Exp {exps[0]}): {total_vol}")
        print(f"Time taken: {time.time() - start_time:.2f}s")
    except Exception as e:
        print(f"Error: {e}")

get_spy_put_volume()
