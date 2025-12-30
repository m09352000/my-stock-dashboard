# logic_database.py
# V111: 資料核心 (含基本面數據抓取)

import pandas as pd
import twstock
import yfinance as yf
import os
import json
import re
import streamlit as st
from datetime import datetime, timedelta, timezone

USERS_FILE = 'stock_users.json'
WATCHLIST_FILE = 'stock_watchlist.json'
COMMENTS_FILE = 'stock_comments.csv'

# --- 輔助函數 ---
def _make_fake_rt(df):
    if df is None or df.empty: return None
    latest = df.iloc[-1]
    return {
        'latest_trade_price': latest['Close'],
        'high': latest['High'],
        'low': latest['Low'],
        'accumulate_trade_volume': latest['Volume'], 
        'previous_close': df.iloc[-2]['Close'] if len(df)>1 else latest['Open']
    }

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

# --- 股票數據核心 (歷史資料 Cache) ---
@st.cache_data(ttl=300, show_spinner=False)
def get_stock_data(code):
    try:
        code = str(code).upper().strip()
        is_tw = code.isdigit() 
        # 預設資訊
        stock_info = {
            'name': code, 
            'code': code, 
            'longBusinessSummary': f"暫無 {code} 詳細描述",
            'sector': "N/A", 
            'industry': "N/A",
            'trailingEps': 0.0, 
            'trailingPE': 0.0
        }

        if is_tw:
            name = code
            if code in twstock.codes: name = twstock.codes[code].name
            stock_info['name'] = name
            
            # 優先嘗試 .TW
            ticker_tw = yf.Ticker(f"{code}.TW")
            df = ticker_tw.history(period="1y", interval="1d")
            
            if df.empty:
                ticker_tw = yf.Ticker(f"{code}.TWO")
                df = ticker_tw.history(period="1y", interval="1d")
            
            # 嘗試抓取 Yahoo 的基本面 (台股有時會有)
            try:
                info = ticker_tw.info
                stock_info['longBusinessSummary'] = info.get('longBusinessSummary', f"{name} 為台灣上市公司")
                stock_info['sector'] = info.get('sector', '台股')
                stock_info['industry'] = info.get('industry', '一般產業')
                stock_info['trailingEps'] = info.get('trailingEps', 0.0)
                stock_info['trailingPE'] = info.get('trailingPE', 0.0)
            except: pass

        else:
            # 美股
            t = yf.Ticker(code)
            try:
                info = t.info
                stock_info['name'] = info.get('longName', code)
                stock_info['longBusinessSummary'] = info.get('longBusinessSummary', '美股企業資料')
                stock_info['sector'] = info.get('sector', '美股')
                stock_info['industry'] = info.get('industry', '科技/金融/傳產')
                stock_info['trailingEps'] = info.get('trailingEps', 0.0)
                stock_info['trailingPE'] = info.get('trailingPE', 0.0)
            except: pass
            df = t.history(period="1y", interval="1d")

        if df.empty: return code, {}, None, "fail"
        
        # yfinance history 回傳的 index 已經是 datetime，但帶有時區，需標準化
        df.index = df.index.tz_localize(None)
        
        if len(df) < 5: return code, {}, None, "fail"

        return code, stock_info, df, "yahoo"
    except Exception as e:
        print(f"History Error: {e}")
        return code, {}, None, "fail"

# --- 即時資料 (每次都抓最新的) ---
def get_realtime_data(df, code):
    if df is None or df.empty: return df, None, _make_fake_rt(df)
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

        # 智慧縫合
        new_df = df.copy()
        last_idx = df.index[-1]
        
        if is_tw: tz = timezone(timedelta(hours=8))
        else: tz = timezone(timedelta(hours=-4))
        now_date = datetime.now(tz).date()
        last_date = last_idx.date()
        
        if last_date < now_date:
            new_idx = pd.Timestamp(now_date)
            new_row = pd.DataFrame([{
                'Open': latest_price, 'High': high if high > 0 else latest_price,
                'Low': low if low > 0 else latest_price, 'Close': latest_price, 'Volume': vol
            }], index=[new_idx])
            new_df = pd.concat([new_df, new_row])
        else:
            new_df.at[last_idx, 'Close'] = latest_price
            if high > 0: new_df.at[last_idx, 'High'] = max(new_df.at[last_idx, 'High'], high)
            if low > 0: new_df.at[last_idx, 'Low'] = min(new_df.at[last_idx, 'Low'], low)
            new_df.at[last_idx, 'Volume'] = vol 
        
        rt_pack = {
            'latest_trade_price': latest_price, 'high': high, 'low': low, 'accumulate_trade_volume': vol, 
            'previous_close': df.iloc[-2]['Close'] if len(df)>1 else df.iloc[-1]['Open']
        }
        return new_df, None, rt_pack
    except: return df, None, _make_fake_rt(df)

def get_color_settings(code):
    return {'up': '#FF2B2B', 'down': '#00E050', 'delta': 'inverse'}

def translate_text(text): 
    # 簡單翻譯映射 (如果是英文財報) - 這裡可接 Google Translate API 但為求穩定先保留原樣
    return text

# ... (其他輔助函數 save_scan_results, solve_stock_id 等維持 V110 不變) ...
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
