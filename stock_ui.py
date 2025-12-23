import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

# --- CSS 樣式優化 (保持緊湊但資訊不減) ---
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
        </style>
    """, unsafe_allow_html=True)

# --- 1. 標題與即時監控 ---
def render_header(title, show_monitor=False):
    inject_custom_css()
    c1, c2 = st.columns([3, 1])
    c1.title(title)
    is_live = False
    if show_monitor:
        st.caption("數據來源: Yahoo Finance / TWSE | V56 完整資訊版")
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
            st.write(summary)

# --- 5. 數據儀表板 (恢復雙排詳細資訊) ---
def render_metrics_dashboard(curr, chg, pct, high, low, amp, main_force, 
                             vol, vol_yest, vol_avg, vol_status, foreign_held, 
                             color_settings):
    with st.container():
        # 第一排：價格核心
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("成交價", f"{curr:.2f}", f"{chg:.2f} ({pct:.2f}%)", delta_color=color_settings['delta'])
        m2.metric("最高價", f"{high:.2f}")
        m3.metric("最低價", f"{low:.2f}")
        m4.metric("振幅", f"{amp:.2f}%")
        m5.metric("主力動向", main_force)
        
        # 第二排：量能核心 (補回詳細數字)
        v1, v2, v3, v4, v5 = st.columns(5)
        v1.metric("今日總量", f"{int(vol/1000):,} 張")
        # 顯示與昨日差額
        diff_vol = int((vol - vol_yest)/1000)
        v2.metric("昨日總量", f"{int(vol_yest/1000):,} 張", f"{diff_vol} 張")
        v3.metric("5日均量", f"{int(vol_avg/1000):,} 張")
        v4.metric("量能狀態", vol_status)
        v5.metric("外資持股", f"{foreign_held:.1f}%")

# --- 6. 詳細診斷卡 (列表用 - 瘦身版) ---
def render_detailed_card(code, name, price, df, source_type="yahoo", key_prefix="btn", rank=None, strategy_info=None):
    chg_color = "black"
    advice_txt = "數據不足"
    advice_color = "gray"
    pct_txt = ""
    
    if df is not None and not df.empty:
        try:
            curr = df['Close'].iloc[-1]
            prev = df['Close'].iloc[-2] if len(df) > 1 else curr
            chg = curr - prev
            pct = (chg / prev) * 100
            
            if chg > 0: chg_color = "red"; pct_txt = f"▲ {pct:.2f}%"
            elif chg < 0: chg_color = "green"; pct_txt = f"▼ {abs(pct):.2f}%"
            
            if len(df) > 20:
                m5 = df['Close'].rolling(5).mean().iloc[-1]
                m20 = df['Close'].rolling(20).mean().iloc[-1]
                
                if curr > m5 and m5 > m20: 
                    advice_txt = "🔥 多頭強勢"; advice_color = "red"
                elif curr < m5 and curr > m20:
                    advice_txt = "📉 短線回檔"; advice_color = "orange"
                elif curr < m20:
                    advice_txt = "❄️ 空頭修正"; advice_color = "green"
                else:
                    advice_txt = "⚖️ 區間震盪"; advice_color = "gray"
        except: pass
    
    rank_tag = f"#{rank} " if rank else ""
    
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([1.5, 1.5, 3.5, 1])
        with c1:
            st.markdown(f"**{rank_tag}{name}**")
            st.caption(f"{code}")
        with c2:
            st.markdown(f"**{price:.2f}**")
            st.markdown(f":{chg_color}[{pct_txt}]")
        with c3:
            st.markdown(f"**{strategy_info if strategy_info else '狀態'}**")
            st.markdown(f":{advice_color}[{advice_txt}]")
        with c4:
            st.write("")
            if st.button("分析", key=f"{key_prefix}_{code}", use_container_width=True):
                return True
    return False

# --- 7. K線圖 ---
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

# --- 8. AI 報告 (🔥 V56: 詳細版 + 關鍵價位) ---
def render_ai_report(curr, m5, m20, m60, rsi, bias, high, low):
    st.subheader("🤖 AI 戰略分析報告")
    
    # 計算 Pivot (關鍵價位)
    pivot = (high + low + curr) / 3
    r1 = 2 * pivot - low
    s1 = 2 * pivot - high
    
    # 使用 Tabs 分開 "詳細診斷" 與 "關鍵價位"
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
            if rsi > 80: st.write("⚠️ **過熱警戒**：短線有回檔風險。")
            elif rsi < 20: st.write("💎 **超賣區**：隨時可能反彈。")
            else: st.write("✅ **動能中性**：無明顯過熱訊號。")
            
        with c3:
            st.markdown("#### 📏 乖離率分析")
            st.metric("季線乖離", f"{bias:.2f}%")
            if bias > 20: st.write("⚠️ **正乖離過大**：容易拉回。")
            elif bias < -20: st.write("💎 **負乖離過大**：有機會反彈。")
            else: st.write("✅ **乖離正常**：沿趨勢線運行。")

    with t2:
        st.markdown("Based on Pivot Point Calculation (僅供參考)")
        cp1, cp2, cp3 = st.columns(3)
        cp1.metric("壓力位 (R1)", f"{r1:.2f}", help="預估上方第一道壓力")
        cp2.metric("中軸 (Pivot)", f"{pivot:.2f}", help="多空分水嶺")
        cp3.metric("支撐位 (S1)", f"{s1:.2f}", help="預估下方第一道支撐")
