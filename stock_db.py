import pandas as pd
import yfinance as yf
import twstock
import json
import os
import hashlib
from datetime import datetime
from deep_translator import GoogleTranslator

# --- 檔案路徑設定 ---
DB_USERS = "db_users.json"
DB_WATCHLISTS = "db_watchlists.json"
DB_HISTORY = "db_history.json"
DB_COMMENTS = "db_comments.csv"

# 策略專屬存檔路徑
SCAN_FILES = {
    'day': 'db_scan_day.json',
    'short': 'db_scan_short.json',
    'long': 'db_scan_long.json',
    'top': 'db_scan_top.json'
}

# --- 資料讀寫基礎 ---
def load_json(path, default):
    if not os.path.exists(path):
        with open(path, 'w', encoding='utf-8') as f: json.dump(default, f, ensure_ascii=False)
        return default
    try:
        with open(path, 'r', encoding='utf-8') as f: return json.load(f)
    except: return default

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=2)

# --- 策略結果存取 ---
def save_scan_results(mode, results):
    if mode in SCAN_FILES:
        save_json(SCAN_FILES[mode], results)

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
    users = load_json(DB_USERS, {})
    if u in users: return False, "帳號已存在"
    users[u] = {"password": hashlib.sha256(p.encode()).hexdigest(), "nickname": n}
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
    users = load_json(DB_USERS, {})
    nick = users.get(user_id, {}).get('nickname', user_id)
    df = pd.read_csv(DB_COMMENTS) if os.path.exists(DB_COMMENTS) else pd.DataFrame(columns=["Time", "Nickname", "Message"])
    new = pd.DataFrame([[datetime.now().strftime("%m/%d %H:%M"), nick, msg]], columns=["Time", "Nickname", "Message"])
    pd.concat([new, df], ignore_index=True).to_csv(DB_COMMENTS, index=False)

def get_comments():
    if os.path.exists(DB_COMMENTS):
        try: return pd.read_csv(DB_COMMENTS)
        except: pass
    return pd.DataFrame(columns=["Time", "Nickname", "Message"])

# --- 工具函式 ---
def get_color_settings(stock_id):
    # 只要有 TW 或者是數字開頭 (包含 00708L)，都視為台股
    sid = str(stock_id).upper()
    if ".TW" in sid or ".TWO" in sid or (len(sid) >= 4 and sid[0].isdigit()):
        return {"up": "#FF0000", "down": "#00FF00", "delta": "inverse"}
    return {"up": "#00FF00", "down": "#FF0000", "delta": "normal"}

def translate_text(text):
    if not text: return "暫無詳細描述"
    try: return GoogleTranslator(source='auto', target='zh-TW').translate(text[:1500])
    except: return text

def update_top_100():
    return True

# --- 雙引擎股票抓取 (V55 修復版) ---
def get_stock_data(code):
    code = str(code).upper().strip()
    
    # 判斷是否為台股 (修復邏輯：只要第一個字是數字，就嘗試加台股後綴)
    # 這樣可以支援 2330, 0050, 00708L, 00632R
    is_tw = code[0].isdigit()
    
    # 1. Yahoo (優先)
    if is_tw:
        suffixes = ['.TW', '.TWO'] 
    else:
        suffixes = [''] # 美股不加後綴

    for s in suffixes:
        try:
            stock = yf.Ticker(f"{code}{s}")
            df = stock.history(period="3mo")
            if not df.empty: return f"{code}{s}", stock, df, "yahoo"
        except: pass
    
    # 2. Twstock (備用) - 也套用新邏輯
    if is_tw:
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
