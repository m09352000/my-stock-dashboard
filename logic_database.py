# logic_database.py
# V112: 資料核心 (修復 lxml, re, Pickling, 資料同步)

import pandas as pd
import twstock
import yfinance as yf
import os
import json
import re  # <--- 補上了！
import streamlit as st
from datetime import datetime, timedelta, timezone

# 嘗試引入翻譯，沒有也沒關係
try:
    from deep_translator import GoogleTranslator
    HAS_TRANSLATOR = True
except ImportError:
    HAS_TRANSLATOR = False

USERS_FILE = 'stock_users.json'
WATCHLIST_FILE = 'stock_watchlist.json'
COMMENTS_FILE = 'stock_comments.csv'

# --- 中文翻譯對照表 ---
SECTOR_MAP = {
    "Technology": "科技業", "Financial Services": "金融業", "Healthcare": "醫療保健",
    "Consumer Cyclical": "循環性消費", "Industrials": "工業", "Communication Services": "通訊服務",
    "Consumer Defensive": "防禦性消費", "Energy": "能源", "Real Estate": "房地產",
    "Basic Materials": "原物料", "Utilities": "公用事業", "Semiconductors": "半導體",
    "Electronic Components": "電子零組件", "Computer Hardware": "電腦硬體"
}

# --- 輔助函數 ---
def _make_fake_rt(df):
    if df is None or df.empty: return None
    latest = df.iloc[-1]
    return {
        'latest_trade_price': latest['Close'],
        'high': latest['High'], 'low': latest['Low'],
        'accumulate_trade_volume': latest['Volume'], 
        'previous_close': df.iloc[-2]['Close'] if len(df)>1 else latest['Open']
    }

def translate_text(text):
    if not HAS_TRANSLATOR or not text: return text
    try:
        # 簡單翻譯前 500 字，避免卡住
        return GoogleTranslator(source='auto', target='zh-TW').translate(text[:500])
    except: return text

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

# --- 股票數據核心 ---
@st.cache_data(ttl=300, show_spinner=False)
def get_stock_data(code):
    try:
        code = str(code).upper().strip()
        is_tw = code.isdigit() 
        
        # 使用字典回傳，避免物件序列化錯誤
        stock_info = {
            'name': code, 'code': code, 
            'longBusinessSummary': f"暫無 {code} 詳細描述",
            'sector': "一般", 'industry': "-",
            'trailingEps': 0.0, 'trailingPE': 0.0
        }

        if is_tw:
            name = code
            if code in twstock.codes: name = twstock.codes[code].name
            stock_info['name'] = name
            
            # 優先嘗試 .TW
            found = False
            for suffix in ['.TW', '.TWO']:
                try:
                    t = yf.Ticker(f"{code}{suffix}")
                    df = t.history(period="1y", interval="1d", auto_adjust=True)
                    if not df.empty:
                        found = True
                        try:
                            info = t.info
                            stock_info['longBusinessSummary'] = info.get('longBusinessSummary', f"{name} 為台灣上市公司")
                            stock_info['sector'] = SECTOR_MAP.get(info.get('sector'), info.get('sector', '台股'))
                            stock_info['industry'] = SECTOR_MAP.get(info.get('industry'), info.get('industry', '一般'))
                            stock_info['trailingEps'] = info.get('trailingEps', 0.0)
                            stock_info['trailingPE'] = info.get('trailingPE', 0.0)
                        except: pass
                        break 
                except: continue
            
            if not found: return code, {}, None, "fail"

        else:
            # 美股
            t = yf.Ticker(code)
            df = t.history(period="1y", interval="1d", auto_adjust=True)
            try:
                info = t.info
                stock_info['name'] = info.get('longName', code)
                stock_info['longBusinessSummary'] = info.get('longBusinessSummary', '美股企業資料')
                stock_info['sector'] = SECTOR_MAP.get(info.get('sector'), info.get('sector', '美股'))
                stock_info['industry'] = SECTOR_MAP.get(info.get('industry'), info.get('industry', '-'))
                stock_info['trailingEps'] = info.get('trailingEps', 0.0)
                stock_info['trailingPE'] = info.get('trailingPE', 0.0)
            except: pass

        if df.empty: return code, {}, None, "fail"
        
        # 關鍵修復：移除時區資訊，解決 PicklingError
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
            
        if len(df) < 5: return code, {}, None, "fail"

        return code, stock_info, df, "yahoo"
    except Exception as e:
        print(f"History Error: {e}")
        return code, {}, None, "fail"

# --- 即時資料同步 (V112 強制更新) ---
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
                if rt['latest_trade_price'] and rt['latest_trade_price'] != '-':
                    latest_price = float(rt['latest_trade_price'])
                    high = float(rt['high']) if rt['high'] != '-' else latest_price
                    low = float(rt['low']) if rt['low'] != '-' else latest_price
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

        # 暴力同步：直接更新 DataFrame
        new_df = df.copy()
        last_idx = df.index[-1]
        
        # 不管日期，只要有最新價，就強制覆蓋最後一筆 Close
        # 這樣圖表上的最後一個點才會跟著大數字跳動
        new_df.at[last_idx, 'Close'] = latest_price
        new_df.at[last_idx, 'High'] = max(new_df.at[last_idx, 'High'], high)
        new_df.at[last_idx, 'Low'] = min(new_df.at[last_idx, 'Low'], low)
        new_df.at[last_idx, 'Volume'] = vol
        
        rt_pack = {
            'latest_trade_price': latest_price, 'high': high, 'low': low, 'accumulate_trade_volume': vol, 
            'previous_close': df.iloc[-2]['Close'] if len(df)>1 else df.iloc[-1]['Open']
        }
        return new_df, None, rt_pack
    except: return df, None, _make_fake_rt(df)

# ... (維持原樣的函式) ...
def get_color_settings(code): return {'up': '#FF2B2B', 'down': '#00E050', 'delta': 'inverse'}
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
