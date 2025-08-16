# --- CryptoGame Main App ---
from data_fetcher import getStockPrice
import streamlit as st
import pandas as pd
import yfinance as yf
import os
import portfolio_analyzer as pa
from game_logic import get_cash_balance, sell_stock, plot_with_indicators, update_cash_balance
import datetime
import achievements as achievements
import store as store
import json

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
        st.rerun()
    st.stop()

st.set_page_config(page_title="Stock Portfolio Game", layout="wide")

# --- Notifications (stateless, session only) ---
if 'notifications' not in st.session_state:
    st.session_state['notifications'] = []

def add_notification(msg, type_="info"):
    st.session_state['notifications'].append({
        'type': type_,
        'msg': msg,
        'time': str(datetime.datetime.now())
    })

# --- Load Sidebar GUI from gui/ folder ---
with open(os.path.join("gui", "sidebar.css"), encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

available_stocks = [
    # US Tech
    "AAPL", "GOOGL", "AMZN", "MSFT", "TSLA", "NFLX", "META", "NVDA", "BRK-B", "V",
    # Indian IT & Banks
    "INFY.NS", "TCS.NS", "HDFCBANK.NS", "RELIANCE.NS", "ICICIBANK.NS",
    # More US Stocks
    "JPM", "BAC", "WMT", "DIS", "PEP", "KO", "MCD", "CSCO", "ORCL", "INTC", "ADBE", "CRM", "PYPL", "ABNB", "AMD", "QCOM", "SBUX", "COST", "PFE", "MRK",
    # More Indian Stocks
    "SBIN.NS", "KOTAKBANK.NS", "AXISBANK.NS", "LT.NS", "ITC.NS", "BAJFINANCE.NS", "SUNPHARMA.NS", "MARUTI.NS", "TITAN.NS", "ONGC.NS", "HCLTECH.NS", "ULTRACEMCO.NS", "ASIANPAINT.NS"
]

sidebar_icons = [
    ("🏠", "Home"),
    ("🏆", "Achievements"),
    ("🛒", "Store"),
    ("📖", "Learn"),
    ("📊", "Detailed Analysis")
]

with st.sidebar:
    st.markdown('<div class="sidebar-title">✨ CryptoGame Menu</div>', unsafe_allow_html=True)
    for icon, label in sidebar_icons:
        btn_key = f"sidebar_{label}"
        if st.button(f"{icon} {label}", key=btn_key):
            st.session_state['sidebar_nav'] = label

if 'sidebar_nav' not in st.session_state:
    st.session_state['sidebar_nav'] = 'Home'
menu = st.session_state['sidebar_nav']


# --- Per-user portfolio and history paths ---
def get_portfolio_path():
    return os.path.join("data", f"Portfolio_{st.session_state['player_name']}.csv")

def get_portfolio_history_path():
    return os.path.join("data", f"portfolio_history_{st.session_state['player_name']}.csv")


if menu == "Home":
    st.title("Stock Game - Virtual Trader 📈")
    st.markdown(f"Welcome, **{st.session_state['player_name']}**! 👋")
    st.markdown("Trade stocks, track your portfolio and grow your virtual net worth")

    # --- Apply active theme (if any) ---
    active_rewards = store.get_active_rewards(st.session_state['player_name'])
    theme_id = active_rewards.get("theme")
    if theme_id == "theme_dark":
        st.markdown("""
            <style>
            body, .stApp { background-color: #181818 !important; color: #f0f0f0 !important; }
            </style>
        """, unsafe_allow_html=True)
    elif theme_id == "theme_light":
        st.markdown("""
            <style>
            body, .stApp { background-color: #f8f8f8 !important; color: #222 !important; }
            </style>
        """, unsafe_allow_html=True)

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

    #-------Market Watch Section-------
    # Create two columns
    left_col, right_col = st.columns([1, 1])  # Ratio 1:2 for more space for the graph
    stock_data = []
    livePrice = {}

    @st.cache_data(ttl=300)
    def get_all_prices(symbols):
        prices = {}
        for symbol in symbols:
            price = getStockPrice(symbol)
            if price is not None:
                prices[symbol] = price
        return prices

    with left_col:
        st.subheader("📃 Available Stocks")
        cols = st.columns([2, 1])  # Table header
        cols[0].write("**Stock**")
        cols[1].write("**Price (INR)**")

        cached_prices = get_all_prices(available_stocks)
        for symbol in available_stocks:
            price = cached_prices.get(symbol)
            if price is not None:
                try:
                    livePrice[symbol] = price
                    cols = st.columns([2, 1])
                    cols[0].write(symbol)
                    cols[1].write(f"₹{price:.2f}")
                except:
                    continue
            else:
                st.warning(f"Could not fetch price for {symbol}")

    with right_col:
        st.subheader("📊 Stock Price Comparison")
        # --- Stock selection for chart ---

        # --- Stock selection for chart ---
        selected_stocks = st.multiselect(
            "Choose stocks to plot (log scale recommended for large price differences):",
            options=available_stocks,
            default=available_stocks[:5],
            key="chart_stock_select"
        )
        if not selected_stocks:
            st.info("Select at least one stock to display the chart.")
        else:
            # --- Plot single chart with log scale ---
            from plotly import graph_objs as go
            fig = go.Figure()
            for symbol in selected_stocks:
                try:
                    data = yf.Ticker(symbol).history(period="1mo")
                    fig.add_trace(go.Scatter(x=data.index, y=data['Close'], mode='lines', name=symbol))
                except Exception:
                    continue
            fig.update_layout(title="Stock Price Comparison (Log Scale)", xaxis_title="Date", yaxis_title="Price (INR)")
            fig.update_yaxes(type="log")
            st.plotly_chart(fig, use_container_width=True)

        #-------Buy Stocks Section-------
        st.markdown("### Buy Stocks")

        buy_symbol = st.selectbox("Select a stock to buy", available_stocks)
        buy_quantity = st.number_input("Quantity", min_value=1, step=1)

        TRANSACTION_FEE_RATE = 0.005
        boost_id = active_rewards.get("boost")
        if boost_id == "boost_no_fee" and store.is_boost_active(st.session_state['player_name'], "boost_no_fee"):
            TRANSACTION_FEE_RATE = 0.0

        if buy_symbol:
            try:
                price = yf.Ticker(buy_symbol).info.get("regularMarketPrice", 0)
                st.info(f"Current price of {buy_symbol} is ₹{price:.2f}")
            except:
                price = None
                st.warning("Invalid stock symbol or data not available.")

            user_cash = balance
            st.markdown(f"Your current cash balance is: ₹{user_cash:,.2f}")
            if price:
                total_cost = price * buy_quantity
                fee = total_cost * TRANSACTION_FEE_RATE
                st.info(f"Transaction Fee: ₹{fee:.2f} ({'0%' if TRANSACTION_FEE_RATE == 0 else '0.5%'})")
                st.info(f"Total Cost (incl. fee): ₹{total_cost + fee:,.2f}")

            if st.button("Confirm purchase"):
                if price and (total_cost + fee) <= st.session_state['balance']:
                    # Deduct cost and fee from balance
                    st.session_state['balance'] -= (total_cost + fee)
                    save_user_data(st.session_state['player_name'], st.session_state['balance'])
                    # Optionally update portfolio here
                    st.success(f"Purchased {buy_quantity} shares of {buy_symbol} for ₹{total_cost + fee:,.2f}.")
                elif price:
                    st.error("Insufficient balance for this purchase.")
                else:
                    st.error("Invalid stock price.")

    #-------Portfolio Section-------
    st.markdown("### Your Portfolio")
    portfolio = pd.DataFrame()
    try:
        portfolio = pd.read_csv(get_portfolio_path())
    except:
        pass
    if not portfolio.empty:
        currentPrices = []
        profitPercents = []
        for index, row in portfolio.iterrows():
            symbol = row['Symbol']
            try:
                livePrice = yf.Ticker(symbol).info.get("regularMarketPrice", 0)
            except:
                livePrice = 0
            currentPrices.append(round(livePrice, 2))
            profit = ((livePrice - row['Buy Price']) / row['Buy Price']) * 100
            profitPercents.append(round(profit, 2))
        portfolio['Current Price'] = currentPrices
        portfolio['Profit (%)'] = profitPercents
        st.dataframe(portfolio, use_container_width=True)
        # Check portfolio value achievements
        portfolio_value = pa.calculate_portfolio_value(portfolio)
        # Achievements per user
        if portfolio_value >= 50000:
            achievements.unlock_achievement(st.session_state['player_name'], "portfolio_50k")
        if portfolio_value >= 100000:
            achievements.unlock_achievement(st.session_state['player_name'], "portfolio_1lakh")
        if portfolio_value >= 500000:
            achievements.unlock_achievement(st.session_state['player_name'], "portfolio_5lakh")
    else:
        st.info("No holdings yet")

    # ---------💸 Sell Section---------------
    st.subheader("💸 Sell Stocks")
    sell_symbol = st.selectbox("Select a stock to sell", portfolio["Symbol"].unique() if not portfolio.empty else [])
    sell_qty = st.number_input("Quantity to sell", min_value=1, step=1)
    if st.button("Sell") and not portfolio.empty:
        success, message = sell_stock(sell_symbol, sell_qty)
        if success:
            try:
                sell_price = yf.Ticker(sell_symbol).info.get("regularMarketPrice", 0)
                sell_total = sell_price * sell_qty
                sell_fee = sell_total * TRANSACTION_FEE_RATE
                boost_id = store.get_active_rewards(st.session_state['player_name']).get("boost")
                double_profit = False
                if boost_id == "boost_double_profit" and store.is_boost_active(st.session_state['player_name'], "boost_double_profit"):
                    buy_price = 0
                    try:
                        buy_price = float(portfolio.loc[portfolio["Symbol"] == sell_symbol, "Buy Price"].values[0])
                    except:
                        pass
                    profit = (sell_price - buy_price) * sell_qty
                    if profit > 0:
                        update_cash_balance(profit)
                        st.session_state['balance'] += profit
                        save_user_data(st.session_state['player_name'], st.session_state['balance'])
                        st.success(f"⚡ Double Profit Day! Extra ₹{profit:.2f} credited.")
                        double_profit = True
                from game_logic import update_cash_balance
                update_cash_balance(-sell_fee)
                st.session_state['balance'] -= sell_fee
                save_user_data(st.session_state['player_name'], st.session_state['balance'])
                st.info(f"Transaction Fee: ₹{sell_fee:.2f} ({'0%' if TRANSACTION_FEE_RATE == 0 else '0.5%'}) deducted from cash balance.")
            except:
                pass
            st.success(str(message))
            achievements.unlock_achievement(st.session_state['player_name'], "first_trade")
            st.toast("🎉 Achievement Unlocked: First Trade!")
            add_notification("🎉 Achievement Unlocked: First Trade!", "success")
        else:
            st.error(str(message))

    # If you update portfolio after sell, save to get_portfolio_path()
    # Example: portfolio.to_csv(get_portfolio_path(), index=False)

    # Log today's portfolio value (once per day)
    try:
        df = pd.read_csv(get_portfolio_path())
        pa.log_portfolio_value(df, history_path=get_portfolio_history_path())
    except:
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
        "theme": "🎨"
    }
    for reward in rewards:
        icon = ICONS.get(reward.get("type", "cash"), "🎁")
        owned_str = "✅ Owned" if reward["id"] in owned else ""
        active_str = "🌟 Active" if active.get(reward["type"]) == reward["id"] else ""
        st.markdown(f"### {icon} {reward['name']} [{reward['difficulty']}] - Cost: {reward['cost']} pts {owned_str} {active_str}")
        st.caption(reward['desc'])
        col1, col2 = st.columns([2,1])
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
                        st.session_state['player_name'],
                        reward['id'],
                        update_cash_balance,
                        lambda: balance
                    )
                    if success:
                        st.success(msg)
                        st.session_state['balance'] = st.session_state['balance']  # update as needed
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
    with col1:
        st.markdown("### 📈 Portfolio Value Over Time")
        fig = pa.plot_portfolio_value_over_time(history_path=get_portfolio_history_path())
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Not enough data yet.")
    with col2:
        st.markdown("### 🧩 Asset Diversification")
        df = pd.read_csv(get_portfolio_path())
        pie = pa.plot_asset_allocation(df)
        if pie:
            st.plotly_chart(pie, use_container_width=True)
        else:
            st.info("Portfolio is empty.")
    st.markdown("### 🔍 Select a Stock for Detailed Analysis")
    selected_symbol = st.selectbox(
        "Choose from your holdings",
        options=df["Symbol"].unique() if not df.empty else [],
        index=0 if not df.empty else None
    )
    if selected_symbol:
        st.markdown(f"### 📉 Price Chart: {selected_symbol}")
        chart = plot_with_indicators(selected_symbol)
        if chart:
            st.plotly_chart(chart, use_container_width=True)
        else:
            st.warning("No data available for this stock.")
        st.markdown(f"### ⚖️ Risk Metrics for {selected_symbol}")
        metrics = pa.calculate_risk_metrics_filtered(df, selected_symbol)
        st.metric("📊 Volatility", metrics["Volatility"])
        st.metric("⚖️ Sharpe Ratio", metrics["Sharpe Ratio"])

        # --- Price Alert Section (with stock selection) ---
        st.markdown("### 🔔 Set Price Alert")
        alert_symbol = st.selectbox(
            "Select stock for alert",
            options=available_stocks,
            key="detailed_alert_symbol"
        )
        alert_direction = st.radio("Alert me when price...", ["goes above", "falls below"], key="alert_direction")
        alert_price = st.number_input("Alert price (INR)", min_value=1.0, step=1.0, key="detailed_alert_price")
        if st.button("Set Alert", key="detailed_set_alert"):
            st.success(f"Alert set for {alert_symbol} when price {alert_direction} ₹{alert_price:.2f}")

        # Check for price alert trigger
        if 'price_alert' in st.session_state:
            alert = st.session_state['price_alert']
            try:
                current = yf.Ticker(alert['symbol']).info.get("regularMarketPrice", 0)
                if (
                    (alert['direction'] == 'goes above' and current >= alert['price']) or
                    (alert['direction'] == 'falls below' and current <= alert['price'])
                ):
                    st.toast(f"🔔 {alert['symbol']} hit your alert: {alert['direction']} ₹{alert['price']:.2f}!")
                    del st.session_state['price_alert']
            except Exception:
                pass

        # --- Dividend & Split Section (moved here) ---
        st.markdown("### 💸 Dividends & Splits")
        import datetime, json
        dividend_state_path = os.path.join("data", "dividend_state.json")
        today = datetime.date.today()
        if os.path.exists(dividend_state_path):
            with open(dividend_state_path, "r") as f:
                dividend_state = json.load(f)
        else:
            dividend_state = {}
        last_div_month = dividend_state.get("last_month")
        if st.button("Collect Dividends", key="detailed_collect_dividends"):
            if last_div_month == f"{today.year}-{today.month:02d}":
                st.info("You have already collected dividends for this month.")
            else:
                try:
                    portfolio = pd.read_csv(get_portfolio_path())
                    total_dividend = 0
                    for idx, row in portfolio.iterrows():
                        shares = row['Quantity']
                        ticker = yf.Ticker(row['Symbol'])
                        dividends = ticker.dividends
                        if not dividends.empty:
                            month_divs = dividends[dividends.index.to_period('M') == pd.Period(today, 'M')]
                            if not month_divs.empty:
                                last_div = month_divs.iloc[-1]
                                dividend = last_div * shares
                                total_dividend += dividend
                    if total_dividend > 0:
                        from game_logic import update_cash_balance, get_cash_balance
                        st.session_state['balance'] += total_dividend
                        save_user_data(st.session_state['player_name'], st.session_state['balance'])
                        update_cash_balance(total_dividend)
                        st.toast(f"💸 Dividend payout: ₹{total_dividend:,.2f} credited!")
                        dividend_state["last_month"] = f"{today.year}-{today.month:02d}"
                        with open(dividend_state_path, "w") as f:
                            json.dump(dividend_state, f)
                    else:
                        st.info("No dividends available for your holdings this month.")
                except Exception as e:
                    st.warning(f"Dividend collection failed: {e}")
        if st.button("Simulate 2-for-1 Stock Split", key="detailed_split"):
            try:
                portfolio = pd.read_csv(get_portfolio_path())
                portfolio['Quantity'] = portfolio['Quantity'] * 2
                portfolio['Buy Price'] = portfolio['Buy Price'] / 2
                portfolio.to_csv(get_portfolio_path(), index=False)
                st.toast("🔀 2-for-1 Stock Split applied to all holdings!")
            except Exception as e:
                st.warning(f"Stock split simulation failed: {e}")

# --- Educational Content Section ---
if menu == "Learn":
    st.title("📚 Learn & Level Up!")
    st.markdown("Sharpen your trading skills as you play. Expand the sections below to learn more about key concepts!")
    with st.expander("What is a Portfolio?"):
        st.write("""
        A portfolio is a collection of financial investments like stocks, bonds, commodities, cash, and cash equivalents, including mutual funds and ETFs. In this game, your portfolio consists of the stocks you buy and sell.
        """)
    with st.expander("How do Dividends Work?"):
        st.write("""
        Dividends are payments made by a corporation to its shareholders, usually as a distribution of profits. If you own a stock when a dividend is paid, you receive a payout per share.
        """)
    with st.expander("What is a Stock Split?"):
        st.write("""
        A stock split increases the number of shares in a company. For example, in a 2-for-1 split, you get 2 shares for every 1 you own, but each is worth half as much. Your total value stays the same.
        """)
    with st.expander("What is Volatility?"):
        st.write("""
        Volatility is a statistical measure of the dispersion of returns for a given security or market index. High volatility means the price of the asset can change dramatically in either direction.
        """)
    with st.expander("What is the Sharpe Ratio?"):
        st.write("""
        The Sharpe Ratio measures the performance of an investment compared to a risk-free asset, after adjusting for its risk. The higher the Sharpe Ratio, the better the risk-adjusted return.
        """)
    with st.expander("What is Diversification?"):
        st.write("""
        Diversification is the practice of spreading your investments across different assets, sectors, or geographies to reduce risk. A diversified portfolio is less likely to experience large losses because different assets often perform differently under the same conditions.
        """)
    with st.expander("What are Transaction Fees?"):
        st.write("""
        Transaction fees are small costs charged when you buy or sell stocks. In this game, a 0.5% fee is applied to each trade (unless you have a No Fee Day boost!). Always consider fees when planning your trades.
        """)
    with st.expander("What are Boosts and Rewards?"):
        st.write("""
        Boosts and rewards are special items you can earn or redeem in the Store. Some boosts give you advantages like no transaction fees or double profits for a day. Badges and themes let you customize your profile and experience.
        """)
    with st.expander("What is a Leaderboard?"):
        st.write("""
        A leaderboard ranks players based on their portfolio value, points, or achievements. Competing on the leaderboard can motivate you to improve your trading skills and try new strategies.
        """)
    with st.expander("What is Risk Management?"):
        st.write("""
        Risk management means using strategies to minimize potential losses. This includes setting stop-losses, diversifying, and not investing all your cash in one stock. Good risk management helps you stay in the game longer and avoid big setbacks.
        """)
    with st.expander("Tips for Virtual Trading Success"):
        st.write("""
        - Diversify your portfolio
        - Monitor your holdings regularly
        - Set price alerts for your favorite stocks
        - Learn from your trades and keep improving!
        - Use boosts and rewards wisely
        - Don’t let emotions drive your trades—stick to your strategy
        - Review your performance and learn from mistakes
        - Stay updated on market news and trends
        """)

st.markdown("---")
st.caption("Built with ❤️ by Ritvik's Trading Engine")

