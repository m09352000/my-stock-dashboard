# ui_components.py
# V121: 視覺元件庫 (全功能修復版 - 含五檔報價、掃描卡片、K線教學)

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import ui_styles
import logic_database as db
import pandas as pd # 確保引入 pandas

# --- 1. 頁面標頭 ---
def render_header(title, show_monitor=False, is_live=False, time_str=""):
    ui_styles.inject_custom_css()
    c1, c2 = st.columns([3, 1])
    if title: c1.title(title)
    if is_live:
        c2.markdown(f"<div style='text-align:right;padding-top:10px;'><span class='live-tag'>● LIVE 連線中</span><br><span style='font-size:0.8rem;color:#888'>最後更新: {time_str}</span></div>", unsafe_allow_html=True)
    st.markdown("<hr class='compact'>", unsafe_allow_html=True)

# --- 2. 基本面看板 (含自動隱藏空介紹) ---
def render_fundamental_panel(stock_info):
    name = stock_info.get('name', '未知個股')
    code = stock_info.get('code', '')
    summary_raw = stock_info.get('longBusinessSummary', '')
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
            # 只有當真的有內容時，才顯示 Expander
            if summary_zh and len(str(summary_zh)) > 5:
                with st.expander("📖 查看業務介紹 (中文)", expanded=True): 
                    st.write(summary_zh)
        with c_info:
            eps_val = f"{eps}" if eps != 0 else "-"
            pe_val = f"{pe:.2f}" if pe != 0 else "-"
            st.metric("EPS (每股盈餘)", eps_val)
            st.metric("P/E (本益比)", pe_val)

# --- 3. 數據儀表板 (含五檔報價) ---
def render_metrics_dashboard(curr, chg, pct, high, low, amp, mf, vol, vy, va, vs, fh, tr, ba, cs, rt_pack, unit="張", code=""):
    with st.container():
        # 第一列：主要價格
        c1, c2, c3, c4 = st.columns(4)
        val_color = "#FF2B2B" if chg > 0 else "#00E050" if chg < 0 else "white"
        c1.markdown(f"<div style='font-size:0.9rem; color:#aaa'>成交價</div><div style='font-size:2.5rem; font-weight:bold; color:{val_color};'>{curr:.2f}</div><div style='font-size:1.2rem; color:{val_color}'>{chg:+.2f} ({pct:+.2f}%)</div>", unsafe_allow_html=True)
        c2.metric("最高", f"{high:.2f}")
        c3.metric("最低", f"{low:.2f}")
        vol_str = f"{int(vol):,}"
        if unit == "股" and vol > 1000000: vol_str = f"{vol/1000000:.2f}M"
        c4.metric("成交量", f"{vol_str} {unit}")
        
        # 第二列：進階量能
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

        # 第三列：五檔報價 (MIS 獨家功能)
        b_p = rt_pack.get('bid_price', [])
        b_v = rt_pack.get('bid_volume', [])
        a_p = rt_pack.get('ask_price', [])
        a_v = rt_pack.get('ask_volume', [])

        if b_p and a_p:
            st.markdown("<hr class='compact'>", unsafe_allow_html=True)
            st.caption("📊 五檔委託即時明細 (資料來源: 臺灣證券交易所 MIS)")
            col_buy, col_mid, col_sell = st.columns([1, 0.1, 1])
            with col_buy:
                st.markdown("<h5 style='text-align:center; color:#FF2B2B'>🔴 委買 (Bid)</h5>", unsafe_allow_html=True)
                for p, v in zip(b_p, b_v):
                    st.markdown(f"<div style='display:flex; justify-content:space-between; border-bottom:1px solid #333; padding:2px;'><span style='color:#FF2B2B; font-weight:bold;'>{p}</span><span style='color:#EEE;'>{v} 張</span></div>", unsafe_allow_html=True)
            with col_sell:
                st.markdown("<h5 style='text-align:center; color:#00E050'>🟢 委賣 (Ask)</h5>", unsafe_allow_html=True)
                for p, v in zip(a_p, a_v):
                    st.markdown(f"<div style='display:flex; justify-content:space-between; border-bottom:1px solid #333; padding:2px;'><span style='color:#00E050; font-weight:bold;'>{p}</span><span style='color:#EEE;'>{v} 張</span></div>", unsafe_allow_html=True)

# --- 4. K線圖 ---
def render_chart(df, title, color_settings, key=None):
    if key is None: key = "chart_default"
    if len(df) > 5: df['MA5'] = df['Close'].rolling(5).mean()
    if len(df) > 20: df['MA20'] = df['Close'].rolling(20).mean()
        
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

# --- 5. AI 診斷室 ---
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
    st.table(pd.DataFrame({
        "關卡": ["壓力 (布林上)", "現價", "建議進場", "支撐 (布林下)"],
        "價格": [f"{analysis['pressure']:.2f}", f"{analysis['close']:.2f}", f"{analysis['suggest_price']:.2f}", f"{analysis['support']:.2f}"]
    }))

# --- 6. 返回按鈕 ---
def render_back_button(callback_func):
    st.markdown("<hr class='compact'>", unsafe_allow_html=True)
    if st.button("⬅️ 返回搜尋 / 列表", use_container_width=True): callback_func()

# --- 7. 名詞解釋卡片 ---
def render_term_card(title, content):
    with st.container(border=True):
        st.subheader(f"📌 {title}"); st.markdown(content)

# --- 8. (修復遺失) 掃描結果列表卡片 ---
def render_detailed_card(code, name, price, df, src, key_prefix, rank, strategy_info, score, w_prob):
    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns([1, 2, 3, 2, 1])
        
        # 排名
        with c1:
            if rank <= 3:
                st.markdown(f"<div class='rank-badge rank-{rank}'>{rank}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='rank-badge rank-norm'>{rank}</div>", unsafe_allow_html=True)
        
        # 股號股名
        with c2:
            st.markdown(f"### {name}")
            st.caption(f"{code} | ${price:.2f}")
            if src == "github_voidful": st.caption("來源: GitHub")
        
        # 策略理由
        with c3:
            st.info(f"🎯 {strategy_info}")

        # AI 分數
        with c4:
            color = "#FF2B2B" if score > 70 else "#FFA500" if score > 50 else "#00E050"
            st.markdown(f"<div style='text-align:center'><span style='font-size:0.8rem'>AI 評分</span><br><span style='font-size:1.5rem;font-weight:bold;color:{color}'>{int(score)}</span></div>", unsafe_allow_html=True)
            st.progress(min(score/100, 1.0), text=f"勝率 {w_prob}%")
        
        # 按鈕
        with c5:
            # 垂直置中
            st.write("")
            if st.button("查看", key=f"{key_prefix}_btn_{code}", use_container_width=True):
                return True
    return False

# --- 9. (修復遺失) K線教學卡片 ---
def render_kline_pattern_card(name, data):
    with st.expander(f"📌 {name}", expanded=False):
        c1, c2 = st.columns([1, 1])
        with c1:
            st.markdown(f"**【型態】**\n{data.get('morphology', '')}")
            st.markdown(f"**【心理】**\n{data.get('psychology', '')}")
            st.success(f"**【SOP】** {data.get('action', '')}")
        with c2:
            # 繪製迷你教學圖表
            if 'data' in data:
                rows = []
                # data['data'] 是列表，轉換成 DF
                for i, d in enumerate(data['data']):
                    # 假設格式 [Open, High, Low, Close]
                    rows.append({'Open': d[0], 'High': d[1], 'Low': d[2], 'Close': d[3], 'Volume': 100})
                df_k = pd.DataFrame(rows)
                
                fig = go.Figure(data=[go.Candlestick(x=df_k.index,
                        open=df_k['Open'], high=df_k['High'],
                        low=df_k['Low'], close=df_k['Close'],
                        increasing_line_color='#FF2B2B', decreasing_line_color='#00E050')])
                fig.update_layout(height=200, margin=dict(l=0,r=0,t=0,b=0), xaxis_visible=False, yaxis_visible=False)
                st.plotly_chart(fig, use_container_width=True, key=f"kline_demo_{name}")
