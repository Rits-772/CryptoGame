# utils.py
import os
import pandas as pd

DATA_DIR = "data"

def load_user_data(player_name):
    portfolio_path = os.path.join(DATA_DIR, f"Portfolio_{player_name}.csv")
    if os.path.exists(portfolio_path):
        return pd.read_csv(portfolio_path)
    return pd.DataFrame(columns=["Symbol", "Quantity", "BuyPrice", "BuyDate"])

def save_user_data(player_name, portfolio):
    portfolio_path = os.path.join(DATA_DIR, f"Portfolio_{player_name}.csv")
    portfolio.to_csv(portfolio_path, index=False)