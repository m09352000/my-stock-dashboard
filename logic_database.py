# logic_database.py
# V120: 資料核心 (解鎖 MIS 五檔報價 + 雙源備援)

import pandas as pd
import twstock
import yfinance as yf
import os
import json
import re
import time
import random
import streamlit as st
from datetime import datetime, timedelta, timezone

# 引入翻譯
try:
    from deep_translator import GoogleTranslator
    HAS_TRANSLATOR = True
except ImportError:
    HAS_TRANSLATOR = False

USERS_FILE = 'stock_users.json'
WATCHLIST_FILE = 'stock_watchlist.json'
COMMENTS_FILE = 'stock_comments.csv'

# --- 輔助：資料來源擴充 (Voidful) ---
def get_data_from_voidful(code):
    """從 voidful/tw_stocker GitHub 資料庫抓取備用數據"""
    try:
        url = f"https://raw.githubusercontent.com/voidful/tw_stocker/main/data/{code}.csv"
        df = pd.read_csv(url, index_col='Datetime', parse_dates=True)
        df.columns = [c.capitalize() for c in df.columns]
        if df.index.tz is not None: df.index = df.index.tz_localize(None)
        if 'Volume' not in df.columns and 'volume' in df.columns:
             df.rename(columns={'volume': 'Volume'}, inplace=True)
        df = df[df['Volume'] > 0]
        return df
    except Exception:
        return pd.DataFrame()

# --- 輔助：自動生成公司介紹 ---
def generate_fallback_info(code, name, sector):
    """不顯示預設文字，保持介面乾淨"""
    return "" 

def translate_sector(text):
    map_dict = {
        "Technology": "科技業", "Financial Services": "金融業", "Healthcare": "醫療保健",
        "Consumer Cyclical": "循環性消費", "Industrials": "工業", "Communication Services": "通訊服務",
        "Consumer Defensive": "防禦性消費", "Energy": "能源", "Real Estate": "房地產",
        "Basic Materials": "原物料", "Utilities": "公用事業", "Semiconductors": "半導體",
        "Electronic Components": "電子零組件", "Computer Hardware": "電腦硬體"
    }
    return map_dict.get(text, text)

def translate_text(text):
    if not text or text.startswith("暫無") or "自動生成" in text: return text
    if not HAS_TRANSLATOR: return text
    try:
        return GoogleTranslator(source='auto', target='zh-TW').translate(text[:1000])
    except: return text

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

@st.cache_data(ttl=300, show_spinner=False)
def get_stock_data(code):
    try:
        code = str(code).upper().strip()
        is_tw = code.isdigit() 
        
        stock_info = {
            'name': code, 'code': code, 
            'longBusinessSummary': "", 
            'sector': "-", 'industry': "-",
            'trailingEps': 0.0, 'trailingPE': 0.0
        }

        if is_tw and code in twstock.codes:
            tw_data = twstock.codes[code]
            stock_info['name'] = tw_data.name
            stock_info['sector'] = tw_data.group if hasattr(tw_data, 'group') else "台股"

        df = pd.DataFrame()
        data_source = "fail"
        
        if is_tw:
            for suffix in ['.TW', '.TWO']:
                try:
                    t = yf.Ticker(f"{code}{suffix}")
                    df = t.history(period="1y", interval="1d", auto_adjust=True)
                    try:
                        info = t.info
                        if info:
                            if 'longBusinessSummary' in info and len(info['longBusinessSummary']) > 10:
                                stock_info['longBusinessSummary'] = info['longBusinessSummary']
                            if 'sector' in info: stock_info['sector'] = translate_sector(info['sector'])
                            if 'industry' in info: stock_info['industry'] = translate_sector(info['industry'])
                            stock_info['trailingEps'] = info.get('trailingEps', 0.0)
                            stock_info['trailingPE'] = info.get('trailingPE', 0.0)
                    except: pass
                    if not df.empty: 
                        data_source = "yahoo"
                        break
                except: continue
        else:
            t = yf.Ticker(code)
            df = t.history(period="1y", interval="1d", auto_adjust=True)
            try:
                info = t.info
                stock_info['name'] = info.get('longName', code)
                stock_info['longBusinessSummary'] = info.get('longBusinessSummary', "")
                stock_info['sector'] = translate_sector(info.get('sector', '美股'))
                stock_info['industry'] = translate_sector(info.get('industry', '-'))
                stock_info['trailingEps'] = info.get('trailingEps', 0.0)
                stock_info['trailingPE'] = info.get('trailingPE', 0.0)
                data_source = "yahoo"
            except: pass

        if df.empty and is_tw:
            df = get_data_from_voidful(code)
            if not df.empty:
                data_source = "github_voidful"
                if stock_info['sector'] == "-": stock_info['sector'] = "台股(GitHub源)"

        if not stock_info['longBusinessSummary']:
            stock_info['longBusinessSummary'] = generate_fallback_info(code, stock_info['name'], stock_info['sector'])

        if not df.empty and df.index.tz is not None:
            df.index = df.index.tz_localize(None)
            
        return code, stock_info, df, data_source

    except Exception as e:
        print(f"Data Error: {e}")
        return code, stock_info, None, "fail"

# --- 即時資料 (新增：解析五檔報價) ---
def get_realtime_data(df, code):
    fake_rt = {
        'latest_trade_price': 0, 'high': 0, 'low': 0, 'accumulate_trade_volume': 0,
        'previous_close': 0,
        'bid_price': [], 'bid_volume': [],
        'ask_price': [], 'ask_volume': []
    }
    
    try:
        code = str(code).upper().strip()
        is_tw = code.isdigit()
        
        latest_price = 0; high = 0; low = 0; vol = 0
        bids_p = []; bids_v = []; asks_p = []; asks_v = []
        
        if is_tw:
            # 使用 twstock (底層就是連線到 MIS 網站)
            real = twstock.realtime.get(code)
            if real['success']:
                rt = real['realtime']
                if rt['latest_trade_price'] and rt['latest_trade_price'] != '-':
                    latest_price = float(rt['latest_trade_price'])
                    high = float(rt['high']) if rt['high'] != '-' else latest_price
                    low = float(rt['low']) if rt['low'] != '-' else latest_price
                    vol = float(rt['accumulate_trade_volume']) * 1000
                    
                    # --- 🌟 抓取五檔 (MIS 獨家數據) ---
                    # twstock 回傳格式: best_bid_price=['45.25', '45.20'...]
                    try:
                        bids_p = [float(x) for x in rt.get('best_bid_price', [])[:5] if x and x != '-']
                        bids_v = [int(x) for x in rt.get('best_bid_volume', [])[:5] if x and x != '-']
                        asks_p = [float(x) for x in rt.get('best_ask_price', [])[:5] if x and x != '-']
                        asks_v = [int(x) for x in rt.get('best_ask_volume', [])[:5] if x and x != '-']
                    except: pass
                    # --------------------------------
                else:
                    if df is not None and not df.empty: return df, None, _make_fake_from_df(df)
                    return df, None, fake_rt
            else:
                if df is not None and not df.empty: return df, None, _make_fake_from_df(df)
                return df, None, fake_rt
        else:
            # 美股 (Yahoo 無五檔)
            t = yf.Ticker(code)
            fast = t.fast_info
            if fast.last_price:
                latest_price = fast.last_price
                high = fast.day_high
                low = fast.day_low
                vol = fast.last_volume
            else:
                if df is not None and not df.empty: return df, None, _make_fake_from_df(df)
                return df, None, fake_rt

        # 準備即時包
        rt_pack = {
            'latest_trade_price': latest_price,
            'high': high, 'low': low,
            'accumulate_trade_volume': vol,
            'previous_close': df.iloc[-2]['Close'] if (df is not None and len(df)>1) else latest_price,
            # 新增五檔資料
            'bid_price': bids_p, 'bid_volume': bids_v,
            'ask_price': asks_p, 'ask_volume': asks_v
        }

        new_df = df.copy() if df is not None else pd.DataFrame()
        if not new_df.empty and latest_price > 0:
            last_idx = new_df.index[-1]
            if is_tw: tz = timezone(timedelta(hours=8))
            else: tz = timezone(timedelta(hours=-4))
            now_date = datetime.now(tz).date()
            last_date = last_idx.date()
            
            if last_date < now_date:
                new_idx = pd.Timestamp(now_date)
                new_row = pd.DataFrame([{'Open': latest_price, 'High': high, 'Low': low, 'Close': latest_price, 'Volume': vol}], index=[new_idx])
                new_df = pd.concat([new_df, new_row])
            else:
                new_df.at[last_idx, 'Close'] = latest_price
                new_df.at[last_idx, 'High'] = max(new_df.at[last_idx, 'High'], high)
                new_df.at[last_idx, 'Low'] = min(new_df.at[last_idx, 'Low'], low)
                new_df.at[last_idx, 'Volume'] = vol 
        
        return new_df, None, rt_pack

    except Exception as e:
        print(f"RT Error: {e}")
        if df is not None and not df.empty: return df, None, _make_fake_from_df(df)
        return df, None, fake_rt

def _make_fake_from_df(df):
    latest = df.iloc[-1]
    return {
        'latest_trade_price': latest['Close'], 'high': latest['High'], 'low': latest['Low'],
        'accumulate_trade_volume': latest['Volume'], 
        'previous_close': df.iloc[-2]['Close'] if len(df)>1 else latest['Open'],
        'bid_price': [], 'bid_volume': [], 'ask_price': [], 'ask_volume': []
    }

# 輔助函式維持不變
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
