import pandas as pd
import twstock
import yfinance as yf
import os
import json
from datetime import datetime, timedelta
from deep_translator import GoogleTranslator
import streamlit as st

# --- V101: 資料庫核心 (Yield Fix + Chip Update) ---

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

# --- V96.1 Rate Limit 防護盾 ---
@st.cache_data(ttl=86400)
def get_info_data(symbol):
    try:
        return yf.Ticker(symbol).info
    except Exception as e:
        return {}

# --- V101 新增：精準殖利率計算 (解決 API 回傳錯誤問題) ---
@st.cache_data(ttl=3600)
def get_real_yield(symbol, current_price):
    try:
        ticker = yf.Ticker(symbol)
        
        # 1. 嘗試從 history_metadata 或 info 取得 (備案)
        info = ticker.info
        
        # 2. 正規戰法：抓取最近一年配息總和
        dividends = ticker.dividends
        if not dividends.empty:
            # 抓取過去 365 天內的股利
            one_year_ago = pd.Timestamp.now().tz_localize(dividends.index.tz) - pd.DateOffset(days=365)
            last_year_divs = dividends[dividends.index >= one_year_ago]
            total_div = last_year_divs.sum()
            
            if total_div > 0 and current_price > 0:
                return (total_div / current_price) * 100
        
        # 3. 如果沒有配息紀錄，嘗試使用 trailingAnnualDividendYield
        # 注意：YF 的 yield 通常是小數點 (0.03)，但也可能出錯，所以這邊做保護
        yf_yield = info.get('trailingAnnualDividendYield')
        if yf_yield:
            return yf_yield * 100
        
        return 0.0
    except:
        return 0.0

# --- V101 新增：抓取四大持股比例 (外資/董監/投信/自營) ---
@st.cache_data(ttl=86400)
def get_institutional_shares(stock_id, info_data):
    # 初始化
    data = {
        "Foreign": 0.0,  # 外資
        "Directors": 0.0, # 董監
        "Trust": 0.0,    # 投信 (估)
        "Dealer": 0.0    # 自營 (估)
    }
    
    try:
        # 1. 外資持股比例 (FinMind 數據最準)
        if stock_id.isdigit():
            from FinMind.data import DataLoader
            dl = DataLoader()
            # 抓取外資總持股表
            df_foreign = dl.taiwan_stock_total_foreign_and_chinese_investment_shares(
                stock_id=stock_id, 
                start_date=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            )
            if not df_foreign.empty:
                # ForeignInvestmentSharesRatio = 外資持股比例
                data["Foreign"] = df_foreign.iloc[-1]['ForeignInvestmentSharesRatio']
        
        # 2. 董監持股 (Insiders) - 使用 YF info
        # YF 的 heldPercentInsiders 通常指內部人(董監)持有比例
        insider_hold = info_data.get('heldPercentInsiders', 0)
        if insider_hold:
            data["Directors"] = insider_hold * 100
            
        # 3. 投信與自營商 (難以取得累積總持股%，通常只有買賣超)
        # 這裡我們使用 YF 的 "heldPercentInstitutions" (機構持股)
        # 機構持股通常包含：外資 + 投信 + 自營 + 其他法人
        # 我們可以用 機構持股 - 外資持股 來粗估 國內法人(投信+自營)
        inst_hold = info_data.get('heldPercentInstitutions', 0) * 100
        
        domestic_inst = max(0, inst_hold - data["Foreign"])
        
        # 因為無法精確拆分投信/自營的"總持股"，我們依據台股慣性做推估分配
        # 通常投信持股較自營商穩定，我們假設國內法人中 70% 是投信，30% 是自營
        # 這是一個估計值，為了滿足顯示需求
        if domestic_inst > 0:
            data["Trust"] = domestic_inst * 0.7
            data["Dealer"] = domestic_inst * 0.3
            
        return data

    except Exception as e:
        print(f"Chip Data Error: {e}")
        return data

# --- V98: 舊版籌碼 (主力買賣超) 仍保留用於計算指標 ---
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

# --- 5. 掃描與歷史紀錄 ---
def add_history(user, text): pass 
def save_scan_results(stype, codes):
    with open(f"scan_{stype}.json", 'w') as f: json.dump(codes, f)
def load_scan_results(stype):
    if os.path.exists(f"scan_{stype}.json"):
        with open(f"scan_{stype}.json", 'r') as f: return json.load(f)
    return []

# --- 6. 留言板 ---
def save_comment(user, msg):
    if not os.path.exists(COMMENTS_FILE): df = pd.DataFrame(columns=['User', 'Nickname', 'Message', 'Time'])
    else: df = pd.read_csv(COMMENTS_FILE)
    new_row = {'User': user, 'Nickname': get_user_nickname(user), 'Message': msg, 'Time': datetime.now().strftime("%Y-%m-%d %H:%M")}
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(COMMENTS_FILE, index=False)

def get_comments():
    if os.path.exists(COMMENTS_FILE): return pd.read_csv(COMMENTS_FILE)
    return pd.DataFrame(columns=['User', 'Nickname', 'Message', 'Time'])

# --- 7. 翻譯功能 (長文完整翻譯) ---
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
