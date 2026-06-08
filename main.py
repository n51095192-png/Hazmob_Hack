#!/usr/bin/env python3
import requests
import time
import random
from datetime import datetime, timezone, timedelta
import json
from functools import wraps

BASE = "https://eadd7.playfabapi.com"
COMMON_PARAMS = "sdk=UnitySDK-2.211.250328&engine=6000.2.6f2&platform=WebGLPlayer"

CUSTOM_ID = "gKmTcMN8DRMGrxFiDQZI6nEEXxW2"   # شناسه شما

FREE_WALL_PLACEMENT = "BE8996213BD00442"
FREE_WALL_REWARD = "1C8F93A112FC6F77"

UPGRADE_PLACEMENT = "7F412E96043AE00A"
UPGRADE_REWARD = "BDE00501F2CC60DC"

PURPLE = "\033[38;2;128;0;255m"
DARK_PURPLE = "\033[38;2;75;0;130m"
LIGHT_PURPLE = "\033[38;2;180;100;255m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
GRAY = "\033[90m"
RESET = "\033[0m"

def colored(text, color):
    return f"{color}{text}{RESET}"

class TokenManager:
    def __init__(self):
        self.session_ticket = None
        self.entity_token = None
        self.expiry = None
        self._login()

    def _login(self):
        url = f"{BASE}/Client/LoginWithCustomID?{COMMON_PARAMS}"
        payload = {
            "CreateAccount": False,
            "CustomId": CUSTOM_ID,
            "InfoRequestParameters": {
                "GetPlayerProfile": True,
                "GetUserAccountInfo": True,
                "GetUserInventory": False,
                "GetUserVirtualCurrency": False,
                "GetUserData": False,
                "GetUserReadOnlyData": False,
                "GetTitleData": False,
                "GetPlayerStatistics": False
            },
            "TitleId": "EADD7"
        }
        try:
            resp = requests.post(url, json=payload, timeout=10)
            data = resp.json()
            if data.get("code") != 200:
                raise Exception(f"Login failed: {data}")
            self.session_ticket = data["data"]["SessionTicket"]
            self.entity_token = data["data"]["EntityToken"]["EntityToken"]
            expiry_str = data["data"]["EntityToken"]["TokenExpiration"]
            self.expiry = datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))
            print(colored("[TOKEN]", GREEN) + colored(f" New tokens obtained, expiry: {self.expiry}", GRAY))
        except Exception as e:
            print(colored("[ERROR]", YELLOW) + colored(f" Login error: {e}", GRAY))
            raise

    def is_expired(self):
        if self.expiry is None:
            return True
        now = datetime.now(timezone.utc)
        return now + timedelta(minutes=5) >= self.expiry

    def ensure_valid(self):
        if self.is_expired():
            print(colored("[TOKEN]", YELLOW) + colored(" Token expired or near expiry, refreshing...", GRAY))
            self._login()

    def get_headers(self):
        self.ensure_valid()
        base = {
            "Content-Type": "application/json",
            "X-PlayFabSDK": "UnitySDK-2.211.250328",
            "X-ReportErrorAsSuccess": "true"
        }
        return {
            "client": {**base, "X-Authorization": self.session_ticket},
            "cloud": {**base, "X-EntityToken": self.entity_token}
        }

def with_auto_refresh(is_cloud=False):
    def decorator(func):
        @wraps(func)
        def wrapper(tm, *args, **kwargs):
            max_retries = 3
            for attempt in range(max_retries):
                headers = tm.get_headers()
                header = headers["cloud"] if is_cloud else headers["client"]
                try:
                    resp = func(header, *args, **kwargs)
                    if resp.get("code") == 200:
                        return resp
                    if resp.get("code") in (401, 1001, 403) or "Invalid" in str(resp):
                        print(colored("[AUTH]", YELLOW) + colored(" Auth error detected, refreshing token...", GRAY))
                        tm._login()
                        continue
                    if attempt < max_retries - 1:
                        print(colored("[RETRY]", YELLOW) + colored(f" Request failed: {resp}, retrying in 2s...", GRAY))
                        time.sleep(2)
                        continue
                    return resp
                except requests.exceptions.RequestException as e:
                    print(colored("[NET]", YELLOW) + colored(f" Network error: {e}, retrying...", GRAY))
                    time.sleep(2)
                    continue
            return {"code": 500, "status": "ERROR", "data": {}}
        return wrapper
    return decorator

@with_auto_refresh(is_cloud=True)
def check_reward_status(headers):
    url = f"{BASE}/CloudScript/ExecuteFunction?{COMMON_PARAMS}"
    payload = {
        "CustomTags": None,
        "Entity": None,
        "FunctionName": "FeW_CheckReward",
        "FunctionParameter": None,
        "GeneratePlayStreamEvent": None,
        "AuthenticationContext": None
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=10)
    return resp.json()

@with_auto_refresh(is_cloud=False)
def report_ad(headers, placement, reward):
    url = f"{BASE}/Client/ReportAdActivity?{COMMON_PARAMS}"
    payload = {
        "Activity": "Opened",
        "CustomTags": None,
        "PlacementId": placement,
        "RewardId": reward,
        "AuthenticationContext": None
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=10)
    return resp.json()

@with_auto_refresh(is_cloud=False)
def reward_ad(headers, placement, reward):
    url = f"{BASE}/Client/RewardAdActivity?{COMMON_PARAMS}"
    payload = {
        "CustomTags": None,
        "PlacementId": placement,
        "RewardId": reward,
        "AuthenticationContext": None
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=10)
    return resp.json()

@with_auto_refresh(is_cloud=True)
def claim_free_wall(headers, line_index):
    url = f"{BASE}/CloudScript/ExecuteFunction?{COMMON_PARAMS}"
    payload = {
        "CustomTags": None,
        "Entity": None,
        "FunctionName": "FeW_GetFreeWallReward",
        "FunctionParameter": {"lineIndex": line_index},
        "GeneratePlayStreamEvent": None,
        "AuthenticationContext": None
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=10)
    return resp.json()

@with_auto_refresh(is_cloud=False)
def get_user_inventory(headers):
    url = f"{BASE}/Client/GetUserInventory?{COMMON_PARAMS}"
    payload = {"CustomTags": None, "AuthenticationContext": None}
    resp = requests.post(url, json=payload, headers=headers, timeout=10)
    return resp.json()

@with_auto_refresh(is_cloud=True)
def upgrade_weapon(headers, instance_id, currency="HM", upgrade_with_ad=True):
    url = f"{BASE}/CloudScript/ExecuteFunction?{COMMON_PARAMS}"
    payload = {
        "CustomTags": None,
        "Entity": None,
        "FunctionName": "UpgradeWeapon",
        "FunctionParameter": {
            "InstanceId": instance_id,
            "Currency": currency,
            "UpgradeWithAd": upgrade_with_ad
        },
        "GeneratePlayStreamEvent": None,
        "AuthenticationContext": None
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=10)
    return resp.json()

def parse_status(data):
    progress = data.get("data", {}).get("FunctionResult", {}).get("Progress", {})
    prize_lines = progress.get("prizeLines", [])
    if len(prize_lines) < 2:
        return None, None, None, None
    line0 = prize_lines[0]
    line1 = prize_lines[1]
    idx0 = line0.get("nextRewardIndex", 0)
    idx1 = line1.get("nextRewardIndex", 0)
    total = line0.get("rewardCount", 100)
    reset_time_str = progress.get("nextResetTime")
    return idx0, idx1, total, reset_time_str

def wait_until_reset(reset_time_str, tm):
    reset_dt = datetime.fromisoformat(reset_time_str.replace('Z', '+00:00'))
    now = datetime.now(timezone.utc)
    if reset_dt <= now:
        return
    wait_seconds = (reset_dt - now).total_seconds()
    print(colored("[WAIT]", YELLOW) + colored(f" >>> Next reset at {reset_time_str}, sleeping {wait_seconds:.0f} seconds...", GRAY))
    print(colored("[UPGRADE]", CYAN) + colored(" Starting upgrade cycle during idle time...", GRAY))
    upgrade_all_items(tm)
    if wait_seconds > 0:
        time.sleep(wait_seconds)

def get_upgradable_items(inventory_data):
    items = inventory_data.get("data", {}).get("Inventory", [])
    upgradable = []
    for item in items:
        custom = item.get("CustomData", {})
        if "lvl" in custom or "PlayableCount" in custom:
            upgradable.append(item)
    return upgradable

def choose_currency(item):
    custom = item.get("CustomData", {})
    if "PlayableCount" in custom and "lvl" not in custom:
        return "HG"
    return "HM"

def get_current_level(item):
    custom = item.get("CustomData", {})
    if "lvl" in custom:
        return int(custom["lvl"])
    if "PlayableCount" in custom:
        return int(custom["PlayableCount"])
    return 0

def upgrade_item(tm, item, target_level=50):
    instance_id = item.get("ItemInstanceId")
    item_name = item.get("DisplayName", "Unknown")
    currency = choose_currency(item)
    current = get_current_level(item)
    if current >= target_level:
        return True

    while current < target_level:
        r1 = report_ad(tm, UPGRADE_PLACEMENT, UPGRADE_REWARD)
        if r1.get("code") != 200:
            print(colored("[UPGRADE]", YELLOW) + colored(f" ReportAd failed: {r1}", GRAY))
            time.sleep(1)
            continue
        r2 = reward_ad(tm, UPGRADE_PLACEMENT, UPGRADE_REWARD)
        if r2.get("code") != 200:
            print(colored("[UPGRADE]", YELLOW) + colored(f" RewardAd failed: {r2}", GRAY))
            time.sleep(1)
            continue

        resp = upgrade_weapon(tm, instance_id, currency=currency, upgrade_with_ad=True)
        if resp.get("code") != 200:
            print(colored("[UPGRADE]", YELLOW) + colored(f" Upgrade failed: {resp}", GRAY))
            time.sleep(1)
            continue

        inv = get_user_inventory(tm)
        updated_item = None
        for it in inv.get("data", {}).get("Inventory", []):
            if it.get("ItemInstanceId") == instance_id:
                updated_item = it
                break
        if updated_item:
            new_level = get_current_level(updated_item)
            if new_level > current:
                print(colored("[UPGRADE]", GREEN) + colored(f" {item_name}: {current} -> {new_level} ({currency})", GRAY))
                current = new_level
            else:
                print(colored("[UPGRADE]", YELLOW) + colored(f" {item_name}: stuck at {current}, will retry later", GRAY))
                return False
        else:
            print(colored("[UPGRADE]", YELLOW) + colored(f" {item_name}: not found after upgrade, will retry later", GRAY))
            return False
        time.sleep(1)
    return True

def upgrade_all_items(tm):
    print(colored("[UPGRADE]", CYAN) + colored(" Fetching inventory for upgrade...", GRAY))
    inv = get_user_inventory(tm)
    if inv.get("code") != 200:
        print(colored("[UPGRADE]", YELLOW) + colored(" Cannot fetch inventory, skipping upgrades.", GRAY))
        return

    items = get_upgradable_items(inv)
    if not items:
        print(colored("[UPGRADE]", YELLOW) + colored(" No upgradable items found.", GRAY))
        return

    weapons = [i for i in items if "lvl" in i.get("CustomData", {})]
    throwables = [i for i in items if "PlayableCount" in i.get("CustomData", {}) and "lvl" not in i.get("CustomData", {})]
    all_items = weapons + throwables

    pending = all_items[:]
    while pending:
        new_pending = []
        for item in pending:
            current = get_current_level(item)
            if current >= 50:
                continue
            print(colored("[UPGRADE]", CYAN) + colored(f" Upgrading {item.get('DisplayName', 'Unknown')} (current: {current})...", GRAY))
            success = upgrade_item(tm, item, target_level=50)
            if not success:
                new_pending.append(item)
        pending = new_pending
        if pending:
            print(colored("[UPGRADE]", YELLOW) + colored(f" {len(pending)} items stuck, waiting 60 seconds before next round...", GRAY))
            time.sleep(60)

    print(colored("[UPGRADE]", GREEN) + colored(" All items upgraded to max level.", GRAY))

# ---------- تابع جدید Claim با تضمین کامل ----------
def claim_with_verification(tm, line_index, line_name, max_global_retries=10):
    for global_attempt in range(max_global_retries):
        status_before = check_reward_status(tm)
        idx0, idx1, total, _ = parse_status(status_before)
        if idx0 is None:
            print(colored("[ERROR]", YELLOW) + " Cannot parse status")
            time.sleep(2)
            continue

        current_idx = idx0 if line_index == 0 else idx1

        # Report + Reward
        r1 = report_ad(tm, FREE_WALL_PLACEMENT, FREE_WALL_REWARD)
        if r1.get("code") != 200:
            time.sleep(1)
            continue
        r2 = reward_ad(tm, FREE_WALL_PLACEMENT, FREE_WALL_REWARD)
        if r2.get("code") != 200:
            time.sleep(1)
            continue

        claim_resp = claim_free_wall(tm, line_index)
        if claim_resp.get("code") != 200:
            time.sleep(1.5)
            continue

        time.sleep(0.8)
        status_after = check_reward_status(tm)
        idx0_after, idx1_after, _, _ = parse_status(status_after)
        new_idx = idx0_after if line_index == 0 else idx1_after

        if new_idx is not None and new_idx > current_idx:
            last_reward = claim_resp.get("data", {}).get("FunctionResult", {}).get("Progress", {}).get("lastReward")
            amount = last_reward.get("rC") if last_reward else None
            if amount:
                print(colored("[CLAIM]", GREEN) + colored(f" >>> {line_name}: +{amount}  ", LIGHT_PURPLE))
            else:
                print(colored("[CLAIM]", GREEN) + colored(f" >>> {line_name}: OK (index {current_idx} -> {new_idx})", LIGHT_PURPLE))
            return True

        print(colored("[WARN]", YELLOW) + colored(f" {line_name} index did NOT increase (still {new_idx}), retrying ({global_attempt+1}/{max_global_retries})...", GRAY))
        time.sleep(random.uniform(1.5, 3.0))

    print(colored("[ERROR]", YELLOW) + colored(f" Failed to claim {line_name} after {max_global_retries} cycles", GRAY))
    return False

# ---------- حلقه اصلی ----------
def main():
    print(colored("=" * 55, DARK_PURPLE))
    print(colored(">>> HAZMOB FREE WALL AUTO CLAIM (MONEY + GOLD) <<<", LIGHT_PURPLE))
    print(colored("=" * 55, DARK_PURPLE))
    print()

    tm = TokenManager()

    while True:
        print(colored("[INFO]", CYAN) + colored(" Fetching current status...", GRAY))
        status = check_reward_status(tm)
        if status.get("code") != 200:
            print(colored("[ERROR]", YELLOW) + f" Failed to get status: {status}")
            time.sleep(5)
            continue

        idx0, idx1, total, reset_time = parse_status(status)
        if idx0 is None:
            print(colored("[ERROR]", YELLOW) + " Could not parse prize lines")
            time.sleep(5)
            continue

        money_remaining = total - idx0
        gold_remaining = total - idx1

        print(colored("[STATUS]", PURPLE) + colored(f" Money index: {idx0}/{total}", CYAN) + colored(" | ", GRAY) + colored(f"Gold index: {idx1}/{total}", CYAN))
        print(colored("     >>> ", GRAY) + colored("Money left:", CYAN) + colored(f" {money_remaining} ", PURPLE) + colored("|", GRAY) + colored(" Gold left:", CYAN) + colored(f" {gold_remaining}", PURPLE))

        if money_remaining <= 0 and gold_remaining <= 0:
            print(colored("[INFO]", YELLOW) + " Both lines fully claimed. Waiting for reset...")
            wait_until_reset(reset_time, tm)
            continue

        while money_remaining > 0 or gold_remaining > 0:
            # انتخاب خط
            if money_remaining >= gold_remaining and money_remaining > 0:
                line, name = 0, "Money"
            elif gold_remaining > 0:
                line, name = 1, "Gold"
            else:
                break

            success = claim_with_verification(tm, line, name)
            if success:
                # به‌روزرسانی وضعیت پس از Claim موفق
                status = check_reward_status(tm)
                idx0, idx1, total, reset_time = parse_status(status)
                if idx0 is not None:
                    money_remaining = total - idx0
                    gold_remaining = total - idx1
                else:
                    print(colored("[ERROR]", YELLOW) + " Could not re-parse status, waiting 2s...")
                    time.sleep(2)
            else:
                print(colored("[FATAL]", YELLOW) + f" Could not claim {name}, waiting 10s before retrying...")
                time.sleep(10)

            time.sleep(random.uniform(0.5, 1.0))

        print(colored("[INFO]", YELLOW) + " Both lines completed for this cycle. Waiting for reset...")
        wait_until_reset(reset_time, tm)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(colored("\n[EXIT] Stopped by user.", LIGHT_PURPLE))
    except Exception as e:
        print(colored(f"\n[FATAL] {e}", YELLOW))
