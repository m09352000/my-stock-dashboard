import streamlit as st
import yfinance as yf
import pandas as pd
import twstock
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from deep_translator import GoogleTranslator
import time
import os
import json
import hashlib
from datetime import datetime

# --- 1. 網頁設定 ---
st.set_page_config(page_title="AI 股市戰情室 V15", layout="wide", initial_sidebar_state="auto")

# --- 2. CSS 優化 ---
st.markdown("""
<style>
    @media (max-width: 768px) {
        .main .block-container { padding-top: 2rem !important; }
        h1 { font-size: 1.8rem !important; }
        [data-testid="stSidebar"] { width: 85% !important; }
    }
    .modebar { display: none !important; }
    .version-text {
        position: fixed; bottom: 10px; left: 20px;
        font-size: 0.8em; color: gray; z-index: 100;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. 初始化 Session State ---
if 'history' not in st.session_state: st.session_state['history'] = []
if 'current_stock' not in st.session_state: st.session_state['current_stock'] = "" 
if 'current_name' not in st.session_state: st.session_state['current_name'] = ""
if 'view_mode' not in st.session_state: st.session_state['view_mode'] = 'welcome' 
if 'scan_range' not in st.session_state: st.session_state['scan_range'] = 'top'
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False # 登入狀態

# --- 4. 資料檔案管理 ---
COMMENTS_FILE = "comments.csv"
USER_DATA_FILE = "user_data.json"

# 預設熱門股清單
TOP_STOCKS = [
    '2330', '2317', '2454', '2308', '2382', '2303', '2603', '2609', '2615', '2881', 
    '2882', '2891', '3231', '3008', '3037', '3034', '3019', '3035', '2379', '3045', 
    '4938', '4904', '2412', '2357', '2327', '2356', '2345', '2301', '2353', '2324', 
    '2352', '2344', '2368', '2409', '3481', '2498', '3017', '3532', '6176', '2002', 
    '1101', '1301', '1303', '2886', '2892', '5880', '2884', '2880', '2885', '2834', 
    '1605', '1513', '1519', '2313', '1216', '2912', '9910', '1402', '2105', '6505'
]

def get_scan_list(mode):
    if mode == 'top': return TOP_STOCKS
    elif mode == 'watchlist': # 回傳自選股
        data = load_user_data()
        return data.get('watchlist', [])
    else:
        all_codes = []
        for code, info in twstock.codes.items():
            if info.type == "股票": all_codes.append(code)
        return all_codes

# --- 5. 用戶資料與密碼函式 (New) ---
def load_user_data():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, 'r') as f:
            return json.load(f)
    return {"password": "", "watchlist": []}

def save_user_data(data):
    with open(USER_DATA_FILE, 'w') as f:
        json.dump(data, f)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def check_login(password):
    data = load_user_data()
    if not data['password']: return False # 還沒設密碼
    return data['password'] == hash_password(password)

def set_password(password):
    data = load_user_data()
    data['password'] = hash_password(password)
    save_user_data(data)

def add_to_watchlist(code):
    data = load_user_data()
    if code not in data['watchlist']:
        data['watchlist'].append(code)
        save_user_data(data)
        return True
    return False

def remove_from_watchlist(code):
    data = load_user_data()
    if code in data['watchlist']:
        data['watchlist'].remove(code)
        save_user_data(data)
        return True
    return False

# --- 6. 核心函式 ---
def get_color_settings(stock_id):
    if ".TW" in stock_id.upper() or ".TWO" in stock_id.upper() or stock_id.isdigit():
        return {"up": "#FF0000", "down": "#00FF00", "delta": "inverse"}
    else:
        return {"up": "#00FF00", "down": "#FF0000", "delta": "normal"}

def set_view_to_analysis(code, name):
    st.session_state['current_stock'] = f"{code}.TW" if ".TW" not in str(code) and code.isdigit() else code
    st.session_state['current_name'] = name
    st.session_state['view_mode'] = 'analysis'

def handle_search():
    raw_code = st.session_state.sidebar_search
    if raw_code:
        name = "美股"
        if raw_code in twstock.codes: name = twstock.codes[raw_code].name
        elif raw_code.isdigit(): name = "台股"
        set_view_to_analysis(raw_code, name)

def translate_text(text):
    if not text or text == "暫無詳細描述": return "暫無詳細描述"
    try: return GoogleTranslator(source='auto', target='zh-TW').translate(text[:2000])
    except: return text

def load_comments():
    if os.path.exists(COMMENTS_FILE): return pd.read_csv(COMMENTS_FILE)
    return pd.DataFrame(columns=["Time", "User", "Message"])

def save_comment(user, msg):
    df = load_comments()
    new_data = pd.DataFrame([[datetime.now().strftime("%m/%d %H:%M"), user, msg]], columns=["Time", "User", "Message"])
    df = pd.concat([new_data, df], ignore_index=True)
    df.to_csv(COMMENTS_FILE, index=False)

# --- 7. 側邊欄 ---
with st.sidebar:
    st.title("🎮 戰情控制台")
    if st.button("🏠 回歡迎頁", use_container_width=True):
        st.session_state['view_mode'] = 'welcome'; st.rerun()
    st.divider()
    
    st.text_input("🔍 代號快速輸入", key="sidebar_search", on_change=handle_search)
    
    st.subheader("🤖 AI 策略選股")
    scan_range_opt = st.radio("📡 掃描範圍", ["⚡ 熱門 100", "🐢 全台股"], index=0 if st.session_state['scan_range']=='top' else 1)
    st.session_state['scan_range'] = 'top' if "熱門" in scan_range_opt else 'all'

    c1, c2, c3 = st.columns(3)
    if c1.button("當沖", use_container_width=True): st.session_state['view_mode'] = 'scan_day'; st.rerun()
    if c2.button("短線", use_container_width=True): st.session_state['view_mode'] = 'scan_short'; st.rerun()
    if c3.button("長線", use_container_width=True): st.session_state['view_mode'] = 'scan_long'; st.rerun()
    
    st.divider()
    # 新增：個人專區按鈕
    if st.button("🔒 個人自選股", use_container_width=True):
        st.session_state['view_mode'] = 'my_watchlist'; st.rerun()
        
    if st.button("💬 戰友留言板", use_container_width=True):
        st.session_state['view_mode'] = 'comments'; st.rerun()
    if st.button("🕒 搜尋歷史", use_container_width=True):
        st.session_state['view_mode'] = 'history'; st.rerun()
    
    if st.session_state['history']:
        st.caption("最近瀏覽")
        for item in st.session_state['history'][:5]:
            code = item.split(" ")[0]; name = item.split(" ")[1] if " " in item else ""
            if st.button(f"{code} {name}", key=f"side_{code}"):
                set_view_to_analysis(code, name); st.rerun()

    st.markdown('<div class="version-text">AI 股市戰情室 V15.0 (個人金庫版)</div>', unsafe_allow_html=True)

# --- 8. 主畫面邏輯 ---

# [頁面 1] 歡迎頁
if st.session_state['view_mode'] == 'welcome':
    st.title("👋 歡迎來到 AI 股市戰情室")
    with st.container(border=True):
        st.markdown("""
        #### 🚀 V15 個人金庫版
        * **🔒 個人自選股**：新增密碼保護功能，建立屬於你的私密關注清單。
        * **🤖 自選股診斷**：一鍵 AI 掃描你的自選股，快速檢視持股健康度。
        * **📝 記憶功能**：系統會自動記住你的自選清單，下次登入還在。
        """)
    st.info("👈 左側新增「🔒 個人自選股」功能，請先去設定密碼！")

# [頁面 2] 個人自選股 (New Feature)
elif st.session_state['view_mode'] == 'my_watchlist':
    st.title("🔒 個人自選股戰情室")
    
    user_data = load_user_data()
    
    # 情況 A: 尚未設定密碼
    if not user_data['password']:
        st.warning("⚠️ 這是你第一次使用個人專區，請設定一組密碼。")
        new_pw = st.text_input("設定新密碼", type="password")
        confirm_pw = st.text_input("確認新密碼", type="password")
        if st.button("確認設定"):
            if new_pw and new_pw == confirm_pw:
                set_password(new_pw)
                st.session_state['logged_in'] = True
                st.success("密碼設定成功！"); time.sleep(1); st.rerun()
            else:
                st.error("密碼不一致或為空")
                
    # 情況 B: 已設密碼，但未登入
    elif not st.session_state['logged_in']:
        st.info("請輸入密碼以存取您的自選股清單")
        pw_input = st.text_input("輸入密碼", type="password")
        if st.button("登入 🔓"):
            if check_login(pw_input):
                st.session_state['logged_in'] = True
                st.success("登入成功！"); st.rerun()
            else:
                st.error("密碼錯誤")
                
    # 情況 C: 已登入，顯示自選股介面
    else:
        # 1. 管理區塊
        with st.expander("⚙️ 管理自選清單 (新增/刪除)", expanded=False):
            c1, c2 = st.columns([3, 1])
            new_stock = c1.text_input("輸入股票代號加入 (例如 2330)")
            if c2.button("加入清單"):
                if new_stock:
                    # 簡易驗證
                    is_valid = False
                    if new_stock in twstock.codes: is_valid = True
                    elif new_stock.isdigit(): is_valid = True # 假設純數字為台股
                    
                    if is_valid:
                        if add_to_watchlist(new_stock): st.success(f"{new_stock} 已加入")
                        else: st.warning("已在清單中")
                        time.sleep(0.5); st.rerun()
                    else: st.error("代號無效")
            
            st.divider()
            st.write("目前清單：")
            current_list = user_data['watchlist']
            if current_list:
                cols = st.columns(5)
                for i, s_code in enumerate(current_list):
                    if cols[i % 5].button(f"🗑️ 刪除 {s_code}", key=f"del_{s_code}"):
                        remove_from_watchlist(s_code)
                        st.rerun()
            else:
                st.caption("目前是空的，快加點股票吧！")

        # 2. 診斷區塊
        st.divider()
        st.subheader(f"📊 自選股 AI 診斷 (共 {len(user_data['watchlist'])} 檔)")
        
        if not user_data['watchlist']:
            st.info("請先加入股票")
        else:
            if st.button("🚀 開始診斷我的持股"):
                pbar = st.progress(0)
                
                # 取得清單並開始掃描
                watchlist = user_data['watchlist']
                for i, code in enumerate(watchlist):
                    pbar.progress((i+1)/len(watchlist))
                    try:
                        # 取得名稱
                        name = twstock.codes[code].name if code in twstock.codes else code
                        # 抓資料
                        data = yf.Ticker(f"{code}.TW").history(period="3mo")
                        
                        if len(data) > 20:
                            curr = data['Close'].iloc[-1]
                            chg = curr - data['Close'].iloc[-2]
                            pct = (chg / data['Close'].iloc[-2])*100
                            m5 = data['Close'].rolling(5).mean().iloc[-1]
                            m20 = data['Close'].rolling(20).mean().iloc[-1]
                            m60 = data['Close'].rolling(60).mean().iloc[-1]
                            
                            # AI 簡易判斷
                            ai_status = "⚖️ 盤整"
                            if curr > m20 and m20 > m60: ai_status = "🔥 多頭"
                            elif curr < m20 and m20 < m60: ai_status = "❄️ 空頭"
                            
                            with st.container(border=True):
                                c1, c2, c3, c4 = st.columns([1, 2, 2, 1])
                                c1.markdown(f"### {code}")
                                c2.write(f"**{name}**")
                                c3.write(f"{curr:.2f} ({pct:+.2f}%) | {ai_status}")
                                c4.button("分析", key=f"my_{code}", on_click=set_view_to_analysis, args=(code, name))
                    except:
                        st.error(f"{code} 資料讀取失敗")
                pbar.empty()

# [頁面 3] 留言板
elif st.session_state['view_mode'] == 'comments':
    st.title("💬 戰友留言板")
    with st.container(border=True):
        c1, c2 = st.columns([1, 4])
        user_name = c1.text_input("暱稱", value="匿名股神")
        user_msg = c2.text_input("留言", placeholder="分享看法...")
        if st.button("送出 📤", use_container_width=True):
            if user_msg:
                save_comment(user_name, user_msg)
                st.success("已送出！"); time.sleep(0.5); st.rerun()
    st.subheader("最新討論")
    df_comments = load_comments()
    if not df_comments.empty:
        for index, row in df_comments.iterrows():
            with st.chat_message("user"):
                st.markdown(f"**{row['User']}** <small>({row['Time']})</small>", unsafe_allow_html=True)
                st.write(row['Message'])
    else: st.write("尚無留言")

# [頁面 4] 個股分析
elif st.session_state['view_mode'] == 'analysis':
    stock_id = st.session_state['current_stock']
    stock_name = st.session_state['current_name']
    if not stock_id: st.warning("請輸入代號")
    else:
        c_head, c_btn = st.columns([3, 1])
        c_head.title(f"{stock_name} {stock_id}")
        auto_refresh = c_btn.checkbox("🔴 即時監控", value=False)
        if auto_refresh: time.sleep(3); st.rerun()
        try:
            rec = f"{stock_id.replace('.TW','')} {stock_name}"
            if rec not in st.session_state['history']: st.session_state['history'].insert(0, rec)
            stock = yf.Ticker(stock_id); df = stock.history(period="1y"); info = stock.info
            if df.empty: st.error("查無資料")
            else:
                colors = get_color_settings(stock_id)
                curr = df['Close'].iloc[-1]; prev = df['Close'].iloc[-2]
                hi = df['High'].iloc[-1]; lo = df['Low'].iloc[-1]
                chg = curr - prev; pct = (chg / prev)*100
                vol_today = df['Volume'].iloc[-1]; vol_yest = df['Volume'].iloc[-2]
                vol_week_avg = df['Volume'].tail(5).mean()
                amplitude = ((hi - lo) / prev) * 100
                
                with st.expander("🏢 公司簡介", expanded=False): st.write(translate_text(info.get('longBusinessSummary', '')))
                st.divider()
                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("成交價", f"{curr:.2f}", f"{chg:.2f} ({pct:.2f}%)", delta_color=colors['delta'])
                m2.metric("最高", f"{hi:.2f}"); m3.metric("最低", f"{lo:.2f}")
                m4.metric("振幅", f"{amplitude:.2f}%")
                main_force = "主力進貨 🔴" if (chg>0 and vol_today>vol_yest) else ("主力出貨 🟢" if (chg<0 and vol_today>vol_yest) else "觀望")
                m5.metric("主力動向", main_force)
                
                v1, v2, v3, v4, v5 = st.columns(5)
                v1.metric("今日量", f"{int(vol_today/1000):,} 張")
                v2.metric("昨日量", f"{int(vol_yest/1000):,} 張", f"{int((vol_today-vol_yest)/1000)} 張")
                v3.metric("本週均量", f"{int(vol_week_avg/1000):,} 張")
                vol_ratio = vol_today / vol_week_avg if vol_week_avg > 0 else 1
                vol_status = "🔥 爆量" if vol_ratio > 1.5 else ("💤 量縮" if vol_ratio < 0.6 else "正常")
                v4.metric("狀態", vol_status)
                v5.metric("外資持股", f"{info.get('heldPercentInstitutions', 0)*100:.1f}%")

                st.subheader("📈 K 線與籌碼")
                df['MA5'] = df['Close'].rolling(5).mean(); df['MA20'] = df['Close'].rolling(20).mean(); df['MA60'] = df['Close'].rolling(60).mean()
                trange = st.select_slider("時間區間", ['3個月','6個月','1年'], value='6個月')
                days = {'3個月':90, '6個月':180, '1年':365}[trange]
                cdf = df.tail(days)
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=cdf.index, open=cdf['Open'], high=cdf['High'], low=cdf['Low'], close=cdf['Close'], name='K線', increasing_line_color=colors['up'], decreasing_line_color=colors['down']), row=1, col=1)
                fig.add_trace(go.Scatter(x=cdf.index, y=cdf['MA5'], line=dict(color='#1f77b4', width=1), name='MA5'), row=1, col=1)
                fig.add_trace(go.Scatter(x=cdf.index, y=cdf['MA20'], line=dict(color='#ff7f0e', width=1), name='MA20'), row=1, col=1)
                fig.add_trace(go.Scatter(x=cdf.index, y=cdf['MA60'], line=dict(color='#9467bd', width=1), name='MA60'), row=1, col=1)
                vol_colors = [colors['up'] if c >= o else colors['down'] for c, o in zip(cdf['Close'], cdf['Open'])]
                fig.add_trace(go.Bar(x=cdf.index, y=cdf['Volume'], marker_color=vol_colors, name='成交量'), row=2, col=1)
                fig.update_layout(height=600, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

                st.subheader("🤖 AI 深度診斷")
                ma20 = df['MA20'].iloc[-1]; ma60 = df['MA60'].iloc[-1]
                delta = df['Close'].diff(); u=delta.copy(); d=delta.copy(); u[u<0]=0; d[d>0]=0
                rs = u.rolling(14).mean()/d.abs().rolling(14).mean(); rsi = (100-100/(1+rs)).iloc[-1]
                bias = ((curr-ma60)/ma60)*100
                with st.container(border=True):
                    c1, c2 = st.columns(2)
                    with c1:
                        if curr > ma20 and ma20 > ma60: st.success("🔥 **多頭排列**：趨勢向上。")
                        elif curr < ma20 and ma20 < ma60: st.error("❄️ **空頭排列**：反壓沉重。")
                        else: st.warning("⚖️ **盤整震盪**：多空拉鋸。")
                    with c2:
                        st.write(f"RSI: `{rsi:.1f}` | 季線乖離: `{bias:.2f}%`")
                        if rsi>80: st.warning("⚠️ 短線過熱")
                        elif rsi<20: st.success("💎 短線超賣")
        except Exception as e: st.error(f"錯誤: {e}")

# [頁面 5, 6, 7] AI 策略
elif st.session_state['view_mode'] in ['scan_day', 'scan_short', 'scan_long']:
    mode = st.session_state['view_mode']
    if mode == 'scan_day': title = "⚡ 當沖快篩"; days_req = 5
    elif mode == 'scan_short': title = "📈 短線波段"; days_req = 30
    else: title = "🐢 長線存股"; days_req = 60
    st.title(f"🤖 AI 推薦：{title}")
    
    scan_mode = st.session_state['scan_range']
    current_list = get_scan_list(scan_mode)
    st.info(f"模式：{'⚡ 熱門 100' if scan_mode=='top' else '🐢 全市場'} | 預計掃描：{len(current_list)} 檔")
    
    if st.button(f"開始 {title}"):
        found = []
        pbar = st.progress(0); status = st.empty()
        for i, code in enumerate(current_list):
            status.text(f"AI 運算中 ({i+1}/{len(current_list)}): {code}...")
            pbar.progress((i+1)/len(current_list))
            try:
                if scan_mode == 'all': time.sleep(0.1)
                data = yf.Ticker(f"{code}.TW").history(period="3mo")
                if len(data) > days_req:
                    curr = data['Close'].iloc[-1]; m5 = data['Close'].rolling(5).mean().iloc[-1]
                    m20 = data['Close'].rolling(20).mean().iloc[-1]
                    vol_curr = data['Volume'].iloc[-1]; vol_avg = data['Volume'].tail(5).mean()
                    match = False; reason = ""
                    if mode == 'scan_day':
                        amp = (data['High'].iloc[-1] - data['Low'].iloc[-1]) / data['Close'].iloc[-2]
                        if vol_curr > 1.5 * vol_avg and amp > 0.02: match = True; reason = f"爆量 {vol_curr/vol_avg:.1f}倍"
                    elif mode == 'scan_short':
                        if curr > m20 and m5 > m20: match = True; reason = "站上月線"
                    elif mode == 'scan_long':
                        m60 = data['Close'].rolling(60).mean().iloc[-1]
                        if curr > m60 and curr > m20: match = True; reason = "長線多頭"
                    if match:
                        name = twstock.codes[code].name if code in twstock.codes else code
                        found.append({'c':code, 'n':name, 'p':curr, 'r':reason})
            except: continue
        pbar.empty(); status.empty()
        if found:
            st.success(f"AI 篩選出 {len(found)} 檔：")
            for item in found:
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([1, 2, 3, 1])
                    c1.write(f"**{item['c']}**"); c2.write(f"{item['n']}")
                    c3.write(f"💰 {item['p']:.2f} | {item['r']}")
                    c4.button("分析", key=f"ai_{item['c']}", on_click=set_view_to_analysis, args=(item['c'], item['n']))
        else: st.warning("無符合")

# [頁面 8] 歷史
elif st.session_state['view_mode'] == 'history':
    st.title("📜 歷史紀錄")
    if st.session_state['history']:
        for item in st.session_state['history']:
            code = item.split(" ")[0]; name = item.split(" ")[1] if " " in item else ""
            c1, c2 = st.columns([4, 1])
            c1.write(f"{item}"); c2.button("查看", key=f"h_{code}", on_click=set_view_to_analysis, args=(code, name))
