import pandas as pd
import twstock
import yfinance as yf
import os
import json
from datetime import datetime, timedelta
from deep_translator import GoogleTranslator
import streamlit as st

# --- V98: 資料庫核心 (Safe Boot 延遲載入版) ---

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
        with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False)
            
    if not os.path.exists(COMMENTS_FILE):
        df = pd.DataFrame(columns=['User', 'Nickname', 'Message', 'Time'])
        df.to_csv(COMMENTS_FILE, index=False)

init_db()

# --- 2. 使用者系統 ---
def login_user(username, password):
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            users = json.load(f)
        if username in users:
            if str(users[username]['password']) == str(password): return True, "登入成功"
            else: return False, "密碼錯誤"
        return False, "帳號不存在"
    except Exception as e: return False, f"系統錯誤: {str(e)}"

def register_user(username, password, nickname):
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            users = json.load(f)
        if username in users: return False, "帳號已存在"
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

# --- 3. 自選股系統 ---
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
            if code not in user_list: user_list.append(code)
        elif action == "remove":
            if code in user_list: user_list.remove(code)
        data[username] = user_list
        with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
        return True
    except: return False

# --- 4. 股票數據 (Yahoo Finance) ---
def get_stock_data(code):
    try:
        ticker = None
        df = pd.DataFrame()
        candidates = [f"{code}.TW", f"{code}.TWO"] if code.isdigit() else [code]
            
        for c in candidates:
            try:
                temp_ticker = yf.Ticker(c)
                temp_df = temp_ticker.history(period="6mo")
                if not temp_df.empty:
                    ticker = temp_ticker
                    df = temp_df
                    df.index = df.index.tz_localize(None)
                    df = df.reset_index()
                    if 'Date' in df.columns:
                        df['Date'] = df['Date'].apply(lambda x: x.strftime('%Y-%m-%d'))
                    break
            except: continue

        if ticker is None or df.empty:
            return code, None, None, "fail"

        return f"{code}", ticker, df, "yahoo"
    except Exception as e:
        return code, None, None, "fail"

# --- V96.1 Rate Limit 防護盾 ---
@st.cache_data(ttl=86400)
def get_info_data(symbol):
    try:
        return yf.Ticker(symbol).info
    except Exception as e:
        return {}

# --- V98 關鍵修改：延遲載入 FinMind (解決開機黑畫面) ---
@st.cache_data(ttl=3600)
def get_chip_data(stock_id):
    try:
        if not stock_id.isdigit(): return None
        
        # ⚠️ 關鍵：用到時才載入，避免開機卡死
        from FinMind.data import DataLoader
        
        dl = DataLoader()
        start_date = (datetime.now() - timedelta(days=15)).strftime('%Y-%m-%d')
        df_inst = dl.taiwan_stock_institutional_investors(stock_id=stock_id, start_date=start_date)
        chip_data = {"foreign": 0, "trust": 0, "dealer": 0, "date": ""}
        if not df_inst.empty:
            latest_date = df_inst['date'].max()
            df_last = df_inst[df_inst['date'] == latest_date]
            chip_data["date"] = latest_date
            for _, row in df_last.iterrows():
                net = (row['buy'] - row['sell']) / 1000
                if row['name'] == 'Foreign_Investor': chip_data['foreign'] = int(net)
                elif row['name'] == 'Investment_Trust': chip_data['trust'] = int(net)
                elif row['name'] == 'Dealer_Self': chip_data['dealer'] += int(net)
                elif row['name'] == 'Dealer_Hedging': chip_data['dealer'] += int(net)
        return chip_data
    except: return None

# --- V99 新增：獲取股權分散表 (籌碼分佈) ---
@st.cache_data(ttl=86400)
def get_shareholding_data(stock_id):
    try:
        if not stock_id.isdigit(): return None
        
        # 延遲載入以避免影響啟動速度
        from FinMind.data import DataLoader
        dl = DataLoader()
        
        # 往回抓 45 天以確保涵蓋到最新的週資料 (有時候 FinMind 更新較慢)
        start_date = (datetime.now() - timedelta(days=45)).strftime('%Y-%m-%d')
        
        # 使用 FinMind 抓取股權分散表
        df = dl.taiwan_stock_shareholding(stock_id=stock_id, start_date=start_date)
        
        if not df.empty:
            # 取得最新日期的資料
            latest_date = df['date'].max()
            df_latest = df[df['date'] == latest_date].copy()
            
            # 整理欄位顯示名稱
            df_latest = df_latest[['HoldingRange', 'people', 'unit', 'percent']]
            df_latest.columns = ['持股分級', '股東人數', '持股數量', '持股比例(%)']
            
            return {"date": latest_date, "data": df_latest}
            
        return None
    except Exception as e:
        return None

def get_color_settings(code):
    return {'up': 'red', 'down': 'green', 'delta': 'inverse'}

# --- 5. 掃描與歷史紀錄 ---
def add_history(user, text): pass 
def save_scan_results(stype, codes):
    with open(f"scan_{stype}.json", 'w') as f: json.dump(codes, f)
def load_scan_results(stype):
    if os.path.exists(f"scan_{stype}.json"):
        with open(f"scan_{stype}.json", 'r') as f: return json.load(f)
    return []

# --- 6. 留言板 ---
def save_comment(user, msg):
    if not os.path.exists(COMMENTS_FILE): df = pd.DataFrame(columns=['User', 'Nickname', 'Message', 'Time'])
    else: df = pd.read_csv(COMMENTS_FILE)
    new_row = {'User': user, 'Nickname': get_user_nickname(user), 'Message': msg, 'Time': datetime.now().strftime("%Y-%m-%d %H:%M")}
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(COMMENTS_FILE, index=False)

def get_comments():
    if os.path.exists(COMMENTS_FILE): return pd.read_csv(COMMENTS_FILE)
    return pd.DataFrame(columns=['User', 'Nickname', 'Message', 'Time'])

# --- 7. 翻譯功能 (長文完整翻譯) ---
def translate_text(text):
    if not text or text == "暫無詳細描述": return "" 
    try:
        translator = GoogleTranslator(source='auto', target='zh-TW')
        if len(text) < 1000: return translator.translate(text)
        chunks = [text[i:i+1000] for i in range(0, len(text), 1000)]
        translated_chunks = []
        for chunk in chunks:
            try:
                res = translator.translate(chunk)
                if res: translated_chunks.append(res)
            except: translated_chunks.append(chunk)
        return "".join(translated_chunks)
    except Exception as e: return text
