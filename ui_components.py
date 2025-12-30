# ui_components.py
# V119: 視覺元件庫 (介面隱藏空內容優化)

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import ui_styles
import logic_database as db

def render_header(title, show_monitor=False, is_live=False, time_str=""):
    ui_styles.inject_custom_css()
    c1, c2 = st.columns([3, 1])
    if title: c1.title(title)
    if is_live:
        c2.markdown(f"<div style='text-align:right;padding-top:10px;'><span class='live-tag'>● LIVE 連線中</span><br><span style='font-size:0.8rem;color:#888'>最後更新: {time_str}</span></div>", unsafe_allow_html=True)
    st.markdown("<hr class='compact'>", unsafe_allow_html=True)

def render_fundamental_panel(stock_info):
    name = stock_info.get('name', '未知個股')
    code = stock_info.get('code', '')
    summary_raw = stock_info.get('longBusinessSummary', '')
    
    # 進行翻譯
    summary_zh = db.translate_text(summary_raw)
    
    sector = stock_info.get('sector', '-')
    industry = stock_info.get('industry', '-')
    eps = stock_info.get('trailingEps', 0.0)
    pe = stock_info.get('trailingPE', 0.0)
    
    with st.container(border=True):
        c_main, c_info = st.columns([3, 1])
        with c_main:
            st.markdown(f"### 🏢 {name} ({code}) 企業概況")
            st.caption(f"板塊: {sector} | 產業: {industry}")
            
            # --- V119 修改：內容檢測 ---
            # 只有當真的有內容時，才顯示 Expander
            # 這樣當 logic_database 回傳空字串時，這裡就會自動隱藏，保持版面乾淨
            if summary_zh and len(str(summary_zh)) > 5:
                with st.expander("📖 查看業務介紹 (中文)", expanded=True): 
                    st.write(summary_zh)
            # -------------------------

        with c_info:
            eps_val = f"{eps}" if eps != 0 else "-"
            pe_val = f"{pe:.2f}" if pe != 0 else "-"
            st.metric("EPS (每股盈餘)", eps_val)
            st.metric("P/E (本益比)", pe_val)

def render_metrics_dashboard(curr, chg, pct, high, low, amp, mf, vol, vy, va, vs, fh, tr, ba, cs, rt, unit="張", code=""):
    with st.container():
        c1, c2, c3, c4 = st.columns(4)
        val_color = "#FF2B2B" if chg > 0 else "#00E050" if chg < 0 else "white"
        
        c1.markdown(f"<div style='font-size:0.9rem; color:#aaa'>成交價</div><div style='font-size:2.5rem; font-weight:bold; color:{val_color};'>{curr:.2f}</div><div style='font-size:1.2rem; color:{val_color}'>{chg:+.2f} ({pct:+.2f}%)</div>", unsafe_allow_html=True)
        
        c2.metric("最高", f"{high:.2f}")
        c3.metric("最低", f"{low:.2f}")
        
        vol_str = f"{int(vol):,}"
        if unit == "股" and vol > 1000000: vol_str = f"{vol/1000000:.2f}M"
        c4.metric("成交量", f"{vol_str} {unit}")
        
        st.markdown("<hr class='compact'>", unsafe_allow_html=True)
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("振幅", f"{amp:.2f}%")
        d2.metric("量能狀態", vs)
        va_str = f"{int(va):,}"
        if unit == "張": va_str = f"{int(va/1000):,}"
        d3.metric("五日均量", f"{va_str}")
        vy_str = f"{int(vy):,}"
        if unit == "張": vy_str = f"{int(vy/1000):,}"
        d4.metric("昨日量", f"{vy_str}")

def render_chart(df, title, color_settings, key=None):
    if key is None: key = "chart_default"
    # 防呆
    if len(df) > 5:
        df['MA5'] = df['Close'].rolling(5).mean()
    if len(df) > 20:
        df['MA20'] = df['Close'].rolling(20).mean()
        
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='K線', increasing_line_color='#FF2B2B', decreasing_line_color='#00E050'), row=1, col=1)
    
    if 'MA5' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='#FF00FF', width=1), name='5MA'), row=1, col=1)
    if 'MA20' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='#FFA500', width=1), name='20MA'), row=1, col=1)
        
    colors = ['#FF2B2B' if c >= o else '#00E050' for c, o in zip(df['Close'], df['Open'])]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors, name='成交量'), row=2, col=1)
    
    fig.update_layout(height=400, xaxis_rangeslider_visible=False, title=dict(text=title, font=dict(size=20)), margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig, use_container_width=True, key=key)

def render_ai_battle_dashboard(analysis):
    st.markdown("---")
    st.subheader("🤖 AI 戰情診斷室")
    c1, c2 = st.columns(2)
    with c1:
        w_prob = analysis.get('weekly_prob', 50)
        w_color = "#FF2B2B" if w_prob > 70 else "#FFA500"
        st.markdown(f"<div class='battle-card'><div class='battle-title'>📅 本週獲利機率 (短線)</div><div style='font-size: 2.5rem; color: {w_color}; font-weight: bold;'>{w_prob}%</div></div>", unsafe_allow_html=True)
    with c2:
        m_prob = analysis.get('monthly_prob', 50)
        m_color = "#FF2B2B" if m_prob > 70 else "#FFA500"
        st.markdown(f"<div class='battle-card'><div class='battle-title'>🌕 本月獲利機率 (波段)</div><div style='font-size: 2.5rem; color: {m_color}; font-weight: bold;'>{m_prob}%</div></div>", unsafe_allow_html=True)
    st.markdown('<div class="battle-card"><div class="battle-title">📝 AI 深度技術分析報告</div>', unsafe_allow_html=True)
    st.markdown(f"<div class='report-text'>{analysis.get('report', '分析中...')}</div>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown("#### 🛡️ 關鍵價位攻防")
    import pandas as pd
    st.table(pd.DataFrame({
        "關卡": ["壓力 (布林上)", "現價", "建議進場", "支撐 (布林下)"],
        "價格": [f"{analysis['pressure']:.2f}", f"{analysis['close']:.2f}", f"{analysis['suggest_price']:.2f}", f"{analysis['support']:.2f}"]
    }))

def render_back_button(callback_func):
    st.markdown("<hr class='compact'>", unsafe_allow_html=True)
    if st.button("⬅️ 返回搜尋 / 列表", use_container_width=True): callback_func()

def render_term_card(title, content):
    with st.container(border=True):
        st.subheader(f"📌 {title}"); st.markdown(content)
