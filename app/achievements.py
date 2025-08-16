# ...existing code from achievements.py will be moved here...
import json
import os

ACH_FILE = os.path.join("data", "achievements.json")
POINTS_FILE = os.path.join("data", "points.txt")

ACHIEVEMENTS = [
    {"id": "first_trade", "name": "Rookie Trader", "difficulty": "Beginner", "points": 10, "desc": "Complete your very first trade (buy or sell)."},
    {"id": "portfolio_10k", "name": "Five Figures Club", "difficulty": "Beginner", "points": 10, "desc": "Grow your portfolio to ₹10,000 or more."},
    {"id": "portfolio_50k", "name": "Halfway Hero", "difficulty": "Intermediate", "points": 25, "desc": "Reach a portfolio value of ₹50,000 or more."},
    {"id": "portfolio_1lakh", "name": "Lakhpati", "difficulty": "Hard", "points": 50, "desc": "Reach a portfolio value of ₹1,00,000 or more."},
    {"id": "portfolio_5lakh", "name": "Half Millionaire", "difficulty": "Godly", "points": 100, "desc": "Reach a portfolio value of ₹5,00,000 or more."},
    {"id": "ten_trades", "name": "Market Explorer", "difficulty": "Intermediate", "points": 20, "desc": "Complete 10 trades (buy or sell)."},
    {"id": "twentyfive_trades", "name": "Trading Enthusiast", "difficulty": "Hard", "points": 40, "desc": "Complete 25 trades (buy or sell)."},
    {"id": "fifty_trades", "name": "Trading Legend", "difficulty": "Godly", "points": 80, "desc": "Complete 50 trades (buy or sell)."},
    {"id": "first_sell", "name": "First Exit", "difficulty": "Beginner", "points": 10, "desc": "Sell a stock for the first time."},
    {"id": "all_green", "name": "All Green", "difficulty": "Hard", "points": 60, "desc": "All your holdings are in profit!"},
    {"id": "diversified", "name": "Diversification Pro", "difficulty": "Intermediate", "points": 30, "desc": "Hold 5 or more different stocks at once."},
    {"id": "big_winner", "name": "Big Winner", "difficulty": "Godly", "points": 100, "desc": "Achieve over 50% profit on a single stock."},
    {"id": "no_cash", "name": "All In", "difficulty": "Hard", "points": 50, "desc": "Let your cash balance drop below ₹100."},
    {"id": "first_loss", "name": "Hard Lesson", "difficulty": "Beginner", "points": 10, "desc": "Sell a stock at a loss for the first time."},
]

def load_achievements():
    if not os.path.exists(ACH_FILE):
        with open(ACH_FILE, "w") as f:
            json.dump({"unlocked": []}, f)
    with open(ACH_FILE, "r") as f:
        return json.load(f)

def save_achievements(data):
    with open(ACH_FILE, "w") as f:
        json.dump(data, f)

def unlock_achievement(ach_id):
    data = load_achievements()
    if ach_id not in data["unlocked"]:
        data["unlocked"].append(ach_id)
        save_achievements(data)
        ach = next(a for a in ACHIEVEMENTS if a["id"] == ach_id)
        add_points(ach["points"])
        return ach
    return None

def get_points():
    if not os.path.exists(POINTS_FILE):
        with open(POINTS_FILE, "w") as f:
            f.write("0")
    with open(POINTS_FILE, "r") as f:
        return int(f.read().strip())

def add_points(pts):
    points = get_points() + pts
    with open(POINTS_FILE, "w") as f:
        f.write(str(points))

def redeem_points(pts):
    points = get_points()
    if points >= pts:
        with open(POINTS_FILE, "w") as f:
            f.write(str(points - pts))
        return True
    return False

def get_unlocked_achievements():
    data = load_achievements()
    return [a for a in ACHIEVEMENTS if a["id"] in data["unlocked"]]
