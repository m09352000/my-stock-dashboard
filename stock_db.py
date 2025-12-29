import pandas as pd
import twstock
import yfinance as yf
import os
import json
import re
from datetime import datetime, timedelta

# --- V101: 資料庫核心 (台美雙核心版) ---

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

# --- 2. 使用者系統 (維持不變) ---
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

# --- 3. 股票數據核心 (V101 重點升級) ---
def get_stock_data(code):
    """
    自動判斷台股/美股並抓取資料
    """
    try:
        code = str(code).upper().strip()
        is_tw = code.isdigit() # 純數字視為台股
        
        # 建立假的 Stock Info 物件，確保 UI 不會報錯
        class FakeStockInfo:
            def __init__(self, code, name):
                self.info = {
                    'name': name,
                    'code': code,
                    'longBusinessSummary': f"{name} ({code}) - 資料來源: Yahoo Finance"
                }

        # --- A. 台股處理邏輯 ---
        if is_tw:
            name = code
            if code in twstock.codes: name = twstock.codes[code].name
            
            fake_stock = FakeStockInfo(code, name)
            
            # 優先嘗試 .TW
            df = yf.download(f"{code}.TW", period="1y", interval="1d", progress=False)
            if df.empty:
                df = yf.download(f"{code}.TWO", period="1y", interval="1d", progress=False)
                
        # --- B. 美股處理邏輯 ---
        else:
            # 美股代號通常是英文 (AAPL, NVDA)
            fake_stock = FakeStockInfo(code, code) 
            
            # 嘗試抓取詳細名稱
            try:
                t = yf.Ticker(code)
                info = t.info
                if 'longName' in info:
                    fake_stock.info['name'] = info['longName']
                    fake_stock.info['longBusinessSummary'] = info.get('longBusinessSummary', '美股企業資料')
            except: pass
            
            df = yf.download(code, period="1y", interval="1d", progress=False)

        # --- 共通資料清洗 ---
        if df.empty: return code, None, None, "fail"
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        if len(df) < 5: return code, None, None, "fail"

        return code, fake_stock, df, "yahoo"
        
    except Exception as e:
        print(f"Error: {e}")
        return code, None, None, "fail"

def get_realtime_data(df, code):
    """
    V101: 雙軌即時資料 (台股抓 twstock, 美股抓 yfinance)
    """
    if df is None or df.empty: return df, None, None
    
    try:
        code = str(code).upper().strip()
        is_tw = code.isdigit()
        
        latest_price = 0
        high = 0
        low = 0
        vol = 0
        
        # A. 台股即時 (用 twstock)
        if is_tw:
            real = twstock.realtime.get(code)
            if real['success']:
                rt = real['realtime']
                if rt['latest_trade_price'] != '-' and rt['latest_trade_price'] is not None:
                    latest_price = float(rt['latest_trade_price'])
                    high = float(rt['high'])
                    low = float(rt['low'])
                    vol = float(rt['accumulate_trade_volume']) * 1000 # 轉股數
                else:
                    return df, None, _make_fake_rt(df)
            else:
                return df, None, _make_fake_rt(df)

        # B. 美股即時 (用 yfinance fast_info)
        else:
            t = yf.Ticker(code)
            fast = t.fast_info
            if fast.last_price:
                latest_price = fast.last_price
                high = fast.day_high if fast.day_high else latest_price
                low = fast.day_low if fast.day_low else latest_price
                vol = fast.last_volume if fast.last_volume else 0
            else:
                 return df, None, _make_fake_rt(df)

        rt_pack = {
            'latest_trade_price': latest_price,
            'high': high,
            'low': low,
            'accumulate_trade_volume': vol, 
            'previous_close': df.iloc[-2]['Close'] if len(df)>1 else latest_price
        }
        
        return df, None, rt_pack

    except Exception as e:
        return df, None, _make_fake_rt(df)

def _make_fake_rt(df):
    latest = df.iloc[-1]
    return {
        'latest_trade_price': latest['Close'],
        'high': latest['High'],
        'low': latest['Low'],
        'accumulate_trade_volume': latest['Volume'],
        'previous_close': df.iloc[-2]['Close'] if len(df)>1 else latest['Open']
    }

def get_color_settings(code):
    # 台股：紅漲綠跌
    # 美股：綠漲紅跌 (國際慣例)
    if str(code).isdigit():
        return {'up': '#FF2B2B', 'down': '#00E050', 'delta': 'inverse'} # 台股模式
    else:
        return {'up': '#00E050', 'down': '#FF2B2B', 'delta': 'normal'} # 美股模式

# --- 其他功能維持不變 ---
def translate_text(text): return text
def save_scan_results(stype, codes):
    with open(f"scan_{stype}.json", 'w') as f: json.dump(codes, f)
def load_scan_results(stype):
    if os.path.exists(f"scan_{stype}.json"):
        with open(f"scan_{stype}.json", 'r') as f: return json.load(f)
    return []
def save_comment(user, msg):
    if not os.path.exists(COMMENTS_FILE): df = pd.DataFrame(columns=['User', 'Nickname', 'Message', 'Time'])
    else: df = pd.read_csv(COMMENTS_FILE)
    new_row = {'User': user, 'Nickname': user, 'Message': msg, 'Time': datetime.now().strftime("%Y-%m-%d %H:%M")}
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(COMMENTS_FILE, index=False)
def get_comments():
    if os.path.exists(COMMENTS_FILE): return pd.read_csv(COMMENTS_FILE)
    return pd.DataFrame(columns=['User', 'Nickname', 'Message', 'Time'])
