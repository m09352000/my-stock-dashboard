import pandas as pd
import yfinance as yf
import twstock
import json
import os
import hashlib
from datetime import datetime
from deep_translator import GoogleTranslator

# --- 檔案路徑 ---
DB_USERS = "db_users.json"
DB_WATCHLISTS = "db_watchlists.json"
DB_HISTORY = "db_history.json"
DB_COMMENTS = "db_comments.csv"

# 掃描存檔
SCAN_FILES = {
    'day': 'db_scan_day.json',
    'short': 'db_scan_short.json',
    'long': 'db_scan_long.json',
    'top': 'db_scan_top.json'
}

# --- JSON 基礎 ---
def load_json(path, default):
    if not os.path.exists(path):
        with open(path, 'w', encoding='utf-8') as f: json.dump(default, f, ensure_ascii=False)
        return default
    try:
        with open(path, 'r', encoding='utf-8') as f: return json.load(f)
    except: return default

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=2)

# --- 掃描結果 (修正為 100 檔) ---
def save_scan_results(mode, results):
    if mode in SCAN_FILES:
        # 確保只存前 100
        save_json(SCAN_FILES[mode], results[:100])

def load_scan_results(mode):
    if mode in SCAN_FILES:
        return load_json(SCAN_FILES[mode], [])
    return []

# --- 會員系統 ---
def login_user(username, password):
    users = load_json(DB_USERS, {"admin": {"password": hashlib.sha256("admin888".encode()).hexdigest(), "nickname": "站長"}})
    if username not in users: return False, "帳號不存在"
    if users[username]['password'] != hashlib.sha256(password.encode()).hexdigest(): return False, "密碼錯誤"
    return True, users[username]

def register_user(u, p, n):
    if not u or not p: return False, "帳號密碼不得為空"
    users = load_json(DB_USERS, {})
    if u in users: return False, "帳號已存在"
    # 這裡確保暱稱被寫入
    users[u] = {
        "password": hashlib.sha256(p.encode()).hexdigest(), 
        "nickname": n if n else u
    }
    save_json(DB_USERS, users)
    init_user_data(u)
    return True, "註冊成功"

def init_user_data(u):
    w = load_json(DB_WATCHLISTS, {})
    if u not in w: w[u] = []; save_json(DB_WATCHLISTS, w)
    h = load_json(DB_HISTORY, {})
    if u not in h: h[u] = []; save_json(DB_HISTORY, h)

# --- 自選股 ---
def get_watchlist(user):
    db = load_json(DB_WATCHLISTS, {})
    return db.get(user, [])

def update_watchlist(user, code, action):
    db = load_json(DB_WATCHLISTS, {})
    if user not in db: db[user] = []
    if action == "add" and code not in db[user]: db[user].append(code)
    elif action == "remove" and code in db[user]: db[user].remove(code)
    save_json(DB_WATCHLISTS, db)

# --- 歷史與留言 ---
def add_history(user, record):
    if not user: return
    db = load_json(DB_HISTORY, {})
    if user not in db: db[user] = []
    if record in db[user]: db[user].remove(record)
    db[user].insert(0, record)
    save_json(DB_HISTORY, db)

def get_history(user): return load_json(DB_HISTORY, {}).get(user, [])

def save_comment(user_id, msg):
    # 抓取使用者暱稱
    users = load_json(DB_USERS, {})
    nick = users.get(user_id, {}).get('nickname', user_id)
    
    df = pd.read_csv(DB_COMMENTS) if os.path.exists(DB_COMMENTS) else pd.DataFrame(columns=["Time", "Nickname", "Message"])
    new = pd.DataFrame([[datetime.now().strftime("%m/%d %H:%M"), nick, msg]], columns=["Time", "Nickname", "Message"])
    # 存檔時包含 header
    pd.concat([new, df], ignore_index=True).to_csv(DB_COMMENTS, index=False)

def get_comments():
    if os.path.exists(DB_COMMENTS):
        try: return pd.read_csv(DB_COMMENTS)
        except: pass
    return pd.DataFrame(columns=["Time", "Nickname", "Message"])

# --- 工具 ---
def get_color_settings(stock_id):
    # 台股：紅漲綠跌
    if ".TW" in stock_id.upper() or ".TWO" in stock_id.upper() or stock_id.isdigit():
        return {"up": "#FF0000", "down": "#00FF00", "delta": "inverse"}
    # 美股：綠漲紅跌
    return {"up": "#00FF00", "down": "#FF0000", "delta": "normal"}

def translate_text(text):
    if not text: return "暫無詳細描述"
    try: return GoogleTranslator(source='auto', target='zh-TW').translate(text[:1000])
    except: return text

def update_top_100():
    # 預留給未來擴充自動更新功能
    return True

# --- 股票數據 (Yahoo + Twstock) ---
def get_stock_data(code):
    # 1. Yahoo (優先)
    suffixes = ['.TW', '.TWO'] if code.isdigit() else ['']
    for s in suffixes:
        try:
            stock = yf.Ticker(f"{code}{s}")
            df = stock.history(period="3mo")
            if not df.empty: return f"{code}{s}", stock, df, "yahoo"
        except: pass
    
    # 2. Twstock (備用)
    if code.isdigit():
        try:
            rt = twstock.realtime.get(code)
            if rt['success'] and rt['realtime']['latest_trade_price'] != '-':
                info = rt['realtime']
                return f"{code} (TWSE)", None, {
                    'Close': float(info['latest_trade_price']),
                    'High': float(info['high']),
                    'Low': float(info['low']),
                    'Volume': int(info['accumulate_trade_volume'])*1000 if info['accumulate_trade_volume'] else 0
                }, "twse"
        except: pass
    return None, None, None, "fail"
