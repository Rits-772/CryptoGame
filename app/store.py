# ...existing code from store.py will be moved here...
import os
import json
import achievements

# To make store state per-user, change:
# OWNED_FILE = os.path.join("data", f"owned_rewards_{username}.json")
# ACTIVE_FILE = os.path.join("data", f"active_rewards_{username}.json")

STORE_FILE = os.path.join("data", "store.json")
ACTIVE_FILE = os.path.join("data", "active_rewards.json")
OWNED_FILE = os.path.join("data", "owned_rewards.json")

# Define store rewards, each with a required achievement difficulty and points cost
REWARDS = [
    {"id": "cash_small", "name": "₹1,000 Bonus", "desc": "Redeem for ₹1,000 cash.", "difficulty": "Beginner", "cost": 10, "value": 1000, "type": "cash"},
    {"id": "cash_medium", "name": "₹5,000 Bonus", "desc": "Redeem for ₹5,000 cash. Requires Intermediate achievement.", "difficulty": "Intermediate", "cost": 25, "value": 5000, "type": "cash"},
    {"id": "cash_large", "name": "₹25,000 Bonus", "desc": "Redeem for ₹25,000 cash. Requires Hard achievement.", "difficulty": "Hard", "cost": 50, "value": 25000, "type": "cash"},
    {"id": "cash_godly", "name": "₹1,00,000 Bonus", "desc": "Redeem for ₹1,00,000 cash. Requires Godly achievement.", "difficulty": "Godly", "cost": 100, "value": 100000, "type": "cash"},
    # Cosmetic badges
    {"id": "badge_gold", "name": "Golden Badge", "desc": "A shiny golden badge for your profile.", "difficulty": "Beginner", "cost": 20, "type": "badge"},
    {"id": "badge_platinum", "name": "Platinum Badge", "desc": "A rare platinum badge for elite traders.", "difficulty": "Hard", "cost": 50, "type": "badge"},
    # Themes
    {"id": "theme_dark", "name": "Dark Theme", "desc": "Switch your UI to a dark theme.", "difficulty": "Beginner", "cost": 10, "type": "theme"},
    {"id": "theme_light", "name": "Light Theme", "desc": "Switch your UI to a light theme.", "difficulty": "Beginner", "cost": 10, "type": "theme"},
    # Temporary boosts
    {"id": "boost_double_profit", "name": "Double Profit Day", "desc": "Doubles your next day's profit! (One-time use)", "difficulty": "Intermediate", "cost": 40, "type": "boost"},
    {"id": "boost_no_fee", "name": "No Fee Day", "desc": "No transaction fees for your next day! (One-time use)", "difficulty": "Intermediate", "cost": 35, "type": "boost"},
    # Analytics tool
    {"id": "analytics_pro", "name": "Analytics Pro", "desc": "Unlock advanced analytics tools.", "difficulty": "Hard", "cost": 60, "type": "analytics"},
]
# --- Activation/Use logic ---

def get_owned_file(username):
    return os.path.join("data", f"owned_rewards_{username}.json")

def get_active_file(username):
    return os.path.join("data", f"active_rewards_{username}.json")

def activate_reward(username, reward_id):
    reward = next((r for r in REWARDS if r["id"] == reward_id), None)
    if not reward:
        return False, "Reward not found."
    active = get_active_rewards(username)
    import time
    if reward["type"] in ["badge", "theme"]:
        active[reward["type"]] = reward_id
    elif reward["type"] == "boost":
        # Only one boost can be active at a time
        active["boost"] = reward_id
        # Store activation time (epoch seconds)
        active["boost_time"] = int(time.time())
    elif reward["type"] == "analytics":
        active["analytics"] = reward_id
    else:
        return False, "Cannot activate this reward."
    with open(get_active_file(username), "w") as f:
        json.dump(active, f)
    return True, f"{reward['name']} activated!"

def get_active_rewards(username):
    active_file = get_active_file(username)
    if not os.path.exists(active_file):
        with open(active_file, "w") as f:
            json.dump({}, f)
    with open(active_file, "r") as f:
        return json.load(f)

def use_boost(username, reward_id):
    """Mark a boost as used (removes it from active and owned)."""
    active = get_active_rewards(username)
    owned = get_owned_rewards(username)
    if active.get("boost") == reward_id and reward_id in owned:
        active.pop("boost", None)
        owned.remove(reward_id)
        with open(get_active_file(username), "w") as f:
            json.dump(active, f)
        with open(get_owned_file(username), "w") as f:
            json.dump(owned, f)
        return True, "Boost used."
    return False, "Boost not active or not owned."

def is_boost_active(username, reward_id):
    import time
    active = get_active_rewards(username)
    if active.get("boost") != reward_id:
        return False
    # Check if boost is within 24 hours
    boost_time = active.get("boost_time")
    if not boost_time:
        return True  # fallback: treat as active
    now = int(time.time())
    if now - boost_time <= 86400:
        return True
    # Expired: remove boost
    use_boost(username, reward_id)
    return False

def get_rewards():
    return REWARDS

def can_redeem(username, reward_id):
    reward = next((r for r in REWARDS if r["id"] == reward_id), None)
    if not reward:
        return False, "Reward not found."
    points = achievements.get_points(username)
    unlocked = [a["difficulty"] for a in achievements.get_unlocked_achievements(username)]
    if points < reward["cost"]:
        return False, "Not enough points."
    if reward["difficulty"] not in unlocked:
        return False, f"You need at least one {reward['difficulty']} achievement unlocked."
    return True, ""

def redeem_reward(username, reward_id, update_cash_balance, get_cash_balance):
    reward = next((r for r in REWARDS if r["id"] == reward_id), None)
    if not reward:
        return False, "Reward not found."
    can, msg = can_redeem(username, reward_id)
    if not can:
        return False, msg
    if achievements.redeem_points(username, reward["cost"]):
        # Handle different reward types
        if reward["type"] == "cash":
            update_cash_balance(get_cash_balance() + reward["value"])
            _add_owned_reward(username, reward_id)
            return True, f"Redeemed! {reward['name']} added to your balance."
        elif reward["type"] in ["badge", "boost", "analytics"]:
            _add_owned_reward(username, reward_id)
            return True, f"Redeemed! {reward['name']} is now available in your profile."
        else:
            return False, "Unknown reward type."
    return False, "Redemption failed."

# --- Owned rewards management ---
def _add_owned_reward(username, reward_id):
    owned = get_owned_rewards(username)
    if reward_id not in owned:
        owned.append(reward_id)
        with open(get_owned_file(username), "w") as f:
            json.dump(owned, f)

def get_owned_rewards(username):
    owned_file = get_owned_file(username)
    if not os.path.exists(owned_file):
        with open(owned_file, "w") as f:
            json.dump([], f)
    with open(owned_file, "r") as f:
        return json.load(f)
