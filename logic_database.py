# logic_database.py
# V110: 資料核心 (修復 NameError 與 資料同步)

import pandas as pd
import twstock
import yfinance as yf
import os
import json
import re  # <--- V110 修正：補上這個遺漏的 import
import streamlit as st
from datetime import datetime, timedelta, timezone

USERS_FILE = 'stock_users.json'
WATCHLIST_FILE = 'stock_watchlist.json'
COMMENTS_FILE = 'stock_comments.csv'

# --- 輔助函數 (定義在最上方以免找不到) ---
def _make_fake_rt(df):
    """當無法取得即時資料時，回傳歷史最後一筆作為備用"""
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

# --- 股票數據核心 (Cache 歷史資料) ---
@st.cache_data(ttl=300, show_spinner=False)
def get_stock_data(code):
    try:
        code = str(code).upper().strip()
        is_tw = code.isdigit() 
        
        # 使用字典 (Dict) 傳遞資訊，避免 Class Pickling Error
        stock_info = {'name': code, 'code': code, 'longBusinessSummary': f"{code} - 資料來源: Yahoo Finance"}

        if is_tw:
            name = code
            if code in twstock.codes: name = twstock.codes[code].name
            stock_info['name'] = name
            stock_info['longBusinessSummary'] = f"{name} ({code}) - 台股資料"
            df = yf.download(f"{code}.TW", period="1y", interval="1d", progress=False)
            if df.empty: df = yf.download(f"{code}.TWO", period="1y", interval="1d", progress=False)
        else:
            try:
                t = yf.Ticker(code)
                stock_info['name'] = code 
            except: pass
            df = yf.download(code, period="1y", interval="1d", progress=False)

        if df.empty: return code, {}, None, "fail"
        
        # 資料清洗
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df.index = pd.to_datetime(df.index)
        
        if len(df) < 5: return code, {}, None, "fail"
        return code, stock_info, df, "yahoo"
    except Exception as e:
        print(f"History Error: {e}")
        return code, {}, None, "fail"

# --- 即時資料處理 (V110: 智慧縫合邏輯) ---
def get_realtime_data(df, code):
    if df is None or df.empty: return df, None, _make_fake_rt(df)
    
    try:
        code = str(code).upper().strip()
        is_tw = code.isdigit()
        
        latest_price = 0; high = 0; low = 0; vol = 0
        
        # 1. 抓取報價
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

        # 2. 智慧縫合 (Smart Stitching)
        # 判斷最後一筆資料的日期
        new_df = df.copy()
        last_idx = df.index[-1]
        last_date = last_idx.date()
        
        # 設定當下時間
        if is_tw:
            tz = timezone(timedelta(hours=8))
            now_date = datetime.now(tz).date()
        else:
            tz = timezone(timedelta(hours=-4)) # 美東
            now_date = datetime.now(tz).date()
            
        # 如果歷史資料停留在昨天 (或更早)，則新增一筆今天的 K 棒
        if last_date < now_date:
            new_idx = pd.Timestamp(now_date)
            # 建立新的一行 DataFrame
            new_row_df = pd.DataFrame([{
                'Open': latest_price, # 暫用最新價當開盤
                'High': high if high > 0 else latest_price,
                'Low': low if low > 0 else latest_price,
                'Close': latest_price,
                'Volume': vol
            }], index=[new_idx])
            new_df = pd.concat([new_df, new_row_df])
        else:
            # 還是同一天，更新最後一筆
            new_df.at[last_idx, 'Close'] = latest_price
            if high > 0: new_df.at[last_idx, 'High'] = max(new_df.at[last_idx, 'High'], high)
            if low > 0: new_df.at[last_idx, 'Low'] = min(new_df.at[last_idx, 'Low'], low)
            new_df.at[last_idx, 'Volume'] = vol 
        
        rt_pack = {
            'latest_trade_price': latest_price, 'high': high, 'low': low, 'accumulate_trade_volume': vol, 
            'previous_close': df.iloc[-2]['Close'] if len(df)>1 else df.iloc[-1]['Open']
        }
        return new_df, None, rt_pack
    except Exception as e:
        print(f"RT Error: {e}")
        return df, None, _make_fake_rt(df)

def get_color_settings(code):
    return {'up': '#FF2B2B', 'down': '#00E050', 'delta': 'inverse'}

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

# 搜尋邏輯 (V110: 使用 re)
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
