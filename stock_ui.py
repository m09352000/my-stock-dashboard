import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

# --- CSS: 極致壓縮版面，讓資訊密度最大化 ---
def inject_custom_css():
    st.markdown("""
        <style>
        div[data-testid="stVerticalBlock"] > div {
            padding-top: 0rem;
            padding-bottom: 0rem;
            gap: 0.5rem;
        }
        button {
            height: auto !important;
            padding-top: 0.1rem !important;
            padding-bottom: 0.1rem !important;
        }
        .stMetric {
            background-color: #1E1E1E;
            padding: 5px;
            border-radius: 5px;
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
        st.caption("策略來源: V59 高勝率多因子模型 | 數據: Yahoo/TWSE")
        is_live = c2.toggle("🔴 即時盤面", value=False)
    st.divider()
    return is_live

# --- 2. 返回 ---
def render_back_button(callback_func):
    st.divider()
    _, c2, _ = st.columns([2, 1, 2])
    if c2.button("⬅️ 返回列表", use_container_width=True):
        callback_func()

# --- 3. 新手村 ---
def render_term_card(title, content):
    with st.container(border=True):
        st.markdown(f"**{title}**")
        st.caption(content)

# --- 4. 簡介 ---
def render_company_profile(summary):
    if summary and summary != "暫無詳細描述":
        with st.expander("🏢 公司簡介", expanded=False):
            st.write(summary)

# --- 5. 儀表板 ---
def render_metrics_dashboard(curr, chg, pct, high, low, amp, main_force, 
                             vol, vol_yest, vol_avg, vol_status, foreign_held, 
                             color_settings):
    with st.container():
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("成交價", f"{curr:.2f}", f"{chg:.2f} ({pct:.2f}%)", delta_color=color_settings['delta'])
        m2.metric("最高", f"{high:.2f}")
        m3.metric("最低", f"{low:.2f}")
        m4.metric("振幅", f"{amp:.2f}%")
        m5.metric("主力", main_force)
        
        v1, v2, v3, v4, v5 = st.columns(5)
        v1.metric("總量", f"{int(vol/1000):,}張")
        v2.metric("昨量", f"{int(vol_yest/1000):,}張")
        v3.metric("均量", f"{int(vol_avg/1000):,}張")
        v4.metric("狀態", vol_status)
        v5.metric("外資", f"{foreign_held:.1f}%")

# --- 6. 戰術建議生成 (V59: 根據你的要求，提供明確價位) ---
def generate_trade_advice(price, high, low, m5, m20, m60, rsi, strategy_type="general"):
    # 計算 Pivot Points (當沖/短線最準的支撐壓力)
    pivot = (high + low + price) / 3
    r1 = 2 * pivot - low
    s1 = 2 * pivot - high
    
    action = "觀望"
    color = "gray"
    target_price = 0
    stop_price = 0
    
    # 根據不同策略給出不同建議
    if strategy_type == 'day': # 當沖邏輯
        stop_price = low * 0.99 # 低點停損
        target_price = high * 1.02 # 突破高點停利
        if price > m5 and price > pivot:
            action = "🔥 強力作多"; color = "red"
        elif price < pivot:
            action = "🧊 偏空操作"; color = "green"
        else:
            action = "⚖️ 區間震盪"; color = "orange"
            
    elif strategy_type == 'short': # 短線邏輯
        stop_price = m20 # 月線停損
        target_price = price * 1.05 # 5% 獲利
        if price > m5 and m5 > m20:
            action = "🚀 多頭續抱"; color = "red"
        elif price < m5:
            action = "📉 回檔測試"; color = "orange"
            
    elif strategy_type == 'long': # 長線邏輯
        stop_price = m60 # 季線停損
        target_price = price * 1.15 # 波段獲利
        if price > m60:
            action = "🐢 存股續抱"; color = "red"
        else:
            action = "⏳ 等待站上"; color = "gray"
            
    else: # 一般/強勢股
        stop_price = m20
        target_price = r1
        if price > m20: action = "💪 強勢股"; color = "red"
        else: action = "⚠️ 轉弱"; color = "green"

    return action, color, f"🎯{target_price:.1f}", f"🛡️{stop_price:.1f}"

# --- 7. 詳細診斷卡 (V59: 緊湊型戰術面板) ---
def render_detailed_card(code, name, price, df, source_type="yahoo", key_prefix="btn", rank=None, strategy_info=None):
    # 顏色與基本數據
    chg_color = "black"
    pct_txt = ""
    action_title = "分析中..."
    action_color = "gray"
    target_txt = ""
    stop_txt = ""
    
    # 判定策略類型 (從 strategy_info 猜測或預設)
    strat_type = "general"
    if strategy_info and "量" in strategy_info: strat_type = "day"
    elif strategy_info and "5日" in strategy_info: strat_type = "short"
    elif strategy_info and "季" in strategy_info: strat_type = "long"

    if df is not None and not df.empty:
        try:
            curr = df['Close'].iloc[-1]
            prev = df['Close'].iloc[-2] if len(df) > 1 else curr
            chg = curr - prev
            pct = (chg / prev) * 100
            high = df['High'].iloc[-1]
            low = df['Low'].iloc[-1]
            
            if chg > 0: chg_color = "red"; pct_txt = f"▲{pct:.2f}%"
            elif chg < 0: chg_color = "green"; pct_txt = f"▼{abs(pct):.2f}%"
            else: chg_color = "gray"; pct_txt = "0.00%"
            
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
                
                # V59: 生成具體價位建議
                action_title, action_color, target_txt, stop_txt = generate_trade_advice(
                    curr, high, low, m5, m20, m60, rsi, strat_type
                )
        except: pass
    
    rank_tag = f"#{rank}" if rank else ""
    
    # --- V59 卡片佈局 (單行顯示所有關鍵資訊) ---
    with st.container(border=True):
        # 欄位分配：[排名代號] [價格漲跌] [操作建議] [目標/停損] [按鈕]
        c1, c2, c3, c4, c5 = st.columns([1.2, 1.2, 1.5, 1.5, 0.8])
        
        with c1:
            st.markdown(f"**{rank_tag} {name}**")
            st.caption(f"{code}")
        with c2:
            st.markdown(f"**{price:.2f}**")
            st.markdown(f":{chg_color}[{pct_txt}]")
        with c3:
            st.markdown(f":{action_color}[**{action_title}**]")
            if strategy_info: st.caption(strategy_info)
        with c4:
            # 顯示目標價與停損價
            st.caption(f"{target_txt}")
            st.caption(f"{stop_txt}")
        with c5:
            st.write("")
            if st.button("分析", key=f"{key_prefix}_{code}", use_container_width=True):
                return True
    return False

# --- 8. K線圖 ---
def render_chart(df, title, color_settings):
    df['MA5'] = df['Close'].rolling(5).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA60'] = df['Close'].rolling(60).mean()
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
    
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], 
        name='K線', increasing_line_color=color_settings['up'], decreasing_line_color=color_settings['down']
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='#FF00FF', width=1), name='MA5'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='#FFA500', width=1), name='MA20'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA60'], line=dict(color='#0000FF', width=1), name='MA60'), row=1, col=1)
    
    vol_colors = [color_settings['up'] if c >= o else color_settings['down'] for c, o in zip(df['Close'], df['Open'])]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=vol_colors, name='成交量'), row=2, col=1)
    
    fig.update_layout(height=450, xaxis_rangeslider_visible=False, title=title, 
                      margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

# --- 9. AI 報告 ---
def render_ai_report(curr, m5, m20, m60, rsi, bias, high, low):
    st.subheader("🤖 AI 戰略分析報告")
    pivot = (high + low + curr) / 3
    r1 = 2 * pivot - low; s1 = 2 * pivot - high
    
    t1, t2 = st.tabs(["📊 詳細診斷", "🎯 關鍵價位"])
    with t1:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("#### 📈 趨勢")
            if curr > m20 and m20 > m60: st.success("🔥 **多頭排列**")
            elif curr < m20: st.error("❄️ **空頭修正**")
            else: st.warning("🌤️ **震盪整理**")
        with c2:
            st.markdown("#### ⚡ 動能")
            st.metric("RSI", f"{rsi:.1f}")
            if rsi>80: st.write("⚠️ 過熱"); elif rsi<20: st.write("💎 超賣")
        with c3:
            st.markdown("#### 📏 乖離")
            st.metric("季乖離", f"{bias:.2f}%")
    with t2:
        c1, c2, c3 = st.columns(3)
        c1.metric("壓力 R1", f"{r1:.2f}")
        c2.metric("中軸 Pivot", f"{pivot:.2f}")
        c3.metric("支撐 S1", f"{s1:.2f}")
