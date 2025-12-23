import streamlit as st
import yfinance as yf
import pandas as pd
import twstock
import plotly.graph_objects as go
from deep_translator import GoogleTranslator
import time
import os
from datetime import datetime

# --- 網頁設定 ---
st.set_page_config(page_title="AI 股市戰情室 V11", layout="wide")

# --- 初始化 Session State ---
if 'history' not in st.session_state: st.session_state['history'] = []
if 'current_stock' not in st.session_state: st.session_state['current_stock'] = "" 
if 'current_name' not in st.session_state: st.session_state['current_name'] = ""
if 'view_mode' not in st.session_state: st.session_state['view_mode'] = 'welcome' 

# --- 留言板檔案設定 ---
COMMENTS_FILE = "comments.csv"

# --- 擴充掃描清單 ---
SCAN_LIST = [
    '2330', '2317', '2454', '2308', '2382', '2303', '2603', '2609', '2615', '2881', 
    '2882', '2891', '3231', '3008', '3037', '3034', '3019', '3035', '2379', '3045', 
    '4938', '4904', '2412', '2357', '2327', '2356', '2345', '2301', '2353', '2324', 
    '2352', '2344', '2368', '2409', '3481', '2498', '3017', '3532', '6176', '2002', 
    '1101', '1301', '1303', '2886', '2892', '5880', '2884', '2880', '2885', '2834', 
    '1605', '1513', '1519', '2313', '1216', '2912', '9910', '1402', '2105', '6505'
]

# --- 核心邏輯函式 ---

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

# --- 留言板功能模組 ---
def load_comments():
    if os.path.exists(COMMENTS_FILE):
        return pd.read_csv(COMMENTS_FILE)
    return pd.DataFrame(columns=["Time", "User", "Message"])

def save_comment(user, msg):
    df = load_comments()
    new_data = pd.DataFrame([[datetime.now().strftime("%Y-%m-%d %H:%M"), user, msg]], columns=["Time", "User", "Message"])
    # 把新留言放在最上面
    df = pd.concat([new_data, df], ignore_index=True)
    df.to_csv(COMMENTS_FILE, index=False)

# --- 側邊欄 ---
with st.sidebar:
    st.title("🎮 戰情控制台")
    if st.button("🏠 回歡迎頁", use_container_width=True):
        st.session_state['view_mode'] = 'welcome'
        st.rerun()
    st.divider()
    
    st.subheader("🔍 快速輸入")
    st.text_input("輸入代號 (Enter)", key="sidebar_search", on_change=handle_search)
    st.divider()

    st.subheader("🤖 智能掃描")
    c1, c2 = st.columns(2)
    if c1.button("🐂 多頭", use_container_width=True):
        st.session_state['view_mode'] = 'bull_scan'
        st.rerun()
    if c2.button("🐻 空頭", use_container_width=True):
        st.session_state['view_mode'] = 'bear_scan'
        st.rerun()
    
    # 新增留言板按鈕
    if st.button("💬 戰友留言板", use_container_width=True):
        st.session_state['view_mode'] = 'comments'
        st.rerun()

    st.divider()
    if st.button("🕒 搜尋歷史", use_container_width=True):
        st.session_state['view_mode'] = 'history'
        st.rerun()

    st.caption("最近搜尋")
    if st.session_state['history']:
        for item in st.session_state['history'][:5]:
            code = item.split(" ")[0]
            name = item.split(" ")[1] if " " in item else ""
            if st.button(f"{code} {name}", key=f"side_{code}"):
                set_view_to_analysis(code, name)
                st.rerun()

# --- 主畫面 ---

# 1. 歡迎頁
if st.session_state['view_mode'] == 'welcome':
    st.title("👋 歡迎來到 AI 股市戰情室 V11")
    st.markdown("### 您的全方位即時看盤助手")
    st.info("👈 請從左側輸入股票代號，或使用智能掃描功能。")
    
    with st.container(border=True):
        st.markdown("""
        #### 🚀 V11 最終版功能
        * **💬 戰友留言板**：新增社群互動功能，與朋友討論明牌。
        * **🔴 即時監控**：每 3 秒自動更新股價。
        * **🎨 色彩校正**：完美支援台股/美股漲跌顏色習慣。
        * **🤖 深度診斷**：結合 RSI、成交量、乖離率的 AI 報告。
        """)

# 2. 留言板頁面 (新增功能)
elif st.session_state['view_mode'] == 'comments':
    st.title("💬 戰友留言板")
    st.info("這裡可以留下你的看盤心得，或給開發者的建議！")

    # 輸入區
    with st.container(border=True):
        c1, c2 = st.columns([1, 4])
        user_name = c1.text_input("暱稱", value="匿名股神")
        user_msg = c2.text_input("想說什麼？", placeholder="例如：2330 今天這根太強了吧！")
        
        if st.button("送出留言 📤"):
            if user_msg:
                save_comment(user_name, user_msg)
                st.success("留言成功！")
                time.sleep(0.5)
                st.rerun()
            else:
                st.warning("請輸入內容喔！")

    st.divider()
    st.subheader("📜 最新討論")

    # 顯示留言
    df_comments = load_comments()
    if not df_comments.empty:
        for index, row in df_comments.iterrows():
            with st.chat_message("user"): # 使用聊天氣泡樣式
                st.markdown(f"**{row['User']}** <span style='color:gray; font-size:0.8em'>({row['Time']})</span>", unsafe_allow_html=True)
                st.write(row['Message'])
    else:
        st.write("目前還沒有留言，快來搶頭香！")

# 3. 個股分析 (核心功能)
elif st.session_state['view_mode'] == 'analysis':
    stock_id = st.session_state['current_stock']
    stock_name = st.session_state['current_name']
    
    if not stock_id:
        st.warning("請輸入代號")
    else:
        col_title, col_refresh = st.columns([3, 1])
        with col_title:
            st.title(f"📊 {stock_name} ({stock_id})")
        with col_refresh:
            auto_refresh = st.checkbox("🔴 啟動即時監控", value=False)
            if auto_refresh:
                time.sleep(3)
                st.rerun()

        try:
            rec = f"{stock_id.replace('.TW','')} {stock_name}"
            if rec not in st.session_state['history']:
                st.session_state['history'].insert(0, rec)

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
                
                with st.expander("🏢 公司簡介與財報 (點擊展開)", expanded=False):
                    c1, c2 = st.columns([2, 1])
                    with c1: st.write(translate_text(info.get('longBusinessSummary', '')))
                    with c2:
                        st.metric("ROE", f"{info.get('returnOnEquity',0)*100:.2f}%")
                        st.metric("毛利率", f"{info.get('grossMargins',0)*100:.2f}%")

                st.divider()
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("成交價", f"{curr:.2f}", f"{chg:.2f} ({pct:.2f}%)", delta_color=colors['delta'])
                m2.metric("最高", f"{df['High'].iloc[-1]:.2f}")
                m3.metric("最低", f"{df['Low'].iloc[-1]:.2f}")
                m4.metric("成交量", f"{int(vol/1000):,} 張")

                st.subheader("📈 技術 K 線圖")
                df['MA5'] = df['Close'].rolling(5).mean()
                df['MA20'] = df['Close'].rolling(20).mean()
                df['MA60'] = df['Close'].rolling(60).mean()
                
                trange = st.select_slider("區間", ['3個月','6個月','1年'], value='6個月')
                days = {'3個月':90, '6個月':180, '1年':365}[trange]
                cdf = df.tail(days)
                
                fig = go.Figure()
                fig.add_trace(go.Candlestick(x=cdf.index, open=cdf['Open'], high=cdf['High'], low=cdf['Low'], close=cdf['Close'], name='K線', increasing_line_color=colors['up'], decreasing_line_color=colors['down']))
                fig.add_trace(go.Scatter(x=cdf.index, y=cdf['MA5'], line=dict(color='blue', width=1), name='MA5'))
                fig.add_trace(go.Scatter(x=cdf.index, y=cdf['MA20'], line=dict(color='orange', width=1), name='MA20'))
                fig.add_trace(go.Scatter(x=cdf.index, y=cdf['MA60'], line=dict(color='purple', width=1), name='MA60'))
                fig.update_layout(height=500, xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)

                st.subheader("🤖 AI 深度戰情分析")
                ma20 = df['MA20'].iloc[-1]
                ma60 = df['MA60'].iloc[-1]
                
                delta = df['Close'].diff()
                u, d = delta.copy(), delta.copy()
                u[u < 0] = 0; d[d > 0] = 0
                rs = u.rolling(14).mean() / d.abs().rolling(14).mean()
                rsi = (100 - 100 / (1 + rs)).iloc[-1]
                bias = ((curr - ma60)/ma60)*100
                vol_r = vol / df['Volume'].rolling(5).mean().iloc[-1] if df['Volume'].rolling(5).mean().iloc[-1] > 0 else 1

                with st.container(border=True):
                    c_main, c_det = st.columns([1.5, 1])
                    with c_main:
                        if curr > ma20 and ma20 > ma60: st.success("🔥 **極強多頭**：均線多排，順勢操作。")
                        elif curr < ma20 and ma20 < ma60: st.error("❄️ **空頭破線**：反壓沉重，避開接刀。")
                        else: st.warning("⚖️ **盤整觀望**：多空不明。")
                        
                        if vol_r > 1.5: st.write(f"🚀 **爆量**：量增 {vol_r:.1f} 倍，注意方向。")
                        elif vol_r < 0.6: st.write("💤 **量縮**：觀望氣氛濃。")
                    with c_det:
                        st.write(f"RSI: `{rsi:.1f}`"); st.write(f"季線乖離: `{bias:.2f}%`")
                        if rsi>80: st.error("⚠️ 過熱")
                        elif rsi<20: st.success("💎 超賣")

        except Exception as e:
            st.error(f"錯誤: {e}")

# 4. 掃描頁
elif st.session_state['view_mode'] in ['bull_scan', 'bear_scan']:
    is_bull = (st.session_state['view_mode'] == 'bull_scan')
    title = "🔥 強勢多頭掃描" if is_bull else "❄️ 弱勢空頭掃描"
    st.title(title)
    
    col1, col2 = st.columns([3, 1])
    target = col1.slider("掃描筆數", 5, 30, 10)
    
    if col2.button("開始掃描"):
        found = []
        pbar = st.progress(0)
        status = st.empty()
        for i, code in enumerate(SCAN_LIST):
            if len(found) >= target: break
            status.text(f"掃描中: {code}...")
            pbar.progress((i+1)/len(SCAN_LIST))
            try:
                data = yf.Ticker(f"{code}.TW").history(period="3mo")
                if len(data) > 50:
                    p = data['Close'].iloc[-1]
                    m5 = data['Close'].rolling(5).mean().iloc[-1]
                    m20 = data['Close'].rolling(20).mean().iloc[-1]
                    m60 = data['Close'].rolling(60).mean().iloc[-1]
                    match = False
                    strength = 0
                    if is_bull and p>m5 and m5>m20 and m20>m60:
                        match = True; strength = (p-m20)/m20
                    elif not is_bull and p<m5 and m5<m20 and m20<m60:
                        match = True; strength = (m20-p)/m20
                    if match:
                        name = twstock.codes[code].name if code in twstock.codes else code
                        found.append({'c':code, 'n':name, 'p':p, 's':strength})
            except: continue
        pbar.empty(); status.empty()
        if found:
            found.sort(key=lambda x: x['s'], reverse=True)
            for rank, item in enumerate(found):
                with st.container(border=True):
                    c1, c2, c3, c4, c5 = st.columns([0.5, 1, 1.5, 1.5, 1])
                    c1.write(f"#{rank+1}")
                    c2.markdown(f"### {item['c']}")
                    c3.write(f"**{item['n']}**")
                    c4.write(f"{item['p']:.2f}")
                    c5.button("分析", key=f"btn_{item['c']}", on_click=set_view_to_analysis, args=(item['c'], item['n']))
        else: st.warning("無符合標的")

# 5. 歷史頁
elif st.session_state['view_mode'] == 'history':
    st.title("📜 歷史紀錄")
    if st.session_state['history']:
        for item in st.session_state['history']:
            code = item.split(" ")[0]; name = item.split(" ")[1] if " " in item else ""
            c1, c2 = st.columns([4, 1])
            c1.write(f"📄 {item}")
            c2.button("查看", key=f"h_full_{code}", on_click=set_view_to_analysis, args=(code, name))
