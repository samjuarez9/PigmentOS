import yfinance as yf
import sys

def get_vix():
    try:
        vix = yf.Ticker("^VIX")
        # Try fast_info first
        try:
            price = vix.fast_info['last_price']
        except:
            # Fallback to history
            price = vix.history(period="1d")['Close'].iloc[-1]
            
        print(price)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    get_vix()
