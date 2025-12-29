import pandas as pd
import twstock
import os
import json
from datetime import datetime

# --- V81: 資料庫核心 (修正 Admin 預設密碼) ---

USERS_FILE = 'stock_users.json'
WATCHLIST_FILE = 'stock_watchlist.json'
COMMENTS_FILE = 'stock_comments.csv'

# --- 1. 初始化資料庫 ---
def init_db():
    # 若使用者檔案不存在，則建立預設 Admin
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            # V81 修正：預設密碼改為 admin888
            default_data = {
                "admin": {
                    "password": "admin888", 
                    "name": "超級管理員"
                }
            }
            json.dump(default_data, f, ensure_ascii=False)
            
    if not os.path.exists(WATCHLIST_FILE):
        with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False)
            
    if not os.path.exists(COMMENTS_FILE):
        df = pd.DataFrame(columns=['User', 'Nickname', 'Message', 'Time'])
        df.to_csv(COMMENTS_FILE, index=False)

# 初始化
init_db()

# --- 2. 使用者系統 ---
def login_user(username, password):
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            users = json.load(f)
        if username in users and users[username]['password'] == password:
            return True, "登入成功"
        return False, "帳號或密碼錯誤"
    except: return False, "系統讀取錯誤"

def register_user(username, password, nickname):
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            users = json.load(f)
        if username in users:
            return False, "帳號已存在"
        
        users[username] = {"password": password, "name": nickname}
        
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False)
        return True, "註冊成功"
    except Exception as e: return False, str(e)

def get_user_nickname(username):
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            users = json.load(f)
        return users.get(username, {}).get('name', username)
    except: return username

# --- 3. 自選股系統 (持久化) ---
def get_watchlist(username):
    try:
        with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get(username, [])
    except: return []

def update_watchlist(username, code, action="add"):
    try:
        with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        user_list = data.get(username, [])
        
        if action == "add":
            if code not in user_list:
                user_list.append(code)
        elif action == "remove":
            if code in user_list:
                user_list.remove(code)
        
        data[username] = user_list
        
        with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
        return True
    except: return False

# --- 4. 股票數據 ---
def get_stock_data(code):
    try:
        stock = twstock.Stock(code)
        hist = stock.fetch_from(2023, 1)
        if len(hist) > 60: hist = hist[-60:]
            
        data = {
            'Date': [d.date for d in hist],
            'Open': [d.open for d in hist],
            'High': [d.high for d in hist],
            'Low': [d.low for d in hist],
            'Close': [d.close for d in hist],
            'Volume': [d.capacity for d in hist]
        }
        df = pd.DataFrame(data)
        df = df.fillna(method='ffill')
        return f"{code}", stock, df, "yahoo"
    except:
        return code, None, None, "fail"

def get_color_settings(code):
    return {'up': 'red', 'down': 'green', 'delta': 'inverse'}

# --- 5. 掃描與歷史紀錄 ---
def add_history(user, text):
    pass 

def save_scan_results(stype, codes):
    filename = f"scan_{stype}.json"
    with open(filename, 'w') as f:
        json.dump(codes, f)

def load_scan_results(stype):
    filename = f"scan_{stype}.json"
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    return []

# --- 6. 留言板 ---
def save_comment(user, msg):
    if not os.path.exists(COMMENTS_FILE):
        df = pd.DataFrame(columns=['User', 'Nickname', 'Message', 'Time'])
    else:
        df = pd.read_csv(COMMENTS_FILE)
    
    new_row = {
        'User': user,
        'Nickname': get_user_nickname(user),
        'Message': msg,
        'Time': datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(COMMENTS_FILE, index=False)

def get_comments():
    if os.path.exists(COMMENTS_FILE):
        return pd.read_csv(COMMENTS_FILE)
    return pd.DataFrame(columns=['User', 'Nickname', 'Message', 'Time'])

# --- 7. 其他 ---
def update_top_100(): pass
def translate_text(text): return text
