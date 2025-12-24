import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

# --- CSS: 版面微調 (讓資訊密度高但不擁擠) ---
def inject_custom_css():
    st.markdown("""
        <style>
        div[data-testid="stVerticalBlock"] > div {
            padding-top: 0.1rem;
            padding-bottom: 0.1rem;
            gap: 0.5rem;
        }
        button {
            height: auto !important;
            padding-top: 0.2rem !important;
            padding-bottom: 0.2rem !important;
        }
        /* 讓卡片文字清晰 */
        .stMarkdown p {
            font-size: 1rem;
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
        st.caption("數據來源: Yahoo Finance / TWSE | V60 完整修復版")
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

# --- 5. 儀表板 (完整雙排數據) ---
def render_metrics_dashboard(curr, chg, pct, high, low, amp, main_force, 
                             vol, vol_yest, vol_avg, vol_status, foreign_held, 
                             color_settings):
    with st.container():
        # 第一排：價格與波動
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("成交價", f"{curr:.2f}", f"{chg:.2f} ({pct:.2f}%)", delta_color=color_settings['delta'])
        m2.metric("最高價", f"{high:.2f}")
        m3.metric("最低價", f"{low:.2f}")
        m4.metric("振幅", f"{amp:.2f}%")
        m5.metric("主力動向", main_force)
        
        # 第二排：量能與籌碼 (絕不簡化)
        v1, v2, v3, v4, v5 = st.columns(5)
        v1.metric("今日總量", f"{int(vol/1000):,} 張")
        diff_vol = int((vol - vol_yest)/1000)
        v2.metric("昨日總量", f"{int(vol_yest/1000):,} 張", f"{diff_vol} 張")
        v3.metric("5日均量", f"{int(vol_avg/1000):,} 張")
        v4.metric("量能狀態", vol_status)
        v5.metric("外資持股", f"{foreign_held:.1f}%")

# --- 6. 戰術建議生成 (含具體價位) ---
def generate_trade_advice(price, high, low, m5, m20, m60, rsi, strategy_type="general"):
    # Pivot Points 計算
    pivot = (high + low + price) / 3
    
    action = "觀望"
    color = "gray"
    target_price = 0.0
    stop_price = 0.0
    
    # 策略邏輯分支
    if strategy_type == 'day': # 當沖
        stop_price = low * 0.99
        target_price = high * 1.02
        if price > m5 and price > pivot:
            action = "🔥 強力作多"; color = "red"
        elif price < pivot:
            action = "🧊 偏空操作"; color = "green"
        else:
            action = "⚖️ 區間震盪"; color = "orange"
            
    elif strategy_type == 'short': # 短線
        stop_price = m20
        target_price = price * 1.05
        if price > m5 and m5 > m20:
            action = "🚀 多頭續抱"; color = "red"
        elif price < m5:
            action = "📉 回檔測試"; color = "orange"
            
    elif strategy_type == 'long': # 長線
        stop_price = m60
        target_price = price * 1.15
        if price > m60:
            action = "🐢 存股續抱"; color = "red"
        else:
            action = "⏳ 等待站上"; color = "gray"
            
    else: # 一般
        stop_price = m20
        target_price = price * 1.03
        if price > m20: 
            action = "💪 強勢股"; color = "red"
        else: 
            action = "⚠️ 轉弱"; color = "green"

    return action, color, f"🎯{target_price:.1f}", f"🛡️{stop_price:.1f}"

# --- 7. 詳細診斷卡 (列表卡片) ---
def render_detailed_card(code, name, price, df, source_type="yahoo", key_prefix="btn", rank=None, strategy_info=None):
    chg_color = "black"
    pct_txt = ""
    action_title = "分析中..."
    action_color = "gray"
    target_txt = ""
    stop_txt = ""
    
    # 判斷策略類型
    strat_type = "general"
    if strategy_info:
        if "量" in strategy_info or "爆量" in strategy_info: strat_type = "day"
        elif "乖離" in strategy_info: strat_type = "short"
        elif "季" in strategy_info: strat_type = "long"

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
                
                delta = df['Close'].diff()
                u = delta.copy(); d = delta.copy()
                u[u<0]=0; d[d>0]=0
                rs = u.rolling(14).mean() / d.abs().rolling(14).mean()
                rsi = (100 - 100/(1+rs)).iloc[-1] if not rs.isna().iloc[-1] else 50
                
                action_title, action_color, target_txt, stop_txt = generate_trade_advice(
                    curr, high, low, m5, m20, m60, rsi, strat_type
                )
        except: pass
    
    rank_tag = f"#{rank}" if rank else ""
    
    with st.container(border=True):
        # 欄位：[代號] [價格] [建議與操作] [目標/停損] [按鈕]
        c1, c2, c3, c4, c5 = st.columns([1.2, 1.2, 1.8, 1.2, 0.8])
        
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

# --- 9. AI 報告 (🔥 修復 SyntaxError) ---
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
            # 🔥 這裡之前寫錯，已修正為標準 Python 寫法
            if rsi > 80:
                st.write("⚠️ **過熱警戒**：短線有回檔風險。")
            elif rsi < 20:
                st.write("💎 **超賣區**：隨時可能反彈。")
            else:
                st.write("✅ **動能中性**：無明顯過熱訊號。")
            
        with c3:
            st.markdown("#### 📏 乖離率分析")
            st.metric("季線乖離", f"{bias:.2f}%")
            if bias > 20: st.write("⚠️ **正乖離過大**：容易拉回。")
            elif bias < -20: st.write("💎 **負乖離過大**：有機會反彈。")
            else: st.write("✅ **乖離正常**：沿趨勢線運行。")

    with t2:
        st.markdown("#### 🎯 Pivot Point 關鍵價位 (當沖/隔日沖參考)")
        st.info("計算基礎：(最高+最低+收盤)/3")
        cp1, cp2, cp3 = st.columns(3)
        cp1.metric("壓力位 (R1)", f"{r1:.2f}", help="預估上方第一道壓力")
        cp2.metric("中軸 (Pivot)", f"{pivot:.2f}", help="多空分水嶺")
        cp3.metric("支撐位 (S1)", f"{s1:.2f}", help="預估下方第一道支撐")
