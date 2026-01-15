import pandas as pd
import twstock
import yfinance as yf
import os
import json
from datetime import datetime, timedelta
from deep_translator import GoogleTranslator
import streamlit as st

# --- V109: 資料庫核心 (Deep Scan + Hybrid Chips) ---

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

@st.cache_data(ttl=86400)
def get_info_data(symbol):
    try:
        t = yf.Ticker(symbol)
        return t.info if t.info else {}
    except: return {}

# --- V106: 暴力股利搜尋 (確保抓到 9.0) ---
@st.cache_data(ttl=3600)
def get_dividend_data(symbol, current_price):
    data = {"cash_div": 0.0, "yield": 0.0}
    try:
        if current_price <= 0: return data
        ticker = yf.Ticker(symbol)
        
        # 策略 1: 直接讀取 info
        div_rate = ticker.info.get('dividendRate')
        
        # 策略 2: 暴力掃描 dividends 歷史
        if not div_rate or div_rate == 0:
            hist = ticker.dividends
            if not hist.empty:
                now = pd.Timestamp.now().tz_localize(None)
                try: hist.index = hist.index.tz_localize(None)
                except: pass
                
                one_year_ago = now - pd.DateOffset(days=365)
                recent = hist[hist.index >= one_year_ago]
                
                if not recent.empty: div_rate = recent.sum()
                else: div_rate = hist.iloc[-1] # 抓最後一筆

        if div_rate and div_rate > 0:
            data["cash_div"] = float(div_rate)
            data["yield"] = (div_rate / current_price) * 100
            
        return data
    except: return data

# --- V106: 混合式籌碼分佈 (外資+法人+董監) ---
@st.cache_data(ttl=86400)
def get_chip_distribution_v2(stock_id, info_data):
    data = { "foreign": 0.0, "directors": 0.0, "domestic_inst": 0.0, "valid": False }
    
    # 1. 董監 (YF)
    try:
        insider = info_data.get('heldPercentInsiders', 0)
        if insider: data['directors'] = insider * 100
    except: pass

    # 2. 外資 (FinMind)
    try:
        if stock_id.isdigit():
            from FinMind.data import DataLoader
            dl = DataLoader()
            start_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
            df_f = dl.taiwan_stock_total_foreign_and_chinese_investment_shares(stock_id=stock_id, start_date=start_date)
            if not df_f.empty:
                data['foreign'] = df_f.iloc[-1]['ForeignInvestmentSharesRatio']
                data['valid'] = True
    except: pass

    # 3. 國內法人 (YF 機構 - FinMind 外資)
    try:
        total_inst = info_data.get('heldPercentInstitutions', 0) * 100
        if data['foreign'] > 0:
            data['domestic_inst'] = max(0, total_inst - data['foreign'])
        elif data['foreign'] == 0 and total_inst > 0:
            data['foreign'] = total_inst * 0.6 # 估算
            data['domestic_inst'] = total_inst * 0.4
        
        if data['foreign'] > 0 or data['domestic_inst'] > 0 or data['directors'] > 0:
            data['valid'] = True
    except: pass
    
    return data

# --- V98 Legacy Chips (用於 AI 訊號) ---
@st.cache_data(ttl=3600)
def get_chip_data(stock_id):
    try:
        if not stock_id.isdigit(): return None
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

def get_color_settings(code):
    return {'up': 'red', 'down': 'green', 'delta': 'inverse'}

def add_history(user, text): pass 
def save_scan_results(stype, codes):
    with open(f"scan_{stype}.json", 'w') as f: json.dump(codes, f)
def load_scan_results(stype):
    if os.path.exists(f"scan_{stype}.json"):
        with open(f"scan_{stype}.json", 'r') as f: return json.load(f)
    return []

def save_comment(user, msg):
    if not os.path.exists(COMMENTS_FILE): df = pd.DataFrame(columns=['User', 'Nickname', 'Message', 'Time'])
    else: df = pd.read_csv(COMMENTS_FILE)
    new_row = {'User': user, 'Nickname': get_user_nickname(user), 'Message': msg, 'Time': datetime.now().strftime("%Y-%m-%d %H:%M")}
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(COMMENTS_FILE, index=False)

def get_comments():
    if os.path.exists(COMMENTS_FILE): return pd.read_csv(COMMENTS_FILE)
    return pd.DataFrame(columns=['User', 'Nickname', 'Message', 'Time'])

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
