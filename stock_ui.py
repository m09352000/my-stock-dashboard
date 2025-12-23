import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. 標題與監控 ---
def render_header(title, show_monitor=False):
    c1, c2 = st.columns([3, 1])
    c1.title(title)
    is_live = False
    if show_monitor:
        is_live = c2.toggle("🔴 啟動即時監控", value=False)
    st.divider()
    return is_live

# --- 2. 底部返回 ---
def render_back_button(callback_func):
    st.divider()
    if st.button("⬅️ 返回上一頁", use_container_width=True):
        callback_func()

# --- 3. 新手村卡片 ---
def render_term_card(title, content):
    st.info(f"### {title}\n\n{content}")

# --- 4. 公司簡介 ---
def render_company_profile(summary):
    if summary and summary != "暫無詳細描述":
        with st.expander("🏢 公司簡介", expanded=False):
            st.write(summary)

# --- 5. 詳細數據儀表板 ---
def render_metrics_dashboard(curr, chg, pct, high, low, amp, main_force, 
                             vol, vol_yest, vol_avg, vol_status, foreign_held, 
                             color_settings):
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("成交價", f"{curr:.2f}", f"{chg:.2f} ({pct:.2f}%)", delta_color=color_settings['delta'])
    m2.metric("最高價", f"{high:.2f}")
    m3.metric("最低價", f"{low:.2f}")
    m4.metric("振幅", f"{amp:.2f}%")
    m5.metric("主力動向", main_force)
    v1, v2, v3, v4, v5 = st.columns(5)
    v1.metric("今日成交量", f"{int(vol/1000):,} 張")
    v2.metric("昨日成交量", f"{int(vol_yest/1000):,} 張", f"{int((vol-vol_yest)/1000)} 張")
    v3.metric("本週均量", f"{int(vol_avg/1000):,} 張")
    v4.metric("量能狀態", vol_status)
    v5.metric("外資持股", f"{foreign_held:.1f}%")

# --- 6. 自選股/掃描 詳細診斷卡 (純 Yahoo 版) ---
def render_detailed_card(code, name, price, df, key_prefix="btn"):
    # 預設值
    status_color = "gray"
    trend_txt = "資料讀取中"
    rsi_txt = "-"
    vol_txt = "-"
    
    # 只要有資料就計算 (寬鬆模式)
    if df is not None and not df.empty and len(df) > 5:
        curr = df['Close'].iloc[-1]
        # 簡單計算均線
        m20 = df['Close'].rolling(20).mean().iloc[-1] if len(df) > 20 else curr
        
        # 趨勢
        if curr > m20:
            trend_txt = "🔥 多頭格局"
            status_color = "green"
        else:
            trend_txt = "❄️ 空頭整理"
            status_color = "red"

        # RSI (如果有足夠資料)
        if len(df) > 15:
            delta = df['Close'].diff()
            u = delta.copy(); d = delta.copy(); u[u<0]=0; d[d>0]=0
            rs = u.rolling(14).mean()/d.abs().rolling(14).mean()
            rsi = (100 - 100/(1+rs)).iloc[-1]
            rsi_txt = f"{rsi:.1f}"
        
        # 量能
        vol_curr = df['Volume'].iloc[-1]
        vol_avg = df['Volume'].tail(5).mean()
        if vol_avg > 0:
            ratio = vol_curr / vol_avg
            vol_txt = "🔥 爆量" if ratio > 1.5 else "量縮" if ratio < 0.6 else "正常"

    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns([1, 1.5, 2, 2.5, 1])
        c1.markdown(f"### {code}")
        c2.write(f"**{name}**")
        c3.metric("現價", f"{price:.2f}")
        c4.markdown(f":{status_color}[{trend_txt}]")
        c4.caption(f"RSI: {rsi_txt} | 量: {vol_txt}")
        # 回傳按鈕
        return c5.button("詳細分析", key=f"{key_prefix}_{code}")

# --- 7. K線圖 ---
def render_chart(df, title):
    df['MA5'] = df['Close'].rolling(5).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='K線'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='blue', width=1), name='MA5'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='orange', width=1), name='MA20'), row=1, col=1)
    colors = ['red' if c >= o else 'green' for c, o in zip(df['Close'], df['Open'])]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors, name='成交量'), row=2, col=1)
    fig.update_layout(height=600, xaxis_rangeslider_visible=False, title=title, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)

# --- 8. AI 報告 ---
def render_ai_report(curr, m20, m60, rsi, bias):
    st.subheader("🤖 AI 深度診斷報告")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.info("📈 **趨勢研判**")
        if curr > m20: st.markdown("### 🔥 強勢多頭"); st.write("股價位於月線之上，趨勢偏多。")
        else: st.markdown("### ❄️ 弱勢整理"); st.write("股價跌破月線，建議觀望。")
    with c2:
        st.warning("⚡ **動能 (RSI)**")
        st.metric("數值", f"{rsi:.1f}")
        if rsi > 80: st.write("⚠️ 過熱")
        elif rsi < 20: st.write("💎 超賣")
        else: st.write("✅ 中性")
    with c3:
        st.error("📏 **乖離率**")
        st.metric("數值", f"{bias:.2f}%")
        if bias > 20: st.write("⚠️ 正乖離大")
        elif bias < -20: st.write("💎 負乖離大")
        else: st.write("✅ 正常")
