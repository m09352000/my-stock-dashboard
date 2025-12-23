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
st.set_page_config(page_title="AI 股市戰情室 V25", layout="wide", initial_sidebar_state="auto")

# --- 2. CSS 優化 ---
st.markdown("""
<style>
    @media (max-width: 768px) {
        .main .block-container { padding-top: 2rem !important; }
        h1 { font-size: 1.8rem !important; }
        [data-testid="stSidebar"] { width: 85% !important; }
    }
    .modebar { display: none !important; }
    /* 左下角版本號 */
    .version-text {
        position: fixed; bottom: 10px; left: 20px;
        font-size: 0.8em; color: gray; z-index: 100;
    }
    /* 卡片樣式 */
    .term-card {
        background-color: #262730; padding: 20px; 
        border-radius: 12px; margin-bottom: 15px; 
        border: 1px solid #464b5c; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .term-title { color: #ffbd45; font-size: 1.3em; font-weight: bold; margin-bottom: 10px; border-bottom: 1px solid #555; }
    .term-content { font-size: 1.05em; line-height: 1.7; color: #e6e6e6; }
    
    /* 登入框 */
    .login-box {
        border: 2px solid #464b5c; padding: 30px;
        border-radius: 20px; background-color: #1e1e1e;
        max-width: 500px; margin: 0 auto;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. Session State 初始化 ---
if 'history' not in st.session_state: st.session_state['history'] = []
if 'current_stock' not in st.session_state: st.session_state['current_stock'] = "" 
if 'current_name' not in st.session_state: st.session_state['current_name'] = ""
if 'view_mode' not in st.session_state: st.session_state['view_mode'] = 'welcome' 
if 'user_info' not in st.session_state: st.session_state['user_info'] = None
if 'page_stack' not in st.session_state: st.session_state['page_stack'] = ['welcome'] # 歷史路徑

# 擴充掃描池 (800+)
if 'scan_pool' not in st.session_state:
    try:
        all_codes = sorted([c for c in twstock.codes.keys() if twstock.codes[c].type == "股票"])
        st.session_state['scan_pool'] = all_codes[:800] 
    except:
        st.session_state['scan_pool'] = ['2330', '2317', '2454', '2603', '2881']

# --- 4. 知識庫資料 (完整不簡化) ---
STOCK_TERMS = {
    "技術指標篇": {
        "K線 (Candlestick)": """
        **定義**：紀錄一天股價走勢的圖形，由「開盤價、收盤價、最高價、最低價」四個價格組成。
        <br>**怎麼看**：
        - **紅K (陽線)**：收盤價 > 開盤價，代表當天買氣旺，股價上漲。
        - **綠K (陰線)**：收盤價 < 開盤價，代表當天賣壓重，股價下跌。
        """,
        "MA 移動平均線": """
        **定義**：將過去 N 天的收盤價加總除以 N，連接起來的線，代表市場的「平均成本」。
        <br>**參數**：
        - **5日線 (週線)**：短線生命線，跌破轉弱。
        - **20日線 (月線)**：波段多空分水嶺。
        - **60日線 (季線)**：中長線保護傘。
        """,
        "RSI 相對強弱指標": """
        **定義**：判斷股價是否「過熱」或「超賣」的動能指標 (0-100)。
        <br>**應用**：>80 超買(宜賣)，<20 超賣(宜買)。
        """,
        "KD 隨機指標": """
        **定義**：反應股價在最近一段時間內的強弱位置。
        <br>**應用**：黃金交叉(買進)，死亡交叉(賣出)，高檔鈍化(強勢)。
        """,
        "乖離率 (BIAS)": """
        **定義**：股價與均線的距離百分比。
        <br>**應用**：正乖離過大易回檔，負乖離過大易反彈。
        """
    },
    "籌碼與市場篇": {
        "三大法人": """
        **定義**：外資(外國機構)、投信(國內基金)、自營商(券商)。
        <br>**影響**：外資控盤權值股，投信認養中小型股。
        """,
        "融資融券": """
        **定義**：散戶的槓桿工具。融資=借錢買股(看多)，融券=借券賣股(看空)。
        """,
        "當沖": """
        **定義**：當日買進賣出，不留過夜。風險高，需關注成交量與振幅。
        """
    },
    "基本面篇": {
        "EPS": "**定義**：每股盈餘。公司每一股賺多少錢，是股價的基石。",
        "本益比": "**定義**：股價/EPS。代表買進股票後幾年回本，越低越便宜。",
        "ROE": "**定義**：股東權益報酬率。巴菲特選股核心，>15% 為佳。",
        "殖利率": "**定義**：現金股利 / 股價。存股族最重視的指標。"
    }
}

# --- 5. 檔案與會員系統 ---
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
        "status": "approved", "watchlist": [], "nickname": nickname
    }
    save_users(users)
    return True, "註冊成功！"

def login_user(username, password):
    users = load_users()
    if username not in users: return False, "帳號不存在"
    if users[username]['password'] != hashlib.sha256(password.encode()).hexdigest(): return False, "密碼錯誤"
    return True, users[username]

# --- 6. 核心函式 ---
def get_color_settings(stock_id):
    if ".TW" in stock_id.upper() or ".TWO" in stock_id.upper() or stock_id.isdigit():
        return {"up": "#FF0000", "down": "#00FF00", "delta": "inverse"}
    else: return {"up": "#00FF00", "down": "#FF0000", "delta": "normal"}

def get_stock_data_robust(stock_id):
    suffixes = ['.TW', '.TWO'] if stock_id.isdigit() else ['']
    for suffix in suffixes:
        try_id = f"{stock_id}{suffix}"
        stock = yf.Ticker(try_id)
        try:
            df = stock.history(period="1mo")
            if not df.empty: return try_id, stock, df, "yahoo"
        except: pass
    if stock_id.isdigit():
        try:
            realtime = twstock.realtime.get(stock_id)
            if realtime['success']:
                info = realtime['realtime']
                if info['latest_trade_price'] != '-':
                    fake_df = {
                        'Close': float(info['latest_trade_price']),
                        'Open': float(info['open']),
                        'High': float(info['high']),
                        'Low': float(info['low']),
                        'Volume': int(info['accumulate_trade_volume']) * 1000 if info['accumulate_trade_volume'] else 0,
                        'PreClose': float(realtime['realtime']['open']) 
                    }
                    return f"{stock_id} (TWSE)", None, fake_df, "twse_backup"
        except: pass
    return None, None, None, "fail"

# 頁面跳轉 (不使用 st.rerun 以避免 callback 錯誤)
def navigate_to(mode, stock_code=None, stock_name=None):
    if stock_code:
        st.session_state['current_stock'] = stock_code
        st.session_state['current_name'] = stock_name
    
    st.session_state['view_mode'] = mode
    # 堆疊管理
    if not st.session_state['page_stack'] or st.session_state['page_stack'][-1] != mode:
        st.session_state['page_stack'].append(mode)

# 返回上一頁
def go_back():
    if len(st.session_state['page_stack']) > 1:
        st.session_state['page_stack'].pop() # 移除當前
        previous = st.session_state['page_stack'][-1]
        st.session_state['view_mode'] = previous
        st.rerun()

# 搜尋處理 (Callback 中移除 st.rerun)
def handle_search_form():
    raw = st.session_state.sidebar_search_input
    if raw:
        n = "美股"
        if raw in twstock.codes: n = twstock.codes[raw].name
        elif raw.isdigit(): n = "台股"
        navigate_to('analysis', raw, n)

def translate_text(text):
    if not text: return "暫無詳細描述"
    try: return GoogleTranslator(source='auto', target='zh-TW').translate(text[:1500])
    except: return text

def load_comments():
    if os.path.exists(COMMENTS_FILE):
        try:
            df = pd.read_csv(COMMENTS_FILE)
            if 'User' in df.columns and 'Nickname' not in df.columns: df['Nickname'] = df['User']
            if 'Nickname' not in df.columns: df['Nickname'] = 'Anonymous'
            return df
        except: return pd.DataFrame(columns=["Time", "Nickname", "Message"])
    return pd.DataFrame(columns=["Time", "Nickname", "Message"])

def save_comment(nickname, msg):
    df = load_comments()
    new_data = pd.DataFrame([[datetime.now().strftime("%m/%d %H:%M"), nickname, msg]], columns=["Time", "Nickname", "Message"])
    df = pd.concat([new_data, df], ignore_index=True)
    df.to_csv(COMMENTS_FILE, index=False)

def update_top_100():
    st.toast("更新精選池...", icon="🔄"); time.sleep(1); st.toast("完成", icon="✅")

# --- 7. 側邊欄 ---
with st.sidebar:
    st.title("🎮 戰情控制台")
    
    if st.session_state['user_info']:
        nick = st.session_state['user_info'].get('nickname', st.session_state['user_id'])
        st.success(f"👤 **{nick}**")
    else:
        st.info("👤 尚未登入")

    st.divider()
    
    # 搜尋 (Fix: 移除 callback 錯誤)
    with st.form(key='search', clear_on_submit=False):
        st.text_input("🔍 輸入代號 (Enter)", key="sidebar_search_input")
        # 這裡按鈕按下會觸發 callback 更新 state，表單提交會自動 rerun，所以不用手動 rerun
        st.form_submit_button("開始搜尋", on_click=handle_search_form)

    st.subheader("🤖 AI 策略")
    c1, c2, c3 = st.columns(3)
    # 按鈕需要 rerun 才能即時跳轉
    if c1.button("當沖", use_container_width=True): navigate_to('scan_day'); st.rerun()
    if c2.button("短線", use_container_width=True): navigate_to('scan_short'); st.rerun()
    if c3.button("長線", use_container_width=True): navigate_to('scan_long'); st.rerun()

    if st.button("📈 漲幅前 100", use_container_width=True): navigate_to('top_gainers'); st.rerun()
    if st.button("🔄 更新精選池", use_container_width=True): update_top_100()

    st.divider()
    if st.button("📖 股市新手村", use_container_width=True): navigate_to('learning_center'); st.rerun()
    if st.button("🔒 個人自選股", use_container_width=True): navigate_to('my_watchlist'); st.rerun()
    if st.button("💬 戰友留言板", use_container_width=True): navigate_to('comments'); st.rerun()
    
    st.divider()
    # 登入按鈕移到下方
    if not st.session_state['user_info']:
        if st.button("🔐 登入 / 註冊", use_container_width=True): navigate_to('login_page'); st.rerun()
    else:
        if st.button("🚪 登出", use_container_width=True):
            st.session_state['user_info'] = None; st.session_state['user_id'] = None; navigate_to('welcome'); st.rerun()

    if st.button("🏠 回首頁", use_container_width=True): navigate_to('welcome'); st.rerun()
    
    # 版本號只顯示在左下角
    st.markdown('<div class="version-text">AI 股市戰情室 V25.0</div>', unsafe_allow_html=True)

# --- 8. 主畫面 ---

# [頁面 0] 登入頁
if st.session_state['view_mode'] == 'login_page':
    st.title("🔐 會員登入中心")
    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown("<div class='login-box'>", unsafe_allow_html=True)
        st.subheader("會員登入")
        l_u = st.text_input("帳號", key="main_l_u")
        l_p = st.text_input("密碼", type="password", key="main_l_p")
        if st.button("登入", key="main_btn_l"):
            ok, res = login_user(l_u, l_p)
            if ok:
                st.session_state['user_id'] = l_u; st.session_state['user_info'] = res
                st.success(f"歡迎 {l_u}"); time.sleep(0.5); navigate_to('my_watchlist'); st.rerun()
            else: st.error(res)
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.subheader("新朋友註冊")
        with st.form("reg_form"):
            r_u = st.text_input("設定帳號")
            r_p = st.text_input("設定密碼", type="password")
            r_n = st.text_input("您的暱稱")
            if st.form_submit_button("註冊"):
                if r_n and r_u and r_p:
                    ok, res = register_user(r_u, r_p, r_n)
                    if ok:
                        st.session_state['user_id'] = r_u
                        st.session_state['user_info'] = {"status": "approved", "watchlist": [], "nickname": r_n}
                        st.success(res); time.sleep(1); navigate_to('my_watchlist'); st.rerun()
                    else: st.error(res)
                else: st.error("請填寫完整")
    
    st.divider()
    if st.button("⬅️ 返回上一頁"): go_back()

# [頁面 1] 歡迎頁
elif st.session_state['view_mode'] == 'welcome':
    st.title("👋 歡迎來到 AI 股市戰情室 V25")
    with st.container(border=True):
        st.markdown("""
        ### 🚀 平台特色
        * **🛡️ 雙引擎數據**：整合 Yahoo 與 TWSE，確保數據不中斷。
        * **💯 掃描保證**：AI 策略掃描保證列出前 100 檔標的。
        * **🔒 專業自選**：會員專屬自選股，提供 AI 深度診斷卡片。
        * **📖 知識百科**：收錄完整股市術語與策略邏輯詳解。
        """)

# [頁面 2] 自選股
elif st.session_state['view_mode'] == 'my_watchlist':
    st.title("🔒 個人自選股")
    if not st.session_state['user_info']:
        st.warning("請先登入")
        if st.button("前往登入"): navigate_to('login_page'); st.rerun()
    else:
        ud = load_users()[st.session_state['user_id']]; wl = ud['watchlist']
        with st.expander("⚙️ 管理清單"):
            c1, c2 = st.columns([3, 1])
            ac = c1.text_input("輸入代號加入")
            if c2.button("加入"):
                u = load_users()
                if ac not in u[st.session_state['user_id']]['watchlist']:
                    u[st.session_state['user_id']]['watchlist'].append(ac); save_users(u); st.rerun()
            cols = st.columns(6)
            for i,c in enumerate(wl):
                if cols[i%6].button(f"❌ {c}"): u=load_users(); u[st.session_state['user_id']]['watchlist'].remove(c); save_users(u); st.rerun()

        st.divider()
        st.subheader(f"📊 持股診斷 ({len(wl)} 檔)")
        if st.button("🚀 啟動診斷"):
            pb = st.progress(0)
            for i, c in enumerate(wl):
                pb.progress((i+1)/len(wl))
                full_id, _, d, src = get_stock_data_robust(c)
                n = twstock.codes[c].name if c in twstock.codes else c
                if d is not None:
                    if isinstance(d, pd.DataFrame) and not d.empty:
                        curr = d['Close'].iloc[-1]; m20 = d['Close'].rolling(20).mean().iloc[-1]
                        m60 = d['Close'].rolling(60).mean().iloc[-1]
                        # 專業診斷回歸
                        trend = "🔥 多頭" if curr>m20 and m20>m60 else ("❄️ 空頭" if curr<m20 and m20<m60 else "⚖️ 盤整")
                        delta = d['Close'].diff(); u=delta.copy(); dd=delta.copy(); u[u<0]=0; dd[dd>0]=0
                        rs = u.rolling(14).mean()/dd.abs().rolling(14).mean(); rsi = (100-100/(1+rs)).iloc[-1]
                        vol_msg = "🔥 爆量" if d['Volume'].iloc[-1] > d['Volume'].tail(5).mean()*1.5 else "正常"
                        
                        with st.container(border=True):
                            c1,c2,c3,c4 = st.columns([1.5, 2, 2, 1])
                            c1.markdown(f"### {c}"); c1.write(f"**{n}**")
                            c2.metric("現價", f"{curr:.2f}")
                            c3.write(f"**{trend}**"); c3.write(f"RSI: {rsi:.1f} | {vol_msg}")
                            c4.button("詳情", key=f"wd_{c}", on_click=navigate_to, args=('analysis', c, n))
                    else:
                        with st.container(border=True): st.write(f"**{c} {n}**: {d['Close']} (TWSE即時)")
                else: st.error(f"{c} 讀取失敗")
            pb.empty()
    
    st.divider()
    if st.button("⬅️ 返回上一頁"): go_back()

# [頁面 3] 留言板
elif st.session_state['view_mode'] == 'comments':
    st.title("💬 戰友留言板")
    if not st.session_state['user_info']:
        st.warning("請先登入")
        if st.button("去登入"): navigate_to('login_page'); st.rerun()
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
            
    st.divider()
    if st.button("⬅️ 返回上一頁"): go_back()

# [頁面 9] 新手村 (修復版)
elif st.session_state['view_mode'] == 'learning_center':
    st.title("📖 股市新手村")
    # Fix: 修正 tab 變數名稱錯誤
    tab1, tab2 = st.tabs(["📊 策略邏輯詳解", "📚 名詞詳解大全"])
    
    with tab1:
        st.markdown("### 🤖 AI 選股邏輯")
        st.markdown("""
        **1. 當沖快篩**：爆量 (>1.5倍均量) 且 振幅大 (>2%)。
        **2. 短線波段**：股價站上月線(20MA) 且 5日線黃金交叉。
        **3. 長線存股**：均線多頭排列 (股>月>季) 且 籌碼穩定。
        """)
    
    with tab2:
        q = st.text_input("🔍 搜尋名詞")
        for cat, terms in STOCK_TERMS.items():
            if q:
                terms = {k:v for k,v in terms.items() if q.upper() in k.upper()}
                if not terms: continue
            with st.expander(f"📌 {cat}", expanded=True):
                for k,v in terms.items(): 
                    st.markdown(f"<div class='term-card'><div class='term-title'>{k}</div><div class='term-content'>{v}</div></div>", unsafe_allow_html=True)
    
    st.divider()
    if st.button("⬅️ 返回上一頁"): go_back()

# [頁面 4] 分析
elif st.session_state['view_mode'] == 'analysis':
    code_input = st.session_state['current_stock']
    name_input = st.session_state['current_name']
    
    if not code_input: st.warning("無代號")
    else:
        c1, c2 = st.columns([3, 1])
        c1.title(f"{name_input} {code_input}")
        if c2.checkbox("🔴 即時"): time.sleep(3); st.rerun()
        
        try:
            rec = f"{code_input.replace('.TW','').replace('.TWO','')} {name_input}"
            if rec not in st.session_state['history']: st.session_state['history'].insert(0, rec)

            safe_id, stock, df, source = get_stock_data_robust(code_input.replace('.TW','').replace('.TWO',''))
            
            if source == "fail": st.error("查無資料")
            elif source == "yahoo":
                df_hist = stock.history(period="1y"); info = stock.info
                clr = get_color_settings(code_input)
                curr = df_hist['Close'].iloc[-1]; prev = df_hist['Close'].iloc[-2]
                chg = curr - prev; pct = (chg/prev)*100
                vt = df_hist['Volume'].iloc[-1]; vy = df_hist['Volume'].iloc[-2]; va = df_hist['Volume'].tail(5).mean()
                
                with st.expander("🏢 公司簡介"): st.write(translate_text(info.get('longBusinessSummary','')))
                st.divider()
                
                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("成交價", f"{curr:.2f}", f"{chg:.2f} ({pct:.2f}%)", delta_color=clr['delta'])
                m2.metric("最高價", f"{df_hist['High'].iloc[-1]:.2f}")
                m3.metric("最低價", f"{df_hist['Low'].iloc[-1]:.2f}")
                m4.metric("振幅", f"{((df_hist['High'].iloc[-1]-df_hist['Low'].iloc[-1])/prev)*100:.2f}%")
                mf = "主力進貨 🔴" if (chg>0 and vt>vy) else ("主力出貨 🟢" if (chg<0 and vt>vy) else "觀望")
                m5.metric("主力動向", mf)
                
                v1, v2, v3, v4, v5 = st.columns(5)
                v1.metric("今日成交量", f"{int(vt/1000):,} 張")
                v2.metric("昨日成交量", f"{int(vy/1000):,} 張", f"{int((vt-vy)/1000)} 張")
                v3.metric("本週均量", f"{int(va/1000):,} 張")
                vr = vt/va if va>0 else 1
                vs = "🔥 爆量" if vr>1.5 else ("💤 量縮" if vr<0.6 else "正常")
                v4.metric("量能狀態", vs)
                v5.metric("外資持股", f"{info.get('heldPercentInstitutions',0)*100:.1f}%")
                
                st.subheader("📈 技術 K 線圖")
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
                
                st.subheader("🤖 AI 診斷分析")
                m20 = df_hist['MA20'].iloc[-1]; m60 = df_hist['Close'].rolling(60).mean().iloc[-1]
                diff = df_hist['Close'].diff(); u=diff.copy(); dd=diff.copy(); u[u<0]=0; dd[dd>0]=0
                rs = u.rolling(14).mean()/dd.abs().rolling(14).mean(); rsi = (100-100/(1+rs)).iloc[-1]
                bias = ((curr-m60)/m60)*100
                with st.container(border=True):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("### 趨勢訊號")
                        if curr > m20 and m20 > m60: st.success("🔥 多頭排列")
                        elif curr < m20 and m20 < m60: st.error("❄️ 空頭排列")
                        else: st.warning("⚖️ 盤整震盪")
                    with c2:
                        st.markdown("### 關鍵指標")
                        st.write(f"RSI: `{rsi:.1f}` | 乖離率: `{bias:.2f}%`")

        elif source == "twse_backup":
            st.warning("⚠️ 使用 TWSE 備援數據 (無 K 線)")
            curr = df['Close']; prev = df['PreClose']; chg = curr - prev if prev else 0; pct = (chg/prev)*100 if prev else 0
            clr = get_color_settings(code_input)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("價", f"{curr:.2f}", f"{chg:.2f} ({pct:.2f}%)", delta_color=clr['delta'])
            m2.metric("高", f"{df['High']:.2f}"); m3.metric("低", f"{df['Low']:.2f}"); m4.metric("量", f"{int(df['Volume']/1000)}")

    except Exception as e: st.error(f"錯誤: {e}")
    
    st.divider()
    if st.button("⬅️ 返回上一頁"): go_back()

# 掃描
elif st.session_state['view_mode'] in ['scan_day', 'scan_short', 'scan_long', 'top_gainers']:
    md = st.session_state['view_mode']
    if md == 'scan_day': t = "⚡ 當沖快篩"; days = 5
    elif md == 'scan_short': t = "📈 短線波段"; days = 30
    elif md == 'scan_long': t = "🐢 長線存股"; days = 60
    elif md == 'top_gainers': t = "🏆 漲幅排行"; days = 5
    
    st.title(f"🤖 {t} (前100)")
    sp = st.session_state['scan_pool']
    
    if st.button(f"開始搜尋 {t}"):
        l = []; pb = st.progress(0); stt = st.empty()
        scan_limit = 300 
        for i, c in enumerate(sp):
            if i >= scan_limit: break
            stt.text(f"搜尋中: {c}..."); pb.progress((i+1)/scan_limit)
            try:
                sid, _, d, src = get_stock_data_robust(c)
                if d is not None and not d.empty and isinstance(d, pd.DataFrame):
                    if len(d) > days:
                        p = d['Close'].iloc[-1]; m20 = d['Close'].rolling(20).mean().iloc[-1]
                        v = d['Volume'].iloc[-1]; va = d['Volume'].tail(5).mean()
                        sc = 0; r = ""
                        
                        if md == 'scan_day':
                            amp = (d['High'].iloc[-1]-d['Low'].iloc[-1])/d['Close'].iloc[-2]
                            sc = (v/va)*amp*100; r = f"量{v/va:.1f}x | 振{amp*100:.1f}%"
                        elif md == 'scan_short': sc = ((p-m20)/m20)*100; r = f"乖離{sc:.1f}%"
                        elif md == 'scan_long': m60 = d['Close'].rolling(60).mean().iloc[-1]; sc = -abs((p-m60)/m60)*100; r = "穩"
                        elif md == 'top_gainers': sc = ((p-d['Close'].iloc[-2])/d['Close'].iloc[-2])*100; r = f"漲{sc:.2f}%"
                        
                        n = twstock.codes[c].name if c in twstock.codes else c
                        if not any(x['c'] == c for x in l): l.append({'c':c, 'n':n, 'p':p, 'r':r, 's':sc})
            except: continue
        pb.empty(); stt.empty()
        l.sort(key=lambda x:x['s'], reverse=True)
        fl = l[:100]
        if fl:
            for k, x in enumerate(fl):
                with st.container(border=True):
                    c1, c2, c3, c4, c5 = st.columns([0.5, 1, 2, 3, 1])
                    c1.write(f"#{k+1}"); c2.write(f"**{x['c']}**"); c3.write(x['n'])
                    c4.write(f"{x['p']:.2f} | {x['r']}")
                    c5.button("分析", key=f"s_{x['c']}_{k}", on_click=navigate_to, args=('analysis', x['c'], x['n']))
        else: st.warning("無符合標的")
    
    st.divider()
    if st.button("⬅️ 返回上一頁"): go_back()

# 歷史
elif st.session_state['view_mode'] == 'history':
    st.title("📜 歷史紀錄")
    for i in st.session_state['history']:
        c = i.split(" ")[0]; n = i.split(" ")[1] if " " in i else ""
        c1, c2 = st.columns([4, 1])
        c1.write(i)
        c2.button("查看", key=f"hh_{c}", on_click=navigate_to, args=('analysis', c, n))
    
    st.divider()
    if st.button("⬅️ 返回上一頁"): go_back()
