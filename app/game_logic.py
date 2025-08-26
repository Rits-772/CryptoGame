# --- game_logic.py (updated for users.csv balance system) ---
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import os
from datetime import datetime

# Import balance functions from main app
from test import load_user_data, save_user_data


STARTING_BALANCE = 10000  # ₹10,000

def get_portfolio_path(player_name):
    return os.path.join("data", f"Portfolio_{player_name}.csv")

# --- Balance Management ---
def get_cash_balance(player_name):
    balance = load_user_data(player_name)
    if balance is None:
        balance = STARTING_BALANCE
        save_user_data(player_name, balance)
    return balance

def update_cash_balance(player_name, new_balance):
    save_user_data(player_name, new_balance)

# --- Portfolio Management ---
def initialize_game(player_name):
    portfolio_file = get_portfolio_path(player_name)
    if not os.path.exists(portfolio_file):
        pd.DataFrame(columns=["Symbol", "Quantity", "Buy Price", "Buy Date"]).to_csv(
            portfolio_file, index=False
        )
    # balances handled entirely via users.csv

def get_portfolio(player_name):
    if os.path.exists(get_portfolio_path(player_name)):
        return pd.read_csv(get_portfolio_path(player_name))
    return pd.DataFrame(columns=["Symbol", "Quantity", "Buy Price", "Buy Date"])

def update_portfolio(player_name, df):
    df.to_csv(get_portfolio_path(player_name), index=False)

# --- Trading Logic ---
def buy_stock(player_name, symbol, quantity):
    quantity = int(quantity)
    stock = yf.Ticker(symbol)
    price = stock.history(period="1d")["Close"][0]
    cost = price * quantity

    balance = get_cash_balance(player_name)
    if cost > balance:
        return False, f"Not enough balance to buy {quantity} shares of {symbol} at ₹{price:.2f}"

    portfolio = get_portfolio(player_name)
    if symbol in portfolio["Symbol"].values:
        row = portfolio.loc[portfolio["Symbol"] == symbol]
        new_qty = row.Quantity.values[0] + quantity
        new_price = (
            (row.Quantity.values[0] * row["Buy Price"].values[0]) + cost
        ) / new_qty
        portfolio.loc[
            portfolio["Symbol"] == symbol, ["Quantity", "Buy Price", "Buy Date"]
        ] = [new_qty, new_price, datetime.now().strftime("%Y-%m-%d")]
    else:
        new_row = {
            "Symbol": symbol,
            "Quantity": quantity,
            "Buy Price": price,
            "Buy Date": datetime.now().strftime("%Y-%m-%d"),
        }
        portfolio = pd.concat([portfolio, pd.DataFrame([new_row])], ignore_index=True)

    update_portfolio(player_name, portfolio)
    update_cash_balance(player_name, balance - cost)
    return True, f"Bought {quantity} shares of {symbol} at ₹{price:.2f} each."

def sell_stock(player_name, symbol, quantity):
    quantity = int(quantity)
    stock = yf.Ticker(symbol)
    price = stock.history(period="1d")["Close"][0]
    revenue = price * quantity

    portfolio = get_portfolio(player_name)
    if symbol not in portfolio["Symbol"].values:
        return False, f"You don't own any shares of {symbol}."

    row = portfolio.loc[portfolio["Symbol"] == symbol]
    current_qty = row.Quantity.values[0]

    if quantity > current_qty:
        return False, f"You only have {current_qty} shares of {symbol}."

    if quantity == current_qty:
        portfolio = portfolio[portfolio["Symbol"] != symbol]
    else:
        portfolio.loc[portfolio["Symbol"] == symbol, "Quantity"] = current_qty - quantity

    update_portfolio(player_name, portfolio)
    update_cash_balance(player_name, get_cash_balance(player_name) + revenue)
    return True, f"Sold {quantity} shares of {symbol} at ₹{price:.2f} each."

# --- Charting ---
def get_combined_price_charts_grouped(symbols):
    fig = go.Figure()
    for symbol in symbols:
        try:
            hist = yf.Ticker(symbol).history(period="3mo")
            fig.add_trace(
                go.Scatter(
                    x=hist.index,
                    y=hist["Close"],
                    mode="lines",
                    name=symbol,
                )
            )
        except Exception:
            continue
    fig.update_layout(
        title="Stock Price Comparison",
        xaxis_title="Date",
        yaxis_title="Price (₹ or $)",
        template="plotly_dark",
    )
    return fig

def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def plot_with_indicators(symbol):
    df = yf.Ticker(symbol).history(period="3mo").reset_index()
    df["SMA_7"] = df["Close"].rolling(window=7).mean()
    df["SMA_14"] = df["Close"].rolling(window=14).mean()
    df["RSI"] = compute_rsi(df["Close"])

    from plotly.subplots import make_subplots

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.7, 0.3],
        vertical_spacing=0.1,
        subplot_titles=(f"{symbol} Price with SMA", "RSI Indicator"),
    )

    fig.add_trace(
        go.Scatter(x=df["Date"], y=df["Close"], name="Price", line=dict(color="black")),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=df["Date"], y=df["SMA_7"], name="7-Day SMA", line=dict(dash="dot")),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df["Date"], y=df["SMA_14"], name="14-Day SMA", line=dict(dash="dash")
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=df["Date"], y=df["RSI"], name="RSI", line=dict(color="orange")),
        row=2,
        col=1,
    )

    fig.add_shape(
        type="line",
        x0=df["Date"].min(),
        x1=df["Date"].max(),
        y0=70,
        y1=70,
        line=dict(dash="dash", color="green"),
        row=2,
        col=1,
    )
    fig.add_shape(
        type="line",
        x0=df["Date"].min(),
        x1=df["Date"].max(),
        y0=30,
        y1=30,
        line=dict(dash="dash", color="red"),
        row=2,
        col=1,
    )

    fig.update_layout(
        height=700,
        xaxis=dict(rangeslider=dict(visible=True), type="date"),
        updatemenus=[
            dict(
                type="buttons",
                direction="right",
                x=0.1,
                y=1.2,
                showactive=True,
                buttons=list(
                    [
                        dict(
                            label="Show All",
                            method="update",
                            args=[{"visible": [True, True, True, True]}],
                        ),
                        dict(
                            label="Only Price",
                            method="update",
                            args=[{"visible": [True, False, False, False]}],
                        ),
                        dict(
                            label="Price + SMA",
                            method="update",
                            args=[{"visible": [True, True, True, False]}],
                        ),
                        dict(
                            label="Price + RSI",
                            method="update",
                            args=[{"visible": [True, False, False, True]}],
                        ),
                    ]
                ),
            )
        ],
        title=f"{symbol} Chart with SMA & RSI",
    )

    return fig