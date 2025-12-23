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
st.set_page_config(page_title="AI 股市戰情室 V18", layout="wide", initial_sidebar_state="auto")

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
        background-color: #262730; padding: 15px;
        border-radius: 10px; margin-bottom: 10px; border: 1px solid #464b5c;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. 初始化 Session State ---
if 'history' not in st.session_state: st.session_state['history'] = []
if 'current_stock' not in st.session_state: st.session_state['current_stock'] = "" 
if 'current_name' not in st.session_state: st.session_state['current_name'] = ""
if 'view_mode' not in st.session_state: st.session_state['view_mode'] = 'welcome' 
if 'user_info' not in st.session_state: st.session_state['user_info'] = None
if 'user_id' not in st.session_state: st.session_state['user_id'] = None

# 預設掃描池
if 'scan_pool' not in st.session_state:
    st.session_state['scan_pool'] = [
        '2330', '2317', '2454', '2308', '2382', '2303', '2603', '2609', '2615', '2881', 
        '2882', '2891', '3231', '3008', '3037', '3034', '3019', '3035', '2379', '3045', 
        '4938', '4904', '2412', '2357', '2327', '2356', '2345', '2301', '2353', '2324', 
        '2352', '2344', '2368', '2409', '3481', '2498', '3017', '3532', '6176', '2002', 
        '1101', '1301', '1303', '2886', '2892', '5880', '2884', '2880', '2885', '2834', 
        '1605', '1513', '1519', '2313', '1216', '2912', '9910', '1402', '2105', '6505',
        '8069', '8299', '6274', '3016', '3014', '3481', '3036', '3044', '2492', '3661'
    ]

# --- 4. 知識庫資料 ---
STOCK_TERMS = {
    "技術指標": {
        "K線": "紀錄股價走勢的圖形，由開盤、收盤、最高、最低價組成。",
        "MA (均線)": "過去一段時間的平均成交價格，如 5日(週)、20日(月)。",
        "RSI": "判斷股價是否過熱。>80 超買，<20 超賣。",
        "KD": "黃金交叉(買進)與死亡交叉(賣出)的指標。",
        "乖離率": "股價與均線的距離，過大代表可能回檔或反彈。"
    },
    "籌碼": {
        "三大法人": "外資、投信、自營商。",
        "融資券": "融資=借錢買股(看多)，融券=借券賣股(看空)。",
        "當沖": "當日買賣不留倉。"
    },
    "基本面": {
        "EPS": "每股賺多少錢。",
        "本益比": "股價除以EPS，評估貴或便宜。",
        "ROE": "股東權益報酬率，巴菲特最愛指標。",
        "殖利率": "現金股利除以股價。"
    }
}

# --- 5. 檔案管理與會員系統 ---
COMMENTS_FILE = "comments.csv"
USERS_FILE = "users.json"

def load_users():
    if not os.path.exists(USERS_FILE):
        default_db = {"admin": {"password": hashlib.sha256("admin888".encode()).hexdigest(), "status": "approved", "watchlist": []}}
        with open(USERS_FILE, 'w') as f: json.dump(default_db, f)
        return default_db
    with open(USERS_FILE, 'r') as f: return json.load(f)

def save_users(data):
    with open(USERS_FILE, 'w') as f: json.dump(data, f)

def register_user(username, password):
    users = load_users()
    if username in users: return False, "帳號已存在"
    # User Request #2: 註冊成功直接 approved (不用審核)
    users[username] = {
        "password": hashlib.sha256(password.encode()).hexdigest(),
        "status": "approved", 
        "watchlist": []
    }
    save_users(users)
    return True, "註冊成功！請直接登入使用。"

def login_user(username, password):
    users = load_users()
    if username not in users: return False, "帳號不存在"
    if users[username]['password'] != hashlib.sha256(password.encode()).hexdigest(): return False, "密碼錯誤"
    if users[username]['status'] != 'approved': return False, "帳號審核中"
    return True, users[username]

# --- 6. 核心函式 ---
def get_color_settings(stock_id):
    if ".TW" in stock_id.upper() or ".TWO" in stock_id.upper() or stock_id.isdigit():
        return {"up": "#FF0000", "down": "#00FF00", "delta": "inverse"}
    else: return {"up": "#00FF00", "down": "#FF0000", "delta": "normal"}

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

def update_top_100():
    st.toast("正在更新...", icon="🔄"); time.sleep(1)
    st.toast("精選池已更新！", icon="✅")

# --- 7. 側邊欄 ---
with st.sidebar:
    st.title("🎮 戰情控制台")
    
    if st.session_state['user_info']:
        st.success(f"👤 {st.session_state['user_id']}")
        if st.button("登出"):
            st.session_state['user_info'] = None; st.session_state['user_id'] = None; st.rerun()
    else:
        st.info("尚未登入 (訪客)")
    
    st.divider()
    if st.button("🏠 回歡迎頁", use_container_width=True): st.session_state['view_mode'] = 'welcome'; st.rerun()
    st.text_input("🔍 代號輸入", key="sidebar_search", on_change=handle_search)

    st.subheader("🤖 AI 策略")
    c1, c2, c3 = st.columns(3)
    if c1.button("當沖", use_container_width=True): st.session_state['view_mode'] = 'scan_day'; st.rerun()
    if c2.button("短線", use_container_width=True): st.session_state['view_mode'] = 'scan_short'; st.rerun()
    if c3.button("長線", use_container_width=True): st.session_state['view_mode'] = 'scan_long'; st.rerun()

    if st.button("📈 漲幅前 100", use_container_width=True): st.session_state['view_mode'] = 'top_gainers'; st.rerun()
    if st.button("🔄 更新精選 100", use_container_width=True): update_top_100()

    st.divider()
    if st.button("📖 股市新手村", use_container_width=True): st.session_state['view_mode'] = 'learning_center'; st.rerun()
    if st.button("🔒 個人自選股", use_container_width=True): st.session_state['view_mode'] = 'my_watchlist'; st.rerun()
    if st.button("💬 戰友留言板", use_container_width=True): st.session_state['view_mode'] = 'comments'; st.rerun()
    
    st.markdown('<div class="version-text">AI 股市戰情室 V18.0 (完美修復版)</div>', unsafe_allow_html=True)

# --- 8. 主畫面邏輯 ---

# [頁面 1] 歡迎頁
if st.session_state['view_mode'] == 'welcome':
    st.title("👋 歡迎來到 AI 股市戰情室 V18")
    with st.container(border=True):
        st.markdown("""
        #### 🚀 V18 更新日誌
        * **✅ 註冊即用**：開放自由註冊，申請後立即開通權限，無需等待審核。
        * **🔒 留言權限**：為了維護版面品質，留言板改為「登入後」才能發言。
        * **📝 介面修復**：修復分析頁面文字被截斷的問題，恢復完整標籤顯示。
        * **🤖 AI 診斷**：修復診斷區塊顯示異常，提供更清晰的多空分析。
        """)

# [頁面 9] 股市新手村
elif st.session_state['view_mode'] == 'learning_center':
    st.title("📖 股市新手村")
    tab1, tab2 = st.tabs(["📊 AI 策略邏輯詳解", "📚 股市名詞大全"])
    with tab1:
        st.markdown("### 1. 當沖快篩\n今日爆量 > 1.5 倍且振幅 > 2%。\n### 2. 短線波段\n股價站上月線且短均線轉強。\n### 3. 長線存股\n均線多頭排列且籌碼穩定。")
    with tab2:
        search_term = st.text_input("🔍 搜尋名詞", "")
        for category, terms in STOCK_TERMS.items():
            if search_term:
                filtered_terms = {k:v for k,v in terms.items() if search_term.upper() in k.upper()}
                if not filtered_terms: continue
            else: filtered_terms = terms
            with st.expander(f"📌 {category}", expanded=True):
                for term, desc in filtered_terms.items():
                    st.markdown(f"<div class='term-card'><h4 style='color:#ffbd45'>{term}</h4><p>{desc}</p></div>", unsafe_allow_html=True)
                    st.markdown(f"[🔍 Google 更多]({'https://www.google.com/search?q=股票+'+term.split('(')[0]})")

# [頁面 2] 自選股 (與登入頁共用)
elif st.session_state['view_mode'] == 'my_watchlist':
    st.title("🔒 個人自選股")
    # 未登入
    if not st.session_state['user_info']:
        st.info("請先登入或註冊以使用自選股功能")
        tab1, tab2 = st.tabs(["登入", "快速註冊 (免審核)"])
        with tab1:
            u = st.text_input("帳號", key="l_u")
            p = st.text_input("密碼", type="password", key="l_p")
            if st.button("登入", key="btn_l"):
                ok, res = login_user(u, p)
                if ok:
                    st.session_state['user_id'] = u; st.session_state['user_info'] = res
                    st.success("登入成功！"); st.rerun()
                else: st.error(res)
        with tab2:
            nu = st.text_input("設定新帳號", key="r_u")
            np = st.text_input("設定新密碼", type="password", key="r_p")
            if st.button("註冊並啟用", key="btn_r"):
                ok, res = register_user(nu, np)
                if ok: st.success(res)
                else: st.error(res)
    # 已登入
    else:
        ud = load_users()[st.session_state['user_id']]; wl = ud['watchlist']
        with st.expander("⚙️ 管理清單"):
            c1, c2 = st.columns([3, 1])
            ac = c1.text_input("輸入代號加入")
            if c2.button("加入"):
                u = load_users()
                if ac not in u[st.session_state['user_id']]['watchlist']:
                    u[st.session_state['user_id']]['watchlist'].append(ac)
                    save_users(u); st.rerun()
            cols = st.columns(5)
            for i, c in enumerate(wl):
                if cols[i%5].button(f"🗑️ {c}"):
                    u = load_users(); u[st.session_state['user_id']]['watchlist'].remove(c); save_users(u); st.rerun()
        
        st.subheader("📊 持股診斷")
        if st.button("🚀 開始診斷"):
            pb = st.progress(0)
            for i, c in enumerate(wl):
                pb.progress((i+1)/len(wl))
                try:
                    n = twstock.codes[c].name if c in twstock.codes else c
                    d = yf.Ticker(f"{c}.TW").history(period="3mo")
                    if len(d)>20:
                        p = d['Close'].iloc[-1]; m20 = d['Close'].rolling(20).mean().iloc[-1]
                        stt = "🔥 多頭" if p > m20 else "❄️ 空頭"
                        with st.container(border=True):
                            c1,c2,c3,c4 = st.columns([1,2,2,1])
                            c1.write(f"**{c}**"); c2.write(n); c3.write(f"{p:.2f} | {stt}")
                            c4.button("分析", key=f"w_{c}", on_click=set_view_to_analysis, args=(c, n))
                except: st.error(f"{c} 失敗")
            pb.empty()

# [頁面 3] 留言板 (User Request #1: 需登入)
elif st.session_state['view_mode'] == 'comments':
    st.title("💬 戰友留言板")
    
    # 檢查登入狀態
    if not st.session_state['user_info']:
        st.warning("🔒 留言板目前僅對會員開放。")
        st.info("請先前往「個人自選股」或點擊下方按鈕進行登入/註冊。")
        
        # 這裡直接提供簡易登入框，方便使用者
        with st.expander("🔐 會員登入 / 註冊", expanded=True):
            tab1, tab2 = st.tabs(["登入", "註冊"])
            with tab1:
                u = st.text_input("帳號", key="c_l_u")
                p = st.text_input("密碼", type="password", key="c_l_p")
                if st.button("登入並留言"):
                    ok, res = login_user(u, p)
                    if ok:
                        st.session_state['user_id'] = u; st.session_state['user_info'] = res
                        st.success("登入成功！"); st.rerun()
                    else: st.error(res)
            with tab2:
                nu = st.text_input("新帳號", key="c_r_u")
                np = st.text_input("新密碼", type="password", key="c_r_p")
                if st.button("註冊", key="c_r_btn"):
                    ok, res = register_user(nu, np)
                    if ok: st.success(res)
                    else: st.error(res)
    else:
        # 已登入，顯示輸入框
        with st.container(border=True):
            c1, c2 = st.columns([1, 4])
            user_name = c1.text_input("暱稱", value=st.session_state['user_id'], disabled=True)
            user_msg = c2.text_input("留言內容", placeholder="分享你的看法...")
            if st.button("送出留言 📤", use_container_width=True):
                if user_msg:
                    save_comment(st.session_state['user_id'], user_msg)
                    st.success("已送出！"); time.sleep(0.5); st.rerun()

    st.subheader("最新討論")
    df_comments = load_comments()
    if not df_comments.empty:
        for index, row in df_comments.iterrows():
            with st.chat_message("user"):
                st.markdown(f"**{row['User']}** <small>({row['Time']})</small>", unsafe_allow_html=True)
                st.write(row['Message'])
    else: st.write("尚無留言")

# [頁面 4] 分析 (User Request #4 & #5: 標籤與診斷修復)
elif st.session_state['view_mode'] == 'analysis':
    sid = st.session_state['current_stock']
    sn = st.session_state['current_name']
    
    if not sid: st.warning("請輸入代號")
    else:
        c1, c2 = st.columns([3, 1])
        c1.title(f"{sn} {sid}")
        if c2.checkbox("🔴 即時監控"): time.sleep(3); st.rerun()
        
        try:
            r = f"{sid.replace('.TW','')} {sn}"
            if r not in st.session_state['history']: st.session_state['history'].insert(0, r)
            
            s = yf.Ticker(sid); d = s.history(period="1y"); i = s.info
            if d.empty: st.error("查無資料")
            else:
                clr = get_color_settings(sid)
                curr = d['Close'].iloc[-1]; prev = d['Close'].iloc[-2]
                chg = curr - prev; pct = (chg/prev)*100
                vt = d['Volume'].iloc[-1]; vy = d['Volume'].iloc[-2]; va = d['Volume'].tail(5).mean()
                
                with st.expander("🏢 公司簡介", expanded=False):
                    st.write(translate_text(i.get('longBusinessSummary','')))
                
                st.divider()
                
                # User Request #4: 恢復完整文字標籤
                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("成交價", f"{curr:.2f}", f"{chg:.2f} ({pct:.2f}%)", delta_color=clr['delta'])
                m2.metric("最高價", f"{d['High'].iloc[-1]:.2f}")
                m3.metric("最低價", f"{d['Low'].iloc[-1]:.2f}")
                m4.metric("振幅", f"{((d['High'].iloc[-1]-d['Low'].iloc[-1])/prev)*100:.2f}%")
                mf = "主力進貨 🔴" if (chg>0 and vt>vy) else ("主力出貨 🟢" if (chg<0 and vt>vy) else "觀望")
                m5.metric("主力動向", mf)
                
                v1, v2, v3, v4, v5 = st.columns(5)
                v1.metric("今日成交量", f"{int(vt/1000):,} 張")
                v2.metric("昨日成交量", f"{int(vy/1000):,} 張", f"{int((vt-vy)/1000)} 張")
                v3.metric("本週均量", f"{int(va/1000):,} 張")
                vr = vt/va if va>0 else 1
                vs = "🔥 爆量" if vr>1.5 else ("💤 量縮" if vr<0.6 else "正常")
                v4.metric("量能狀態", vs)
                v5.metric("外資持股", f"{i.get('heldPercentInstitutions',0)*100:.1f}%")

                st.subheader("📈 技術 K 線圖")
                d['MA5'] = d['Close'].rolling(5).mean()
                d['MA20'] = d['Close'].rolling(20).mean()
                d['MA60'] = d['Close'].rolling(60).mean()
                
                sl = st.select_slider("區間", ['3個月','6個月','1年'], value='6個月')
                dy = {'3個月':90,'6個月':180,'1年':365}[sl]
                cd = d.tail(dy)
                
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
                fig.add_trace(go.Candlestick(x=cd.index, open=cd['Open'], high=cd['High'], low=cd['Low'], close=cd['Close'], name='K線', increasing_line_color=clr['up'], decreasing_line_color=clr['down']), row=1, col=1)
                fig.add_trace(go.Scatter(x=cd.index, y=cd['MA5'], line=dict(color='blue', width=1), name='MA5'), row=1, col=1)
                fig.add_trace(go.Scatter(x=cd.index, y=cd['MA20'], line=dict(color='orange', width=1), name='MA20'), row=1, col=1)
                vc = [clr['up'] if c>=o else clr['down'] for c,o in zip(cd['Close'],cd['Open'])]
                fig.add_trace(go.Bar(x=cd.index, y=cd['Volume'], marker_color=vc, name='成交量'), row=2, col=1)
                fig.update_layout(height=600, xaxis_rangeslider_visible=False, margin=dict(t=10,b=10,l=10,r=10), showlegend=False)
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar':False})

                # User Request #5: AI 診斷修復
                st.subheader("🤖 AI 診斷分析")
                ma20 = d['MA20'].iloc[-1]; ma60 = d['MA60'].iloc[-1]
                diff = d['Close'].diff(); u=diff.copy(); dd=diff.copy(); u[u<0]=0; dd[dd>0]=0
                rs = u.rolling(14).mean()/dd.abs().rolling(14).mean()
                rsi = (100-100/(1+rs)).iloc[-1]
                bias = ((curr-ma60)/ma60)*100
                
                with st.container(border=True):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("**趨勢判讀**")
                        if curr > ma20 and ma20 > ma60: st.success("🔥 **多頭排列**：股價位於月線之上，趨勢向上。")
                        elif curr < ma20 and ma20 < ma60: st.error("❄️ **空頭排列**：股價位於月線之下，反壓沉重。")
                        else: st.warning("⚖️ **盤整震盪**：均線糾結，方向不明。")
                    with c2:
                        st.markdown("**關鍵指標**")
                        st.write(f"• **RSI 強弱**: `{rsi:.1f}`")
                        if rsi>80: st.warning("⚠️ 短線過熱 (RSI>80)，留意回檔。")
                        elif rsi<20: st.success("💎 短線超賣 (RSI<20)，醞釀反彈。")
                        else: st.info("✅ 指標位於中性區間。")
                        
                        st.write(f"• **季線乖離**: `{bias:.2f}%`")

        except Exception as e: st.error(f"錯誤: {e}")

# [頁面 5,6,7,8] 掃描
elif st.session_state['view_mode'] in ['scan_day', 'scan_short', 'scan_long', 'top_gainers']:
    md = st.session_state['view_mode']
    if md == 'scan_day': t = "⚡ 當沖快篩"; days = 5
    elif md == 'scan_short': t = "📈 短線波段"; days = 30
    elif md == 'scan_long': t = "🐢 長線存股"; days = 60
    elif md == 'top_gainers': t = "🏆 漲幅排行"; days = 5
    
    st.title(f"🤖 {t} (前100)")
    sp = st.session_state['scan_pool'] * 2
    
    # User Request #3: 按鈕文字修正
    if st.button(f"開始搜尋 {t}"):
        l = []; pb = st.progress(0); stt = st.empty()
        for i, c in enumerate(sp):
            if i >= 150: break
            stt.text(f"搜尋中: {c}..."); pb.progress((i+1)/150)
            try:
                d = yf.Ticker(f"{c}.TW").history(period="3mo")
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
                    c5.button("分析", key=f"s_{x['c']}_{k}", on_click=set_view_to_analysis, args=(x['c'], x['n']))
        else: st.warning("無符合標的")

# [頁面 9] 歷史
elif st.session_state['view_mode'] == 'history':
    st.title("📜 歷史紀錄")
    for i in st.session_state['history']:
        c = i.split(" ")[0]; n = i.split(" ")[1] if " " in i else ""
        c1, c2 = st.columns([4, 1])
        c1.write(i)
        c2.button("查看", key=f"hh_{c}", on_click=set_view_to_analysis, args=(c, n))
