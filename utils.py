import json
import yfinance as yf

WATCHLIST = 'watchlist.json'

def save_watchlist(tickers):
    with open(WATCHLIST, 'w') as f:
        json.dump(tickers, f)

def load_watchlist():
    try:
        with open(WATCHLIST, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def fetch_stockdata(ticker):
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period='1d')
        if not data.empty:
            row = data.iloc[-1]
            price = row['Close']
            high = row['High']
            low = row['Low']
            volume = row['Volume']
            prev_close = stock.info.get('previousClose', price)
            change = price - prev_close
            change_percent = (change / prev_close * 100) if prev_close else 0
            date = row.name.strftime("%Y-%m-%d")

            return {
                'ticker': ticker,
                'price': price,
                'date': date,
                'change': change,
                'change_percent': change_percent,
                'high': high,
                'low': low,
                'volume': volume,
            }
        return None
    except Exception:
        return None