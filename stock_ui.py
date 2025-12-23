import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

# --- CSS 樣式優化 ---
def inject_custom_css():
    st.markdown("""
        <style>
        div[data-testid="stVerticalBlock"] > div {
            padding-top: 0.1rem;
            padding-bottom: 0.1rem;
        }
        button {
            height: auto !important;
            padding-top: 0.2rem !important;
            padding-bottom: 0.2rem !important;
        }
        /* 讓卡片內的文字排版更緊湊 */
        div[data-testid="stMetricValue"] {
            font-size: 1.2rem !important;
        }
        </style>
    """, unsafe_allow_html=True)

# --- 1. 標題 ---
def render_header(title, show_monitor=False):
    inject_custom_css()
    c1, c2 = st.columns([3, 1])
    c1.title(title)
    is_live = False
    if show_monitor:
        st.caption("數據來源: Yahoo Finance / TWSE | V58 自選股增強版")
        is_live = c2.toggle("🔴 啟動即時盤面", value=False)
    st.divider()
    return is_live

# --- 2. 返回 ---
def render_back_button(callback_func):
    st.divider()
    _, c2, _ = st.columns([2, 1, 2])
    if c2.button("⬅️ 返回上一頁", use_container_width=True):
        callback_func()

# --- 3. 新手村 ---
def render_term_card(title, content):
    with st.container(border=True):
        st.markdown(f"**{title}**")
        st.caption(content)

# --- 4. 簡介 ---
def render_company_profile(summary):
    if summary and summary != "暫無詳細描述":
        with st.expander("🏢 公司簡介與業務", expanded=False):
            st.write(summary)

# --- 5. 儀表板 ---
def render_metrics_dashboard(curr, chg, pct, high, low, amp, main_force, 
                             vol, vol_yest, vol_avg, vol_status, foreign_held, 
                             color_settings):
    with st.container():
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("成交價", f"{curr:.2f}", f"{chg:.2f} ({pct:.2f}%)", delta_color=color_settings['delta'])
        m2.metric("最高價", f"{high:.2f}")
        m3.metric("最低價", f"{low:.2f}")
        m4.metric("振幅", f"{amp:.2f}%")
        m5.metric("主力動向", main_force)
        
        v1, v2, v3, v4, v5 = st.columns(5)
        v1.metric("今日總量", f"{int(vol/1000):,} 張")
        diff_vol = int((vol - vol_yest)/1000)
        v2.metric("昨日總量", f"{int(vol_yest/1000):,} 張", f"{diff_vol} 張")
        v3.metric("5日均量", f"{int(vol_avg/1000):,} 張")
        v4.metric("量能狀態", vol_status)
        v5.metric("外資持股", f"{foreign_held:.1f}%")

# --- 6. 戰術建議生成器 (V58: 這是產生詳細推薦的核心) ---
def generate_trade_advice(price, m5, m20, m60, rsi):
    advice = "數據不足"
    color = "gray"
    action = "觀望"
    
    # 1. 強勢多頭 (價格 > 5日 > 20日)
    if price > m5 and m5 > m20:
        dist_m5 = ((price - m5) / m5) * 100
        if dist_m5 > 5: 
            advice = "🔥 過熱"; action = f"乖離{dist_m5:.1f}%，等回測{m5:.1f}接"
            color = "orange"
        else:
            advice = "🚀 強勢"; action = f"沿5日線 {m5:.1f} 續抱/加碼"
            color = "red"
            
    # 2. 震盪偏多 (價格在 20日之上，但跌破 5日)
    elif price > m20 and price < m5:
        advice = "📈 回檔"; action = f"守月線 {m20:.1f} 找買點"
        color = "orange"
        
    # 3. 空頭走勢 (價格 < 20日)
    elif price < m20:
        advice = "❄️ 弱勢"; action = f"反彈 {m20:.1f} 遇壓減碼"
        color = "green"
    
    # RSI 特判
    if rsi > 80: advice = "⚠️ 過熱"; action = "RSI>80 隨時準備獲利"
    elif rsi < 20: advice = "💎 超賣"; action = "RSI<20 醞釀反彈"
    
    return advice, color, action

# --- 7. 詳細診斷卡 (V58: 列表卡片升級) ---
def render_detailed_card(code, name, price, df, source_type="yahoo", key_prefix="btn", rank=None, strategy_info=None):
    """
    V58 改版：在卡片上直接顯示「具體操作建議」與「詳細數據」
    """
    chg_color = "black"
    pct_txt = ""
    advice_title = "分析中"
    advice_color = "gray"
    advice_action = ""
    extra_info = "" # 顯示成交量或乖離
    
    if df is not None and not df.empty:
        try:
            curr = df['Close'].iloc[-1]
            prev = df['Close'].iloc[-2] if len(df) > 1 else curr
            chg = curr - prev
            pct = (chg / prev) * 100
            
            if chg > 0: chg_color = "red"; pct_txt = f"▲ {pct:.2f}%"
            elif chg < 0: chg_color = "green"; pct_txt = f"▼ {abs(pct):.2f}%"
            else: chg_color = "gray"; pct_txt = "0.00%"
            
            if len(df) > 20:
                m5 = df['Close'].rolling(5).mean().iloc[-1]
                m20 = df['Close'].rolling(20).mean().iloc[-1]
                m60 = df['Close'].rolling(60).mean().iloc[-1]
                vol = df['Volume'].iloc[-1]
                
                # 計算 RSI
                delta = df['Close'].diff()
                u = delta.copy(); d = delta.copy()
                u[u<0]=0; d[d>0]=0
                rs = u.rolling(14).mean() / d.abs().rolling(14).mean()
                rsi = (100 - 100/(1+rs)).iloc[-1] if not rs.isna().iloc[-1] else 50
                
                # 呼叫 V58 戰術生成
                advice_title, advice_color, advice_action = generate_trade_advice(curr, m5, m20, m60, rsi)
                
                # 額外資訊：成交量 + 季線乖離
                bias = ((curr-m60)/m60)*100
                extra_info = f"量: {int(vol/1000)}張 | 季乖離: {bias:.1f}%"
                
        except: pass
    
    rank_tag = f"#{rank} " if rank else ""
    
    # --- 卡片 UI (四欄位設計) ---
    with st.container(border=True):
        # 1.代號  2.價格  3.詳細建議(最寬)  4.按鈕
        c1, c2, c3, c4 = st.columns([1.2, 1.2, 3.0, 0.8])
        
        with c1:
            st.markdown(f"**{rank_tag}{name}**")
            st.caption(f"{code}")
            
        with c2:
            st.markdown(f"**{price:.2f}**")
            st.markdown(f":{chg_color}[{pct_txt}]")
            
        with c3:
            # V58 重點：顯示標題 + 具體操作建議 + 數據
            st.markdown(f":{advice_color}[**{advice_title}**] {advice_action}")
            st.caption(f"{extra_info}")
            
        with c4:
            st.write("") # 排版用
            if st.button("分析", key=f"{key_prefix}_{code}", use_container_width=True):
                return True
                
    return False

# --- 8. K線圖 ---
def render_chart(df, title, color_settings):
    df['MA5'] = df['Close'].rolling(5).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA60'] = df['Close'].rolling(60).mean()
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
    
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], 
        name='K線', increasing_line_color=color_settings['up'], decreasing_line_color=color_settings['down']
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='#FF00FF', width=1), name='MA5'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='#FFA500', width=1), name='MA20'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA60'], line=dict(color='#0000FF', width=1), name='MA60'), row=1, col=1)
    
    vol_colors = [color_settings['up'] if c >= o else color_settings['down'] for c, o in zip(df['Close'], df['Open'])]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=vol_colors, name='成交量'), row=2, col=1)
    
    fig.update_layout(height=500, xaxis_rangeslider_visible=False, title=title, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)

# --- 9. AI 報告 (保留 V57 的完整版) ---
def render_ai_report(curr, m5, m20, m60, rsi, bias, high, low):
    st.subheader("🤖 AI 戰略分析報告")
    
    pivot = (high + low + curr) / 3
    r1 = 2 * pivot - low
    s1 = 2 * pivot - high
    
    t1, t2 = st.tabs(["📊 詳細趨勢診斷", "🎯 關鍵價位試算"])
    
    with t1:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("#### 📈 趨勢研判")
            if curr > m20 and m20 > m60: st.success("🔥 **多頭排列**：均線向上，多方控盤。")
            elif curr < m20 and m20 < m60: st.error("❄️ **空頭排列**：均線反壓，建議保守。")
            elif curr > m20: st.warning("🌤️ **震盪偏多**：站上月線，留意前高。")
            else: st.info("🌧️ **震盪偏空**：月線之下，等待底部。")
        with c2:
            st.markdown("#### ⚡ 動能指標 (RSI)")
            st.metric("RSI (14)", f"{rsi:.1f}")
            if rsi > 80: st.write("⚠️ **過熱警戒**")
            elif rsi < 20: st.write("💎 **超賣區**")
            else: st.write("✅ **動能中性**")
        with c3:
            st.markdown("#### 📏 乖離率")
            st.metric("季線乖離", f"{bias:.2f}%")
            if bias > 20: st.write("⚠️ **正乖離過大**")
            elif bias < -20: st.write("💎 **負乖離過大**")
            else: st.write("✅ **乖離正常**")

    with t2:
        st.markdown("#### 🎯 Pivot Point 關鍵價位")
        cp1, cp2, cp3 = st.columns(3)
        cp1.metric("壓力位 (R1)", f"{r1:.2f}")
        cp2.metric("中軸 (Pivot)", f"{pivot:.2f}")
        cp3.metric("支撐位 (S1)", f"{s1:.2f}")
