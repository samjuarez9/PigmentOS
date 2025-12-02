import yfinance as yf

ticker = yf.Ticker("SPY")
hist = ticker.history(period="5d")
print(hist[['Close', 'Volume']])
