# logic_database.py
# V3.1: 強化基本面抓取 + 混合數據源引擎

import pandas as pd
import yfinance as yf
import datetime
from datetime import timedelta, timezone
from FinMind.data import DataLoader
import streamlit as st

# 初始化
def init_db(): pass

# 輔助：FinMind 數據處理
def get_finmind_history(code, days=365):
    try:
        dl = DataLoader()
        end_date = datetime.datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
        
        df = dl.taiwan_stock_daily(stock_id=code, start_date=start_date, end_date=end_date)
        if df.empty: return pd.DataFrame()

        df = df.rename(columns={'date': 'Date', 'open': 'Open', 'max': 'High', 'min': 'Low', 'close': 'Close', 'Trading_Volume': 'Volume'})
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.set_index('Date')
        return df[['Open', 'High', 'Low', 'Close', 'Volume']].astype(float)
    except: return pd.DataFrame()

def get_finmind_realtime(code):
    try:
        dl = DataLoader()
        df = dl.taiwan_stock_tick_snapshot(stock_id=code)
        if df.empty: return None
        return df.iloc[0]
    except: return None

# 核心：取得股票數據 (混合雙引擎)
@st.cache_data(ttl=300, show_spinner=False)
def get_stock_data(code):
    code = str(code).upper().strip(); is_tw = code.isdigit()
    
    # 預設空資料結構
    stock_info = {
        'name': code, 
        'code': code, 
        'longBusinessSummary': "暫無詳細資料", 
        'sector': "台股" if is_tw else "美股", 
        'industry': "-", 
        'trailingEps': 0.0, 
        'trailingPE': 0.0,
        'marketCap': 0
    }
    df = pd.DataFrame(); source = "fail"

    try:
        if is_tw:
            # 1. 先用 FinMind 抓 K 線 (最準確)
            df = get_finmind_history(code)
            if not df.empty:
                source = "FinMind"
            else:
                # 備案：Yahoo 抓 K 線
                t = yf.Ticker(f"{code}.TW")
                df = t.history(period="1y")
                if not df.empty: source = "Yahoo(Backup)"

            # 2. 【關鍵修改】無論如何都用 Yahoo 嘗試補強「基本面資料」
            # 因為 FinMind 免費版沒有公司介紹 API，Yahoo 有
            try:
                t = yf.Ticker(f"{code}.TW")
                info = t.info
                if info:
                    # 嘗試抓中文名，沒有就用英文
                    stock_info['name'] = info.get('longName', code)
                    stock_info['longBusinessSummary'] = info.get('longBusinessSummary', "暫無詳細業務介紹")
                    stock_info['sector'] = info.get('sector', "台股")
                    stock_info['industry'] = info.get('industry', "-")
                    stock_info['trailingEps'] = info.get('trailingEps', 0.0)
                    stock_info['trailingPE'] = info.get('trailingPE', 0.0)
                    stock_info['marketCap'] = info.get('marketCap', 0)
            except Exception as e:
                print(f"Yahoo Info Error: {e}")

        else:
            # 美股策略：全靠 Yahoo
            t = yf.Ticker(code)
            df = t.history(period="1y")
            if not df.empty:
                source = "Yahoo"
                try:
                    info = t.info
                    stock_info['name'] = info.get('longName', code)
                    stock_info['longBusinessSummary'] = info.get('longBusinessSummary', "")
                    stock_info['sector'] = info.get('sector', "美股")
                    stock_info['trailingEps'] = info.get('trailingEps', 0.0)
                    stock_info['trailingPE'] = info.get('trailingPE', 0.0)
                except: pass

        if not df.empty and df.index.tz is not None: df.index = df.index.tz_localize(None)
        return code, stock_info, df, source
    except: return code, stock_info, None, "fail"

# 核心：取得即時數據
def get_realtime_data(df_hist, code):
    code = str(code).upper().strip(); is_tw = code.isdigit()
    rt_pack = {'bid_price': [], 'bid_volume': [], 'ask_price': [], 'ask_volume': []}
    
    # 預設值
    latest_price=0; high=0; low=0; open_p=0; vol=0
    
    try:
        if is_tw:
            data = get_finmind_realtime(code)
            if data is not None:
                latest_price = float(data['close']) if data['close'] else 0
                high = float(data['high']) if data['high'] else latest_price
                low = float(data['low']) if data['low'] else latest_price
                open_p = float(data['open']) if data['open'] else latest_price
                vol = float(data['total_volume']) if data['total_volume'] else 0
                if 'best_bid_price' in data and data['best_bid_price']:
                    rt_pack['bid_price'] = data['best_bid_price']
                    rt_pack['bid_volume'] = data['best_bid_volume']
                    rt_pack['ask_price'] = data['best_ask_price']
                    rt_pack['ask_volume'] = data['best_ask_volume']
        else:
            t = yf.Ticker(code); fast = t.fast_info
            if fast.last_price: 
                latest_price=fast.last_price; high=fast.day_high; low=fast.day_low; open_p=fast.open; vol=fast.last_volume

        new_df = df_hist.copy() if df_hist is not None else pd.DataFrame()
        if not new_df.empty and latest_price > 0:
            last_idx = new_df.index[-1]
            now_date = datetime.datetime.now().date()
            if last_idx.date() < now_date:
                new_row = pd.DataFrame([{'Open': open_p, 'High': high, 'Low': low, 'Close': latest_price, 'Volume': vol}], index=[pd.Timestamp(now_date)])
                new_df = pd.concat([new_df, new_row])
            else:
                new_df.at[last_idx, 'Close'] = latest_price
                new_df.at[last_idx, 'High'] = max(new_df.at[last_idx, 'High'], high)
                new_df.at[last_idx, 'Low'] = min(new_df.at[last_idx, 'Low'], low)
                new_df.at[last_idx, 'Volume'] = vol

        return new_df, None, rt_pack
    except: 
        # 失敗時回傳歷史最後一筆作為假即時
        return df_hist, None, {'bid_price': [], 'bid_volume': [], 'ask_price': [], 'ask_volume': []}

# 輔助
def get_color_settings(code): return {'up': '#FF2B2B', 'down': '#00E050', 'delta': 'inverse'}
def solve_stock_id(val):
    val = str(val).strip().upper()
    if val.isdigit(): return val, val 
    return val, val
def translate_text(text):
    try:
        from deep_translator import GoogleTranslator
        if not text or len(text) < 2: return ""
        return GoogleTranslator(source='auto', target='zh-TW').translate(text[:1000])
    except: return text
