# logic_database.py
# 資料處理核心：負責抓取股票資料、使用者資料庫存取

import pandas as pd
import twstock
import yfinance as yf
import os
import json
import re
from datetime import datetime

USERS_FILE = 'stock_users.json'
WATCHLIST_FILE = 'stock_watchlist.json'
COMMENTS_FILE = 'stock_comments.csv'

# --- 資料庫初始化 ---
def init_db():
    users = {}
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f: users = json.load(f)
        except: users = {}

    users["admin"] = {"password": "admin888", "name": "超級管理員"}
    with open(USERS_FILE, 'w', encoding='utf-8') as f: json.dump(users, f, ensure_ascii=False)

    if not os.path.exists(WATCHLIST_FILE):
        with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f: json.dump({}, f)
            
    if not os.path.exists(COMMENTS_FILE):
        df = pd.DataFrame(columns=['User', 'Nickname', 'Message', 'Time'])
        df.to_csv(COMMENTS_FILE, index=False)

init_db()

# --- 股票資料獲取 (雙核心) ---
def get_stock_data(code):
    try:
        code = str(code).upper().strip()
        is_tw = code.isdigit() 
        
        class FakeStockInfo:
            def __init__(self, code, name):
                self.info = {'name': name, 'code': code, 'longBusinessSummary': f"{name} ({code}) - 資料來源: Yahoo Finance"}

        if is_tw:
            name = code
            if code in twstock.codes: name = twstock.codes[code].name
            fake_stock = FakeStockInfo(code, name)
            df = yf.download(f"{code}.TW", period="1y", interval="1d", progress=False)
            if df.empty: df = yf.download(f"{code}.TWO", period="1y", interval="1d", progress=False)
        else:
            fake_stock = FakeStockInfo(code, code) 
            try:
                t = yf.Ticker(code); info = t.info
                if 'longName' in info:
                    fake_stock.info['name'] = info['longName']
                    fake_stock.info['longBusinessSummary'] = info.get('longBusinessSummary', '美股企業資料')
            except: pass
            df = yf.download(code, period="1y", interval="1d", progress=False)

        if df.empty: return code, None, None, "fail"
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        if len(df) < 5: return code, None, None, "fail"

        return code, fake_stock, df, "yahoo"
    except Exception as e:
        print(f"Error: {e}")
        return code, None, None, "fail"

def get_realtime_data(df, code):
    if df is None or df.empty: return df, None, None
    try:
        code = str(code).upper().strip()
        is_tw = code.isdigit()
        latest_price = 0; high = 0; low = 0; vol = 0
        
        if is_tw:
            real = twstock.realtime.get(code)
            if real['success']:
                rt = real['realtime']
                if rt['latest_trade_price'] != '-' and rt['latest_trade_price'] is not None:
                    latest_price = float(rt['latest_trade_price'])
                    high = float(rt['high']); low = float(rt['low'])
                    vol = float(rt['accumulate_trade_volume']) * 1000
                else: return df, None, _make_fake_rt(df)
            else: return df, None, _make_fake_rt(df)
        else:
            t = yf.Ticker(code); fast = t.fast_info
            if fast.last_price:
                latest_price = fast.last_price
                high = fast.day_high if fast.day_high else latest_price
                low = fast.day_low if fast.day_low else latest_price
                vol = fast.last_volume if fast.last_volume else 0
            else: return df, None, _make_fake_rt(df)

        rt_pack = {
            'latest_trade_price': latest_price, 'high': high, 'low': low, 'accumulate_trade_volume': vol, 
            'previous_close': df.iloc[-2]['Close'] if len(df)>1 else latest_price
        }
        return df, None, rt_pack
    except: return df, None, _make_fake_rt(df)

def _make_fake_rt(df):
    latest = df.iloc[-1]
    return {
        'latest_trade_price': latest['Close'], 'high': latest['High'], 'low': latest['Low'],
        'accumulate_trade_volume': latest['Volume'], 'previous_close': df.iloc[-2]['Close'] if len(df)>1 else latest['Open']
    }

def get_color_settings(code):
    return {'up': '#FF2B2B', 'down': '#00E050', 'delta': 'inverse'} # 統一紅漲綠跌

# --- 輔助函式 ---
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
def solve_stock_id(val):
    val = str(val).strip().upper()
    if not val: return None, None
    if val.isdigit() and len(val) == 4:
        name = val
        if val in twstock.codes: name = twstock.codes[val].name
        return val, name
    if re.match(r'^[A-Z]+$', val): return val, val 
    for code, data in twstock.codes.items():
        if data.type in ["股票", "ETF"]:
            if val == data.name: return code, data.name
    for code, data in twstock.codes.items():
        if data.type in ["股票", "ETF"]:
            if val in data.name: return code, data.name
    return None, None
