import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

# --- CSS 樣式優化 (讓卡片變窄的核心) ---
def inject_custom_css():
    st.markdown("""
        <style>
        /* 縮減容器內部的上下留白 */
        div[data-testid="stVerticalBlock"] > div {
            padding-top: 0.1rem;
            padding-bottom: 0.1rem;
        }
        /* 讓按鈕變扁一點 */
        button {
            height: auto !important;
            padding-top: 0.2rem !important;
            padding-bottom: 0.2rem !important;
        }
        /* 調整文字行高 */
        p, .stMarkdown {
            margin-bottom: 0px !important;
        }
        </style>
    """, unsafe_allow_html=True)

# --- 1. 標題與即時監控 ---
def render_header(title, show_monitor=False):
    # 注入 CSS
    inject_custom_css()
    
    c1, c2 = st.columns([3, 1])
    c1.title(title)
    is_live = False
    if show_monitor:
        st.caption("數據來源: Yahoo Finance / TWSE | V53 極速瘦身版")
        is_live = c2.toggle("🔴 啟動即時盤面", value=False)
    st.divider()
    return is_live

# --- 2. 返回按鈕 ---
def render_back_button(callback_func):
    st.divider()
    _, c2, _ = st.columns([2, 1, 2])
    if c2.button("⬅️ 返回上一頁", use_container_width=True):
        callback_func()

# --- 3. 新手村卡片 ---
def render_term_card(title, content):
    with st.container(border=True):
        st.markdown(f"**{title}**")
        st.caption(content)

# --- 4. 公司簡介 ---
def render_company_profile(summary):
    if summary and summary != "暫無詳細描述":
        with st.expander("🏢 公司簡介與業務", expanded=False):
            st.caption(summary)

# --- 5. 數據儀表板 (緊湊版) ---
def render_metrics_dashboard(curr, chg, pct, high, low, amp, main_force, 
                             vol, vol_yest, vol_avg, vol_status, foreign_held, 
                             color_settings):
    # 使用 container 減少與上方的距離
    with st.container():
        # 第一排
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("成交價", f"{curr:.2f}", f"{chg:.2f} ({pct:.2f}%)", delta_color=color_settings['delta'])
        m2.metric("最高", f"{high:.2f}")
        m3.metric("最低", f"{low:.2f}")
        m4.metric("量能", vol_status)
        m5.metric("主力", main_force)

# --- 6. 戰術建議生成器 (V53 新核心) ---
def generate_trade_advice(price, m5, m20, m60, rsi):
    """
    根據技術指標生成具體的「一句話操作建議」
    """
    advice = ""
    color = "gray"
    
    # 1. 強勢多頭 (價格 > 5日 > 20日)
    if price > m5 and m5 > m20:
        dist_m5 = ((price - m5) / m5) * 100
        if dist_m5 > 5: # 乖離過大
            advice = f"⚡ 過熱 (乖離{dist_m5:.1f}%)，勿追高，等回測 {m5:.1f} 接"
            color = "orange"
        else:
            advice = f"🚀 強勢攻擊，沿 5日線 {m5:.1f} 續抱/加碼"
            color = "red"
            
    # 2. 震盪偏多 (價格在 20日之上，但跌破 5日)
    elif price > m20 and price < m5:
        advice = f"📈 多頭回檔，觀察月線 {m20:.1f} 支撐是否守住"
        color = "orange"
        
    # 3. 空頭走勢 (價格 < 20日)
    elif price < m20:
        advice = f"❄️ 弱勢整理，反彈至 {m20:.1f} 遇壓建議減碼"
        color = "green"
        
    # 4. 特殊情況：RSI
    if rsi > 80: advice = "⚠️ RSI 過熱 (>80)，隨時準備獲利了結"
    elif rsi < 20: advice = "💎 RSI 超賣 (<20)，搶反彈機會"
    
    return advice, color

# --- 7. 詳細診斷卡 (V53 瘦身版) ---
def render_detailed_card(code, name, price, df, source_type="yahoo", key_prefix="btn", rank=None, strategy_info=None):
    """
    V53 改版重點：
    1. 高度壓縮：一行顯示所有資訊
    2. 資訊合併：代號+名稱、價格+漲跌
    3. 新增欄位：具體操作建議 (Action)
    """
    
    # 預設值
    chg_color = "black"
    advice_txt = "數據分析中..."
    advice_color = "gray"
    pct_txt = ""
    
    if df is not None and not df.empty:
        try:
            curr = df['Close'].iloc[-1]
            prev = df['Close'].iloc[-2] if len(df) > 1 else curr
            chg = curr - prev
            pct = (chg / prev) * 100
            
            # 顏色邏輯 (台股)
            if chg > 0: chg_color = "red"; pct_txt = f"▲ {pct:.2f}%"
            elif chg < 0: chg_color = "green"; pct_txt = f"▼ {abs(pct):.2f}%"
            else: chg_color = "gray"; pct_txt = "0.00%"
            
            # 戰術建議計算
            if len(df) > 20:
                m5 = df['Close'].rolling(5).mean().iloc[-1]
                m20 = df['Close'].rolling(20).mean().iloc[-1]
                m60 = df['Close'].rolling(60).mean().iloc[-1]
                
                # 計算 RSI
                delta = df['Close'].diff()
                u = delta.copy(); d = delta.copy()
                u[u<0]=0; d[d>0]=0
                rs = u.rolling(14).mean() / d.abs().rolling(14).mean()
                rsi = (100 - 100/(1+rs)).iloc[-1] if not rs.isna().iloc[-1] else 50
                
                advice_txt, advice_color = generate_trade_advice(curr, m5, m20, m60, rsi)
            else:
                advice_txt = "資料不足，僅顯示報價"
                
        except: pass
    
    # 顯示排名 (選用)
    rank_tag = f"#{rank} " if rank else ""
    
    # --- UI 繪製 (使用 columns 達成單行佈局) ---
    with st.container(border=True):
        # 佈局比例：[股票名稱] [價格資訊] [操作建議(最寬)] [按鈕]
        c1, c2, c3, c4 = st.columns([1.5, 1.5, 3.5, 1])
        
        with c1:
            # 股票代號與名稱
            st.markdown(f"**{rank_tag}{name}**")
            st.caption(f"{code}")
            
        with c2:
            # 價格與漲跌幅
            st.markdown(f"**{price:.2f}**")
            st.markdown(f":{chg_color}[{pct_txt}]")
            
        with c3:
            # 戰術建議 (V53 重點)
            st.markdown(f"**策略：{strategy_info if strategy_info else '綜合分析'}**")
            st.markdown(f":{advice_color}[{advice_txt}]")
            
        with c4:
            # 按鈕置中
            st.write("") # 墊高一點讓按鈕置中
            if st.button("分析", key=f"{key_prefix}_{code}", use_container_width=True):
                return True
                
    return False

# --- 8. K線圖 ---
def render_chart(df, title, color_settings):
    df['MA5'] = df['Close'].rolling(5).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
    
    # K線
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], 
        name='K線', increasing_line_color=color_settings['up'], decreasing_line_color=color_settings['down']
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='#FF00FF', width=1), name='MA5'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='#FFA500', width=1), name='MA20'), row=1, col=1)
    
    # 成交量
    vol_colors = [color_settings['up'] if c >= o else color_settings['down'] for c, o in zip(df['Close'], df['Open'])]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=vol_colors, name='成交量'), row=2, col=1)
    
    fig.update_layout(height=450, xaxis_rangeslider_visible=False, title=title, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)

# --- 9. AI 深度診斷報告 (下方詳細頁用) ---
def render_ai_report(curr, m5, m20, m60, rsi, bias, high, low):
    st.subheader("🤖 AI 戰略分析")
    
    pivot = (high + low + curr) / 3
    r1 = 2 * pivot - low
    s1 = 2 * pivot - high
    
    t1, t2 = st.tabs(["💡 操作建議", "📊 關鍵價位"])
    
    with t1:
        advice, color = generate_trade_advice(curr, m5, m20, m60, rsi)
        st.info(f"### {advice}")
        st.write(f"目前趨勢：{'多頭排列' if curr>m20 else '空頭/整理'} (月線乖離 {bias:.2f}%)")
        
    with t2:
        c1, c2, c3 = st.columns(3)
        c1.metric("壓力 (R1)", f"{r1:.2f}")
        c2.metric("中軸 (Pivot)", f"{pivot:.2f}")
        c3.metric("支撐 (S1)", f"{s1:.2f}")
