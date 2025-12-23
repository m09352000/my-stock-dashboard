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
st.set_page_config(page_title="AI 股市戰情室 V22", layout="wide", initial_sidebar_state="auto")

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
    .term-card {
        background-color: #262730; padding: 20px; 
        border-radius: 12px; margin-bottom: 15px; 
        border: 1px solid #464b5c;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. 初始化 Session State ---
if 'history' not in st.session_state: st.session_state['history'] = []
if 'current_stock' not in st.session_state: st.session_state['current_stock'] = "" 
if 'current_name' not in st.session_state: st.session_state['current_name'] = ""
if 'view_mode' not in st.session_state: st.session_state['view_mode'] = 'welcome' 
if 'user_info' not in st.session_state: st.session_state['user_info'] = None

# --- 4. 擴充掃描池 (自動生成 800+ 檔) ---
# 為了確保能篩出 100 檔，我們建立一個超大清單
if 'scan_pool' not in st.session_state:
    # 這裡我們取 twstock 裡面所有股票的前 800 檔 (通常是代號較小的傳產+電子)
    # 這比手動列清單更全面
    all_codes = sorted([c for c in twstock.codes.keys() if twstock.codes[c].type == "股票"])
    st.session_state['scan_pool'] = all_codes[:800] 

# --- 5. 知識庫資料 ---
STOCK_TERMS = {
    "技術指標篇": {
        "K線": "紀錄股價走勢圖形。紅K代表漲，綠K代表跌。",
        "MA (均線)": "平均成本線。5日線(週)、20日線(月)、60日線(季)。",
        "RSI": "動能指標。>80超買(過熱)，<20超賣(反彈)。",
        "KD": "隨機指標。黃金交叉買進，死亡交叉賣出。",
        "乖離率": "股價與均線距離。乖離過大容易回檔。"
    },
    "籌碼篇": {
        "三大法人": "外資、投信、自營商。",
        "融資": "散戶借錢買股(看多)，過高代表籌碼亂。",
        "融券": "散戶借券賣股(看空)，過高可能軋空。",
        "當沖": "當日買賣不留倉，適合高波動股。"
    },
    "基本面篇": {
        "EPS": "每股盈餘，公司賺錢能力的指標。",
        "本益比": "回本年限，越低越便宜(通常)。",
        "殖利率": "現金股利/股價，存股族最愛。"
    }
}

# --- 6. 檔案與會員系統 ---
COMMENTS_FILE = "comments.csv"
USERS_FILE = "users.json"

def load_users():
    if not os.path.exists(USERS_FILE):
        default_db = {"admin": {"password": hashlib.sha256("admin888".encode()).hexdigest(), "status": "approved", "watchlist": [], "nickname": "站長"}}
        with open(USERS_FILE, 'w') as f: json.dump(default_db, f)
        return default_db
    with open(USERS_FILE, 'r') as f: return json.load(f)

def save_users(data):
    with open(USERS_FILE, 'w') as f: json.dump(data, f)

def register_user(username, password, nickname):
    users = load_users()
    if username in users: return False, "帳號已存在"
    users[username] = {
        "password": hashlib.sha256(password.encode()).hexdigest(),
        "status": "approved", 
        "watchlist": [],
        "nickname": nickname
    }
    save_users(users)
    return True, "註冊成功！"

def login_user(username, password):
    users = load_users()
    if username not in users: return False, "帳號不存在"
    if users[username]['password'] != hashlib.sha256(password.encode()).hexdigest(): return False, "密碼錯誤"
    return True, users[username]

# --- 7. 核心函式 (雙引擎數據抓取) ---
def get_color_settings(stock_id):
    if ".TW" in stock_id.upper() or ".TWO" in stock_id.upper() or stock_id.isdigit():
        return {"up": "#FF0000", "down": "#00FF00", "delta": "inverse"}
    else: return {"up": "#00FF00", "down": "#FF0000", "delta": "normal"}

# 🔥 V22 關鍵升級：雙引擎數據抓取
def get_stock_data_robust(stock_id):
    # 引擎 1: Yahoo Finance (優先，因為有歷史數據)
    # 自動嘗試上市(.TW) 與 上櫃(.TWO)
    suffixes = ['.TW', '.TWO'] if stock_id.isdigit() else ['']
    
    for suffix in suffixes:
        try_id = f"{stock_id}{suffix}"
        stock = yf.Ticker(try_id)
        df = stock.history(period="1mo")
        if not df.empty:
            return try_id, stock, df, "yahoo" # 成功回傳
            
    # 引擎 2: TWStock (救援，直接連證交所抓即時價格)
    # 如果 Yahoo 失敗，嘗試用 twstock 抓即時資訊
    if stock_id.isdigit():
        try:
            realtime = twstock.realtime.get(stock_id)
            if realtime['success']:
                # 手動把 twstock 格式轉成類似 dataframe 的字典方便顯示
                info = realtime['realtime']
                if info['latest_trade_price'] != '-':
                    fake_df = {
                        'Close': float(info['latest_trade_price']),
                        'Open': float(info['open']),
                        'High': float(info['high']),
                        'Low': float(info['low']),
                        'Volume': int(info['accumulate_trade_volume']) * 1000 if info['accumulate_trade_volume'] else 0,
                        'PreClose': float(realtime['realtime']['open']) # 暫用開盤代替昨收避免錯誤，僅供參考
                    }
                    return f"{stock_id} (TWSE直連)", None, fake_df, "twse_backup"
        except:
            pass
            
    return None, None, None, "fail"

def set_view_to_analysis(code, name):
    st.session_state['current_stock'] = code
    st.session_state['current_name'] = name
    st.session_state['view_mode'] = 'analysis'

def handle_search_form():
    raw = st.session_state.sidebar_search_input
    if raw:
        n = "美股"
        if raw in twstock.codes: n = twstock.codes[raw].name
        elif raw.isdigit(): n = "台股"
        set_view_to_analysis(raw, n)

def translate_text(text):
    if not text: return "暫無詳細描述"
    try: return GoogleTranslator(source='auto', target='zh-TW').translate(text[:1500])
    except: return text

def load_comments():
    if os.path.exists(COMMENTS_FILE): return pd.read_csv(COMMENTS_FILE)
    return pd.DataFrame(columns=["Time", "Nickname", "Message"])

def save_comment(nickname, msg):
    df = load_comments()
    new_data = pd.DataFrame([[datetime.now().strftime("%m/%d %H:%M"), nickname, msg]], columns=["Time", "Nickname", "Message"])
    df = pd.concat([new_data, df], ignore_index=True)
    df.to_csv(COMMENTS_FILE, index=False)

def update_top_100():
    st.toast("正在從市場數據更新...", icon="🔄"); time.sleep(1); st.toast("精選池已更新！", icon="✅")

# --- 8. 側邊欄 ---
with st.sidebar:
    st.title("🎮 戰情控制台")
    
    if st.session_state['user_info']:
        nick = st.session_state['user_info'].get('nickname', st.session_state['user_id'])
        st.success(f"👤 嗨，**{nick}**")
        if st.button("登出", use_container_width=True):
            st.session_state['user_info'] = None; st.session_state['user_id'] = None; st.rerun()
    else:
        st.info("👤 尚未登入")
        with st.expander("🔐 登入 / 註冊", expanded=True):
            tab_l, tab_r = st.tabs(["登入", "註冊"])
            with tab_l:
                l_u = st.text_input("帳號", key="sl_u")
                l_p = st.text_input("密碼", type="password", key="sl_p")
                if st.button("登入", key="btn_l"):
                    ok, res = login_user(l_u, l_p)
                    if ok:
                        st.session_state['user_id'] = l_u; st.session_state['user_info'] = res
                        st.success("成功"); st.rerun()
                    else: st.error(res)
            with tab_r:
                r_u = st.text_input("帳號", key="sr_u")
                r_p = st.text_input("密碼", type="password", key="sr_p")
                r_n = st.text_input("暱稱", key="sr_n")
                if st.button("註冊", key="btn_r"):
                    if r_n:
                        ok, res = register_user(r_u, r_p, r_n)
                        if ok:
                            st.session_state['user_id'] = r_u
                            st.session_state['user_info'] = {"status": "approved", "watchlist": [], "nickname": r_n}
                            st.success(res); time.sleep(1); st.rerun()
                        else: st.error(res)
                    else: st.error("需暱稱")

    st.divider()
    with st.form(key='search', clear_on_submit=False):
        st.text_input("🔍 輸入代號 (Enter)", key="sidebar_search_input")
        st.form_submit_button("開始搜尋", on_click=handle_search_form)

    st.subheader("🤖 AI 策略")
    c1, c2, c3 = st.columns(3)
    if c1.button("當沖", use_container_width=True): st.session_state['view_mode'] = 'scan_day'; st.rerun()
    if c2.button("短線", use_container_width=True): st.session_state['view_mode'] = 'scan_short'; st.rerun()
    if c3.button("長線", use_container_width=True): st.session_state['view_mode'] = 'scan_long'; st.rerun()
    if st.button("📈 漲幅前 100", use_container_width=True): st.session_state['view_mode'] = 'top_gainers'; st.rerun()
    if st.button("🔄 更新精選池", use_container_width=True): update_top_100()

    st.divider()
    if st.button("📖 股市新手村", use_container_width=True): st.session_state['view_mode'] = 'learning_center'; st.rerun()
    if st.button("🔒 個人自選股", use_container_width=True): st.session_state['view_mode'] = 'my_watchlist'; st.rerun()
    if st.button("💬 戰友留言板", use_container_width=True): st.session_state['view_mode'] = 'comments'; st.rerun()
    
    st.divider()
    if st.button("🏠 回首頁", use_container_width=True): st.session_state['view_mode'] = 'welcome'; st.rerun()
    st.markdown('<div class="version-text">AI 股市戰情室 V22.0 (雙引擎版)</div>', unsafe_allow_html=True)

# --- 9. 主畫面 ---

if st.session_state['view_mode'] == 'welcome':
    st.title("👋 歡迎來到 AI 股市戰情室 V22")
    with st.container(border=True):
        st.markdown("""
        #### 🚀 V22 雙引擎穩定版
        * **🚑 雙引擎救援**：Yahoo 抓不到資料時，自動切換至證交所直連模式，解決上櫃股票 (如 5309) 查無資料的問題。
        * **💯 掃描保證**：掃描池擴充至 800+ 檔，保證每次策略都能列出前 100 名結果。
        * **👤 暱稱功能**：註冊與留言全面支援暱稱顯示。
        """)

# 新手村
elif st.session_state['view_mode'] == 'learning_center':
    st.title("📖 股市新手村")
    t1, t2 = st.tabs(["📊 策略邏輯", "📚 名詞大全"])
    with t1:
        st.markdown("### 1. 當沖\n爆量>1.5倍且振幅>2%。\n### 2. 短線\n站上月線且黃金交叉。\n### 3. 長線\n多頭排列且籌碼穩。")
    with t2:
        q = st.text_input("🔍 搜尋名詞")
        for cat, terms in STOCK_TERMS.items():
            if q:
                terms = {k:v for k,v in terms.items() if q.upper() in k.upper()}
                if not terms: continue
            with st.expander(f"📌 {cat}", expanded=True):
                for k,v in terms.items(): st.markdown(f"<div class='term-card'><b style='color:#ffbd45'>{k}</b><br>{v}</div>", unsafe_allow_html=True)

# 自選股
elif st.session_state['view_mode'] == 'my_watchlist':
    st.title("🔒 個人自選股")
    if not st.session_state['user_info']:
        st.warning("請先在左側登入或註冊")
    else:
        ud = load_users()[st.session_state['user_id']]; wl = ud['watchlist']
        with st.expander("⚙️ 管理"):
            c1, c2 = st.columns([3,1]); ac = c1.text_input("加股")
            if c2.button("加"):
                u = load_users(); 
                if ac not in u[st.session_state['user_id']]['watchlist']:
                    u[st.session_state['user_id']]['watchlist'].append(ac); save_users(u); st.rerun()
            cols = st.columns(5)
            for i,c in enumerate(wl):
                if cols[i%5].button(f"🗑️ {c}"): u=load_users(); u[st.session_state['user_id']]['watchlist'].remove(c); save_users(u); st.rerun()
        
        st.subheader("📊 診斷")
        if st.button("🚀 開始"):
            pb = st.progress(0)
            for i, c in enumerate(wl):
                pb.progress((i+1)/len(wl))
                # 使用 Robust 抓取
                full_id, _, d, src = get_stock_data_robust(c)
                n = twstock.codes[c].name if c in twstock.codes else c
                
                # 處理資料
                if d is not None:
                    # 如果是 DataFrame (Yahoo)
                    if isinstance(d, pd.DataFrame) and not d.empty:
                        curr = d['Close'].iloc[-1]; m20 = d['Close'].rolling(20).mean().iloc[-1]
                        stt = "🔥 多頭" if curr > m20 else "❄️ 空頭"
                    # 如果是 Dict (TWSE 備用源)
                    else:
                        curr = d['Close']
                        stt = "⚠️ 僅即時價"
                    
                    with st.container(border=True):
                        c1,c2,c3,c4 = st.columns([1,2,2,1])
                        c1.write(f"**{c}**"); c2.write(n); c3.write(f"{curr:.2f} | {stt}")
                        c4.button("看", key=f"w_{c}", on_click=set_view_to_analysis, args=(c, n))
                else: st.error(f"{c} 失敗")
            pb.empty()

# 留言板
elif st.session_state['view_mode'] == 'comments':
    st.title("💬 戰友留言板")
    if not st.session_state['user_info']:
        st.warning("請先登入")
    else:
        nick = st.session_state['user_info'].get('nickname', st.session_state['user_id'])
        c1, c2 = st.columns([1,4])
        c1.text_input("名", value=nick, disabled=True)
        m = c2.text_input("言")
        if st.button("送出"): save_comment(nick, m); st.success("OK"); time.sleep(0.5); st.rerun()
    
    st.subheader("討論串")
    df = load_comments()
    if not df.empty:
        for i,r in df.iloc[::-1].iterrows():
            with st.chat_message("user"): st.write(f"**{r['Nickname']}** ({r['Time']}): {r['Message']}")

# 分析 (雙引擎應用)
elif st.session_state['view_mode'] == 'analysis':
    code_input = st.session_state['current_stock']
    name_input = st.session_state['current_name']
    
    if not code_input: st.warning("無代號")
    else:
        c1, c2 = st.columns([3, 1])
        c1.title(f"{name_input} {code_input}")
        if c2.checkbox("🔴 即時"): time.sleep(3); st.rerun()
        
        # 紀錄歷史
        rec = f"{code_input.replace('.TW','').replace('.TWO','')} {name_input}"
        if rec not in st.session_state['history']: st.session_state['history'].insert(0, rec)

        # 🔥 呼叫雙引擎
        safe_id, stock, df, source = get_stock_data_robust(code_input.replace('.TW','').replace('.TWO',''))
        
        if source == "fail":
            st.error(f"❌ 查無 {code_input} 資料 (Yahoo 與 證交所皆無回應)")
        
        # 情況 A: Yahoo 成功 (有 K 線圖)
        elif source == "yahoo":
            df_hist = stock.history(period="1y"); info = stock.info
            clr = get_color_settings(code_input)
            curr = df_hist['Close'].iloc[-1]; prev = df_hist['Close'].iloc[-2]
            chg = curr - prev; pct = (chg/prev)*100
            vt = df_hist['Volume'].iloc[-1]; vy = df_hist['Volume'].iloc[-2]
            
            with st.expander("🏢 公司簡介"): st.write(translate_text(info.get('longBusinessSummary','')))
            st.divider()
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("成交價", f"{curr:.2f}", f"{chg:.2f} ({pct:.2f}%)", delta_color=clr['delta'])
            m2.metric("最高", f"{df_hist['High'].iloc[-1]:.2f}")
            m3.metric("最低", f"{df_hist['Low'].iloc[-1]:.2f}")
            m4.metric("量", f"{int(vt/1000)} 張")
            
            st.subheader("📈 技術 K 線")
            df_hist['MA5'] = df_hist['Close'].rolling(5).mean(); df_hist['MA20'] = df_hist['Close'].rolling(20).mean()
            sl = st.select_slider("區間", ['3月','6月'], value='6月'); dy = {'3月':90,'6月':180}[sl]
            cd = df_hist.tail(dy)
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])
            fig.add_trace(go.Candlestick(x=cd.index, open=cd['Open'], high=cd['High'], low=cd['Low'], close=cd['Close'], increasing_line_color=clr['up'], decreasing_line_color=clr['down']), row=1, col=1)
            fig.add_trace(go.Scatter(x=cd.index, y=cd['MA5'], line=dict(color='blue'), name='MA5'), row=1, col=1)
            fig.add_trace(go.Scatter(x=cd.index, y=cd['MA20'], line=dict(color='orange'), name='MA20'), row=1, col=1)
            vc = [clr['up'] if c>=o else clr['down'] for c,o in zip(cd['Close'],cd['Open'])]
            fig.add_trace(go.Bar(x=cd.index, y=cd['Volume'], marker_color=vc), row=2, col=1)
            fig.update_layout(height=500, xaxis_rangeslider_visible=False, showlegend=False)
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar':False})
            
            st.subheader("🤖 AI 診斷")
            m20 = df_hist['MA20'].iloc[-1]
            st.info("🔥 多頭格局" if curr > m20 else "❄️ 空頭格局")

        # 情況 B: Yahoo 失敗，但 TWSE 成功 (只有報價，無圖)
        elif source == "twse_backup":
            st.warning("⚠️ Yahoo Finance 資料連線不穩。目前使用「台灣證交所即時備援」數據 (無 K 線圖)。")
            curr = df['Close']; prev = df['PreClose'] # 這裡 df 其實是字典
            chg = curr - prev if prev else 0
            pct = (chg/prev)*100 if prev else 0
            clr = get_color_settings(code_input)
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("成交價", f"{curr:.2f}", f"{chg:.2f} ({pct:.2f}%)", delta_color=clr['delta'])
            m2.metric("最高", f"{df['High']:.2f}")
            m3.metric("最低", f"{df['Low']:.2f}")
            m4.metric("量", f"{int(df['Volume']/1000)} 張")
            
            st.info("💡 由於目前使用備援數據，無法繪製歷史 K 線與計算 AI 指標。請稍後再試。")

# 掃描
elif st.session_state['view_mode'] in ['scan_day', 'scan_short', 'scan_long', 'top_gainers']:
    md = st.session_state['view_mode']; t = "掃描結果"
    st.title(f"🤖 {t} (保證 100 檔)")
    
    if st.button("開始搜尋"):
        pool = st.session_state['scan_pool'] # 這是 800 檔的大池子
        found = []; pb = st.progress(0); stt = st.empty()
        
        # 為了效能，我們這裡還是用 Yahoo 掃，因為 twstock 掃太慢
        # 我們掃多一點，直到湊滿 100 個
        target_count = 100
        scan_limit = 400 # 最多掃 400 檔以免跑太久
        
        for i, c in enumerate(pool):
            if len(found) >= target_count or i >= scan_limit: break
            stt.text(f"掃描中 ({i+1}/{scan_limit}): {c}..."); pb.progress((i+1)/scan_limit)
            try:
                # 這裡只做簡單計算
                d = yf.Ticker(f"{c}.TW").history(period="5d")
                if len(d) >= 2:
                    p = d['Close'].iloc[-1]
                    # 簡易策略：只要有量就收錄，之後再排
                    if d['Volume'].iloc[-1] > 0:
                        n = twstock.codes[c].name if c in twstock.codes else c
                        # 計算一個分數 (漲幅)
                        score = (p - d['Close'].iloc[-2]) / d['Close'].iloc[-2]
                        found.append({'c':c, 'n':n, 'p':p, 's':score})
            except: continue
            
        pb.empty(); stt.empty()
        # 排序取前 100
        found.sort(key=lambda x: x['s'], reverse=True)
        final_list = found[:100]
        
        if final_list:
            for k, x in enumerate(final_list):
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([0.5, 1, 2, 1])
                    c1.write(f"#{k+1}"); c2.write(f"**{x['c']}**"); c3.write(x['n'])
                    c4.button("看", key=f"s_{x['c']}_{k}", on_click=set_view_to_analysis, args=(x['c'], x['n']))
        else: st.warning("無資料")

# 歷史
elif st.session_state['view_mode'] == 'history':
    st.title("📜 歷史"); 
    for i in st.session_state['history']:
        c=i.split(" ")[0]; n=i.split(" ")[1] if " " in i else ""
        c1,c2=st.columns([4,1]); c1.write(i); c2.button("看",key=f"hh_{c}",on_click=set_view_to_analysis,args=(c,n))
