import pandas as pd
import twstock
import yfinance as yf
import os
import json
from datetime import datetime, timedelta
from deep_translator import GoogleTranslator
import streamlit as st

# --- V103: 資料庫核心 (Fix Yield & Chip Logic) ---

USERS_FILE = 'stock_users.json'
WATCHLIST_FILE = 'stock_watchlist.json'
COMMENTS_FILE = 'stock_comments.csv'

# --- 1. 初始化資料庫 ---
def init_db():
    users = {}
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                users = json.load(f)
        except: users = {}
    
    users["admin"] = {"password": "admin888", "name": "超級管理員"}
    
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False)

    if not os.path.exists(WATCHLIST_FILE):
        with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False)
            
    if not os.path.exists(COMMENTS_FILE):
        df = pd.DataFrame(columns=['User', 'Nickname', 'Message', 'Time'])
        df.to_csv(COMMENTS_FILE, index=False)

init_db()

# --- 2. 使用者系統 ---
def login_user(username, password):
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            users = json.load(f)
        if username in users:
            if str(users[username]['password']) == str(password): return True, "登入成功"
            else: return False, "密碼錯誤"
        return False, "帳號不存在"
    except Exception as e: return False, f"系統錯誤: {str(e)}"

def register_user(username, password, nickname):
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            users = json.load(f)
        if username in users: return False, "帳號已存在"
        users[username] = {"password": password, "name": nickname}
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False)
        return True, "註冊成功"
    except Exception as e: return False, str(e)

def get_user_nickname(username):
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            users = json.load(f)
        return users.get(username, {}).get('name', username)
    except: return username

# --- 3. 自選股系統 ---
def get_watchlist(username):
    try:
        with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get(username, [])
    except: return []

def update_watchlist(username, code, action="add"):
    try:
        with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        user_list = data.get(username, [])
        if action == "add":
            if code not in user_list: user_list.append(code)
        elif action == "remove":
            if code in user_list: user_list.remove(code)
        data[username] = user_list
        with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
        return True
    except: return False

# --- 4. 股票數據 (Yahoo Finance) ---
def get_stock_data(code):
    try:
        ticker = None
        df = pd.DataFrame()
        candidates = [f"{code}.TW", f"{code}.TWO"] if code.isdigit() else [code]
            
        for c in candidates:
            try:
                temp_ticker = yf.Ticker(c)
                temp_df = temp_ticker.history(period="6mo")
                if not temp_df.empty:
                    ticker = temp_ticker
                    df = temp_df
                    df.index = df.index.tz_localize(None)
                    df = df.reset_index()
                    if 'Date' in df.columns:
                        df['Date'] = df['Date'].apply(lambda x: x.strftime('%Y-%m-%d'))
                    break
            except: continue

        if ticker is None or df.empty:
            return code, None, None, "fail"

        return f"{code}", ticker, df, "yahoo"
    except Exception as e:
        return code, None, None, "fail"

@st.cache_data(ttl=86400)
def get_info_data(symbol):
    try:
        return yf.Ticker(symbol).info
    except Exception as e:
        return {}

# --- V103 新增：精確股利數據抓取 ---
@st.cache_data(ttl=3600)
def get_dividend_data(symbol, current_price):
    """
    抓取最新的現金股利金額，並計算即時殖利率。
    優先順序：dividendRate (年度宣告) > last_dividend (最近一次)
    """
    data = {"cash_div": 0.0, "yield": 0.0}
    try:
        if current_price <= 0: return data
        
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        # 1. 嘗試直接取得年度股利 (dividendRate)
        # 這通常對應到「今年宣布」或「去年整年」的總和
        div_rate = info.get('dividendRate')
        
        # 2. 如果沒有，嘗試抓取 actions (配息紀錄)
        if not div_rate:
            dividends = ticker.dividends
            if not dividends.empty:
                # 抓取最近 365 天的配息總和 (TTM)
                one_year_ago = pd.Timestamp.now().tz_localize(dividends.index.tz) - pd.DateOffset(days=365)
                recent_divs = dividends[dividends.index >= one_year_ago]
                if not recent_divs.empty:
                    div_rate = recent_divs.sum()
                else:
                    # 若一年內無配息，取最近一次的紀錄 (Last)
                    div_rate = dividends.iloc[-1]

        if div_rate and div_rate > 0:
            data["cash_div"] = float(div_rate)
            data["yield"] = (div_rate / current_price) * 100
            
        return data
    except:
        return data

# --- V103 新增：複合式籌碼分佈 (FinMind 強力版) ---
@st.cache_data(ttl=86400)
def get_chip_distribution_v2(stock_id):
    """
    結合 [外資總持股] 與 [集保分級] 來推算籌碼結構。
    解決免費 API 抓不到投信/自營總持股的問題。
    """
    data = {
        "foreign": 0.0,      # 外資 (FinMind)
        "big_hands": 0.0,    # 大戶 (>400張) (FinMind)
        "retail": 0.0,       # 散戶 (<50張) (推算)
        "other_big": 0.0,    # 本土主力/法人 (大戶 - 外資)
        "valid": False
    }
    
    if not stock_id.isdigit(): return data

    try:
        from FinMind.data import DataLoader
        dl = DataLoader()
        start_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
        
        # 1. 抓取外資總持股比例
        df_foreign = dl.taiwan_stock_total_foreign_and_chinese_investment_shares(
            stock_id=stock_id, start_date=start_date
        )
        if not df_foreign.empty:
            data["foreign"] = df_foreign.iloc[-1]['ForeignInvestmentSharesRatio']

        # 2. 抓取集保分佈 (判斷大戶與散戶)
        df_share = dl.taiwan_stock_shareholding(
            stock_id=stock_id, start_date=start_date
        )
        
        if not df_share.empty:
            latest_date = df_share['date'].max()
            df_latest = df_share[df_share['date'] == latest_date]
            
            # 定義：大戶 = 持股 > 400 張 (等級 15, 16, 17)
            # FinMind 的 HoldingRange 字串處理需小心
            # 這裡簡化邏輯：抓取 percent 加總
            
            big_percent = 0.0
            retail_percent = 0.0
            
            for _, row in df_latest.iterrows():
                level = row['HoldingRange'] # e.g., "1-999" or "1,000,001-..."
                pct = row['percent']
                
                # 解析級距 (這裡做簡單判斷)
                # FinMind 級距通常固定，等級 15 是 400,001-600,000
                # 若無法精確解析，我們依賴 "more than 400,000" 的關鍵字或列表索引
                # 簡單法：假設 FinMind 資料順序是固定的，後段是大戶
                
                # 更精確的做法：解析字串
                try:
                    # 處理 "1,000,001-" 或 "400,001-600,000"
                    lower_bound = 0
                    clean_range = str(level).replace(',', '')
                    if '-' in clean_range:
                        lower_bound = int(clean_range.split('-')[0])
                    elif 'more than' in clean_range or '以上' in clean_range: # 處理 "1,000,001以上"
                         # 提取數字
                         import re
                         nums = re.findall(r'\d+', clean_range)
                         if nums: lower_bound = int(nums[0])

                    if lower_bound >= 400000: # 大於 400 張
                        big_percent += pct
                    elif lower_bound < 50000: # 小於 50 張 (散戶)
                        retail_percent += pct
                        
                except: continue
            
            data["big_hands"] = big_percent
            data["retail"] = retail_percent
            
            # 計算 "本土主力/法人" = 大戶總數 - 外資 (若外資也是大戶)
            # 這是一個估計值，讓圖表不要只有 "外資" 跟 "散戶"
            # 若 Big < Foreign (理論上不應發生，除非外資很多是中小戶)，則歸零
            data["other_big"] = max(0, data["big_hands"] - data["foreign"])
            data["valid"] = True
            
        return data

    except Exception as e:
        print(f"Chip V2 Error: {e}")
        return data

# --- V98: 舊版籌碼 (主力買賣超) 仍保留用於計算指標分數 ---
@st.cache_data(ttl=3600)
def get_chip_data(stock_id):
    try:
        if not stock_id.isdigit(): return None
        from FinMind.data import DataLoader
        dl = DataLoader()
        start_date = (datetime.now() - timedelta(days=15)).strftime('%Y-%m-%d')
        df_inst = dl.taiwan_stock_institutional_investors(stock_id=stock_id, start_date=start_date)
        chip_data = {"foreign": 0, "trust": 0, "dealer": 0, "date": ""}
        if not df_inst.empty:
            latest_date = df_inst['date'].max()
            df_last = df_inst[df_inst['date'] == latest_date]
            chip_data["date"] = latest_date
            for _, row in df_last.iterrows():
                net = (row['buy'] - row['sell']) / 1000
                if row['name'] == 'Foreign_Investor': chip_data['foreign'] = int(net)
                elif row['name'] == 'Investment_Trust': chip_data['trust'] = int(net)
                elif row['name'] == 'Dealer_Self': chip_data['dealer'] += int(net)
                elif row['name'] == 'Dealer_Hedging': chip_data['dealer'] += int(net)
        return chip_data
    except: return None

def get_color_settings(code):
    return {'up': 'red', 'down': 'green', 'delta': 'inverse'}

def add_history(user, text): pass 
def save_scan_results(stype, codes):
    with open(f"scan_{stype}.json", 'w') as f: json.dump(codes, f)
def load_scan_results(stype):
    if os.path.exists(f"scan_{stype}.json"):
        with open(f"scan_{stype}.json", 'r') as f: return json.load(f)
    return []

def save_comment(user, msg):
    if not os.path.exists(COMMENTS_FILE): df = pd.DataFrame(columns=['User', 'Nickname', 'Message', 'Time'])
    else: df = pd.read_csv(COMMENTS_FILE)
    new_row = {'User': user, 'Nickname': get_user_nickname(user), 'Message': msg, 'Time': datetime.now().strftime("%Y-%m-%d %H:%M")}
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(COMMENTS_FILE, index=False)

def get_comments():
    if os.path.exists(COMMENTS_FILE): return pd.read_csv(COMMENTS_FILE)
    return pd.DataFrame(columns=['User', 'Nickname', 'Message', 'Time'])

def translate_text(text):
    if not text or text == "暫無詳細描述": return "" 
    try:
        translator = GoogleTranslator(source='auto', target='zh-TW')
        if len(text) < 1000: return translator.translate(text)
        chunks = [text[i:i+1000] for i in range(0, len(text), 1000)]
        translated_chunks = []
        for chunk in chunks:
            try:
                res = translator.translate(chunk)
                if res: translated_chunks.append(res)
            except: translated_chunks.append(chunk)
        return "".join(translated_chunks)
    except Exception as e: return text
