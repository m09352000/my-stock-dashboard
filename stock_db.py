import pandas as pd
import twstock
import yfinance as yf
import os
import json
import requests
from datetime import datetime, timedelta
from deep_translator import GoogleTranslator
import streamlit as st

# --- V113: 資料庫核心 (OpenAPI Bypass + OTC Sync) ---

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
        t = yf.Ticker(symbol)
        return t.info if t.info else {}
    except: return {}

@st.cache_data(ttl=3600)
def get_dividend_data(symbol, current_price):
    data = {"cash_div": 0.0, "yield": 0.0}
    try:
        if current_price <= 0: return data
        ticker = yf.Ticker(symbol)
        
        div_rate = ticker.info.get('dividendRate')
        
        if not div_rate or div_rate == 0:
            hist = ticker.dividends
            if not hist.empty:
                now = pd.Timestamp.now().tz_localize(None)
                try: hist.index = hist.index.tz_localize(None)
                except: pass
                
                one_year_ago = now - pd.DateOffset(days=365)
                recent = hist[hist.index >= one_year_ago]
                
                if not recent.empty: div_rate = recent.sum()
                else: div_rate = hist.iloc[-1]

        if div_rate and div_rate > 0:
            data["cash_div"] = float(div_rate)
            data["yield"] = (div_rate / current_price) * 100
            
        return data
    except: return data

@st.cache_data(ttl=86400)
def get_chip_distribution_v2(stock_id, info_data):
    data = { "foreign": 0.0, "directors": 0.0, "domestic_inst": 0.0, "valid": False }
    
    try:
        insider = info_data.get('heldPercentInsiders', 0)
        if insider: data['directors'] = insider * 100
    except: pass

    try:
        if stock_id.isdigit():
            from FinMind.data import DataLoader
            dl = DataLoader()
            start_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
            df_f = dl.taiwan_stock_total_foreign_and_chinese_investment_shares(stock_id=stock_id, start_date=start_date)
            if not df_f.empty:
                data['foreign'] = df_f.iloc[-1]['ForeignInvestmentSharesRatio']
                data['valid'] = True
    except: pass

    try:
        total_inst = info_data.get('heldPercentInstitutions', 0) * 100
        if data['foreign'] > 0:
            data['domestic_inst'] = max(0, total_inst - data['foreign'])
        elif data['foreign'] == 0 and total_inst > 0:
            data['foreign'] = total_inst * 0.6 
            data['domestic_inst'] = total_inst * 0.4
        
        if data['foreign'] > 0 or data['domestic_inst'] > 0 or data['directors'] > 0:
            data['valid'] = True
    except: pass
    
    return data

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

# --- V113 終極突破防線版：注意/處置股 同步引擎 ---
@st.cache_data(ttl=1800)
def get_warning_stocks():
    results = []
    
    # 使用 urllib 與特定 Header 來繞過 Cloudflare 針對 requests 的基本阻擋
    def fetch_twse_secure(url):
        import urllib.request
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Referer': 'https://www.twse.com.tw/zh/announcement/punish.html',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'X-Requested-With': 'XMLHttpRequest'
        })
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode('utf-8'))
        except: return None

    # 1. 抓取 TWSE 處置股 (上市)
    res_disp = fetch_twse_secure("https://www.twse.com.tw/exchangeReport/TWT43U?response=json")
    if res_disp and res_disp.get('stat') == 'OK':
        for row in res_disp.get('data', []):
            time_str = row[2].replace('民國', '').strip() if len(row) > 2 else ""
            start_time = time_str.split('~')[0].strip() if '~' in time_str else time_str
            end_time = time_str.split('~')[1].strip() if '~' in time_str else "-"
            results.append({
                "代號": row[0], "名稱": row[1], "類別": "處置股",
                "狀態": "🔴 已處置 (上市)", "確定列入時間": start_time,
                "預計解禁時間": end_time, "原因": row[3] if len(row) > 3 else "達處置標準"
            })
    else:
        # 【突破點】如果主站仍阻擋，直接切換到 TWSE OpenAPI (無防爬蟲限制)
        try:
            res_open = requests.get("https://openapi.twse.com.tw/v1/announcement/punish", timeout=5).json()
            for row in res_open:
                vals = list(row.values())
                time_str = vals[2].replace('民國', '').strip() if len(vals) > 2 else ""
                start_time = time_str.split('~')[0].strip() if '~' in time_str else time_str
                end_time = time_str.split('~')[1].strip() if '~' in time_str else "-"
                results.append({
                    "代號": vals[0], "名稱": vals[1], "類別": "處置股",
                    "狀態": "🔴 已處置 (上市)", "確定列入時間": start_time,
                    "預計解禁時間": end_time, "原因": vals[3] if len(vals) > 3 else "達處置標準"
                })
        except: pass

    # 2. 抓取 TWSE 注意股 (上市)
    res_att = fetch_twse_secure("https://www.twse.com.tw/exchangeReport/TWT38U?response=json")
    if res_att and res_att.get('stat') == 'OK':
        raw_date = str(res_att.get('date', datetime.now().strftime("%Y%m%d")))
        date_str = f"{int(raw_date[:4])}/{raw_date[4:6]}/{raw_date[6:]}" if len(raw_date) == 8 else raw_date
        for row in res_att.get('data', []):
            reason = row[2] if len(row) > 2 else "達注意標準"
            is_warning = "連續三個營業日" in reason or "六個營業日" in reason
            if is_warning:
                results.append({"代號": row[0], "名稱": row[1], "類別": "預警股", "狀態": "🚨 處置聽牌 (上市)", "確定列入時間": date_str, "預計解禁時間": "若明日續異常，即將處置", "原因": reason})
            results.append({"代號": row[0], "名稱": row[1], "類別": "注意股", "狀態": "🟡 已注意 (上市)", "確定列入時間": date_str, "預計解禁時間": "視後續表現", "原因": reason})
    else:
        # 【突破點】OpenAPI 備援
        try:
            res_open = requests.get("https://openapi.twse.com.tw/v1/exchangeReport/TWT38U", timeout=5).json()
            date_str = datetime.now().strftime("%Y/%m/%d")
            for row in res_open:
                vals = list(row.values())
                reason = vals[2] if len(vals) > 2 else "達注意標準"
                is_warning = "連續三個營業日" in reason or "六個營業日" in reason
                if is_warning:
                    results.append({"代號": vals[0], "名稱": vals[1], "類別": "預警股", "狀態": "🚨 處置聽牌 (上市)", "確定列入時間": date_str, "預計解禁時間": "若明日續異常，即將處置", "原因": reason})
                results.append({"代號": vals[0], "名稱": vals[1], "類別": "注意股", "狀態": "🟡 已注意 (上市)", "確定列入時間": date_str, "預計解禁時間": "視後續表現", "原因": reason})
        except: pass

    # 3. 抓取 TPEx 處置股 (上櫃 - 加碼功能，直接用櫃買 OpenAPI 不會擋)
    try:
        res_tpex = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_disposal_information", timeout=5).json()
        for row in res_tpex:
            vals = list(row.values())
            time_str = vals[2].replace('民國', '').strip() if len(vals) > 2 else ""
            start_time = time_str.split('~')[0].strip() if '~' in time_str else time_str
            end_time = time_str.split('~')[1].strip() if '~' in time_str else "-"
            results.append({
                "代號": vals[0], "名稱": vals[1], "類別": "處置股",
                "狀態": "🔴 已處置 (上櫃)", "確定列入時間": start_time,
                "預計解禁時間": end_time, "原因": vals[3] if len(vals) > 3 else "達處置標準"
            })
    except: pass

    # 4. 抓取 TPEx 注意股 (上櫃)
    try:
        res_tpex_att = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_trading_warning_information", timeout=5).json()
        date_str = datetime.now().strftime("%Y/%m/%d")
        for row in res_tpex_att:
            vals = list(row.values())
            reason = vals[2] if len(vals) > 2 else "達注意標準"
            is_warning = "連續三個營業日" in reason or "六個營業日" in reason
            if is_warning:
                results.append({"代號": vals[0], "名稱": vals[1], "類別": "預警股", "狀態": "🚨 處置聽牌 (上櫃)", "確定列入時間": date_str, "預計解禁時間": "若明日續異常，即將處置", "原因": reason})
            results.append({"代號": vals[0], "名稱": vals[1], "類別": "注意股", "狀態": "🟡 已注意 (上櫃)", "確定列入時間": date_str, "預計解禁時間": "視後續表現", "原因": reason})
    except: pass

    df = pd.DataFrame(results)
    if not df.empty:
        # 移除可能因多管道重複抓取的資料
        df = df.drop_duplicates(subset=['代號', '類別'])
    else:
        df = pd.DataFrame(columns=["代號", "名稱", "類別", "狀態", "確定列入時間", "預計解禁時間", "原因"])
        
    return df

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
