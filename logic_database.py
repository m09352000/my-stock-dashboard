# logic_database.py
# V118: 資料核心 (不死鳥架構 + 自動生成介紹)

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

# --- 輔助：自動生成公司介紹 (當 Yahoo 抓不到時) ---
def generate_fallback_info(code, name, sector):
    """如果抓不到資料，就自己寫一段介紹，避免空白"""
    if not sector or sector == "-": sector = "一般"
    
    desc = f"""
    **{name} ({code})** 是一家位於台灣的上市櫃公司，主要業務範疇屬於 **{sector}**。
    
    該公司在台灣股市佔有一席之地，投資人可關注其營收變化與產業趨勢。
    (註：由於資料源暫時無法取得詳細英文財報，本段文字由 AI 根據基本資料自動生成)
    """
    return desc

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

# --- 股票數據核心 (V118: 容錯機制) ---
@st.cache_data(ttl=300, show_spinner=False)
def get_stock_data(code):
    try:
        code = str(code).upper().strip()
        is_tw = code.isdigit() 
        
        # 1. 預設結構 (絕對有值)
        stock_info = {
            'name': code, 'code': code, 
            'longBusinessSummary': "", # 先留空，後面補
            'sector': "-", 'industry': "-",
            'trailingEps': 0.0, 'trailingPE': 0.0
        }

        # 2. Twstock 優先取得正確中文名
        if is_tw and code in twstock.codes:
            tw_data = twstock.codes[code]
            stock_info['name'] = tw_data.name
            stock_info['sector'] = tw_data.group if hasattr(tw_data, 'group') else "台股"

        # 3. Yahoo 抓取 (容許失敗)
        df = pd.DataFrame()
        if is_tw:
            for suffix in ['.TW', '.TWO']:
                try:
                    t = yf.Ticker(f"{code}{suffix}")
                    # 嘗試抓歷史
                    df = t.history(period="1y", interval="1d", auto_adjust=True)
                    
                    # 嘗試抓基本面
                    try:
                        info = t.info
                        if info:
                            # 如果 Yahoo 有給 summary，就用；否則等一下自動生成
                            if 'longBusinessSummary' in info and len(info['longBusinessSummary']) > 10:
                                stock_info['longBusinessSummary'] = info['longBusinessSummary']
                            
                            # 更新產業
                            if 'sector' in info: stock_info['sector'] = translate_sector(info['sector'])
                            if 'industry' in info: stock_info['industry'] = translate_sector(info['industry'])
                            
                            # 更新數據
                            stock_info['trailingEps'] = info.get('trailingEps', 0.0)
                            stock_info['trailingPE'] = info.get('trailingPE', 0.0)
                    except: pass
                    
                    if not df.empty: break
                except: continue
        else:
            # 美股
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
            except: pass

        # 4. 補完計畫：如果沒有介紹，自動生成
        if not stock_info['longBusinessSummary']:
            stock_info['longBusinessSummary'] = generate_fallback_info(code, stock_info['name'], stock_info['sector'])

        # 5. 回傳 (就算 df 是空的，也回傳 stock_info 讓標題能顯示)
        # 移除時區
        if not df.empty and df.index.tz is not None:
            df.index = df.index.tz_localize(None)
            
        return code, stock_info, df, "yahoo" # 永遠回傳 yahoo 讓程式繼續跑

    except Exception as e:
        print(f"Data Error: {e}")
        # 發生嚴重錯誤時，回傳最小可用資料
        return code, stock_info, None, "fail"

# --- 即時資料 (V118: 雙重確認) ---
def get_realtime_data(df, code):
    # 建立一個假的結構以免報錯
    fake_rt = {
        'latest_trade_price': 0, 'high': 0, 'low': 0, 'accumulate_trade_volume': 0,
        'previous_close': 0
    }
    
    try:
        code = str(code).upper().strip()
        is_tw = code.isdigit()
        
        latest_price = 0; high = 0; low = 0; vol = 0
        
        if is_tw:
            # Twstock Realtime
            real = twstock.realtime.get(code)
            if real['success']:
                rt = real['realtime']
                
                # 檢查資料有效性
                if rt['latest_trade_price'] and rt['latest_trade_price'] != '-':
                    latest_price = float(rt['latest_trade_price'])
                    high = float(rt['high']) if rt['high'] != '-' else latest_price
                    low = float(rt['low']) if rt['low'] != '-' else latest_price
                    vol = float(rt['accumulate_trade_volume']) * 1000
                else:
                    # 如果盤中抓不到，可能是剛開盤或暫停，回傳歷史最後一筆
                    if df is not None and not df.empty:
                        return df, None, _make_fake_from_df(df)
                    return df, None, fake_rt
            else:
                if df is not None and not df.empty: return df, None, _make_fake_from_df(df)
                return df, None, fake_rt
        else:
            # 美股
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
            'high': high,
            'low': low,
            'accumulate_trade_volume': vol,
            'previous_close': df.iloc[-2]['Close'] if (df is not None and len(df)>1) else latest_price
        }

        # 縫合到 DF
        new_df = df.copy() if df is not None else pd.DataFrame()
        
        if not new_df.empty:
            last_idx = new_df.index[-1]
            if is_tw: tz = timezone(timedelta(hours=8))
            else: tz = timezone(timedelta(hours=-4))
            now_date = datetime.now(tz).date()
            last_date = last_idx.date()
            
            if last_date < now_date:
                # 新增
                new_idx = pd.Timestamp(now_date)
                new_row = pd.DataFrame([{
                    'Open': latest_price, 'High': high, 'Low': low, 'Close': latest_price, 'Volume': vol
                }], index=[new_idx])
                new_df = pd.concat([new_df, new_row])
            else:
                # 更新
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
        'previous_close': df.iloc[-2]['Close'] if len(df)>1 else latest['Open']
    }

# ... (維持原樣) ...
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
