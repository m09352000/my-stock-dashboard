import pandas as pd
import twstock
import os
import json
from datetime import datetime

# --- V82: 資料庫核心 (強制重置 Admin 權限版) ---

USERS_FILE = 'stock_users.json'
WATCHLIST_FILE = 'stock_watchlist.json'
COMMENTS_FILE = 'stock_comments.csv'

# --- 1. 初始化資料庫 (V82: 強制修復邏輯) ---
def init_db():
    # 1. 處理使用者資料庫
    users = {}
    
    # 如果檔案存在，先讀取舊資料，以免覆蓋掉其他註冊的使用者
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                users = json.load(f)
        except:
            users = {} # 如果檔案壞掉，就重來

    # V82 關鍵修正：不管檔案在不在，強制將 admin 密碼重置為 admin888
    # 這樣保證您更新程式碼後，一定能登入
    users["admin"] = {
        "password": "admin888", 
        "name": "超級管理員"
    }
    
    # 寫回檔案
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False)

    # 2. 處理自選股資料庫
    if not os.path.exists(WATCHLIST_FILE):
        with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False)
            
    # 3. 處理留言板資料庫
    if not os.path.exists(COMMENTS_FILE):
        df = pd.DataFrame(columns=['User', 'Nickname', 'Message', 'Time'])
        df.to_csv(COMMENTS_FILE, index=False)

# 程式啟動時立即執行初始化與修復
init_db()

# --- 2. 使用者系統 ---
def login_user(username, password):
    try:
        # 每次登入都重新讀取檔案，確保抓到最新的強制重置結果
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            users = json.load(f)
        
        if username in users:
            # 比對密碼
            if str(users[username]['password']) == str(password):
                return True, "登入成功"
            else:
                return False, "密碼錯誤"
        return False, "帳號不存在"
    except Exception as e: 
        return False, f"系統錯誤: {str(e)}"

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
        
        # 立即寫入硬碟
        with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
        return True
    except: return False

# --- 4. 股票數據 (快取與抓取) ---
def get_stock_data(code):
    try:
        stock = twstock.Stock(code)
        # 抓取近 60 日資料以確保技術指標準確
        hist = stock.fetch_from(2023, 1) 
        if len(hist) > 60:
            hist = hist[-60:]
            
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
def update_top_100():
    pass

def translate_text(text):
    return text
