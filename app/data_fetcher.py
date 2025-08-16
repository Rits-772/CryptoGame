import yfinance as yf
import requests

def getStockPrice(symbol):
    """
    Fetches the latest stock closing price using yfinance.
    """
    try:
        stock = yf.Ticker(symbol)
        data = stock.history(period="1d")
        return round(data['Close'].iloc[-1], 2)
    except Exception as e:
        print(f"[Stock Error] {symbol}: {e}")
        return None

def getCryptoPrice(symbol):
    """
    Fetches the latest crypto price in USD using the CryptoCompare API.
    """
    try:
        url = f"https://min-api.cryptocompare.com/data/price?fsym={symbol.upper()}&tsyms=USD"
        res = requests.get(url)
        return round(res.json()["USD"], 2)
    except Exception as e:
        print(f"[Crypto Error] {symbol}: {e}")
        return None
