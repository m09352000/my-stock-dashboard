import pandas as pd
import twstock
import os
import json
from datetime import datetime

# --- V79: JSON 持久化資料庫系統 ---
# 確保資料寫入硬碟，重整網頁也不會消失

USERS_FILE = 'stock_users.json'
WATCHLIST_FILE = 'stock_watchlist.json'
COMMENTS_FILE = 'stock_comments.csv'

# --- 1. 初始化資料庫 (若檔案不存在則建立) ---
def init_db():
    if not os.path.exists(USERS_FILE):
        # 預設建立一個 admin 帳號
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump({"admin": {"password": "123", "name": "管理員"}}, f, ensure_ascii=False)
            
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
    except: return False, "系統錯誤"

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
        hist = stock.fetch_from(2023, 1) # 簡單抓取，實際應用可優化日期
        # 為了效能，我們只取最近 60 筆
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
        
        # 處理無成交量的 NaN
        df = df.fillna(method='ffill')
        
        return f"{code}", stock, df, "yahoo" # 這裡模擬 yahoo 格式回傳
    except:
        return code, None, None, "fail"

def get_color_settings(code):
    return {'up': 'red', 'down': 'green', 'delta': 'inverse'}

# --- 5. 掃描與歷史紀錄 (簡易實作) ---
def add_history(user, text):
    pass # 實作略，可擴充寫入 log 檔

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

# --- 7. 更新精選池 (模擬) ---
def update_top_100():
    pass

# --- 8. 翻譯功能 (模擬) ---
def translate_text(text):
    return text # 實際可接 Google Translate API
