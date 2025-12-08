import yfinance as yf

print("Fetching Earnings Dates for NVDA...")
try:
    ticker = yf.Ticker("NVDA")
    calendar = ticker.calendar
    print(f"Calendar: {calendar}")
    
    earnings_dates = ticker.earnings_dates
    if earnings_dates is not None:
        print(f"Earnings Dates (Head): \n{earnings_dates.head()}")
    else:
        print("Earnings Dates is None")
        
except Exception as e:
    print(f"Error: {e}")
