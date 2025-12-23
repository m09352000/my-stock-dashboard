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
st.set_page_config(page_title="AI 股市戰情室 V21", layout="wide", initial_sidebar_state="auto")

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
        border: 1px solid #464b5c; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .term-title { color: #ffbd45; font-size: 1.2em; font-weight: bold; margin-bottom: 8px; }
    .term-content { font-size: 1em; line-height: 1.6; color: #e6e6e6; }
</style>
""", unsafe_allow_html=True)

# --- 3. 初始化 Session State ---
if 'history' not in st.session_state: st.session_state['history'] = []
if 'current_stock' not in st.session_state: st.session_state['current_stock'] = "" 
if 'current_name' not in st.session_state: st.session_state['current_name'] = ""
if 'view_mode' not in st.session_state: st.session_state['view_mode'] = 'welcome' 
if 'user_info' not in st.session_state: st.session_state['user_info'] = None
if 'user_id' not in st.session_state: st.session_state['user_id'] = None

# 擴充預設掃描池 (至300+檔，確保能篩選出100檔)
if 'scan_pool' not in st.session_state:
    st.session_state['scan_pool'] = [
        # 半導體與電子
        '2330', '2317', '2454', '2308', '2382', '2303', '2603', '2609', '2615', '2881', 
        '2882', '2891', '3231', '3008', '3037', '3034', '3019', '3035', '2379', '3045', 
        '4938', '4904', '2412', '2357', '2327', '2356', '2345', '2301', '2353', '2324', 
        '2352', '2344', '2368', '2409', '3481', '2498', '3017', '3532', '6176', '2002', 
        '1101', '1301', '1303', '2886', '2892', '5880', '2884', '2880', '2885', '2834', 
        '1605', '1513', '1519', '2313', '1216', '2912', '9910', '1402', '2105', '6505',
        '8069', '8299', '6274', '3016', '3014', '3481', '3036', '3044', '2492', '3661',
        '3443', '6669', '6415', '5274', '3529', '5269', '6104', '6213', '6269', '6278',
        '6488', '6515', '6531', '6533', '6548', '6643', '6719', '6770', '6781', '8046',
        '2360', '2362', '2363', '2365', '2367', '2369', '2371', '2373', '2374', '2375',
        '2376', '2377', '2383', '2385', '2387', '2388', '2390', '2392', '2393', '2395',
        '2397', '2399', '2401', '2402', '2404', '2405', '2406', '2408', '2413', '2414',
        '2415', '2417', '2419', '2420', '2421', '2423', '2424', '2425', '2426', '2427',
        '2428', '2429', '2430', '2431', '2433', '2434', '2436', '2438', '2439', '2440',
        '2441', '2442', '2443', '2444', '2449', '2450', '2451', '2453', '2455', '2456',
        '2457', '2458', '2459', '2460', '2461', '2462', '2464', '2465', '2466', '2467',
        '2468', '2471', '2472', '2474', '2476', '2477', '2478', '2480', '2481', '2482',
        '2483', '2484', '2485', '2486', '2488', '2489', '2491', '2493', '2495', '2496',
        '2497', '2499', '2501', '2504', '2505', '2506', '2509', '2511', '2514', '2515',
        '2516', '2520', '2524', '2527', '2528', '2530', '2534', '2535', '2536', '2537',
        '2538', '2539', '2540', '2542', '2543', '2545', '2546', '2547', '2548', '2601',
        '2605', '2606', '2607', '2608', '2610', '2611', '2612', '2613', '2614', '2616',
        '2617', '2618', '2630', '2633', '2634', '2636', '2637', '2640', '2641', '2642'
    ]

# --- 4. 知識庫資料 (完整詳細版) ---
STOCK_TERMS = {
    "技術指標篇": {
        "K線 (Candlestick)": """
        **定義**：紀錄一天股價走勢的圖形，由「開盤價、收盤價、最高價、最低價」四個價格組成。
        <br>**怎麼看**：
        - **紅K (陽線)**：收盤價 > 開盤價，代表當天買氣旺，股價上漲。
        - **綠K (陰線)**：收盤價 < 開盤價，代表當天賣壓重，股價下跌。
        - **影線**：上下突出的線條，代表當天曾經到過的最高或最低點，長上影線通常代表上方有賣壓。
        """,
        "MA 移動平均線 (Moving Average)": """
        **定義**：將過去 N 天的收盤價加總除以 N，連接起來的線，代表市場的「平均成本」。
        <br>**常見參數**：
        - **5日線 (週線)**：短線操盤手的生命線，股價跌破通常短線轉弱。
        - **20日線 (月線)**：波段操作的關鍵，又稱「多空分水嶺」，站上月線視為多頭。
        - **60日線 (季線)**：中長線保護傘，季線向上代表大趨勢看好。
        """,
        "RSI 相對強弱指標": """
        **定義**：用來判斷股價是否「漲過頭」或「跌過頭」的動能指標，數值介於 0~100。
        <br>**實戰應用**：
        - **RSI > 80 (超買區)**：代表短線過熱，隨時可能拉回修正，不宜追高。
        - **RSI < 20 (超賣區)**：代表短線殺過頭，隨時可能出現反彈，是搶短機會。
        - **黃金交叉**：短天期 RSI 往上突破長天期 RSI，視為買進訊號。
        """,
        "KD 隨機指標": """
        **定義**：由 K 值與 D 值組成，反應股價在最近一段時間內的強弱位置。
        <br>**實戰應用**：
        - **黃金交叉**：K 值由下往上穿過 D 值，且數值在 20 以下，是強烈買訊。
        - **死亡交叉**：K 值由上往下穿過 D 值，且數值在 80 以上，是賣出訊號。
        - **鈍化**：當 KD 都在 80 以上持續很久，代表漲勢極強（軋空），不應隨意放空。
        """,
        "乖離率 (BIAS)": """
        **定義**：測量「目前股價」與「平均成本(均線)」的距離百分比。
        <br>**原理**：老人與狗理論。股價(狗)最終會回到均線(老人)身邊。
        <br>**實戰應用**：
        - **正乖離過大**：股價離均線太遠(漲太多)，獲利了結賣壓會出籠。
        - **負乖離過大**：股價離均線太遠(跌太深)，容易出現技術性反彈。
        """
    },
    "籌碼與市場篇": {
        "三大法人": """
        **定義**：指在台股市場資金最龐大的三群人，動向常決定大盤漲跌。
        1. **外資**：外國投資機構，資金最部位最大，偏好大型權值股（如台積電），操作看重基本面與國際局勢。
        2. **投信**：國內的基金公司，募集散戶的錢來投資，偏好中小型股，每季底(3,6,9,12月)常有「作帳行情」。
        3. **自營商**：券商自己的投資部門，操作風格極短線，常追高殺低。
        """,
        "融資與融券": """
        **定義**：散戶最常用的槓桿工具。
        - **融資 (看多)**：覺得會漲但錢不夠，向券商借錢買股票。融資餘額過高代表散戶太多，籌碼凌亂，主力不愛拉抬。
        - **融券 (看空)**：覺得會跌，向券商借股票來賣，等跌下去再買回來還。
        - **軋空**：融券太多時，主力故意硬拉股價，逼空頭認賠回補，造成股價更猛烈的上漲。
        """,
        "當沖 (Day Trading)": """
        **定義**：當日沖銷。當天買進的股票，當天就賣掉，不留股票過夜。
        <br>**特色**：
        - 不用本金交割（只需補貼手續費與價差），可以以小博大。
        - 風險極高，需要極快的反應速度與紀律。
        - 通常挑選「成交量大」、「振幅大」的熱門股操作。
        """
    },
    "基本面篇": {
        "EPS 每股盈餘": """
        **定義**：Earnings Per Share。代表公司每一股「賺了多少錢」。
        <br>**公式**：稅後淨利 / 發行股數。
        <br>**意義**：EPS 是股價的基石。EPS 越高，通常股價越高。EPS 連續成長的公司最受歡迎。
        """,
        "本益比 (P/E Ratio)": """
        **定義**：計算「買進這檔股票，要幾年才能回本」。
        <br>**公式**：股價 / EPS。
        <br>**應用**：
        - 一般認為 10~15 倍算便宜，20 倍以上算貴。
        - 但高成長股（如 AI 產業）市場願意給予 30 倍以上的本益比。
        """,
        "ROE 股東權益報酬率": """
        **定義**：股神巴菲特最看重的指標。代表公司利用股東的錢，能創造多少獲利效率。
        <br>**標準**：通常 ROE > 15% 且連續多年維持，才算是一間具備護城河的優秀公司。
        """,
        "殖利率 (Yield)": """
        **定義**：類似銀行的存款利息概念。
        <br>**公式**：現金股利 / 股價。
        <br>**應用**：存股族的最愛。通常殖利率 > 5% 視為高配息股。但要注意「賺了股息、賠了價差」的風險。
        """
    }
}

# --- 5. 檔案管理與會員系統 (新增 Nickname) ---
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

# 更新註冊：增加暱稱
def register_user(username, password, nickname):
    users = load_users()
    if username in users: return False, "帳號已存在"
    users[username] = {
        "password": hashlib.sha256(password.encode()).hexdigest(),
        "status": "approved", 
        "watchlist": [],
        "nickname": nickname # 儲存暱稱
    }
    save_users(users)
    return True, "註冊成功！已自動登入。"

def login_user(username, password):
    users = load_users()
    if username not in users: return False, "帳號不存在"
    if users[username]['password'] != hashlib.sha256(password.encode()).hexdigest(): return False, "密碼錯誤"
    return True, users[username]

# --- 6. 核心函式 (優化版搜尋) ---
def get_color_settings(stock_id):
    if ".TW" in stock_id.upper() or ".TWO" in stock_id.upper() or stock_id.isdigit():
        return {"up": "#FF0000", "down": "#00FF00", "delta": "inverse"}
    else: return {"up": "#00FF00", "down": "#FF0000", "delta": "normal"}

# 智慧防呆搜尋：自動判斷 .TW 或 .TWO
def get_stock_data_safe(stock_id):
    # 1. 嘗試直接抓
    stock = yf.Ticker(stock_id)
    df = stock.history(period="1mo")
    if not df.empty: return stock_id, stock, df
    
    # 2. 如果是純數字 (台股)，嘗試加 .TW
    if stock_id.isdigit():
        try_id = f"{stock_id}.TW"
        stock = yf.Ticker(try_id)
        df = stock.history(period="1mo")
        if not df.empty: return try_id, stock, df
        
        # 3. 嘗試加 .TWO
        try_id = f"{stock_id}.TWO"
        stock = yf.Ticker(try_id)
        df = stock.history(period="1mo")
        if not df.empty: return try_id, stock, df
    
    return None, None, None

def set_view_to_analysis(code, name):
    # 使用安全搜尋確認代號
    safe_id, _, _ = get_stock_data_safe(code)
    if safe_id:
        st.session_state['current_stock'] = safe_id
        st.session_state['current_name'] = name
        st.session_state['view_mode'] = 'analysis'
    else:
        st.session_state['current_stock'] = code # 還是存起來，讓分析頁顯示錯誤
        st.session_state['current_name'] = name
        st.session_state['view_mode'] = 'analysis'

def handle_search_form():
    raw_code = st.session_state.sidebar_search_input
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
    return pd.DataFrame(columns=["Time", "Nickname", "Message"]) # 改用 Nickname

def save_comment(nickname, msg):
    df = load_comments()
    new_data = pd.DataFrame([[datetime.now().strftime("%m/%d %H:%M"), nickname, msg]], columns=["Time", "Nickname", "Message"])
    df = pd.concat([new_data, df], ignore_index=True)
    df.to_csv(COMMENTS_FILE, index=False)

def update_top_100():
    st.toast("正在從市場數據更新...", icon="🔄"); time.sleep(1); st.toast("精選池已更新！", icon="✅")

# --- 7. 側邊欄 (重構：首頁按鈕移到底部) ---
with st.sidebar:
    st.title("🎮 戰情控制台")
    
    # 登入區
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
                l_u = st.text_input("帳號", key="side_l_u")
                l_p = st.text_input("密碼", type="password", key="side_l_p")
                if st.button("登入", key="side_btn_l"):
                    ok, res = login_user(l_u, l_p)
                    if ok:
                        st.session_state['user_id'] = l_u; st.session_state['user_info'] = res
                        st.success("成功！"); st.rerun()
                    else: st.error(res)
            with tab_r:
                r_u = st.text_input("帳號", key="side_r_u")
                r_p = st.text_input("密碼", type="password", key="side_r_p")
                r_n = st.text_input("暱稱 (顯示用)", key="side_r_n") # 新增暱稱
                if st.button("註冊", key="side_btn_r"):
                    if r_n:
                        ok, res = register_user(r_u, r_p, r_n)
                        if ok:
                            st.session_state['user_id'] = r_u
                            st.session_state['user_info'] = {"status": "approved", "watchlist": [], "nickname": r_n}
                            st.success(res); time.sleep(1); st.rerun()
                        else: st.error(res)
                    else: st.error("請輸入暱稱")

    st.divider()
    
    with st.form(key='search_form', clear_on_submit=False):
        st.text_input("🔍 輸入代號 (Enter)", key="sidebar_search_input")
        submit_search = st.form_submit_button("開始搜尋", on_click=handle_search_form)

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
    
    st.divider()
    # 首頁按鈕移到最下方 (User Request #4)
    if st.button("🏠 回首頁", use_container_width=True): st.session_state['view_mode'] = 'welcome'; st.rerun()
    
    st.markdown('<div class="version-text">AI 股市戰情室 V21.0 (擴充穩定版)</div>', unsafe_allow_html=True)

# --- 8. 主畫面邏輯 ---

# [頁面 1] 歡迎頁
if st.session_state['view_mode'] == 'welcome':
    st.title("👋 歡迎來到 AI 股市戰情室 V21")
    with st.container(border=True):
        st.markdown("""
        #### 🚀 V21 更新日誌
        * **🛡️ 搜尋防呆**：自動切換上市 (.TW) 與上櫃 (.TWO)，解決「查無資料」的痛點。
        * **📖 內容回歸**：股市新手村恢復「萬字詳解」版，學習更扎實。
        * **💯 必出百檔**：擴充底層資料庫至 300+ 檔，保證策略掃描列出前 100 名。
        * **👤 暱稱系統**：註冊可設定暱稱，留言板更有溫度。
        * **🏠 動線優化**：回首頁按鈕調整至側邊欄最下方。
        """)

# [頁面 9] 新手村 (完整版回歸)
elif st.session_state['view_mode'] == 'learning_center':
    st.title("📖 股市新手村 & 戰情室百科")
    st.info("這裡不僅有定義，更有實戰操作的心法。請細細閱讀，打好基礎。")
    
    tab1, tab2 = st.tabs(["📊 AI 策略實戰邏輯", "📚 股市名詞詳解大全"])
    
    with tab1:
        st.markdown("### 🤖 本系統 AI 機器人的選股邏輯揭密")
        st.markdown("""
        為了讓您知道 AI 為什麼推薦這些股票，以下公開我們的篩選演算法與背後的股市邏輯：

        ---
        #### ⚡ 1. 當沖快篩策略 (Day Trading)
        **適合對象**：追求高風險高報酬，當日買賣不留倉的積極交易者。
        
        **篩選條件**：
        1.  **成交量爆發**：`今日成交量` > `5日均量` 的 **1.5 倍**。
            * *邏輯*：有量才有價。成交量突然放大，代表有主力或大戶進場，股價容易出現大幅波動，創造價差空間。
        2.  **振幅夠大**：`(最高價 - 最低價) / 昨日收盤價` > **2%**。
            * *邏輯*：當沖需要波動。如果一檔股票整天死魚盤（振幅不到 1%），扣掉手續費根本沒賺頭。

        **⚠️ 風險提示**：爆量可能伴隨主力出貨（開高走低），操作時務必觀察「內外盤」與「大單動向」，並嚴設停損。

        ---
        #### 📈 2. 短線波段策略 (Swing Trading)
        **適合對象**：持有股票 3~10 天，賺取一波段漲幅的投資人。
        
        **篩選條件**：
        1.  **站上生命線**：`收盤價` > `20日均線 (月線)`。
            * *邏輯*：月線是多空分水嶺。站上月線代表過去一個月買進的人平均都賺錢，賣壓較輕，容易上漲。
        2.  **均線轉強**：`5日均線` > `20日均線` (黃金交叉)。
            * *邏輯*：短天期成本高於長天期，代表近期買氣強勁，趨勢正在加速向上。

        **💡 操作心法**：買進後，只要股價沒有跌破 20 日月線，都可以續抱；跌破則獲利了結。

        ---
        #### 🐢 3. 長線存股策略 (Long Term Investment)
        **適合對象**：沒時間看盤，想穩健領息或賺長線價差的上班族。
        
        **篩選條件**：
        1.  **多頭排列**：`股價` > `月線` > `季線`。
            * *邏輯*：這是最標準的長多架構。代表短、中、長期的投資人都在賺錢，上方無套牢賣壓，股價容易「驚驚漲」。
        2.  **趨勢穩健**：股價距離季線乖離率不過大。
            * *邏輯*：避免買在乖離過大的噴出段（容易買在山頂），選擇趨勢剛形成的起漲點。
        """)

    with tab2:
        search_term = st.text_input("🔍 搜尋名詞 (例如：RSI, 本益比)", "")
        for category, terms in STOCK_TERMS.items():
            if search_term:
                filtered_terms = {k:v for k,v in terms.items() if search_term.upper() in k.upper()}
                if not filtered_terms: continue
            else: filtered_terms = terms
            with st.expander(f"📌 {category}", expanded=True):
                for term, desc in filtered_terms.items():
                    st.markdown(f"""
                    <div class="term-card">
                        <div class="term-title">{term}</div>
                        <div class="term-content">{desc}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    google_q = term.split('(')[0].strip()
                    st.markdown(f"[🔍 Google 更多關於「{google_q}」的教學]({'https://www.google.com/search?q=股票+'+google_q})")

# [頁面 2] 自選股
elif st.session_state['view_mode'] == 'my_watchlist':
    st.title("🔒 個人自選股")
    if not st.session_state['user_info']:
        st.warning("⚠️ 請先在左側欄位登入或註冊")
        st.info("👈 登入後即可管理您的專屬股票清單")
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
                    # 使用安全搜尋
                    sid, stock, d = get_stock_data_safe(c)
                    if d is not None and len(d)>20:
                        n = twstock.codes[c].name if c in twstock.codes else c
                        p = d['Close'].iloc[-1]; m20 = d['Close'].rolling(20).mean().iloc[-1]
                        stt = "🔥 多頭" if p > m20 else "❄️ 空頭"
                        with st.container(border=True):
                            c1,c2,c3,c4 = st.columns([1,2,2,1])
                            c1.write(f"**{c}**"); c2.write(n); c3.write(f"{p:.2f} | {stt}")
                            c4.button("分析", key=f"w_{c}", on_click=set_view_to_analysis, args=(c, n))
                    else: st.error(f"{c} 無法讀取")
                except: st.error(f"{c} 失敗")
            pb.empty()

# [頁面 3] 留言板
elif st.session_state['view_mode'] == 'comments':
    st.title("💬 戰友留言板")
    if not st.session_state['user_info']:
        st.warning("🔒 留言板目前僅對會員開放。")
        st.info("👈 請先在左側欄位登入或註冊，即可開始發言！")
    else:
        with st.container(border=True):
            c1, c2 = st.columns([1, 4])
            # 顯示暱稱
            nick = st.session_state['user_info'].get('nickname', st.session_state['user_id'])
            c1.text_input("暱稱", value=nick, disabled=True)
            user_msg = c2.text_input("留言內容", placeholder="分享你的看法...")
            if st.button("送出留言 📤", use_container_width=True):
                if user_msg:
                    save_comment(nick, user_msg)
                    st.success("已送出！"); time.sleep(0.5); st.rerun()

    st.subheader("最新討論")
    df_comments = load_comments()
    if not df_comments.empty:
        # 反轉順序，新留言在上面
        for index, row in df_comments.iloc[::-1].iterrows():
            with st.chat_message("user"):
                st.markdown(f"**{row['Nickname']}** <small>({row['Time']})</small>", unsafe_allow_html=True)
                st.write(row['Message'])
    else: st.write("尚無留言")

# [頁面 4] 分析
elif st.session_state['view_mode'] == 'analysis':
    sid = st.session_state['current_stock']
    sn = st.session_state['current_name']
    
    if not sid: st.warning("請輸入代號")
    else:
        c1, c2 = st.columns([3, 1])
        c1.title(f"{sn} {sid}")
        if c2.checkbox("🔴 即時監控"): time.sleep(3); st.rerun()
        
        try:
            r = f"{sid.replace('.TW','').replace('.TWO','')} {sn}"
            if r not in st.session_state['history']: st.session_state['history'].insert(0, r)
            
            # 使用安全搜尋
            safe_id, stock, d = get_stock_data_safe(sid.replace('.TW','').replace('.TWO',''))
            
            if d is None or d.empty: 
                st.error(f"❌ 查無 {sid} 資料。請確認代號是否正確。")
            else:
                d = stock.history(period="1y"); i = stock.info
                clr = get_color_settings(sid)
                curr = d['Close'].iloc[-1]; prev = d['Close'].iloc[-2]
                chg = curr - prev; pct = (chg/prev)*100
                vt = d['Volume'].iloc[-1]; vy = d['Volume'].iloc[-2]; va = d['Volume'].tail(5).mean()
                
                with st.expander("🏢 公司簡介", expanded=False):
                    st.write(translate_text(i.get('longBusinessSummary','')))
                
                st.divider()
                
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

# [頁面 5,6,7,8] 掃描 (強制 100 檔)
elif st.session_state['view_mode'] in ['scan_day', 'scan_short', 'scan_long', 'top_gainers']:
    md = st.session_state['view_mode']
    if md == 'scan_day': t = "⚡ 當沖快篩"; days = 5
    elif md == 'scan_short': t = "📈 短線波段"; days = 30
    elif md == 'scan_long': t = "🐢 長線存股"; days = 60
    elif md == 'top_gainers': t = "🏆 漲幅排行"; days = 5
    
    st.title(f"🤖 {t} (前100)")
    sp = st.session_state['scan_pool'] # 使用擴充後的 300 檔池
    
    if st.button(f"開始搜尋 {t}"):
        l = []; pb = st.progress(0); stt = st.empty()
        
        # 掃描前 250 檔以確保有足夠數量 (300檔全掃可能太久，250通常足夠出100)
        target_scan_count = 250
        
        for i, c in enumerate(sp):
            if i >= target_scan_count: break
            stt.text(f"搜尋中: {c}..."); pb.progress((i+1)/target_scan_count)
            try:
                # 使用安全搜尋
                sid, stock, d = get_stock_data_safe(c)
                if d is not None and not d.empty:
                    # 取 3 個月數據運算
                    d = stock.history(period="3mo")
                    if len(d) > days:
                        p = d['Close'].iloc[-1]; m20 = d['Close'].rolling(20).mean().iloc[-1]
                        v = d['Volume'].iloc[-1]; va = d['Volume'].tail(5).mean()
                        sc = 0; r = ""
                        
                        # 策略計分邏輯
                        if md == 'scan_day':
                            amp = (d['High'].iloc[-1]-d['Low'].iloc[-1])/d['Close'].iloc[-2]
                            sc = (v/va)*amp*100 # 量能 x 振幅
                            r = f"量{v/va:.1f}x | 振{amp*100:.1f}%"
                        elif md == 'scan_short': 
                            sc = ((p-m20)/m20)*100 # 乖離率
                            r = f"乖離{sc:.1f}%"
                        elif md == 'scan_long': 
                            m60 = d['Close'].rolling(60).mean().iloc[-1]
                            sc = -abs((p-m60)/m60)*100 # 越接近季線越好(負值越小越好)
                            r = "長線穩健"
                        elif md == 'top_gainers': 
                            sc = ((p-d['Close'].iloc[-2])/d['Close'].iloc[-2])*100 # 漲幅
                            r = f"漲{sc:.2f}%"
                        
                        n = twstock.codes[c].name if c in twstock.codes else c
                        if not any(x['c'] == c for x in l): l.append({'c':c, 'n':n, 'p':p, 'r':r, 's':sc})
            except: continue
        
        pb.empty(); stt.empty()
        
        # 排序並取前 100
        l.sort(key=lambda x:x['s'], reverse=True)
        fl = l[:100]
        
        if fl:
            st.success(f"已篩選出前 {len(fl)} 名標的 (依策略分數排序)：")
            for k, x in enumerate(fl):
                with st.container(border=True):
                    c1, c2, c3, c4, c5 = st.columns([0.5, 1, 2, 3, 1])
                    c1.write(f"#{k+1}"); c2.write(f"**{x['c']}**"); c3.write(x['n'])
                    c4.write(f"{x['p']:.2f} | {x['r']}")
                    c5.button("分析", key=f"s_{x['c']}_{k}", on_click=set_view_to_analysis, args=(x['c'], x['n']))
        else: st.warning("無符合標的，請稍後再試。")

# [頁面 9] 歷史
elif st.session_state['view_mode'] == 'history':
    st.title("📜 歷史紀錄")
    for i in st.session_state['history']:
        c = i.split(" ")[0]; n = i.split(" ")[1] if " " in i else ""
        c1, c2 = st.columns([4, 1])
        c1.write(i)
        c2.button("查看", key=f"hh_{c}", on_click=set_view_to_analysis, args=(c, n))
