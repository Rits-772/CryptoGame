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
sidebar_css_path = os.path.join("gui", "sidebar.css")
if os.path.exists(sidebar_css_path):
    with open(sidebar_css_path, encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
