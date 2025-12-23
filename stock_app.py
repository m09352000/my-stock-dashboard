import streamlit as st
import yfinance as yf
import pandas as pd
import twstock
import plotly.graph_objects as go
from deep_translator import GoogleTranslator
import time
import os
from datetime import datetime

# --- 1. 網頁設定 ---
st.set_page_config(page_title="AI 股市戰情室 V12", layout="wide", initial_sidebar_state="auto")

# --- 2. 注入手機版專屬 CSS (魔法樣式) ---
# 這段程式碼會自動偵測裝置，如果是手機，就會強制縮小間距與字體
st.markdown("""
<style>
    /* 手機版優化 (螢幕寬度小於 768px 時觸發) */
    @media (max-width: 768px) {
        /* 縮小頂部留白，讓內容往上提 */
        .main .block-container {
            padding-top: 2rem !important;
            padding-bottom: 1rem !important;
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
        }
        /* 縮小大標題字體 */
        h1 {
            font-size: 1.8rem !important;
        }
        /* 縮小副標題 */
        h2, h3 {
            font-size: 1.4rem !important;
        }
        /* 讓按鈕在手機上好按一點 */
        .stButton button {
            width: 100%;
            margin-bottom: 0.5rem;
        }
        /* 調整側邊欄的寬度與字體 */
        [data-testid="stSidebar"] {
            width: 80% !important; 
        }
    }
    
    /* 隱藏 Plotly 圖表右上角的工具列 (手機上很佔位) */
    .modebar {
        display: none !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. 初始化 Session State ---
if 'history' not in st.session_state: st.session_state['history'] = []
if 'current_stock' not in st.session_state: st.session_state['current_stock'] = "" 
if 'current_name' not in st.session_state: st.session_state['current_name'] = ""
if 'view_mode' not in st.session_state: st.session_state['view_mode'] = 'welcome' 

# --- 4. 參數與清單 ---
COMMENTS_FILE = "comments.csv"
SCAN_LIST = [
    '2330', '2317', '2454', '2308', '2382', '2303', '2603', '2609', '2615', '2881', 
    '2882', '2891', '3231', '3008', '3037', '3034', '3019', '3035', '2379', '3045', 
    '4938', '4904', '2412', '2357', '2327', '2356', '2345', '2301', '2353', '2324', 
    '2352', '2344', '2368', '2409', '3481', '2498', '3017', '3532', '6176', '2002', 
    '1101', '1301', '1303', '2886', '2892', '5880', '2884', '2880', '2885', '2834', 
    '1605', '1513', '1519', '2313', '1216', '2912', '9910', '1402', '2105', '6505'
]

# --- 5. 核心函式 ---
def get_color_settings(stock_id):
    if ".TW" in stock_id.upper() or ".TWO" in stock_id.upper():
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
        if raw_code in twstock.codes:
            name = twstock.codes[raw_code].name
        elif raw_code.isdigit():
             name = "台股"
        set_view_to_analysis(raw_code, name)

def translate_text(text):
    if not text or text == "暫無詳細描述": return "暫無詳細描述"
    try:
        return GoogleTranslator(source='auto', target='zh-TW').translate(text[:2000])
    except:
        return text

def load_comments():
    if os.path.exists(COMMENTS_FILE):
        return pd.read_csv(COMMENTS_FILE)
    return pd.DataFrame(columns=["Time", "User", "Message"])

def save_comment(user, msg):
    df = load_comments()
    new_data = pd.DataFrame([[datetime.now().strftime("%m/%d %H:%M"), user, msg]], columns=["Time", "User", "Message"])
    df = pd.concat([new_data, df], ignore_index=True)
    df.to_csv(COMMENTS_FILE, index=False)

# --- 6. 側邊欄 (手機上會自動收合) ---
with st.sidebar:
    st.title("🎮 戰情控制台")
    if st.button("🏠 回歡迎頁", use_container_width=True):
        st.session_state['view_mode'] = 'welcome'
        st.rerun()
    st.divider()
    
    st.text_input("🔍 輸入代號 (Enter)", key="sidebar_search", on_change=handle_search)
    
    c1, c2 = st.columns(2)
    if c1.button("🐂 多頭", use_container_width=True):
        st.session_state['view_mode'] = 'bull_scan'; st.rerun()
    if c2.button("🐻 空頭", use_container_width=True):
        st.session_state['view_mode'] = 'bear_scan'; st.rerun()
    
    if st.button("💬 留言板", use_container_width=True):
        st.session_state['view_mode'] = 'comments'; st.rerun()

    st.divider()
    if st.button("🕒 搜尋歷史", use_container_width=True):
        st.session_state['view_mode'] = 'history'; st.rerun()

    if st.session_state['history']:
        for item in st.session_state['history'][:5]:
            code = item.split(" ")[0]
            name = item.split(" ")[1] if " " in item else ""
            if st.button(f"{code} {name}", key=f"side_{code}"):
                set_view_to_analysis(code, name); st.rerun()

# --- 7. 主畫面 ---

# [頁面 1] 歡迎頁
if st.session_state['view_mode'] == 'welcome':
    st.title("👋 歡迎來到 AI 股市戰情室 V12")
    st.info("👈 左上角箭頭可打開選單。支援手機/電腦最佳化瀏覽。")
    
    with st.container(border=True):
        st.markdown("""
        #### 📱 V12 介面自適應升級
        * **電腦版**：寬螢幕多欄位顯示，資訊一覽無遺。
        * **手機版**：自動切換為緊湊模式，字體放大、邊距縮小，單手好操作。
        * **K線圖**：手機上自動隱藏工具列，避免誤觸，滑動更順暢。
        """)

# [頁面 2] 留言板
elif st.session_state['view_mode'] == 'comments':
    st.title("💬 戰友留言板")
    with st.container(border=True):
        c1, c2 = st.columns([1, 4])
        user_name = c1.text_input("暱稱", value="匿名股神")
        user_msg = c2.text_input("留言內容", placeholder="分享你的看法...")
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
    else:
        st.write("尚無留言")

# [頁面 3] 個股分析 (手機優化重點)
elif st.session_state['view_mode'] == 'analysis':
    stock_id = st.session_state['current_stock']
    stock_name = st.session_state['current_name']
    
    if not stock_id:
        st.warning("請輸入代號")
    else:
        # 手機版標題會自動縮小
        c_head, c_btn = st.columns([3, 1])
        c_head.title(f"{stock_name} {stock_id}")
        
        # 自動刷新開關
        auto_refresh = c_btn.checkbox("🔴 即時監控", value=False)
        if auto_refresh: time.sleep(3); st.rerun()

        try:
            # 歷史紀錄
            rec = f"{stock_id.replace('.TW','')} {stock_name}"
            if rec not in st.session_state['history']: st.session_state['history'].insert(0, rec)

            stock = yf.Ticker(stock_id)
            df = stock.history(period="1y")
            info = stock.info
            
            if df.empty:
                st.error("查無資料")
            else:
                colors = get_color_settings(stock_id)
                curr = df['Close'].iloc[-1]
                prev = df['Close'].iloc[-2]
                chg = curr - prev
                pct = (chg / prev)*100
                vol = df['Volume'].iloc[-1]
                
                with st.expander("🏢 公司簡介 (手機點我展開)", expanded=False):
                    st.write(translate_text(info.get('longBusinessSummary', '')))
                    c1, c2 = st.columns(2)
                    c1.metric("ROE", f"{info.get('returnOnEquity',0)*100:.2f}%")
                    c2.metric("毛利率", f"{info.get('grossMargins',0)*100:.2f}%")

                st.divider()
                
                # 手機上這四個會自動變成 2x2 或 1x4 排列
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("成交價", f"{curr:.2f}", f"{chg:.2f} ({pct:.2f}%)", delta_color=colors['delta'])
                m2.metric("最高", f"{df['High'].iloc[-1]:.2f}")
                m3.metric("最低", f"{df['Low'].iloc[-1]:.2f}")
                m4.metric("量", f"{int(vol/1000)} 張")

                st.subheader("📈 技術 K 線")
                # 計算
                df['MA5'] = df['Close'].rolling(5).mean()
                df['MA20'] = df['Close'].rolling(20).mean()
                df['MA60'] = df['Close'].rolling(60).mean()
                
                trange = st.select_slider("時間", ['3個月','6個月','1年'], value='6個月')
                days = {'3個月':90, '6個月':180, '1年':365}[trange]
                cdf = df.tail(days)
                
                # 繪圖 (針對手機優化配置)
                fig = go.Figure()
                fig.add_trace(go.Candlestick(x=cdf.index, open=cdf['Open'], high=cdf['High'], low=cdf['Low'], close=cdf['Close'], name='K線', increasing_line_color=colors['up'], decreasing_line_color=colors['down']))
                fig.add_trace(go.Scatter(x=cdf.index, y=cdf['MA5'], line=dict(color='blue', width=1), name='MA5'))
                fig.add_trace(go.Scatter(x=cdf.index, y=cdf['MA20'], line=dict(color='orange', width=1), name='MA20'))
                
                # 手機上隱藏靜態圖表工具列，並設定適當高度
                fig.update_layout(
                    height=450, 
                    xaxis_rangeslider_visible=False,
                    margin=dict(l=10, r=10, t=10, b=10),
                    dragmode='pan' # 手機上預設為拖曳模式
                )
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False}) # 隱藏工具列

                # AI 診斷
                st.subheader("🤖 AI 診斷")
                ma20 = df['MA20'].iloc[-1]; ma60 = df['MA60'].iloc[-1]
                delta = df['Close'].diff(); u=delta.copy(); d=delta.copy(); u[u<0]=0; d[d>0]=0
                rs = u.rolling(14).mean()/d.abs().rolling(14).mean()
                rsi = (100-100/(1+rs)).iloc[-1]
                bias = ((curr-ma60)/ma60)*100
                vol_r = vol/df['Volume'].rolling(5).mean().iloc[-1] if df['Volume'].rolling(5).mean().iloc[-1]>0 else 1

                with st.container(border=True):
                    if curr>ma20 and ma20>ma60: st.success("🔥 強勢多頭")
                    elif curr<ma20 and ma20<ma60: st.error("❄️ 空頭破線")
                    else: st.warning("⚖️ 盤整中")
                    
                    c_det1, c_det2 = st.columns(2)
                    c_det1.write(f"RSI: `{rsi:.1f}`")
                    c_det2.write(f"量比: `{vol_r:.1f}倍`")
                    if rsi>80: st.error("⚠️ 過熱")
                    elif rsi<20: st.success("💎 超賣")

        except Exception as e:
            st.error(f"錯誤: {e}")

# [頁面 4] 掃描頁
elif st.session_state['view_mode'] in ['bull_scan', 'bear_scan']:
    is_bull = (st.session_state['view_mode'] == 'bull_scan')
    title = "🔥 多頭掃描" if is_bull else "❄️ 空頭掃描"
    st.title(title)
    
    col1, col2 = st.columns([3, 1])
    target = col1.slider("筆數", 5, 30, 10)
    if col2.button("開始"):
        found = []
        pbar = st.progress(0); status = st.empty()
        for i, code in enumerate(SCAN_LIST):
            if len(found)>=target: break
            status.text(f"掃描: {code}...")
            pbar.progress((i+1)/len(SCAN_LIST))
            try:
                data = yf.Ticker(f"{code}.TW").history(period="3mo")
                if len(data)>50:
                    p=data['Close'].iloc[-1]; m5=data['Close'].rolling(5).mean().iloc[-1]
                    m20=data['Close'].rolling(20).mean().iloc[-1]; m60=data['Close'].rolling(60).mean().iloc[-1]
                    match=False; s=0
                    if is_bull and p>m5 and m5>m20 and m20>m60: match=True; s=(p-m20)/m20
                    elif not is_bull and p<m5 and m5<m20 and m20<m60: match=True; s=(m20-p)/m20
                    if match:
                        name = twstock.codes[code].name if code in twstock.codes else code
                        found.append({'c':code, 'n':name, 'p':p, 's':s})
            except: continue
        pbar.empty(); status.empty()
        if found:
            found.sort(key=lambda x: x['s'], reverse=True)
            for item in found:
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([1.5, 2, 1.5, 1])
                    c1.markdown(f"**{item['c']}**") # 手機上強調代號
                    c2.write(f"{item['n']}")
                    c3.write(f"{item['p']:.1f}")
                    c4.button("看", key=f"b_{item['c']}", on_click=set_view_to_analysis, args=(item['c'], item['n']))
        else: st.warning("無符合")

# [頁面 5] 歷史頁
elif st.session_state['view_mode'] == 'history':
    st.title("📜 紀錄")
    if st.session_state['history']:
        for item in st.session_state['history']:
            code = item.split(" ")[0]; name = item.split(" ")[1] if " " in item else ""
            c1, c2 = st.columns([4, 1])
            c1.write(f"{item}")
            c2.button("看", key=f"h_{code}", on_click=set_view_to_analysis, args=(code, name))
