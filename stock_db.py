import pandas as pd
import twstock
import yfinance as yf # 新增這行
import os
import json
import time
from datetime import datetime

# --- V92: 資料庫核心 (抗 Ban 穩定版) ---

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

    # 強制重置 admin，確保您能登入
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

# --- 4. 股票數據 (V92 核心修正：改用 Yahoo Finance 抓歷史) ---
def get_stock_data(code):
    """
    策略：
    1. 透過 twstock 判斷上市(.TW) 或 上櫃(.TWO)
    2. 使用 yfinance 下載歷史資料 (避開 TWSE IP Ban)
    3. 回傳格式統一，讓 UI 端無縫接軌
    """
    try:
        # 1. 判斷股票後綴 (Yahoo Finance 需要 .TW 或 .TWO)
        suffix = ".TW" # 預設上市
        stock_info = twstock.codes.get(code)
        
        if stock_info:
            if stock_info.market == "上櫃":
                suffix = ".TWO"
        else:
            # 若 twstock 查不到(如ETF)，嘗試猜測或預設
            pass 

        yf_ticker = f"{code}{suffix}"
        
        # 2. 使用 yfinance 下載資料 (速度快，不鎖 IP)
        # 抓取 1 年份資料，間隔 1 天
        df = yf.download(yf_ticker, period="1y", interval="1d", progress=False)
        
        if df.empty:
            # 嘗試另一種後綴 (有時候 ETF 判斷會失準)
            alt_suffix = ".TWO" if suffix == ".TW" else ".TW"
            df = yf.download(f"{code}{alt_suffix}", period="1y", interval="1d", progress=False)
            if df.empty:
                return code, None, None, "fail"
        
        # 3. 格式清理 (yfinance 有時會有 MultiIndex)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        # 確保索引是 Datetime
        df.index = pd.to_datetime(df.index)
        
        # 確保欄位名稱正確 (相容原本程式)
        # yfinance 欄位通常是 Open, High, Low, Close, Volume
        
        # 模擬一個 twstock 物件回傳 (只為了取 info)
        fake_stock_obj = type('obj', (object,), {'info': {}})
        if stock_info:
            fake_stock_obj.info = {
                'name': stock_info.name,
                'code': stock_info.code,
                'sharesOutstanding': 0, # yfinance 免費版不易取得，設 0 避免錯誤
                'heldPercentInstitutions': 0,
                'longBusinessSummary': f"{stock_info.name} (資料來源: Yahoo Finance)"
            }
        
        return f"{code}", fake_stock_obj, df, "yahoo"
        
    except Exception as e:
        print(f"Error fetching {code}: {e}")
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
    
    new_row = {
        'User': user, 'Nickname': user, # 簡化
        'Message': msg, 'Time': datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(COMMENTS_FILE, index=False)

def get_comments():
    if os.path.exists(COMMENTS_FILE): return pd.read_csv(COMMENTS_FILE)
    return pd.DataFrame(columns=['User', 'Nickname', 'Message', 'Time'])

def translate_text(text): return text
