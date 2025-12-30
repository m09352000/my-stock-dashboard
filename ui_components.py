# ui_components.py
# V2.0: UI 適配 FinMind 數據

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import ui_styles
import logic_database as db
import pandas as pd

# --- 1. Header ---
def render_header(title, show_monitor=False, is_live=False, time_str=""):
    ui_styles.inject_custom_css()
    c1, c2 = st.columns([3, 1])
    if title: c1.title(title)
    if is_live:
        c2.markdown(f"<div style='text-align:right;padding-top:10px;'><span class='live-tag'>● LIVE 連線中 (FinMind)</span><br><span style='font-size:0.8rem;color:#888'>更新: {time_str}</span></div>", unsafe_allow_html=True)
    st.markdown("<hr class='compact'>", unsafe_allow_html=True)

# --- 2. Fundamental Panel ---
def render_fundamental_panel(stock_info):
    name = stock_info.get('name', '未知個股')
    code = stock_info.get('code', '')
    summary_raw = stock_info.get('longBusinessSummary', '')
    summary_zh = db.translate_text(summary_raw)
    
    sector = stock_info.get('sector', '-')
    eps = stock_info.get('trailingEps', 0.0)
    pe = stock_info.get('trailingPE', 0.0)
    
    with st.container(border=True):
        c_main, c_info = st.columns([3, 1])
        with c_main:
            st.markdown(f"### 🏢 {name} ({code})")
            st.caption(f"板塊: {sector}")
            if summary_zh and len(str(summary_zh)) > 5:
                with st.expander("📖 業務介紹", expanded=False):
                    st.write(summary_zh)
        with c_info:
            st.metric("EPS", f"{eps}" if eps else "-")
            st.metric("P/E", f"{pe:.2f}" if pe else "-")

# --- 3. Metrics Dashboard (五檔) ---
def render_metrics_dashboard(curr, chg, pct, high, low, amp, mf, vol, vy, va, vs, fh, tr, ba, cs, rt_pack, unit="張", code=""):
    with st.container():
        c1, c2, c3, c4 = st.columns(4)
        val_color = "#FF2B2B" if chg > 0 else "#00E050" if chg < 0 else "white"
        
        c1.markdown(f"<div style='color:#888;font-size:0.9rem'>成交價</div><div style='font-size:2.5rem;font-weight:bold;color:{val_color}'>{curr:.2f}</div><div style='color:{val_color};font-size:1.2rem'>{chg:+.2f} ({pct:+.2f}%)</div>", unsafe_allow_html=True)
        c2.metric("最高", f"{high:.2f}")
        c3.metric("最低", f"{low:.2f}")
        
        vol_str = f"{int(vol):,}"
        if unit == "股" and vol > 1000000: vol_str = f"{vol/1000000:.2f}M"
        c4.metric("成交量", f"{vol_str} {unit}")
        
        st.markdown("---")
        
        # 五檔顯示
        b_p = rt_pack.get('bid_price', [])
        b_v = rt_pack.get('bid_volume', [])
        a_p = rt_pack.get('ask_price', [])
        a_v = rt_pack.get('ask_volume', [])
        
        if b_p and len(b_p) > 0:
            st.caption("📊 FinMind 即時五檔")
            col_b, col_s = st.columns(2)
            with col_b:
                st.markdown("<h5 style='color:#FF2B2B;text-align:center'>買進 (Bid)</h5>", unsafe_allow_html=True)
                # 倒序顯示，讓價格高的在上面
                for i in range(min(5, len(b_p))):
                    st.markdown(f"<div style='display:flex;justify-content:space-between;border-bottom:1px solid #333'><span>{b_p[i]}</span><span>{b_v[i]}</span></div>", unsafe_allow_html=True)
            with col_s:
                st.markdown("<h5 style='color:#00E050;text-align:center'>賣出 (Ask)</h5>", unsafe_allow_html=True)
                for i in range(min(5, len(a_p))):
                    st.markdown(f"<div style='display:flex;justify-content:space-between;border-bottom:1px solid #333'><span>{a_p[i]}</span><span>{a_v[i]}</span></div>", unsafe_allow_html=True)

# --- 4. Chart ---
def render_chart(df, title, color_settings, key=None):
    if key is None: key = "chart"
    if len(df) > 5: df['MA5'] = df['Close'].rolling(5).mean()
    if len(df) > 20: df['MA20'] = df['Close'].rolling(20).mean()
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='K線'), row=1, col=1)
    if 'MA5' in df.columns: fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='magenta', width=1), name='5MA'), row=1, col=1)
    if 'MA20' in df.columns: fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='orange', width=1), name='20MA'), row=1, col=1)
    
    colors = ['red' if c >= o else 'green' for c, o in zip(df['Close'], df['Open'])]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors, name='Vol'), row=2, col=1)
    
    fig.update_layout(height=450, xaxis_rangeslider_visible=False, title=title, margin=dict(l=20, r=20, t=40, b=20))
    st.plotly_chart(fig, use_container_width=True, key=key)

# --- 5. AI Dashboard ---
def render_ai_battle_dashboard(analysis):
    st.subheader("🤖 AI 戰情分析")
    st.info(analysis.get('report', '資料不足，無法分析'))

# --- 6. Back Button ---
def render_back_button(func):
    if st.button("⬅️ 返回", use_container_width=True): func()

# --- 7. Term Card ---
def render_term_card(title, content):
    with st.container(border=True):
        st.subheader(title)
        st.markdown(content)

# --- 8. K-Line Pattern ---
def render_kline_pattern_card(name, data):
    with st.expander(f"📌 {name}", expanded=False):
        st.markdown(data.get('morphology', ''))
        st.info(data.get('action', ''))
        
# --- 9. Scan Card ---
def render_detailed_card(code, name, price, df, src, key_prefix, rank, strategy_info, score, w_prob):
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([1, 2, 4, 1])
        with c1: st.markdown(f"### #{rank}")
        with c2: 
            st.markdown(f"**{code}**")
            st.caption(f"${price:.2f}")
        with c3: st.info(strategy_info)
        with c4: 
            if st.button("查看", key=f"btn_{key_prefix}_{code}"): return True
    return False
