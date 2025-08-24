# --- CryptoGame Main App (Enhanced, Fixed) ---
import os
import json
import time
import base64
import datetime
from typing import Dict, List

import pandas as pd
import yfinance as yf
import streamlit as st
import streamlit.components.v1 as components

# Local modules
from data_fetcher import getStockPrice
import portfolio_analyzer as pa
from game_logic import get_cash_balance, sell_stock, plot_with_indicators, update_cash_balance
import achievements as achievements
import store as store

# =============================
# Early config (must be the first Streamlit call)
# =============================
st.set_page_config(page_title="CryptoGame", page_icon="💹", layout="wide")

# Ensure required folders exist
os.makedirs("data", exist_ok=True)
os.makedirs("gui", exist_ok=True)

# =============================
# Config & Helpers
# =============================
PRICE_FILE = os.path.join("data", "prices.csv")
REFRESH_HOURS = 6  # cache refresh twice a day
REFRESH_INTERVAL = REFRESH_HOURS * 60 * 60

EMOJI_PREFIX = {
    "info": "ℹ️ ",
    "success": "✅ ",
    "warning": "⚠️ ",
    "error": "❌ ",
}

def ui_msg(kind: str, text: str):
    prefix = EMOJI_PREFIX.get(kind, "")
    st.markdown(f"{prefix}{text}")


def normalize_close_df(close_obj, symbols: List[str]) -> pd.DataFrame:
    """Ensure we always return a DataFrame with columns for each symbol.
    yf.download returns:
      - DataFrame with MultiIndex columns for multiple tickers
      - Series for a single ticker
    """
    if isinstance(close_obj, pd.Series):
        df = close_obj.to_frame(name=symbols[0])
    else:
        df = close_obj.copy()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
    cols = [c for c in symbols if c in df.columns]
    return df[cols]


def load_price_cache(symbols: List[str], period: str = "6mo") -> pd.DataFrame:
    """Load cached Close prices for symbols; refresh if older than REFRESH_INTERVAL."""
    if os.path.exists(PRICE_FILE):
        try:
            modified_time = os.path.getmtime(PRICE_FILE)
            if time.time() - modified_time < REFRESH_INTERVAL:
                cached = pd.read_csv(PRICE_FILE, index_col=0, parse_dates=True)
                return cached[[c for c in symbols if c in cached.columns]]
        except Exception:
            pass

    try:
        data = yf.download(symbols, period=period, auto_adjust=False, threads=True)
        close = data["Close"] if "Close" in data else data  # if single series
        df = normalize_close_df(close, symbols)
        if os.path.exists(PRICE_FILE):
            try:
                old = pd.read_csv(PRICE_FILE, index_col=0, parse_dates=True)
                df = old.combine_first(df).join(df, how="outer", rsuffix="_new")
                for col in list(df.columns):
                    if col.endswith("_new"):
                        base = col[:-4]
                        df[base] = df[col].combine_first(df.get(base))
                        df.drop(columns=[col], inplace=True)
            except Exception:
                pass
        df.sort_index(inplace=True)
        df.to_csv(PRICE_FILE)
        return df[[c for c in symbols if c in df.columns]]
    except Exception:
        if os.path.exists(PRICE_FILE):
            try:
                cached = pd.read_csv(PRICE_FILE, index_col=0, parse_dates=True)
                return cached[[c for c in symbols if c in cached.columns]]
            except Exception:
                pass
        return pd.DataFrame()


def latest_price_from_cache(symbol: str, prices_df: pd.DataFrame) -> float | None:
    try:
        if symbol in prices_df.columns and not prices_df[symbol].dropna().empty:
            return float(prices_df[symbol].dropna().iloc[-1])
    except Exception:
        pass
    return None

SYMBOL_TO_DOMAIN = {
    # US Tech
    "AAPL": "apple.com", "GOOGL": "abc.xyz", "AMZN": "amazon.com", "MSFT": "microsoft.com",
    "TSLA": "tesla.com", "NFLX": "netflix.com", "META": "meta.com", "NVDA": "nvidia.com",
    "BRK-B": "berkshirehathaway.com", "V": "visa.com",
    # India (best-guess primary domains)
    "INFY.NS": "infosys.com", "TCS.NS": "tcs.com", "HDFCBANK.NS": "hdfcbank.com",
    "RELIANCE.NS": "ril.com", "ICICIBANK.NS": "icicibank.com", "SBIN.NS": "sbi.co.in",
    "KOTAKBANK.NS": "kotak.com", "AXISBANK.NS": "axisbank.com", "LT.NS": "larsentoubro.com",
    "ITC.NS": "itcportal.com", "BAJFINANCE.NS": "bajajfinserv.in", "SUNPHARMA.NS": "sunpharma.com",
    "MARUTI.NS": "marutisuzuki.com", "TITAN.NS": "titan.co.in", "ONGC.NS": "ongcindia.com",
    "HCLTECH.NS": "hcltech.com", "ULTRACEMCO.NS": "ultratechcement.com", "ASIANPAINTS.NS": "asianpaints.com",
}

@st.cache_data(ttl=6*60*60)
def logo_url_for(symbol: str) -> str | None:
    try:
        info = yf.Ticker(symbol).info
        if isinstance(info, dict):
            logo = info.get("logo_url")
            if logo:
                return logo
    except Exception:
        pass
    domain = SYMBOL_TO_DOMAIN.get(symbol)
    if domain:
        return f"https://logo.clearbit.com/{domain}"
    return None

# --- User Login & Persistent Balance ---
USER_DATA_FILE = os.path.join("data", "users.csv")

def load_user_data(name):
    if os.path.exists(USER_DATA_FILE):
        df = pd.read_csv(USER_DATA_FILE)
        user = df[df['name'] == name]
        if not user.empty:
            return float(user.iloc[0]['balance'])
    return None


def save_user_data(name, balance):
    if os.path.exists(USER_DATA_FILE):
        df = pd.read_csv(USER_DATA_FILE)
        if name in df['name'].values:
            df.loc[df['name'] == name, 'balance'] = balance
        else:
            df = pd.concat([df, pd.DataFrame([{'name': name, 'balance': balance}])], ignore_index=True)
    else:
        df = pd.DataFrame([{'name': name, 'balance': balance}])
    df.to_csv(USER_DATA_FILE, index=False)

if 'player_name' not in st.session_state:
    st.session_state['player_name'] = ""
if 'balance' not in st.session_state:
    st.session_state['balance'] = None
if "is_mobile" not in st.session_state:
    st.session_state["is_mobile"] = False

# Detect mobile via viewport width
components.html(
    """
    <script>
    const width = window.innerWidth;
    if (width < 768) {
        window.parent.postMessage({streamlitMessage: {is_mobile: true}}, "*");
    } else {
        window.parent.postMessage({streamlitMessage: {is_mobile: false}}, "*");
    }
    </script>
    """,
    height=0,
)

if not st.session_state['player_name']:
    st.title("Welcome to CryptoGame!")
    st.markdown("Please enter your name to start playing:")
    name = st.text_input("Your Name")
    if name:
        st.session_state['player_name'] = name
        user_balance = load_user_data(name)
        if user_balance is not None:
            st.session_state['balance'] = user_balance
        else:
            st.session_state['balance'] = 10000
            save_user_data(name, 10000)
            st.session_state['is_new_player'] =True 
        st.rerun()
    st.stop()

# === Full-page CSS tweaks ===
st.markdown(
    """
    <style>
    [data-testid="collapsedControl"] {
        display: block !important;
        visibility: visible !important;
        opacity: 1 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Notifications (stateless, session only) ---
if 'notifications' not in st.session_state:
    st.session_state['notifications'] = []

def add_notification(msg, type_="info"):
    st.session_state['notifications'].append({
        'type': type_,
        'msg': msg,
        'time': str(datetime.datetime.now())
    })

# --- Load Sidebar GUI from gui/ folder (optional) ---
#sidebar_css_path = os.path.join("gui", "sidebar.css")
#if os.path.exists(sidebar_css_path):
#    with open(sidebar_css_path, encoding="utf-8") as f:
#        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

available_stocks = [
    # US Tech
    "AAPL", "GOOGL", "AMZN", "MSFT", "TSLA", "NFLX", "META", "NVDA", "BRK-B", "V",
    # Indian IT & Banks
    "INFY.NS", "TCS.NS", "HDFCBANK.NS", "RELIANCE.NS", "ICICIBANK.NS",
    # More US Stocks
    "JPM", "BAC", "WMT", "DIS", "PEP", "KO", "MCD", "CSCO", "ORCL", "INTC", "ADBE", "CRM", "PYPL", "ABNB", "AMD", "QCOM", "SBUX", "COST", "PFE", "MRK",
    # More Indian Stocks
    "SBIN.NS", "KOTAKBANK.NS", "AXISBANK.NS", "LT.NS", "ITC.NS", "BAJFINANCE.NS", "SUNPHARMA.NS", "MARUTI.NS", "TITAN.NS", "ONGC.NS", "HCLTECH.NS", "ULTRACEMCO.NS", "ASIANPAINTS.NS"
]

with st.sidebar:
    # --- Header / Profile Section ---
    st.markdown(
    """
    <div style="text-align:center; font-size:28px; font-weight:bold;">
        📊 Dashboard
    </div>
    """,
    unsafe_allow_html=True,
)

    # Profile Picture (display only)
    if st.session_state.get("profile_pic"):
        st.markdown(
            f"""
            <div style="text-align:center;">
                <img src="data:image/png;base64,{base64.b64encode(st.session_state['profile_pic'].getvalue()).decode()}" 
                     style="width:120px; border-radius:50%;" />
                <p><b>{st.session_state['player_name']}</b></p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div style="text-align:center;">
                <img src="https://cdn-icons-png.flaticon.com/512/3135/3135715.png" 
                     style="width:120px;" />
                <p><b>{st.session_state['player_name']}</b></p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Balance centered
    st.markdown(
        f"""
        <div style="text-align:center; font-size:18px; font-weight:bold; margin-top:10px;">
            💰 ₹{st.session_state.get('balance', 0):,.2f}
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # --- Menu (buttons as before) ---
    
    sidebar_icons = [
        ("🏠", "Home"),
        ("📊", "Detailed Analysis"),
        ("🏆", "Achievements"),
        ("🛒", "Store"),
        ("📖", "Learn"),
    ]
    for icon, label in sidebar_icons:
        btn_key = f"sidebar_{label}"
        if st.button(f"{icon} {label}", key=btn_key):
            st.session_state['sidebar_nav'] = label

    if 'sidebar_nav' not in st.session_state:
        st.session_state['sidebar_nav'] = 'Home'
    menu = st.session_state['sidebar_nav']

    st.markdown("---")

    # --- Settings Section ---
    with st.expander("⚙️ Settings", expanded=False):
        # Change Username
        new_name = st.text_input("Change Username", value=st.session_state.get("player_name", ""))
        if st.button("Update Username"):
            if new_name.strip():
                old_name = st.session_state['player_name']
                st.session_state['player_name'] = new_name.strip()
                # Update CSV
                if os.path.exists("users.csv"):
                    users = pd.read_csv("users.csv")
                    if old_name in users['Name'].values:
                        users.loc[users['Name'] == old_name, 'Name'] = new_name.strip()
                        users.to_csv("users.csv", index=False)
                st.success(f"✅ Username updated to {new_name.strip()}")
                st.rerun()

        # Change Profile Picture (moved here)
        uploaded_pic = st.file_uploader("Upload Profile Picture", type=["png", "jpg", "jpeg"])
        if uploaded_pic:
            st.session_state["profile_pic"] = uploaded_pic
            st.rerun()
        if st.button("Remove Profile Picture"):
            st.session_state["profile_pic"] = None
            st.rerun()

        # Theme Selector
        theme = st.selectbox("🎨 Theme", ["Light", "Dark", "System Default"])

        # Sound Effects Toggle
        sound = st.checkbox("🔊 Enable Sound Effects", value=True)

    # --- Logout Button ---
    if st.button("🚪 Logout"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# --- Per-user portfolio and history paths ---

def get_portfolio_path():
    return os.path.join("data", f"Portfolio_{st.session_state['player_name']}.csv")


def get_portfolio_history_path():
    return os.path.join("data", f"portfolio_history_{st.session_state['player_name']}.csv")


# Preload cached prices once per page render (fast thereafter)
prices_df = load_price_cache(available_stocks, period="6mo")


if menu == "Home":
    st.title("Stock Game - Virtual Trader 📈")
    st.markdown(f"Welcome, {st.session_state['player_name']}! 👋")
    st.markdown("Trade stocks, track your portfolio and grow your virtual net worth")
    
    
    if st.session_state.get("is_new_player", False):
        with st.popover("Quick Tutorial"):
        
            st.markdown("### How to Play")
            st.write("Here’s a quick guide to get started:")
            st.markdown("""
            Welcome to CryptoGame! Here's a step-by-step guide to get you started:

            **Step 1: Enter Your Name**
            - On the welcome screen, enter your name to create your player profile.
            - Your cash balance and progress will be saved for future sessions.

            **Step 2: Explore Available Stocks**
            - Browse the list of stocks from US and Indian markets.
            - View current prices and company logos for each stock.
    
            **Step 3: Buy Stocks**
            - Select a stock and enter the quantity you want to buy.
            - Review the transaction fee and total cost.
            - Confirm your purchase. Your cash balance will be updated, and the stock will be added to your portfolio.
    
            **Step 4: View and Manage Your Portfolio**
            - See all your holdings, including quantity, buy price, current price, and profit/loss.
            - Track your portfolio value and performance.
    
            **Step 5: Sell Stocks**
            - Select a stock from your portfolio and enter the quantity to sell.
            - Confirm the sale. Your cash balance will increase, minus transaction fees.
    
            **Step 6: Earn Achievements**
            - Unlock achievements by trading, growing your portfolio, and reaching milestones.
            - View your achievements and total points in the Achievements section.
    
            **Step 7: Redeem Rewards in the Store**
            - Use your points to redeem cash, badges, boosts, analytics tools, and themes.
            - Activate boosts for special advantages (e.g., no transaction fees, double profit).

            **Step 8: Analyze Your Portfolio**
            - Use the Detailed Analysis section to view portfolio value over time, asset allocation, and risk metrics.
            - Set price alerts and simulate dividends or stock splits.
    
            **Step 9: Learn and Improve**
            - Read educational content to understand key concepts like diversification, volatility, and risk management.
            - Apply these strategies to grow your virtual wealth.
    
            **Step 10: Compete and Have Fun!**
            - Try to maximize your portfolio value and achievements.
            - Experiment with different strategies and boosts.
            - Enjoy learning about trading in a risk-free environment!
    
            Ready to play? Head to the Home section and start trading!_
            """)
    
    

    # --- Apply active theme (if any) ---
    active_rewards = store.get_active_rewards(st.session_state['player_name'])
    theme_id = active_rewards.get("theme")
    if theme_id == "theme_dark":
        st.markdown(
            """
            <style>
            body, .stApp { background-color: #181818 !important; color: #f0f0f0 !important; }
            </style>
            """,
            unsafe_allow_html=True,
        )
    elif theme_id == "theme_light":
        st.markdown(
            """
            <style>
            body, .stApp { background-color: #f8f8f8 !important; color: #222 !important; }
            </style>
            """,
            unsafe_allow_html=True,
        )

    # 💰 Display Current Balance (persistent per user)
    balance = st.session_state['balance']



    badge_id = active_rewards.get("badge")
    badge_name = None
    if badge_id:
        badge = next((r for r in store.get_rewards() if r["id"] == badge_id), None)
        if badge:
            badge_name = badge["name"]
            st.sidebar.markdown(f"🏅 **{badge_name}**")
    st.metric(label="💰 Available Cash", value=f"₹{balance:,.2f}")

    st.subheader("📃 Available Stocks")


    # --- Add responsive CSS ---
    st.markdown(
        """
        <style>
        @media (max-width: 768px) {
            .desktop-only {display: none;}
            .mobile-only {display: block;}
        }
        @media (min-width: 769px) {
            .desktop-only {display: block;}
            .mobile-only {display: none;}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    
    # --- Desktop layout ---
    st.markdown('<div class="desktop-only">', unsafe_allow_html=True)
    header_cols = st.columns([2, 1, 1])
    header_cols[0].write("**Stock**")
    header_cols[1].write("**Price (₹)**")
    header_cols[2].write("**Logo**")
    
    for symbol in available_stocks:
        price = latest_price_from_cache(symbol, prices_df)
        if price is None:
            try:
                price = getStockPrice(symbol)
            except Exception:
                price = None
        try:
            logo_url = logo_url_for(symbol)
        except Exception:
            logo_url = None
    
        row_cols = st.columns([2, 1, 1])
        row_cols[0].write(symbol)
        row_cols[1].write(f"₹{price:.2f}" if price is not None else "N/A")
        if logo_url:
            row_cols[2].image(logo_url, width=32)
        else:
            row_cols[2].write("")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # --- Mobile layout ---
    st.markdown('<div class="mobile-only">', unsafe_allow_html=True)
    for symbol in available_stocks:
        price = latest_price_from_cache(symbol, prices_df)
        if price is None:
            try:
                price = getStockPrice(symbol)
            except Exception:
                price = None
        try:
            logo_url = logo_url_for(symbol)
        except Exception:
            logo_url = None
    
        st.markdown(
            f"""
            <div style="border:1px solid #ddd; border-radius:10px; padding:10px; margin-bottom:10px;">
                <b>{symbol}</b><br>
                💰 Price: {f"₹{price:.2f}" if price is not None else "N/A"}<br>
                {"<img src='"+logo_url+"' width='40'>" if logo_url else ""}
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)
        
    st.subheader("📊 Stock Price Comparison")
    selected_stocks = st.multiselect(
        "Choose stocks to plot (log scale recommended for large price differences):",
        options=available_stocks,
        default=available_stocks[:5],
        key="chart_stock_select",        )
    if not selected_stocks:
        ui_msg("info", "Select at least one stock to display the chart.")
    else:
        # Use cached prices for speed; restrict to last 1 month
        from plotly import graph_objs as go
        if not prices_df.empty:
            last_month_idx = prices_df.index >= (prices_df.index.max() - pd.Timedelta(days=30))
            subdf = prices_df.loc[last_month_idx, [c for c in selected_stocks if c in prices_df.columns]].dropna(how="all")
            fig = go.Figure()
            for symbol in subdf.columns:
                fig.add_trace(go.Scatter(x=subdf.index, y=subdf[symbol], mode='lines', name=symbol))
            fig.update_layout(title="Stock Price Comparison (Log Scale)", xaxis_title="Date", yaxis_title="Price (₹)")
            fig.update_yaxes(type="log")
            st.plotly_chart(fig, use_container_width=True)
        else:
            ui_msg("warning", "Cached price data not available right now.")
    # ------- Buy Stocks Section -------
    st.markdown("### Buy Stocks")
    buy_symbol = st.selectbox("Select a stock to buy", available_stocks)
    buy_quantity = st.number_input("Quantity", min_value=1, step=1)

    TRANSACTION_FEE_RATE = 0.005
    boost_id = active_rewards.get("boost")
    if boost_id == "boost_no_fee" and store.is_boost_active(st.session_state['player_name'], "boost_no_fee"):
        TRANSACTION_FEE_RATE = 0.0

    price = None
    if buy_symbol:
        # Prefer cached latest price
        price = latest_price_from_cache(buy_symbol, prices_df)
        if price is not None:
            ui_msg("info", f"Current price of **{buy_symbol}** is ₹{price:.2f}")
        else:
            try:
                live_price = yf.Ticker(buy_symbol).info.get("regularMarketPrice", 0)
                price = float(live_price) if live_price else None
                if price:
                    ui_msg("info", f"Current price of **{buy_symbol}** is ₹{price:.2f}")
                else:
                    ui_msg("warning", "Symbol data not available right now.")
            except Exception:
                price = None
                ui_msg("warning", "Invalid stock symbol or data not available.")

        user_cash = balance
        st.markdown(f"Your current cash balance is: ₹{user_cash:,.2f}")
        if price:
            total_cost = price * buy_quantity
            fee = total_cost * TRANSACTION_FEE_RATE
            ui_msg("info", f"Transaction Fee: ₹{fee:.2f} ({'0%' if TRANSACTION_FEE_RATE == 0 else '0.5%'})")
            ui_msg("info", f"Total Cost (incl. fee): ₹{total_cost + fee:,.2f}")

        if st.button("Confirm purchase"):
            if price and (total_cost + fee) <= st.session_state['balance']:
                # Deduct cost and fee from balance
                st.session_state['balance'] -= (total_cost + fee)
                save_user_data(st.session_state['player_name'], st.session_state['balance'])

                # --- Update portfolio file ---
                portfolio_path = get_portfolio_path()
                try:
                    portfolio = pd.read_csv(portfolio_path)
                except Exception:
                    portfolio = pd.DataFrame(columns=["Symbol", "Quantity", "Buy Price", "Buy Date"])
                if buy_symbol in portfolio["Symbol"].values:
                    row = portfolio.loc[portfolio["Symbol"] == buy_symbol]
                    new_qty = row.Quantity.values[0] + buy_quantity
                    new_price = ((row.Quantity.values[0] * row["Buy Price"].values[0]) + (price * buy_quantity)) / new_qty
                    portfolio.loc[portfolio["Symbol"] == buy_symbol, ["Quantity", "Buy Price", "Buy Date"]] = [
                        new_qty, new_price, datetime.datetime.now().strftime("%Y-%m-%d")
                    ]
                else:
                    new_row = {
                        "Symbol": buy_symbol,
                        "Quantity": buy_quantity,
                        "Buy Price": price,
                        "Buy Date": datetime.datetime.now().strftime("%Y-%m-%d"),
                    }
                    portfolio = pd.concat([portfolio, pd.DataFrame([new_row])], ignore_index=True)
                portfolio.to_csv(portfolio_path, index=False)

                # --- Achievement: first_trade ---
                achievements.unlock_achievement(st.session_state['player_name'], "first_trade")
                st.toast("🎉 Achievement Unlocked: First Trade!")
                add_notification("🎉 Achievement Unlocked: First Trade!", "success")

                # --- NEW Achievement: Perfect Timing (buy at monthly low) ---
                try:
                    if buy_symbol in prices_df.columns:
                        month_df = prices_df[buy_symbol].dropna()
                        month_df = month_df[month_df.index >= (month_df.index.max() - pd.Timedelta(days=30))]
                        if not month_df.empty and abs(price - float(month_df.min())) <= max(0.01, 0.001 * price):
                            achievements.unlock_achievement(st.session_state['player_name'], "perfect_timing")
                            st.toast("🎯 Perfect Timing unlocked! Bought at monthly low.")
                except Exception:
                    pass

                # --- Log portfolio value ---
                pa.log_portfolio_value(portfolio, history_path=get_portfolio_history_path())

                ui_msg("success", f"Purchased {buy_quantity} shares of **{buy_symbol}** for ₹{total_cost + fee:,.2f}.")
                st.rerun()
            elif price:
                ui_msg("error", "Insufficient balance for this purchase.")
            else:
                ui_msg("error", "Invalid stock price.")

    # ------- Portfolio Section -------
    st.markdown("### Your Portfolio")
    try:
        portfolio = pd.read_csv(get_portfolio_path())
    except Exception:
        portfolio = pd.DataFrame()

    if not portfolio.empty:
        # Compute current prices using cache (fallback to yfinance if missing)
        current_prices: List[float] = []
        for _, row in portfolio.iterrows():
            symbol = row['Symbol']
            p = latest_price_from_cache(symbol, prices_df)
            if p is None:
                try:
                    p = float(yf.Ticker(symbol).info.get("regularMarketPrice", 0)) or None
                except Exception:
                    p = None
            current_prices.append(round(p, 2) if p is not None else 0.0)

        portfolio['Current Price'] = current_prices

        # --- Better Portfolio Metrics (NEW) ---
        portfolio['Total Invested'] = portfolio['Quantity'] * portfolio['Buy Price']
        portfolio['Current Value'] = portfolio['Quantity'] * portfolio['Current Price']
        portfolio['Unrealized P&L (₹)'] = portfolio['Current Value'] - portfolio['Total Invested']
        portfolio['Unrealized P&L (%)'] = portfolio.apply(
            lambda r: (r['Unrealized P&L (₹)'] / r['Total Invested']) * 100 if r['Total Invested'] > 0 else 0.0,
            axis=1,
        )

        # Simple color hint with emoji in a separate column for vibes
        portfolio['📈/📉'] = portfolio['Unrealized P&L (₹)'].apply(lambda x: '📈' if x >= 0 else '📉')

        st.dataframe(portfolio, use_container_width=True)

        # Check portfolio value achievements
        portfolio_value = pa.calculate_portfolio_value(portfolio)
        if portfolio_value >= 50000:
            achievements.unlock_achievement(st.session_state['player_name'], "portfolio_50k")
        if portfolio_value >= 100000:
            achievements.unlock_achievement(st.session_state['player_name'], "portfolio_1lakh")
        if portfolio_value >= 500000:
            achievements.unlock_achievement(st.session_state['player_name'], "portfolio_5lakh")

        # --- NEW Achievement: Moonshot (100% gain on a single holding)
        try:
            if (portfolio['Unrealized P&L (%)'] >= 100).any():
                achievements.unlock_achievement(st.session_state['player_name'], "moonshot")
                st.toast("🚀 Moonshot unlocked! 100% gain on a stock.")
        except Exception:
            pass

        # --- NEW Achievement: Bear Slayer (profit during basket 5% drop over 7 days)
        try:
            if not prices_df.empty:
                # basket avg return last 7 days
                last = prices_df.iloc[-1]
                first_idx = prices_df.index.max() - pd.Timedelta(days=7)
                prev = prices_df[prices_df.index >= first_idx].iloc[0]
                # Align columns
                common = [c for c in last.index if c in prev.index]
                if common:
                    basket_return = (last[common].mean() - prev[common].mean()) / max(prev[common].mean(), 1e-9)
                    if basket_return < -0.05 and portfolio['Unrealized P&L (₹)'].sum() > 0:
                        achievements.unlock_achievement(st.session_state['player_name'], "bear_slayer")
                        st.toast("🐻 Bear Slayer unlocked! Profit during a 5% market drop.")
        except Exception:
            pass

    else:
        ui_msg("info", "No holdings yet. Start your journey from the **Buy Stocks** section above!")

    # --------- 💸 Sell Section ---------------
    st.subheader("💸 Sell Stocks")
    sell_symbol = st.selectbox("Select a stock to sell", portfolio["Symbol"].unique() if not portfolio.empty else [])
    sell_qty = st.number_input("Quantity to sell", min_value=1, step=1)
    if st.button("Sell") and not portfolio.empty:
        success, message = sell_stock(sell_symbol, sell_qty)
        if success:
            try:
                sell_price = latest_price_from_cache(sell_symbol, prices_df)
                if sell_price is None:
                    sell_price = float(yf.Ticker(sell_symbol).info.get("regularMarketPrice", 0))
                sell_total = sell_price * sell_qty
                sell_fee = sell_total * TRANSACTION_FEE_RATE
                boost_id = store.get_active_rewards(st.session_state['player_name']).get("boost")
                if boost_id == "boost_double_profit" and store.is_boost_active(st.session_state['player_name'], "boost_double_profit"):
                    buy_price = 0
                    try:
                        buy_price = float(portfolio.loc[portfolio["Symbol"] == sell_symbol, "Buy Price"].values[0])
                    except Exception:
                        pass
                    profit = (sell_price - buy_price) * sell_qty
                    if profit > 0:
                        update_cash_balance(profit)
                        st.session_state['balance'] += profit
                        save_user_data(st.session_state['player_name'], st.session_state['balance'])
                        ui_msg("success", f"⚡ Double Profit Day! Extra ₹{profit:.2f} credited.")
                from game_logic import update_cash_balance as _update_cash_balance
                _update_cash_balance(-sell_fee)
                st.session_state['balance'] -= sell_fee
                save_user_data(st.session_state['player_name'], st.session_state['balance'])
                ui_msg("info", f"Transaction Fee: ₹{sell_fee:.2f} ({'0%' if TRANSACTION_FEE_RATE == 0 else '0.5%'}) deducted from cash balance.")
            except Exception:
                pass
            ui_msg("success", str(message))
            achievements.unlock_achievement(st.session_state['player_name'], "first_trade")
            st.toast("🎉 Achievement Unlocked: First Trade!")
            add_notification("🎉 Achievement Unlocked: First Trade!", "success")
            st.rerun()
        else:
            ui_msg("error", str(message))

    # Log today's portfolio value (once per day)
    try:
        df = pd.read_csv(get_portfolio_path())
        pa.log_portfolio_value(df, history_path=get_portfolio_history_path())
    except Exception:
        pass

elif menu == "Achievements":
    st.markdown("## 🏆 Achievements")
    unlocked_ids = [a['id'] for a in achievements.get_unlocked_achievements(st.session_state['player_name'])]
    for ach in achievements.ACHIEVEMENTS:
        is_unlocked = ach['id'] in unlocked_ids
        icon = "✅" if is_unlocked else "🔒"
        with st.expander(f"{icon} {ach['name']} [{ach['difficulty']}] [+{ach['points']} pts]", expanded=False):
            st.write(ach['desc'])
            if is_unlocked:
                st.success("Unlocked!")
            else:
                st.info("Locked")
    st.info(f"Total Points: {achievements.get_points(st.session_state['player_name'])}")

elif menu == "Store":
    st.markdown("## 🛒 Store")
    st.write("Redeem your points for cash, badges, boosts, and analytics tools!")
    rewards = store.get_rewards()
    owned = store.get_owned_rewards(st.session_state['player_name'])
    active = store.get_active_rewards(st.session_state['player_name'])
    ICONS = {
        "cash": "💰",
        "badge": "🏅",
        "boost": "⚡",
        "analytics": "📊",
        "theme": "🎨",
    }
    for reward in rewards:
        icon = ICONS.get(reward.get("type", "cash"), "🎁")
        owned_str = "✅ Owned" if reward["id"] in owned else ""
        active_str = "🌟 Active" if active.get(reward["type"]) == reward["id"] else ""
        st.markdown(f"### {icon} {reward['name']} [{reward['difficulty']}] - Cost: {reward['cost']} pts {owned_str} {active_str}")
        st.caption(reward['desc'])
        col1, col2 = st.columns([2, 1])
        with col1:
            if reward["id"] in owned:
                if reward["type"] in ["badge", "theme", "boost", "analytics"]:
                    if active.get(reward["type"]) == reward["id"]:
                        st.button("Activated", key=f"active_{reward['id']}", disabled=True)
                    else:
                        if st.button(f"Activate: {reward['name']}", key=f"activate_{reward['id']}"):
                            ok, msg = store.activate_reward(st.session_state['player_name'], reward['id'])
                            if ok:
                                st.success(msg)
                            else:
                                st.error(msg)
                else:
                    st.button(f"Redeemed", key=f"owned_{reward['id']}", disabled=True)
            else:
                if st.button(f"Redeem: {reward['name']}", key=reward['id']):
                    success, msg = store.redeem_reward(
                        st.session_state['player_name'], reward['id'], update_cash_balance, lambda: st.session_state['balance']
                    )
                    if success:
                        st.success(msg)
                        save_user_data(st.session_state['player_name'], st.session_state['balance'])
                    else:
                        st.error(msg)
        # For boosts, add a "Use" button if active
        if reward["type"] == "boost" and reward["id"] in owned and active.get("boost") == reward["id"]:
            with col2:
                if st.button(f"Use {reward['name']}", key=f"use_{reward['id']}"):
                    ok, msg = store.use_boost(st.session_state['player_name'], reward['id'])
                    if ok:
                        st.success("Boost used! Effect will apply to your next eligible action.")
                    else:
                        st.error(msg)

    # Show owned rewards section
    if owned:
        st.markdown("---")
        st.markdown("### 🎖️ Your Rewards")
        for reward_id in owned:
            reward = next((r for r in rewards if r["id"] == reward_id), None)
            if reward:
                icon = ICONS.get(reward.get("type", "cash"), "🎁")
                is_active = active.get(reward.get("type")) == reward_id
                st.markdown(f"{icon} **{reward['name']}**: {reward['desc']} {'🌟 Active' if is_active else ''}")

elif menu == "Detailed Analysis":
    st.markdown("## 📊 Portfolio Analytics")
    col1, col2 = st.columns(2)

    # --- Portfolio Value Chart ---
    with col1:
        st.markdown("### 📈 Portfolio Value Over Time")
        try:
            fig = pa.plot_portfolio_value_over_time(history_path=get_portfolio_history_path())
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                ui_msg("info", "Not enough data yet.")
        except Exception as e:
            ui_msg("warning", f"Unable to plot portfolio history: {e}")

    # --- Asset Allocation Pie ---
    with col2:
        st.markdown("### 🧩 Asset Diversification")
        try:
            df = pd.read_csv(get_portfolio_path())
            pie = pa.plot_asset_allocation(df)
            if pie:
                st.plotly_chart(pie, use_container_width=True)
            else:
                ui_msg("info", "Portfolio is empty.")
        except FileNotFoundError:
            df = pd.DataFrame()
            ui_msg("info", "Portfolio not found yet.")

    # --- Stock Analysis ---
    st.markdown("### 🔍 Select a Stock for Detailed Analysis")
    selected_symbol = st.selectbox(
        "Choose from your holdings",
        options=df["Symbol"].unique() if not df.empty else [],
        index=0 if not df.empty else None,
    )
    if selected_symbol:
        st.markdown(f"### 📉 Price Chart: {selected_symbol}")
        chart = plot_with_indicators(selected_symbol)
        if chart:
            st.plotly_chart(chart, use_container_width=True)
        else:
            ui_msg("warning", "No data available for this stock.")

        # --- Risk Metrics ---
        st.markdown(f"### ⚖️ Risk Metrics for {selected_symbol}")
        try:
            metrics = pa.calculate_risk_metrics_filtered(df, selected_symbol)
            if metrics:
                st.metric("📊 Volatility", metrics.get("Volatility", "N/A"))
                st.metric("⚖️ Sharpe Ratio", metrics.get("Sharpe Ratio", "N/A"))
            else:
                ui_msg("info", "Risk metrics unavailable.")
        except Exception as e:
            ui_msg("warning", f"Risk metric calculation failed: {e}")

        # --- Price Alerts ---
        st.markdown("### 🔔 Set Price Alert")
        alert_symbol = st.selectbox(
            "Select stock for alert",
            options=available_stocks,
            key="detailed_alert_symbol",
        )
        alert_direction = st.radio("Alert me when price...", ["goes above", "falls below"], key="alert_direction")
        alert_price = st.number_input("Alert price (INR)", min_value=1.0, step=1.0, key="detailed_alert_price")

        if st.button("Set Alert", key="detailed_set_alert"):
            st.session_state['price_alert'] = {
                "symbol": alert_symbol,
                "direction": alert_direction,
                "price": alert_price,
            }
            ui_msg("success", f"Alert set for **{alert_symbol}** when price {alert_direction} ₹{alert_price:.2f}")

        # Check for trigger
        if 'price_alert' in st.session_state:
            alert = st.session_state['price_alert']
            try:
                current = latest_price_from_cache(alert['symbol'], prices_df)
                if current is None:
                    current = float(yf.Ticker(alert['symbol']).info.get("regularMarketPrice", 0))
                if (
                    (alert['direction'] == 'goes above' and current >= alert['price']) or
                    (alert['direction'] == 'falls below' and current <= alert['price'])
                ):
                    st.toast(f"🔔 {alert['symbol']} hit your alert: {alert['direction']} ₹{alert['price']:.2f}!")
                    del st.session_state['price_alert']
            except Exception:
                pass

        # --- Dividends & Splits ---
        st.markdown("### 💸 Dividends & Splits")
        dividend_state_path = os.path.join("data", "dividend_state.json")
        today = datetime.date.today()
        if os.path.exists(dividend_state_path):
            try:
                with open(dividend_state_path, "r") as f:
                    content = f.read().strip()
                    dividend_state = json.loads(content) if content else {}
            except (json.JSONDecodeError, FileNotFoundError):
                dividend_state = {}
        else:
            dividend_state = {}
        last_div_month = dividend_state.get("last_month")

        if st.button("Collect Dividends", key="detailed_collect_dividends"):
            if last_div_month == f"{today.year}-{today.month:02d}":
                ui_msg("info", "You have already collected dividends this month.")
            else:
                try:
                    portfolio_df = pd.read_csv(get_portfolio_path())
                    total_dividend = 0
                    for _, row in portfolio_df.iterrows():
                        shares = row['Quantity']
                        ticker = yf.Ticker(row['Symbol'])
                        dividends = getattr(ticker, "dividends", pd.Series())
                        if not dividends.empty:
                            month_divs = dividends[dividends.index.to_period('M') == pd.Period(today, 'M')]
                            if not month_divs.empty:
                                last_div = month_divs.iloc[-1]
                                total_dividend += float(last_div) * float(shares)
                    if total_dividend > 0:
                        st.session_state['balance'] += total_dividend
                        save_user_data(st.session_state['player_name'], st.session_state['balance'])
                        update_cash_balance(total_dividend)
                        st.toast(f"💸 Dividend payout: ₹{total_dividend:,.2f} credited!")
                        dividend_state["last_month"] = f"{today.year}-{today.month:02d}"
                        with open(dividend_state_path, "w") as f:
                            json.dump(dividend_state, f)
                    else:
                        ui_msg("info", "No dividends available this month.")
                except Exception as e:
                    ui_msg("warning", f"Dividend collection failed: {e}")

        if st.button("Simulate 2-for-1 Stock Split", key="detailed_split"):
            try:
                portfolio_df = pd.read_csv(get_portfolio_path())
                portfolio_df['Quantity'] *= 2
                portfolio_df['Buy Price'] /= 2
                portfolio_df.to_csv(get_portfolio_path(), index=False)
                st.toast("🔀 2-for-1 Stock Split applied to all holdings!")
            except Exception as e:
                ui_msg("warning", f"Stock split simulation failed: {e}")


# --- Educational Content Section ---
if menu == "Learn":
    st.title("📚 Learn & Level Up!")
    st.markdown("Sharpen your trading skills as you play. Expand the sections below to learn more about key concepts!")
    with st.expander("🧑‍🏫 Tutorial: How to Play CryptoGame", expanded=True):
        st.markdown("""
        Welcome to CryptoGame! Here's a step-by-step guide to get you started:

        **Step 1: Enter Your Name**
        - On the welcome screen, enter your name to create your player profile.
        - Your cash balance and progress will be saved for future sessions.

        **Step 2: Explore Available Stocks**
        - Browse the list of stocks from US and Indian markets.
        - View current prices and company logos for each stock.

        **Step 3: Buy Stocks**
        - Select a stock and enter the quantity you want to buy.
        - Review the transaction fee and total cost.
        - Confirm your purchase. Your cash balance will be updated, and the stock will be added to your portfolio.

        **Step 4: View and Manage Your Portfolio**
        - See all your holdings, including quantity, buy price, current price, and profit/loss.
        - Track your portfolio value and performance.

        **Step 5: Sell Stocks**
        - Select a stock from your portfolio and enter the quantity to sell.
        - Confirm the sale. Your cash balance will increase, minus transaction fees.

        **Step 6: Earn Achievements**
        - Unlock achievements by trading, growing your portfolio, and reaching milestones.
        - View your achievements and total points in the Achievements section.

        **Step 7: Redeem Rewards in the Store**
        - Use your points to redeem cash, badges, boosts, analytics tools, and themes.
        - Activate boosts for special advantages (e.g., no transaction fees, double profit).

        **Step 8: Analyze Your Portfolio**
        - Use the Detailed Analysis section to view portfolio value over time, asset allocation, and risk metrics.
        - Set price alerts and simulate dividends or stock splits.

        **Step 9: Learn and Improve**
        - Read educational content to understand key concepts like diversification, volatility, and risk management.
        - Apply these strategies to grow your virtual wealth.

        **Step 10: Compete and Have Fun!**
        - Try to maximize your portfolio value and achievements.
        - Experiment with different strategies and boosts.
        - Enjoy learning about trading in a risk-free environment!

        _Ready to play? Head to the Home section and start trading!_
        """)
    with st.expander("What is a Portfolio?"):
        st.write(
            """
        A portfolio is a collection of financial investments like stocks, bonds, commodities, cash, and cash equivalents, including mutual funds and ETFs. In this game, your portfolio consists of the stocks you buy and sell.
        """
        )
    with st.expander("How do Dividends Work?"):
        st.write(
            """
        Dividends are payments made by a corporation to its shareholders, usually as a distribution of profits. If you own a stock when a dividend is paid, you receive a payout per share.
        """
        )
    with st.expander("What is a Stock Split?"):
        st.write(
            """
        A stock split increases the number of shares in a company. For example, in a 2-for-1 split, you get 2 shares for every 1 you own, but each is worth half as much. Your total value stays the same.
        """
        )
    with st.expander("What is Volatility?"):
        st.write(
            """
        Volatility is a statistical measure of the dispersion of returns for a given security or market index. High volatility means the price of the asset can change dramatically in either direction.
        """
        )
    with st.expander("What is the Sharpe Ratio?"):
        st.write(
            """
        The Sharpe Ratio measures the performance of an investment compared to a risk-free asset, after adjusting for its risk. The higher the Sharpe Ratio, the better the risk-adjusted return.
        """
        )
    with st.expander("What is Diversification?"):
        st.write(
            """
        Diversification is the practice of spreading your investments across different assets, sectors, or geographies to reduce risk. A diversified portfolio is less likely to experience large losses because different assets often perform differently under the same conditions.
        """
        )
    with st.expander("What are Transaction Fees?"):
        st.write(
            """
        Transaction fees are small costs charged when you buy or sell stocks. In this game, a 0.5% fee is applied to each trade (unless you have a No Fee Day boost!). Always consider fees when planning your trades.
        """
        )
    with st.expander("What are Boosts and Rewards?"):
        st.write(
            """
        Boosts and rewards are special items you can earn or redeem in the Store. Some boosts give you advantages like no transaction fees or double profits for a day. Badges and themes let you customize your profile and experience.
        """
        )
    with st.expander("What is a Leaderboard?"):
        st.write(
            """
        A leaderboard ranks players based on their portfolio value, points, or achievements. Competing on the leaderboard can motivate you to improve your trading skills and try new strategies.
        """
        )
    with st.expander("What is Risk Management?"):
        st.write(
            """
        Risk management means using strategies to minimize potential losses. This includes setting stop-losses, diversifying, and not investing all your cash in one stock. Good risk management helps you stay in the game longer and avoid big setbacks.
        """
        )
    with st.expander("Tips for Virtual Trading Success"):
        st.write(
            """
        - Diversify your portfolio
        - Monitor your holdings regularly
        - Set price alerts for your favorite stocks
        - Learn from your trades and keep improving!
        - Use boosts and rewards wisely
        - Don’t let emotions drive your trades—stick to your strategy
        - Review your performance and learn from mistakes
        - Stay updated on market news and trends
        """
        )




st.markdown("---")
st.caption("Built with ❤️ by Ritvik's Trading Engine")
