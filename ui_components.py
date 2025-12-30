# ui_components.py
# V112: 介面美化 + 基本面

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import ui_styles

def render_header(title, show_monitor=False, is_live=False, time_str=""):
    ui_styles.inject_custom_css()
    c1, c2 = st.columns([3, 1])
    c1.title(title)
    if is_live:
        c2.markdown(f"<div style='text-align:right;padding-top:10px;'><span class='live-tag'>● LIVE 連線中</span><br><span style='font-size:0.8rem;color:#888'>{time_str}</span></div>", unsafe_allow_html=True)
    st.markdown("<hr class='compact'>", unsafe_allow_html=True)

def render_back_button(callback_func):
    st.markdown("<hr class='compact'>", unsafe_allow_html=True)
    if st.button("⬅️ 返回搜尋 / 列表", use_container_width=True): callback_func()

def render_term_card(title, content):
    with st.container(border=True):
        st.subheader(f"📌 {title}"); st.markdown(content)

def render_kline_pattern_card(title, pattern_data):
    morph = pattern_data.get('morphology', '')
    psycho = pattern_data.get('psychology', '')
    action = pattern_data.get('action', '')
    raw_data = pattern_data.get('data', [])
    with st.container(border=True):
        c1, c2 = st.columns([1, 2.5]) 
        with c1:
            idx = list(range(len(raw_data)))
            opens = [x[0] for x in raw_data]; highs = [x[1] for x in raw_data]
            lows = [x[2] for x in raw_data]; closes = [x[3] for x in raw_data]
            fig = go.Figure(data=[go.Candlestick(x=idx, open=opens, high=highs, low=lows, close=closes, increasing_line_color='#FF2B2B', decreasing_line_color='#00E050')])
            fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=150, xaxis=dict(visible=False), yaxis=dict(visible=False), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        with c2:
            st.markdown(f"### 💡 {title}")
            st.markdown(f"**【形態特徵】** {morph}")
            st.markdown(f"**【市場心理】**\n{psycho}")
            st.markdown(f"**【操作 SOP】**\n👉 {action}")

def render_fundamental_panel(stock_info):
    summary = stock_info.get('longBusinessSummary', '暫無資料')
    sector = stock_info.get('sector', 'N/A')
    industry = stock_info.get('industry', 'N/A')
    eps = stock_info.get('trailingEps', 0.0)
    pe = stock_info.get('trailingPE', 0.0)
    
    with st.container(border=True):
        c_main, c_info = st.columns([3, 1])
        with c_main:
            st.caption(f"板塊: {sector} | 產業: {industry}")
            st.markdown(f"#### 🏢 企業概況")
            with st.expander("📖 查看業務介紹 (已自動翻譯)", expanded=False):
                st.write(summary)
        with c_info:
            st.metric("EPS (每股盈餘)", f"{eps}")
            st.metric("P/E (本益比)", f"{pe:.2f}" if pe else "-")

def render_metrics_dashboard(curr, chg, pct, high, low, amp, mf, vol, vy, va, vs, fh, tr, ba, cs, rt, unit="張", code=""):
    with st.container():
        c1, c2, c3, c4 = st.columns(4)
        val_color = "#FF2B2B" if chg > 0 else "#00E050" if chg < 0 else "white"
        c1.markdown(f"<div style='font-size:0.9rem; color:#aaa'>成交價</div><div style='font-size:2.2rem; font-weight:bold; color:{val_color}; text-shadow: 0 0 10px rgba(255,255,255,0.1);'>{curr:.2f}</div><div style='font-size:1.1rem; color:{val_color}'>{chg:+.2f} ({pct:+.2f}%)</div>", unsafe_allow_html=True)
        c2.metric("最高", f"{high:.2f}"); c3.metric("最低", f"{low:.2f}")
        vol_str = f"{int(vol):,}"
        if unit == "股" and vol > 1000000: vol_str = f"{vol/1000000:.2f}M"
        c4.metric("成交量", f"{vol_str} {unit}")
        st.markdown("<hr class='compact'>", unsafe_allow_html=True)
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("振幅", f"{amp:.2f}%"); d2.metric("量能狀態", vs)
        va_str = f"{int(va):,}"
        if unit == "張": va_str = f"{int(va/1000):,}"
        elif va > 1000000: va_str = f"{va/1000000:.2f}M"
        d3.metric("五日均量", f"{va_str}")
        vy_str = f"{int(vy):,}"
        if unit == "張": vy_str = f"{int(vy/1000):,}"
        elif vy > 1000000: vy_str = f"{vy/1000000:.2f}M"
        d4.metric("昨日量", f"{vy_str}")

def render_detailed_card(code, name, price, df, source_type="yahoo", key_prefix="btn", rank=None, strategy_info=None, score=0, w_prob=50):
    chg_color = "gray"; pct_txt = "0.00%"
    if df is not None and not df.empty:
        curr = df['Close'].iloc[-1]; prev = df['Close'].iloc[-2]
        chg_val = curr - prev; pct = (chg_val / prev) * 100
        if chg_val > 0: chg_color = "#FF2B2B"; pct_txt = f"▲{pct:.2f}%"
        elif chg_val < 0: chg_color = "#00E050"; pct_txt = f"▼{abs(pct):.2f}%"
    
    rank_html = f"<div class='rank-badge rank-{rank if rank and rank<=3 else 'norm'}'>{rank if rank else '-'}</div>"
    
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([0.6, 2.0, 1.2, 1.0])
        with c1: st.markdown(rank_html, unsafe_allow_html=True)
        with c2: st.markdown(f"### {name}"); st.caption(f"代號: {code}")
        with c3: st.markdown(f"<div style='text-align:right; font-weight:bold; font-size:1.2rem; color:{chg_color}'>{price:.2f}<br><span style='font-size:0.9rem'>{pct_txt}</span></div>", unsafe_allow_html=True)
        with c4:
            st.write(""); 
            if st.button("查看", key=f"{key_prefix}_{code}", use_container_width=True): return True

        st.markdown("<hr class='compact'>", unsafe_allow_html=True)
        d1, d2 = st.columns([3, 1])
        with d1:
            st.markdown(f"**🎯 理由：** {strategy_info}")
            st.progress(w_prob/100, text=f"本週預估勝率: {w_prob}%")
        with d2:
            tag_color = "#FF0000" if score >= 80 else "#FFA500" if score >= 60 else "#888"
            tag_text = "極強" if score >= 80 else "強勢" if score >= 60 else "普通"
            st.markdown(f"<div class='status-tag' style='background-color:{tag_color}; color:white; width:100%; margin-top:10px;'>{tag_text}</div>", unsafe_allow_html=True)
    return False

def render_chart(df, title, color_settings, key=None):
    df['MA5'] = df['Close'].rolling(5).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='K線', increasing_line_color='#FF2B2B', decreasing_line_color='#00E050'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='#FF00FF', width=1), name='5日線'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='#FFA500', width=1), name='20日線'), row=1, col=1)
    colors = ['#FF2B2B' if c >= o else '#00E050' for c, o in zip(df['Close'], df['Open'])]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors, name='成交量'), row=2, col=1)
    fig.update_layout(height=400, xaxis_rangeslider_visible=False, title=dict(text=title, font=dict(size=20)), margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig, use_container_width=True, key=key)

def render_company_profile(summary):
    pass # 為了相容舊版呼叫保留空函式，實際邏輯已移至 render_fundamental_panel

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
