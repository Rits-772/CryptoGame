# ...existing code from PortfolioAnalyzer.py will be moved here...
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import plotly.express as px
import datetime
import os
import numpy as np

def calculate_portfolio_value(portfolio_df):
    totalValue = 0
    for _, row in portfolio_df.iterrows():
        try:
            currentPrice = yf.Ticker(row['Symbol']).info.get("regularMarketPrice", 0)
            totalValue += currentPrice * row['Quantity']
        except:
            continue
        
    return totalValue

def log_portfolio_value(portfolio_df, cashBalanceFile="cashBalance.txt", historyFile="portfolio_history.csv"):
    today = datetime.date.today().isoformat()
    totalStockValue = calculate_portfolio_value(portfolio_df)
    cash = float(open(cashBalanceFile).read().strip()) if os.path.exists(cashBalanceFile) else 0.0
    totalValue = totalStockValue + cash

    df = pd.DataFrame([[today, totalValue]], columns=["Date", "Portfolio Value"])
    if os.path.exists(historyFile):
        existing = pd.read_csv(historyFile)
        if today not in existing['Date'].values:
            df = pd.concat([existing, df])
        else:
            df = existing
    df.to_csv(historyFile, index=False)
    
def plot_portfolio_value_over_time(historyFile="portfolio_history.csv"):
    if os.path.exists(historyFile):
        return None
    
    df = pd.read_csv(historyFile)
    fig = px.line(df, x='Date', y='Portfolio Value', title='Portfolio Value Over Time')
    return fig

def plot_asset_allocation(portfolio_df):
    if portfolio_df.empty:
        return None
    
    allocations = []
    labels = []
    
    for _, row in portfolio_df.iterrows():
        try:
            currentPrice = yf.Ticker(row['Symbol']).info.get("regularMarketPrice", 0)
            value = currentPrice * row['Quantity']
            allocations.append(value)
            labels.append(row['Symbol'])
        except:
            continue
    
    fig = px.pie(names=labels, values=allocations, title='Asset Allocation')
    return fig

def plot_stock_vs_buy_price(portfolio_df):
    plots = []
    for _, row in portfolio_df.iterrows():
        symbol = row["Symbol"]
        qty = row["Quantity"]
        buy_price = row["Buy Price"]
        try:
            hist = yf.Ticker(symbol).history(period="3mo")
            fig = px.line(hist, x=hist.index, y="Close", title=f"{symbol} - 📉 Price vs Buy Price")
            fig.add_hline(y=buy_price, line_dash="dash", line_color="red", annotation_text="Buy Price")
            plots.append(fig)
        except:
            continue
    return plots

def calculate_risk_metrics(portfolio_df):
    returns = []
    for _, row in portfolio_df.iterrows():
        symbol = row["Symbol"]
        try:
            hist = yf.Ticker(symbol).history(period="3mo")["Close"].pct_change().dropna()
            returns.append(hist)
        except:
            continue
    if not returns:
        return {"Volatility": "N/A", "Sharpe Ratio": "N/A"}

    combined = pd.concat(returns, axis=1).dropna()
    portfolio_returns = combined.mean(axis=1)
    volatility = np.std(portfolio_returns) * np.sqrt(252)
    sharpe_ratio = (portfolio_returns.mean() * 252) / volatility if volatility != 0 else 0

    return {
        "Volatility": round(volatility, 4),
        "Sharpe Ratio": round(sharpe_ratio, 4)
    }

def plot_stock_vs_buy_price_filtered(portfolio_df, symbol):
    row = portfolio_df[portfolio_df["Symbol"] == symbol].iloc[0]
    buy_price = row["Buy Price"]
    try:
        hist = yf.Ticker(symbol).history(period="3mo")
        fig = px.line(hist, x=hist.index, y="Close", title=f"{symbol} - 📉 Price vs Buy Price")
        fig.add_hline(y=buy_price, line_dash="dash", line_color="red", annotation_text="Buy Price")
        return fig
    except:
        return None

def calculate_risk_metrics_filtered(portfolio_df, symbol):
    try:
        hist = yf.Ticker(symbol).history(period="3mo")["Close"].pct_change().dropna()
        if hist.empty:
            return {"Volatility": "N/A", "Sharpe Ratio": "N/A"}
        volatility = np.std(hist) * np.sqrt(252)
        sharpe = (hist.mean() * 252) / volatility if volatility != 0 else 0
        return {
            "Volatility": round(volatility, 4),
            "Sharpe Ratio": round(sharpe, 4)
        }
    except:
        return {"Volatility": "N/A", "Sharpe Ratio": "N/A"}
