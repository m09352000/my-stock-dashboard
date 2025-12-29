import pandas as pd
import twstock
import yfinance as yf
import os
import json
from datetime import datetime

# --- V93: 資料庫核心 (暴力雙路徑版) ---

USERS_FILE = 'stock_users.json'
WATCHLIST_FILE = 'stock_watchlist.json'
COMMENTS_FILE = 'stock_comments.csv'

# --- 1. 初始化資料庫 ---
def init_db():
    users = {}
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                users = json.load(f)
        except: users = {}

    users["admin"] = {"password": "admin888", "name": "超級管理員"}
    
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False)

    if not os.path.exists(WATCHLIST_FILE):
        with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f: json.dump({}, f)
            
    if not os.path.exists(COMMENTS_FILE):
        df = pd.DataFrame(columns=['User', 'Nickname', 'Message', 'Time'])
        df.to_csv(COMMENTS_FILE, index=False)

init_db()

# --- 2. 使用者系統 ---
def login_user(username, password):
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f: users = json.load(f)
        if username in users:
            if str(users[username]['password']) == str(password): return True, "登入成功"
            else: return False, "密碼錯誤"
        return False, "帳號不存在"
    except Exception as e: return False, str(e)

def register_user(username, password, nickname):
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f: users = json.load(f)
        if username in users: return False, "帳號已存在"
        users[username] = {"password": password, "name": nickname}
        with open(USERS_FILE, 'w', encoding='utf-8') as f: json.dump(users, f, ensure_ascii=False)
        return True, "註冊成功"
    except Exception as e: return False, str(e)

def get_user_nickname(username):
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f: users = json.load(f)
        return users.get(username, {}).get('name', username)
    except: return username

# --- 3. 自選股系統 ---
def get_watchlist(username):
    try:
        with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f: return json.load(f).get(username, [])
    except: return []

def update_watchlist(username, code, action="add"):
    try:
        with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f: data = json.load(f)
        user_list = data.get(username, [])
        if action == "add" and code not in user_list: user_list.append(code)
        elif action == "remove" and code in user_list: user_list.remove(code)
        data[username] = user_list
        with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False)
        return True
    except: return False

# --- 4. 股票數據 (V93 核心修正：暴力試錯法) ---
def get_stock_data(code):
    """
    不管 twstock 說什麼，直接用 yfinance 試 .TW 和 .TWO
    """
    try:
        # 建立假的 Stock 物件結構，避免 UI 報錯
        class FakeStockInfo:
            def __init__(self, code, name):
                self.info = {
                    'name': name,
                    'code': code,
                    'sharesOutstanding': 0,
                    'heldPercentInstitutions': 0,
                    'longBusinessSummary': '資料由 Yahoo Finance 提供 (TWSE IP Bypass Mode)'
                }

        # 嘗試取得名稱 (若 twstock 還活著)
        name = code
        try:
            if code in twstock.codes:
                name = twstock.codes[code].name
        except: pass

        fake_stock_obj = FakeStockInfo(code, name)

        # 策略 A: 先試上市 (.TW)
        try:
            df = yf.download(f"{code}.TW", period="1y", interval="1d", progress=False)
            if not df.empty and len(df) > 5:
                # 清洗 MultiIndex
                if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
                return f"{code}", fake_stock_obj, df, "yahoo"
        except: pass

        # 策略 B: 若失敗，試上櫃 (.TWO)
        try:
            df = yf.download(f"{code}.TWO", period="1y", interval="1d", progress=False)
            if not df.empty and len(df) > 5:
                if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
                return f"{code}", fake_stock_obj, df, "yahoo"
        except: pass

        # 都失敗
        return code, None, None, "fail"
        
    except Exception as e:
        print(f"Global Error fetching {code}: {e}")
        return code, None, None, "fail"

def get_color_settings(code):
    return {'up': 'red', 'down': 'green', 'delta': 'inverse'}

# --- 5. 掃描與歷史紀錄 ---
def add_history(user, text): pass 

def save_scan_results(stype, codes):
    filename = f"scan_{stype}.json"
    with open(filename, 'w') as f: json.dump(codes, f)

def load_scan_results(stype):
    filename = f"scan_{stype}.json"
    if os.path.exists(filename):
        with open(filename, 'r') as f: return json.load(f)
    return []

# --- 6. 留言板 ---
def save_comment(user, msg):
    if not os.path.exists(COMMENTS_FILE):
        df = pd.DataFrame(columns=['User', 'Nickname', 'Message', 'Time'])
    else: df = pd.read_csv(COMMENTS_FILE)
    new_row = {'User': user, 'Nickname': user, 'Message': msg, 'Time': datetime.now().strftime("%Y-%m-%d %H:%M")}
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(COMMENTS_FILE, index=False)

def get_comments():
    if os.path.exists(COMMENTS_FILE): return pd.read_csv(COMMENTS_FILE)
    return pd.DataFrame(columns=['User', 'Nickname', 'Message', 'Time'])

def translate_text(text): return text
