# logic_database.py
# V115: 資料核心 (修復 lxml 依賴 + 強制中文名稱備援)

import pandas as pd
import twstock
import yfinance as yf
import os
import json
import re
import streamlit as st
from datetime import datetime, timedelta, timezone

# 引入翻譯 (選用)
try:
    from deep_translator import GoogleTranslator
    HAS_TRANSLATOR = True
except ImportError:
    HAS_TRANSLATOR = False

USERS_FILE = 'stock_users.json'
WATCHLIST_FILE = 'stock_watchlist.json'
COMMENTS_FILE = 'stock_comments.csv'

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

def translate_sector(text):
    map_dict = {
        "Technology": "科技業", "Financial Services": "金融業", "Healthcare": "醫療保健",
        "Consumer Cyclical": "循環性消費", "Industrials": "工業", "Communication Services": "通訊服務",
        "Consumer Defensive": "防禦性消費", "Energy": "能源", "Real Estate": "房地產",
        "Basic Materials": "原物料", "Utilities": "公用事業", "Semiconductors": "半導體"
    }
    return map_dict.get(text, text)

def translate_text(text):
    if not text or "暫無" in text: return text
    if not HAS_TRANSLATOR: return text
    try:
        return GoogleTranslator(source='auto', target='zh-TW').translate(text[:1000])
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

# --- 股票數據核心 (V115 強力修復) ---
@st.cache_data(ttl=300, show_spinner=False)
def get_stock_data(code):
    try:
        code = str(code).upper().strip()
        is_tw = code.isdigit() 
        
        # 1. 預設資料結構
        stock_info = {
            'name': code, 
            'code': code, 
            'longBusinessSummary': f"目前無法取得 {code} 的詳細業務說明 (可能是資料源暫時無法存取)",
            'sector': "一般產業", 
            'industry': "-",
            'trailingEps': 0.0, 
            'trailingPE': 0.0
        }

        # 2. 如果是台股，先用 twstock 強制取得正確中文名
        if is_tw and code in twstock.codes:
            stock_info['name'] = twstock.codes[code].name # 例如：旺宏
            
            # 簡單的產業判斷備援
            if code.startswith('23') or code.startswith('24'): stock_info['sector'] = "電子工業"
            elif code.startswith('28'): stock_info['sector'] = "金融業"

        # 3. 嘗試抓取 Yahoo 資料
        if is_tw:
            # 嘗試 .TW 和 .TWO
            found = False
            for suffix in ['.TW', '.TWO']:
                try:
                    t = yf.Ticker(f"{code}{suffix}")
                    df = t.history(period="1y", interval="1d", auto_adjust=True)
                    if not df.empty:
                        found = True
                        # 嘗試抓基本面
                        try:
                            info = t.info
                            if 'longBusinessSummary' in info:
                                stock_info['longBusinessSummary'] = info['longBusinessSummary']
                            if 'sector' in info:
                                stock_info['sector'] = translate_sector(info['sector'])
                            if 'industry' in info:
                                stock_info['industry'] = translate_sector(info['industry'])
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
                stock_info['longBusinessSummary'] = info.get('longBusinessSummary', stock_info['longBusinessSummary'])
                stock_info['sector'] = translate_sector(info.get('sector', '美股'))
                stock_info['industry'] = translate_sector(info.get('industry', '-'))
                stock_info['trailingEps'] = info.get('trailingEps', 0.0)
                stock_info['trailingPE'] = info.get('trailingPE', 0.0)
            except: pass

        if df.empty: return code, {}, None, "fail"
        
        # 移除時區避免錯誤
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
            
        if len(df) < 5: return code, {}, None, "fail"

        return code, stock_info, df, "yahoo"
    except Exception as e:
        print(f"History Error: {e}")
        return code, {}, None, "fail"

# --- 即時資料 ---
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
                'Open': latest_price, 'High': high, 'Low': low, 'Close': latest_price, 'Volume': vol
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

# ... (其餘函式如 get_color_settings 等保持不變) ...
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
