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
st.set_page_config(page_title="AI 股市戰情室 V17", layout="wide", initial_sidebar_state="auto")

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
    /* 名詞解釋卡片樣式 */
    .term-card {
        background-color: #262730;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
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
if 'scan_pool' not in st.session_state:
    st.session_state['scan_pool'] = [
        '2330', '2317', '2454', '2308', '2382', '2303', '2603', '2609', '2615', '2881', 
        '2882', '2891', '3231', '3008', '3037', '3034', '3019', '3035', '2379', '3045', 
        '4938', '4904', '2412', '2357', '2327', '2356', '2345', '2301', '2353', '2324', 
        '2352', '2344', '2368', '2409', '3481', '2498', '3017', '3532', '6176', '2002', 
        '1101', '1301', '1303', '2886', '2892', '5880', '2884', '2880', '2885', '2834', 
        '1605', '1513', '1519', '2313', '1216', '2912', '9910', '1402', '2105', '6505',
        '8069', '8299', '6274', '3016', '3014', '3481', '3036', '3044', '2492', '3661',
        '3443', '6669', '6415', '5274', '3529', '5269', '6104', '6213', '6269', '6278',
        '6488', '6515', '6531', '6533', '6548', '6643', '6719', '6770', '6781', '8046',
        '2618', '2610', '2606', '2605', '1503', '1504', '1514', '1515', '1516', '1517'
    ]

# --- 4. 知識庫資料 (內建名詞辭典) ---
STOCK_TERMS = {
    "技術指標": {
        "K線 (Candlestick)": "紀錄股價走勢的圖形，由開盤價、收盤價、最高價、最低價組成。紅K代表漲(收盤>開盤)，綠K代表跌(收盤<開盤)。",
        "MA (移動平均線)": "Moving Average，代表過去一段時間的平均成交價格。常見有 5日(週線)、20日(月線)、60日(季線)。是用來看趨勢的重要指標。",
        "RSI (相對強弱指標)": "用來判斷股價是否「過熱」或「超賣」。數值 0-100，通常 >80 代表超買(可能回跌)，<20 代表超賣(可能反彈)。",
        "KD (隨機指標)": "由 K 值和 D 值組成。K 線由下往上穿過 D 線稱為「黃金交叉」(買進訊號)；反之為「死亡交叉」(賣出訊號)。",
        "乖離率 (BIAS)": "股價與均線的距離。正乖離過大代表漲太多可能回檔；負乖離過大代表跌太深可能反彈。",
        "MACD": "平滑異同移動平均線，用來判斷中長期趨勢。紅柱狀體代表多頭增強，綠柱狀體代表空頭增強。"
    },
    "籌碼與市場": {
        "三大法人": "指「外資」、「投信」、「自營商」。他們資金龐大，動向常左右大盤趨勢。",
        "外資": "外國的投資機構。資金最龐大，偏好權值股（如台積電），操作通常看長線。",
        "投信": "國內的基金公司。資金來自大眾基金，偏好中小型股，操作節奏較快，常有「季底作帳」行情。",
        "融資": "向券商借錢買股票（看多）。融資餘額過高代表散戶多，籌碼凌亂，股價較難漲。",
        "融券": "向券商借股票來賣（看空）。預期未來股價下跌，先賣出高價，之後再買回還給券商。",
        "當沖 (Day Trading)": "當日沖銷。在同一天內買進並賣出，不留股票過夜。適合波動大的股票，但風險極高。"
    },
    "基本面": {
        "EPS (每股盈餘)": "Earnings Per Share，代表公司每 1 股賺了多少錢。EPS 越高，代表公司獲利能力越強。",
        "本益比 (P/E Ratio)": "股價除以 EPS。用來評估股價是否昂貴。通常 10-15 倍算便宜，20 倍以上算貴（視產業而定）。",
        "ROE (股東權益報酬率)": "公司拿股東的錢去投資賺回來的報酬率。巴菲特最愛指標，通常 >15% 算是好公司。",
        "殖利率 (Yield)": "現金股利除以股價。代表你買這張股票，公司每年發多少利息給你。存股族最重視的指標。",
        "營收 (Revenue)": "公司賣產品或服務收到的總金額。營收創新高通常是股價上漲的動力。"
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
    users[username] = {"password": hashlib.sha256(password.encode()).hexdigest(), "status": "pending", "watchlist": []}
    save_users(users)
    return True, "申請成功，請等待站長核准！"

def login_user(username, password):
    users = load_users()
    if username not in users: return False, "帳號不存在"
    if users[username]['password'] != hashlib.sha256(password.encode()).hexdigest(): return False, "密碼錯誤"
    if users[username]['status'] != 'approved': return False, "帳號審核中"
    return True, users[username]

def approve_user(username):
    users = load_users()
    if username in users:
        users[username]['status'] = 'approved'; save_users(users); return True
    return False

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
    st.session_state['scan_pool'] = st.session_state['scan_pool'] 
    st.toast("精選池已更新！", icon="✅")

# --- 7. 側邊欄 ---
with st.sidebar:
    st.title("🎮 戰情控制台")
    
    if st.session_state['user_info']:
        st.success(f"👤 {st.session_state['user_id']}")
        if st.button("登出"):
            st.session_state['user_info'] = None; st.session_state['user_id'] = None; st.rerun()
        if st.session_state['user_id'] == 'admin':
            if st.button("🔧 站長後台", use_container_width=True): st.session_state['view_mode'] = 'admin_panel'; st.rerun()
    
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
    # User Request: 策略說明與名詞解說變成一個獨立頁面
    if st.button("📖 股市新手村 (名詞/策略)", use_container_width=True):
        st.session_state['view_mode'] = 'learning_center'; st.rerun()

    if st.button("🔒 個人自選股", use_container_width=True): st.session_state['view_mode'] = 'my_watchlist'; st.rerun()
    if st.button("💬 戰友留言板", use_container_width=True): st.session_state['view_mode'] = 'comments'; st.rerun()
    
    st.markdown('<div class="version-text">AI 股市戰情室 V17.0 (百科版)</div>', unsafe_allow_html=True)

# --- 8. 主畫面邏輯 ---

# [頁面 0] Admin
if st.session_state['view_mode'] == 'admin_panel':
    st.title("🔧 站長管理後台")
    if st.session_state.get('user_id') != 'admin': st.error("權限不足！")
    else:
        st.subheader("待審核")
        users = load_users()
        pending = [u for u, d in users.items() if d['status'] == 'pending']
        if pending:
            for u in pending:
                c1, c2 = st.columns([3, 1])
                c1.write(f"申請人: **{u}**")
                if c2.button(f"✅ 核准 {u}", key=f"app_{u}"): approve_user(u); st.success(f"已核准 {u}"); time.sleep(1); st.rerun()
        else: st.info("無待審核申請")
        st.divider(); st.subheader("資料庫"); st.json(users)

# [頁面 1] 歡迎頁
elif st.session_state['view_mode'] == 'welcome':
    st.title("👋 歡迎來到 AI 股市戰情室 V17")
    with st.container(border=True):
        st.markdown("""
        #### 🚀 V17 股市百科版
        * **📖 股市新手村**：新增專屬頁面，收錄超過 30 個股市專有名詞解釋。
        * **🔍 網路連動**：名詞看不懂？一鍵 Google 幫你找更多網路教學。
        * **🧠 策略揭密**：公開本系統的 AI 篩選邏輯，讓你知其然也知其所以然。
        """)

# [頁面 9] 股市新手村 (User Request)
elif st.session_state['view_mode'] == 'learning_center':
    st.title("📖 股市新手村 & 戰情室百科")
    st.info("這裡匯集了本系統的策略邏輯，以及網路上常見的股市術語，幫助你快速脫離小白！")
    
    tab1, tab2 = st.tabs(["📊 AI 策略邏輯詳解", "📚 股市名詞大全 (可搜尋)"])
    
    with tab1:
        st.header("🤖 AI 機器人是怎麼選股的？")
        st.markdown("""
        本系統運用 Python 程式，即時計算股價與成交量的變化，策略邏輯如下：

        ### ⚡ 1. 當沖快篩策略 (Day Trading)
        * **目標**：找出今天波動大、資金湧入的股票，適合當日買賣。
        * **核心條件**：
            1.  **爆量**：今日成交量 > 5 日均量的 1.5 倍 (代表有人在照顧)。
            2.  **振幅大**：(最高價 - 最低價) / 昨日收盤價 > 2% (代表有價差可賺)。
        * **風險提示**：波動大代表機會多，但也容易受傷，務必嚴設停損。

        ### 📈 2. 短線波段策略 (Swing Trading)
        * **目標**：找出剛剛轉強，準備發動攻勢的股票。
        * **核心條件**：
            1.  **站上月線**：收盤價 > 20 日均線 (生命線)。
            2.  **短線強勢**：5 日均線 > 20 日均線 (均線黃金交叉)。
        * **操作建議**：只要股價不跌破月線，都可以續抱。

        ### 🐢 3. 長線存股策略 (Long Term)
        * **目標**：找出趨勢穩健向上，適合長期持有的標的。
        * **核心條件**：
            1.  **多頭排列**：股價 > 月線 > 季線 (長期趨勢向上)。
            2.  **籌碼穩定**：近 3 個月股價波動度相對穩定，無暴漲暴跌。
        """)

    with tab2:
        st.header("📚 股市名詞懶人包")
        
        # 搜尋功能
        search_term = st.text_input("🔍 搜尋名詞 (例如：KD, 外資, 本益比)", "")
        
        # 顯示名詞
        for category, terms in STOCK_TERMS.items():
            # 如果有搜尋，檢查類別內有沒有符合的關鍵字
            if search_term:
                filtered_terms = {k:v for k,v in terms.items() if search_term.upper() in k.upper()}
                if not filtered_terms: continue # 如果這類別沒搜到，跳過
            else:
                filtered_terms = terms
            
            with st.expander(f"📌 {category}", expanded=True):
                for term, desc in filtered_terms.items():
                    st.markdown(f"""
                    <div class="term-card">
                        <h4 style="color:#ffbd45">{term}</h4>
                        <p>{desc}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # 外部搜尋連結 (User Request: 網路抓相關解說)
                    # 由於不能直接內嵌外部網站，我們提供一個按鈕開新視窗搜尋
                    google_url = f"https://www.google.com/search?q=股票+{term.split('(')[0]}+意思"
                    st.markdown(f"[🔍 Google 更多關於「{term.split('(')[0]}」的教學]({google_url})")

# [頁面 2] 自選股
elif st.session_state['view_mode'] == 'my_watchlist':
    st.title("🔒 個人自選股")
    if not st.session_state['user_info']:
        tab1, tab2 = st.tabs(["登入", "註冊"])
        with tab1:
            u=st.text_input("帳"); p=st.text_input("密",type="password")
            if st.button("登"):
                ok,r=login_user(u,p)
                if ok: st.session_state['user_id']=u; st.session_state['user_info']=r; st.rerun()
                else: st.error(r)
        with tab2:
            nu=st.text_input("新帳"); np=st.text_input("新密",type="password")
            if st.button("申"): ok,r=register_user(nu,np); st.success(r) if ok else st.error(r)
    else:
        ud=load_users()[st.session_state['user_id']]; wl=ud['watchlist']
        with st.expander("⚙️ 管理"):
            c1,c2=st.columns([3,1]); ac=c1.text_input("加股"); 
            if c2.button("加"): 
                u=load_users(); 
                if ac not in u[st.session_state['user_id']]['watchlist']: u[st.session_state['user_id']]['watchlist'].append(ac); save_users(u); st.rerun()
            cols=st.columns(5)
            for i,c in enumerate(wl):
                if cols[i%5].button(f"🗑️ {c}"): u=load_users(); u[st.session_state['user_id']]['watchlist'].remove(c); save_users(u); st.rerun()
        st.subheader("📊 診斷")
        if st.button("診"):
            pb=st.progress(0)
            for i,c in enumerate(wl):
                pb.progress((i+1)/len(wl)); n=twstock.codes[c].name if c in twstock.codes else c; d=yf.Ticker(f"{c}.TW").history(period="3mo")
                if len(d)>20:
                    p=d['Close'].iloc[-1]; m20=d['Close'].rolling(20).mean().iloc[-1]
                    with st.container(border=True):
                        c1,c2,c3,c4=st.columns([1,2,2,1]); c1.write(f"**{c}**"); c2.write(n); c3.write(f"{p:.2f} | {'🔥 多' if p>m20 else '❄️ 空'}")
                        c4.button("看", key=f"w_{c}", on_click=set_view_to_analysis, args=(c, n))
            pb.empty()

# [頁面 3] 留言
elif st.session_state['view_mode'] == 'comments':
    st.title("💬 留言"); c1,c2=st.columns([1,4]); u=c1.text_input("名",value=st.session_state['user_id'] or "客"); m=c2.text_input("言")
    if st.button("送"): save_comment(u,m); st.rerun()
    d=load_comments(); 
    if not d.empty: 
        for i,r in d.iterrows(): st.chat_message("user").write(f"**{r['User']}**: {r['Message']}")

# [頁面 4] 分析
elif st.session_state['view_mode'] == 'analysis':
    sid=st.session_state['current_stock']; sn=st.session_state['current_name']
    if not sid: st.warning("無")
    else:
        c1,c2=st.columns([3,1]); c1.title(f"{sn} {sid}"); ar=c2.checkbox("🔴 監控"); 
        if ar: time.sleep(3); st.rerun()
        try:
            r=f"{sid.replace('.TW','')} {sn}"; 
            if r not in st.session_state['history']: st.session_state['history'].insert(0,r)
            s=yf.Ticker(sid); d=s.history(period="1y"); i=s.info
            if d.empty: st.error("無資料")
            else:
                clr=get_color_settings(sid); cur=d['Close'].iloc[-1]; pre=d['Close'].iloc[-2]; chg=cur-pre; pct=(chg/pre)*100
                vt=d['Volume'].iloc[-1]; vy=d['Volume'].iloc[-2]; va=d['Volume'].tail(5).mean()
                with st.expander("簡介"): st.write(translate_text(i.get('longBusinessSummary','')))
                st.divider(); m1,m2,m3,m4,m5=st.columns(5)
                m1.metric("價",f"{cur:.2f}",f"{chg:.2f} ({pct:.2f}%)",delta_color=clr['delta']); m2.metric("高",f"{d['High'].iloc[-1]:.2f}")
                m3.metric("低",f"{d['Low'].iloc[-1]:.2f}"); m4.metric("振",f"{((d['High'].iloc[-1]-d['Low'].iloc[-1])/pre)*100:.2f}%")
                m5.metric("力", "🔴 進" if chg>0 and vt>vy else "🟢 出")
                v1,v2,v3,v4,v5=st.columns(5); v1.metric("今量",f"{int(vt/1000)}張"); v2.metric("昨量",f"{int(vy/1000)}張")
                v3.metric("均量",f"{int(va/1000)}張"); v4.metric("態", "🔥 爆" if vt/va>1.5 else "💤 縮"); v5.metric("外資",f"{i.get('heldPercentInstitutions',0)*100:.1f}%")
                
                st.subheader("📈 線圖"); d['M5']=d['Close'].rolling(5).mean(); d['M20']=d['Close'].rolling(20).mean(); d['M60']=d['Close'].rolling(60).mean()
                sl=st.select_slider("期",['3月','6月','1年'],value='6月'); dy={'3月':90,'6月':180,'1年':365}[sl]; cd=d.tail(dy)
                fig=make_subplots(rows=2,cols=1,shared_xaxes=True,row_heights=[0.7,0.3],vertical_spacing=0.03)
                fig.add_trace(go.Candlestick(x=cd.index,open=cd['Open'],high=cd['High'],low=cd['Low'],close=cd['Close'],increasing_line_color=clr['up'],decreasing_line_color=clr['down'],name='K'),row=1,col=1)
                fig.add_trace(go.Scatter(x=cd.index,y=cd['M5'],line=dict(color='blue',width=1),name='M5'),row=1,col=1)
                fig.add_trace(go.Scatter(x=cd.index,y=cd['M20'],line=dict(color='orange',width=1),name='M20'),row=1,col=1)
                vc=[clr['up'] if c>=o else clr['down'] for c,o in zip(cd['Close'],cd['Open'])]
                fig.add_trace(go.Bar(x=cd.index,y=cd['Volume'],marker_color=vc,name='V'),row=2,col=1)
                fig.update_layout(height=600,xaxis_rangeslider_visible=False,margin=dict(t=10,b=10,l=10,r=10),showlegend=False); st.plotly_chart(fig,use_container_width=True,config={'displayModeBar':False})

                st.subheader("🤖 診斷"); m20=d['M20'].iloc[-1]; m60=d['M60'].iloc[-1]; dt=d['Close'].diff(); u=dt.copy(); dd=dt.copy(); u[u<0]=0; dd[dd>0]=0
                rs=u.rolling(14).mean()/dd.abs().rolling(14).mean(); rsi=(100-100/(1+rs)).iloc[-1]; bi=((cur-m60)/m60)*100
                with st.container(border=True):
                    c1,c2=st.columns(2); c1.success("🔥 多") if cur>m20 and m20>m60 else c1.error("❄️ 空") if cur<m20 and m20<m60 else c1.warning("⚖️ 盤")
                    c2.write(f"RSI: `{rsi:.1f}` | 乖離: `{bi:.2f}%`")
        except: st.error("錯")

# [頁面 5,6,7,8] 掃描
elif st.session_state['view_mode'] in ['scan_day', 'scan_short', 'scan_long', 'top_gainers']:
    md=st.session_state['view_mode']; ti={"scan_day":"⚡ 當沖","scan_short":"📈 短線","scan_long":"🐢 長線","top_gainers":"🏆 漲幅"}[md]
    st.title(f"🤖 {ti} (前100)"); sp=st.session_state['scan_pool']*2
    if st.button("搜"):
        lst=[]; pb=st.progress(0); stt=st.empty()
        for i,c in enumerate(sp):
            if i>=150: break
            stt.text(f"搜: {c}..."); pb.progress((i+1)/150)
            try:
                d=yf.Ticker(f"{c}.TW").history(period="3mo")
                if len(d)>5:
                    p=d['Close'].iloc[-1]; m20=d['Close'].rolling(20).mean().iloc[-1]; v=d['Volume'].iloc[-1]; va=d['Volume'].tail(5).mean()
                    sc=0; r=""
                    if md=='scan_day': amp=(d['High'].iloc[-1]-d['Low'].iloc[-1])/d['Close'].iloc[-2]; sc=(v/va)*amp*100; r=f"量{v/va:.1f}x"
                    elif md=='scan_short': sc=((p-m20)/m20)*100; r=f"乖離{sc:.1f}%"
                    elif md=='scan_long': m60=d['Close'].rolling(60).mean().iloc[-1]; sc=-abs((p-m60)/m60)*100; r="穩"
                    elif md=='top_gainers': sc=((p-d['Close'].iloc[-2])/d['Close'].iloc[-2])*100; r=f"漲{sc:.2f}%"
                    n=twstock.codes[c].name if c in twstock.codes else c
                    if not any(x['c']==c for x in lst): lst.append({'c':c,'n':n,'p':p,'r':r,'s':sc})
            except: continue
        pb.empty(); stt.empty(); lst.sort(key=lambda x:x['s'],reverse=True); fl=lst[:100]
        if fl:
            for k,x in enumerate(fl):
                with st.container(border=True):
                    c1,c2,c3,c4,c5=st.columns([0.5,1,2,3,1]); c1.write(f"#{k+1}"); c2.write(f"**{x['c']}**"); c3.write(x['n']); c4.write(f"{x['p']:.2f}|{x['r']}"); c5.button("看",key=f"a_{x['c']}_{k}",on_click=set_view_to_analysis,args=(x['c'],x['n']))
        else: st.warning("無")

# [頁面 9] 歷史
elif st.session_state['view_mode'] == 'history':
    st.title("📜"); 
    for i in st.session_state['history']: c=i.split(" ")[0]; n=i.split(" ")[1] if " " in i else ""; c1,c2=st.columns([4,1]); c1.write(i); c2.button("看",key=f"hh_{c}",on_click=set_view_to_analysis,args=(c,n))
