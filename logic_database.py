# logic_database.py
# V120: 資料核心

import pandas as pd
import twstock
import yfinance as yf
import os
import json
import re
import streamlit as st
from datetime import datetime, timedelta, timezone

try:
    from deep_translator import GoogleTranslator
    HAS_TRANSLATOR = True
except ImportError: HAS_TRANSLATOR = False

def get_data_from_voidful(code):
    try:
        url = f"https://raw.githubusercontent.com/voidful/tw_stocker/main/data/{code}.csv"
        df = pd.read_csv(url, index_col='Datetime', parse_dates=True)
        df.columns = [c.capitalize() for c in df.columns]
        if df.index.tz is not None: df.index = df.index.tz_localize(None)
        if 'Volume' not in df.columns and 'volume' in df.columns: df.rename(columns={'volume': 'Volume'}, inplace=True)
        df = df[df['Volume'] > 0]
        return df
    except: return pd.DataFrame()

def generate_fallback_info(code, name, sector): return "" 

def translate_text(text):
    if not text or "自動生成" in text: return text
    if not HAS_TRANSLATOR: return text
    try: return GoogleTranslator(source='auto', target='zh-TW').translate(text[:1000])
    except: return text

@st.cache_data(ttl=300, show_spinner=False)
def get_stock_data(code):
    try:
        code = str(code).upper().strip(); is_tw = code.isdigit() 
        stock_info = {'name': code, 'code': code, 'longBusinessSummary': "", 'sector': "-", 'industry': "-", 'trailingEps': 0.0, 'trailingPE': 0.0}
        if is_tw and code in twstock.codes:
            stock_info['name'] = twstock.codes[code].name
            stock_info['sector'] = twstock.codes[code].group
        
        df = pd.DataFrame(); data_source = "fail"
        if is_tw:
            for suffix in ['.TW', '.TWO']:
                try:
                    t = yf.Ticker(f"{code}{suffix}")
                    df = t.history(period="1y", interval="1d", auto_adjust=True)
                    if not df.empty:
                        data_source = "yahoo"
                        try:
                           if t.info:
                               stock_info['longBusinessSummary'] = t.info.get('longBusinessSummary', "")
                               stock_info['trailingEps'] = t.info.get('trailingEps', 0.0)
                               stock_info['trailingPE'] = t.info.get('trailingPE', 0.0)
                        except: pass
                        break
                except: continue
        else:
            t = yf.Ticker(code)
            df = t.history(period="1y", interval="1d", auto_adjust=True)
            if not df.empty: data_source = "yahoo"

        if df.empty and is_tw:
            df = get_data_from_voidful(code)
            if not df.empty: data_source = "github_voidful"

        if not df.empty and df.index.tz is not None: df.index = df.index.tz_localize(None)
        return code, stock_info, df, data_source
    except: return code, stock_info, None, "fail"

def get_realtime_data(df, code):
    fake_rt = {'latest_trade_price': 0, 'high': 0, 'low': 0, 'accumulate_trade_volume': 0, 'previous_close': 0}
    try:
        code = str(code).upper().strip(); is_tw = code.isdigit()
        latest_price=0; high=0; low=0; vol=0; b_p=[]; b_v=[]; a_p=[]; a_v=[]
        
        if is_tw:
            real = twstock.realtime.get(code)
            if real['success']:
                rt = real['realtime']
                if rt['latest_trade_price'] != '-':
                    latest_price = float(rt['latest_trade_price'])
                    high = float(rt['high']); low = float(rt['low'])
                    vol = float(rt['accumulate_trade_volume']) * 1000
                    try:
                        b_p = [float(x) for x in rt.get('best_bid_price', [])[:5] if x!='-']
                        b_v = [int(x) for x in rt.get('best_bid_volume', [])[:5] if x!='-']
                        a_p = [float(x) for x in rt.get('best_ask_price', [])[:5] if x!='-']
                        a_v = [int(x) for x in rt.get('best_ask_volume', [])[:5] if x!='-']
                    except: pass
        else:
            t = yf.Ticker(code); fast = t.fast_info
            if fast.last_price: latest_price = fast.last_price; high=fast.day_high; low=fast.day_low; vol=fast.last_volume

        new_df = df.copy() if df is not None else pd.DataFrame()
        if not new_df.empty and latest_price > 0:
            last_idx = new_df.index[-1]
            if is_tw: tz = timezone(timedelta(hours=8))
            else: tz = timezone(timedelta(hours=-4))
            now_date = datetime.now(tz).date()
            if last_idx.date() < now_date:
                new_row = pd.DataFrame([{'Open': latest_price, 'High': high, 'Low': low, 'Close': latest_price, 'Volume': vol}], index=[pd.Timestamp(now_date)])
                new_df = pd.concat([new_df, new_row])
            else:
                new_df.at[last_idx, 'Close'] = latest_price
                new_df.at[last_idx, 'High'] = max(new_df.at[last_idx, 'High'], high)
                new_df.at[last_idx, 'Low'] = min(new_df.at[last_idx, 'Low'], low)
                new_df.at[last_idx, 'Volume'] = vol

        rt_pack = {'bid_price': b_p, 'bid_volume': b_v, 'ask_price': a_p, 'ask_volume': a_v}
        return new_df, None, rt_pack
    except: return df, None, fake_rt

# 輔助函式
def get_color_settings(code): return {'up': '#FF2B2B', 'down': '#00E050', 'delta': 'inverse'}
def solve_stock_id(val):
    val = str(val).strip().upper()
    if val.isdigit(): return (val, twstock.codes[val].name) if val in twstock.codes else (val, val)
    for c, d in twstock.codes.items():
        if d.type in ["股票", "ETF"] and val == d.name: return c, d.name
    return None, None
