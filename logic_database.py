# logic_database.py
# V106: 資料核心 (極速快取架構)

import pandas as pd
import twstock
import yfinance as yf
import os
import json
import streamlit as st
from datetime import datetime, timedelta

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

# --- 股票數據核心 (V106: 加入快取機制) ---
# 設定 TTL=300秒，代表歷史 K 線 5 分鐘更新一次即可，不需要每秒更新
@st.cache_data(ttl=300, show_spinner=False)
def get_stock_data_history(code):
    """
    抓取歷史 K 線資料 (Heavy Operation)
    使用 Cache 機制，避免重複下載拖慢速度
    """
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
            # 台股歷史資料
            df = yf.download(f"{code}.TW", period="1y", interval="1d", progress=False)
            if df.empty: df = yf.download(f"{code}.TWO", period="1y", interval="1d", progress=False)
        else:
            # 美股歷史資料
            fake_stock = FakeStockInfo(code, code) 
            try:
                t = yf.Ticker(code); info = t.info
                if 'longName' in info:
                    fake_stock.info['name'] = info['longName']
                    fake_stock.info['longBusinessSummary'] = info.get('longBusinessSummary', '美股企業資料')
            except: pass
            df = yf.download(code, period="1y", interval="1d", progress=False)

        if df.empty: return code, None, None, "fail"
        
        # 資料清洗
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        # 確保索引格式正確
        df.index = pd.to_datetime(df.index)
        
        if len(df) < 5: return code, None, None, "fail"

        return code, fake_stock, df, "yahoo"
    except Exception as e:
        print(f"History Error: {e}")
        return code, None, None, "fail"

def get_realtime_data(df, code):
    """
    抓取即時報價 (Light Operation)
    這部分不快取，每次呼叫都拿最新的
    """
    if df is None or df.empty: return df, None, None
    
    try:
        code = str(code).upper().strip()
        is_tw = code.isdigit()
        
        latest_price = 0; high = 0; low = 0; vol = 0
        
        # 1. 抓取最新報價
        if is_tw:
            real = twstock.realtime.get(code)
            if real['success']:
                rt = real['realtime']
                if rt['latest_trade_price'] != '-' and rt['latest_trade_price'] is not None:
                    latest_price = float(rt['latest_trade_price'])
                    high = float(rt['high']); low = float(rt['low'])
                    vol = float(rt['accumulate_trade_volume']) * 1000
                else: return _merge_fake_rt(df)
            else: return _merge_fake_rt(df)
        else:
            t = yf.Ticker(code); fast = t.fast_info
            if fast.last_price:
                latest_price = fast.last_price
                high = fast.day_high if fast.day_high else latest_price
                low = fast.day_low if fast.day_low else latest_price
                vol = fast.last_volume if fast.last_volume else 0
            else: return _merge_fake_rt(df)

        # 2. 將最新報價「縫合」進 DataFrame (V106 關鍵)
        # 這樣畫圖時才會看到最新那根 K 棒在跳動
        last_idx = df.index[-1]
        now_date = datetime.now().date()
        df_last_date = last_idx.date()
        
        # 如果最後一筆是今天的日期，直接更新；如果不是，新增一筆 (或者是 Yahoo 還沒收盤的狀況)
        # 為了簡化與效能，我們直接更新最後一筆 (假設 Yahoo 有給出今天的開盤 K)
        # 或是如果發現最新價與收盤價差異太大，代表是新的一天? 
        # 簡單策略：直接用最新價覆蓋 Close, 更新 High/Low
        
        # 為了避免 SettingWithCopyWarning，使用 copy
        new_df = df.copy()
        
        new_df.at[last_idx, 'Close'] = latest_price
        new_df.at[last_idx, 'High'] = max(new_df.at[last_idx, 'High'], high)
        new_df.at[last_idx, 'Low'] = min(new_df.at[last_idx, 'Low'], low)
        new_df.at[last_idx, 'Volume'] = vol # 更新量
        
        rt_pack = {
            'latest_trade_price': latest_price, 'high': high, 'low': low, 'accumulate_trade_volume': vol, 
            'previous_close': df.iloc[-2]['Close'] if len(df)>1 else df.iloc[-1]['Open']
        }
        
        return new_df, None, rt_pack

    except Exception as e:
        print(f"Realtime Error: {e}")
        return _merge_fake_rt(df)

def _merge_fake_rt(df):
    latest = df.iloc[-1]
    rt_pack = {
        'latest_trade_price': latest['Close'], 'high': latest['High'], 'low': latest['Low'],
        'accumulate_trade_volume': latest['Volume'], 
        'previous_close': df.iloc[-2]['Close'] if len(df)>1 else latest['Open']
    }
    return df, None, rt_pack

def get_color_settings(code):
    return {'up': '#FF2B2B', 'down': '#00E050', 'delta': 'inverse'}

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
