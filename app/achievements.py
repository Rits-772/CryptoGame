# ...existing code from achievements.py will be moved here...
import json
import os

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

def get_ach_file(username):
    return os.path.join("data", f"achievements_{username}.json")

def get_points_file(username):
    return os.path.join("data", f"points_{username}.txt")

def load_achievements(username):
    ach_file = get_ach_file(username)
    if not os.path.exists(ach_file):
        with open(ach_file, "w") as f:
            json.dump({"unlocked": []}, f)
    with open(ach_file, "r") as f:
        return json.load(f)

def save_achievements(username, data):
    ach_file = get_ach_file(username)
    with open(ach_file, "w") as f:
        json.dump(data, f)

def unlock_achievement(username, ach_id):
    data = load_achievements(username)
    if ach_id not in data["unlocked"]:
        data["unlocked"].append(ach_id)
        save_achievements(username, data)
        ach = next(a for a in ACHIEVEMENTS if a["id"] == ach_id)
        add_points(username, ach["points"])
        return ach
    return None

def get_points(username):
    points_file = get_points_file(username)
    if not os.path.exists(points_file):
        with open(points_file, "w") as f:
            f.write("0")
    with open(points_file, "r") as f:
        return int(f.read().strip())

def add_points(username, pts):
    points = get_points(username) + pts
    points_file = get_points_file(username)
    with open(points_file, "w") as f:
        f.write(str(points))

def redeem_points(username, pts):
    points = get_points(username)
    points_file = get_points_file(username)
    if points >= pts:
        with open(points_file, "w") as f:
            f.write(str(points - pts))
        return True
    return False

def get_unlocked_achievements(username):
    data = load_achievements(username)
    return [a for a in ACHIEVEMENTS if a["id"] in data["unlocked"]]
