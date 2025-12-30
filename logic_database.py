# logic_database.py
# V2.0: FinMind 引擎核心 (台股專用) + yfinance (美股備用)

import pandas as pd
import yfinance as yf
import os
import json
import re
import datetime
from datetime import timedelta, timezone
from FinMind.data import DataLoader

# --- 初始化設定 ---
def init_db():
    # 這裡可以放 User 登入系統的初始化，若不需要可保持簡單
    pass

# --- 輔助：FinMind 數據處理 ---
def get_finmind_history(code, days=365):
    """使用 FinMind 抓取台股歷史日線資料"""
    try:
        dl = DataLoader()
        # 設定日期範圍
        end_date = datetime.datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
        
        # 抓取數據
        df = dl.taiwan_stock_daily(
            stock_id=code,
            start_date=start_date,
            end_date=end_date
        )
        
        if df.empty:
            return pd.DataFrame()

        # FinMind 欄位轉換為系統標準格式 (Open, High, Low, Close, Volume)
        # FinMind 原欄位: date, stock_id, Trading_Volume, Trading_money, open, max, min, close, spread, Trading_turnover
        df = df.rename(columns={
            'date': 'Date',
            'open': 'Open',
            'max': 'High',
            'min': 'Low',
            'close': 'Close',
            'Trading_Volume': 'Volume'
        })
        
        # 設定 Index 為 Datetime
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.set_index('Date')
        
        # 確保數據類型正確
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].astype(float)
        
        return df
    except Exception as e:
        print(f"FinMind History Error: {e}")
        return pd.DataFrame()

def get_finmind_realtime(code):
    """使用 FinMind 抓取台股即時快照 (Snapshot)"""
    try:
        dl = DataLoader()
        df = dl.taiwan_stock_tick_snapshot(stock_id=code)
        
        if df.empty:
            return None
            
        # FinMind Snapshot 格式
        # date, stock_id, open, high, low, close, change_price, change_rate, average_price, volume, total_volume...
        # 還有最佳五檔: best_bid_price, best_bid_volume ... (是列表格式)
        
        data = df.iloc[0]
        return data
    except Exception as e:
        print(f"FinMind Realtime Error: {e}")
        return None

# --- 核心：取得股票數據 (整合 FinMind + Yahoo) ---
def get_stock_data(code):
    """
    統一入口：
    - 台股 (純數字)：優先使用 FinMind
    - 美股 (英文)：使用 yfinance
    """
    code = str(code).upper().strip()
    is_tw = code.isdigit()
    
    stock_info = {
        'name': code, 'code': code, 
        'longBusinessSummary': "", 
        'sector': "台股" if is_tw else "美股", 
        'industry': "-",
        'trailingEps': 0.0, 'trailingPE': 0.0
    }
    
    df = pd.DataFrame()
    source = "fail"

    try:
        if is_tw:
            # === 台股策略：FinMind ===
            # 1. 抓歷史
            df = get_finmind_history(code)
            
            if not df.empty:
                source = "FinMind"
                # 嘗試抓取一些基本資訊 (FinMind 基本面資料需要另外的 API，這裡先維持簡單，或用 yf 補資訊)
                # 為了讓使用者體驗更好，我們用 yfinance "只抓資訊" 不抓價格
                try:
                    t = yf.Ticker(f"{code}.TW")
                    info = t.info
                    if info:
                        stock_info['name'] = info.get('longName', code)
                        stock_info['longBusinessSummary'] = info.get('longBusinessSummary', "")
                        stock_info['sector'] = info.get('sector', "台股")
                        stock_info['trailingEps'] = info.get('trailingEps', 0.0)
                        stock_info['trailingPE'] = info.get('trailingPE', 0.0)
                except:
                    pass # 如果 yf 連資訊都抓不到，就維持預設
            else:
                # Fallback: 如果 FinMind 掛了，回頭試試 Yahoo
                t = yf.Ticker(f"{code}.TW")
                df = t.history(period="1y")
                if not df.empty: source = "Yahoo(Backup)"

        else:
            # === 美股策略：Yahoo Finance ===
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

        # 移除時區
        if not df.empty and df.index.tz is not None:
            df.index = df.index.tz_localize(None)

        return code, stock_info, df, source

    except Exception as e:
        print(f"Get Data Critical Error: {e}")
        return code, stock_info, None, "fail"

# --- 核心：取得即時數據 (FinMind Snapshot) ---
def get_realtime_data(df_hist, code):
    """
    整合 FinMind Snapshot 取得盤中即時報價與五檔
    """
    code = str(code).upper().strip()
    is_tw = code.isdigit()
    
    # 預設空包
    rt_pack = {'bid_price': [], 'bid_volume': [], 'ask_price': [], 'ask_volume': []}
    fake_rt = {'latest_trade_price': 0, 'high': 0, 'low': 0, 'accumulate_trade_volume': 0, 'previous_close': 0}
    
    latest_price = 0
    high = 0
    low = 0
    vol = 0
    
    try:
        if is_tw:
            # 使用 FinMind Snapshot
            data = get_finmind_realtime(code)
            if data is not None:
                latest_price = float(data['close']) if data['close'] else 0
                high = float(data['high']) if data['high'] else latest_price
                low = float(data['low']) if data['low'] else latest_price
                vol = float(data['total_volume']) if data['total_volume'] else 0
                
                # 處理五檔 (FinMind 回傳的是列表)
                if 'best_bid_price' in data and data['best_bid_price']:
                    rt_pack['bid_price'] = data['best_bid_price']
                    rt_pack['bid_volume'] = data['best_bid_volume']
                    rt_pack['ask_price'] = data['best_ask_price']
                    rt_pack['ask_volume'] = data['best_ask_volume']
            else:
                # 盤後或抓不到，用歷史資料最後一筆
                if df_hist is not None and not df_hist.empty:
                    return df_hist, None, _make_fake_from_df(df_hist)
        else:
            # 美股 (Yahoo)
            t = yf.Ticker(code)
            fast = t.fast_info
            if fast.last_price:
                latest_price = fast.last_price
                high = fast.day_high
                low = fast.day_low
                vol = fast.last_volume

        # 合併到 DataFrame
        new_df = df_hist.copy() if df_hist is not None else pd.DataFrame()
        
        if not new_df.empty and latest_price > 0:
            last_idx = new_df.index[-1]
            now_date = datetime.datetime.now().date()
            
            # 判斷是否為新的一天 (簡單判斷)
            if last_idx.date() < now_date:
                # 新增一行
                new_row = pd.DataFrame([{
                    'Open': latest_price, 'High': high, 'Low': low, 'Close': latest_price, 'Volume': vol
                }], index=[pd.Timestamp(now_date)])
                new_df = pd.concat([new_df, new_row])
            else:
                # 更新最後一行
                new_df.at[last_idx, 'Close'] = latest_price
                new_df.at[last_idx, 'High'] = max(new_df.at[last_idx, 'High'], high)
                new_df.at[last_idx, 'Low'] = min(new_df.at[last_idx, 'Low'], low)
                new_df.at[last_idx, 'Volume'] = vol

        return new_df, None, rt_pack

    except Exception as e:
        print(f"RT Logic Error: {e}")
        if df_hist is not None and not df_hist.empty:
            return df_hist, None, _make_fake_from_df(df_hist)
        return df_hist, None, fake_rt

def _make_fake_from_df(df):
    latest = df.iloc[-1]
    return {
        'bid_price': [], 'bid_volume': [], 'ask_price': [], 'ask_volume': []
    }

# --- 其他輔助 ---
def get_color_settings(code): return {'up': '#FF2B2B', 'down': '#00E050', 'delta': 'inverse'}

def solve_stock_id(val):
    val = str(val).strip().upper()
    # 簡單判斷：如果是數字回傳數字，英文回傳英文
    # 若要進階名稱搜尋，需要一份股票代碼表 (這裡簡化處理)
    if val.isdigit(): return val, val 
    return val, val

# 翻譯輔助 (保留原本功能)
def translate_text(text):
    if not text: return ""
    try:
        return GoogleTranslator(source='auto', target='zh-TW').translate(text[:1000])
    except: return text
