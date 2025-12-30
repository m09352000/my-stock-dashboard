# logic_database.py
# V115: 絕對防禦版 (名稱強制 Twstock / 錯誤全面攔截)

import pandas as pd
import twstock
import yfinance as yf
import streamlit as st
from datetime import datetime, timedelta, timezone
import random

# 翻譯模組 (選用)
try:
    from deep_translator import GoogleTranslator
    HAS_TRANSLATOR = True
except:
    HAS_TRANSLATOR = False

# --- 輔助：安全的回傳結構 ---
def get_safe_stock_info(code):
    """回傳一個絕對不會缺欄位的基本面字典"""
    return {
        'name': code,
        'code': code,
        'longBusinessSummary': f"目前無法取得 {code} 的詳細業務資料。",
        'sector': "一般產業",
        'industry': "-",
        'trailingEps': 0.0,
        'trailingPE': 0.0
    }

def translate_text(text):
    if not HAS_TRANSLATOR or not text: return text
    try:
        # 限制長度避免翻譯逾時
        return GoogleTranslator(source='auto', target='zh-TW').translate(text[:800])
    except: return text

# --- 核心：獲取股票資料 (快取) ---
@st.cache_data(ttl=300, show_spinner=False)
def get_stock_data(code):
    try:
        code = str(code).strip().upper()
        is_tw = code.isdigit()
        
        # 1. 初始化安全結構
        stock_info = get_safe_stock_info(code)
        df = pd.DataFrame()
        source = "fail"

        # 2. 名稱獲取 (Twstock 優先)
        if is_tw and code in twstock.codes:
            stock_info['name'] = twstock.codes[code].name
        
        # 3. 歷史資料獲取 (Yahoo)
        if is_tw:
            tickers = [f"{code}.TW", f"{code}.TWO"]
        else:
            tickers = [code]
            
        for t_code in tickers:
            try:
                ticker = yf.Ticker(t_code)
                temp_df = ticker.history(period="1y", interval="1d")
                
                if not temp_df.empty:
                    df = temp_df
                    source = "yahoo"
                    
                    # 順便抓基本面 (Yahoo info)
                    try:
                        info = ticker.info
                        # 如果是美股，名稱以 Yahoo 為主
                        if not is_tw: 
                            stock_info['name'] = info.get('longName', code)
                        
                        stock_info['longBusinessSummary'] = info.get('longBusinessSummary', stock_info['longBusinessSummary'])
                        stock_info['sector'] = info.get('sector', stock_info['sector'])
                        stock_info['industry'] = info.get('industry', stock_info['industry'])
                        stock_info['trailingEps'] = info.get('trailingEps', 0.0)
                        stock_info['trailingPE'] = info.get('trailingPE', 0.0)
                    except: pass
                    
                    break # 抓到就跳出
            except: continue

        # 4. 資料清洗
        if df.empty:
            return code, stock_info, None, "fail"
        
        # 移除時區 (關鍵修復 PicklingError)
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
            
        return code, stock_info, df, source

    except Exception as e:
        print(f"Global Error: {e}")
        return code, get_safe_stock_info(code), None, "fail"

# --- 核心：即時資料 (不快取) ---
def get_realtime_data(df, code):
    """
    不管歷史資料如何，強制去抓最新的報價
    """
    if df is None or df.empty: return df, None, None
    
    try:
        latest_price = df.iloc[-1]['Close']
        high = df.iloc[-1]['High']
        low = df.iloc[-1]['Low']
        vol = df.iloc[-1]['Volume']
        
        is_tw = code.isdigit()
        
        # 1. 嘗試抓取即時報價
        if is_tw:
            try:
                real = twstock.realtime.get(code)
                if real['success']:
                    rt = real['realtime']
                    # 確保不是 '-' (剛開盤或暫停交易)
                    if rt['latest_trade_price'] and rt['latest_trade_price'] != '-':
                        latest_price = float(rt['latest_trade_price'])
                        high = float(rt['high']) if rt['high'] != '-' else latest_price
                        low = float(rt['low']) if rt['low'] != '-' else latest_price
                        vol = float(rt['accumulate_trade_volume']) * 1000
            except: pass # 抓不到就用歷史最後一筆
        else:
            try:
                t = yf.Ticker(code)
                # 使用 fast_info 比較快且穩
                if hasattr(t, 'fast_info'):
                    latest_price = t.fast_info.last_price
                    high = t.fast_info.day_high
                    low = t.fast_info.day_low
                    vol = t.fast_info.last_volume
            except: pass

        # 2. 智慧縫合 (Smart Stitching)
        new_df = df.copy()
        last_idx = df.index[-1]
        
        # 判斷是否為新的一天
        # 這裡用簡單邏輯：如果現在時間 > 最後一筆時間 + 12小時，視為新的一天
        time_diff = datetime.now() - last_idx
        is_new_day = time_diff.total_seconds() > 43200 # 12小時
        
        if is_new_day and is_tw: # 台股比較需要處理這個，美股 Yahoo 通常更新快
             # 創建新索引 (今天)
             new_idx = pd.Timestamp(datetime.now().date())
             if new_idx > last_idx:
                 new_row = pd.DataFrame([{
                     'Open': latest_price, 'High': high, 'Low': low, 'Close': latest_price, 'Volume': vol
                 }], index=[new_idx])
                 new_df = pd.concat([new_df, new_row])
        else:
            # 同一天，直接覆蓋最後一筆
            new_df.at[last_idx, 'Close'] = latest_price
            new_df.at[last_idx, 'High'] = max(new_df.at[last_idx, 'High'], high)
            new_df.at[last_idx, 'Low'] = min(new_df.at[last_idx, 'Low'], low)
            new_df.at[last_idx, 'Volume'] = vol

        rt_pack = {
            'latest_trade_price': latest_price,
            'high': high,
            'low': low,
            'accumulate_trade_volume': vol,
            'previous_close': df.iloc[-2]['Close'] if len(df)>1 else df.iloc[-1]['Open']
        }
        
        return new_df, None, rt_pack

    except Exception as e:
        # 萬一出錯，回傳原始 df，不要崩潰
        return df, None, {
            'latest_trade_price': df.iloc[-1]['Close'],
            'high': df.iloc[-1]['High'],
            'low': df.iloc[-1]['Low'],
            'accumulate_trade_volume': df.iloc[-1]['Volume'],
            'previous_close': df.iloc[-2]['Close']
        }

# ... (其餘工具函式) ...
def solve_stock_id(val):
    if not val: return None, None
    val = str(val).strip().upper()
    if val.isdigit():
        name = val
        if val in twstock.codes: name = twstock.codes[val].name
        return val, name
    return val, val # 美股直接回傳

def get_color_settings(code):
    return {'up': '#FF2B2B', 'down': '#00E050', 'delta': 'inverse'}
