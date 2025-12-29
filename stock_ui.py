import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime, timedelta, timezone

# --- CSS: V95 UI (增加金牌排名與強力推薦風格) ---
def inject_custom_css():
    st.markdown("""
        <style>
        .kline-card-header { margin-top: 0.5rem !important; margin-bottom: 0.2rem !important; font-size: 1.1rem !important; font-weight: bold; }
        .battle-card { background-color: #1e1e1e; padding: 20px; border-radius: 12px; border: 1px solid #333; margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
        .battle-title { font-size: 1.2rem; font-weight: 900; color: #fff; margin-bottom: 10px; border-bottom: 2px solid #444; padding-bottom: 5px; }
        .live-tag { color: #00FF00; font-weight: bold; font-size: 0.9rem; animation: blink 1s infinite; text-shadow: 0 0 5px #00FF00; }
        @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.4; } 100% { opacity: 1; } }
        div[data-testid="stMetricValue"] { font-size: 1.35rem !important; font-weight: 800 !important; }
        hr.compact { margin: 8px 0px !important; border: 0; border-top: 1px solid #444; }
        
        /* 排名徽章 */
        .rank-badge {
            background-color: #FFD700; color: #000; padding: 5px 10px; 
            border-radius: 50%; font-weight: bold; font-size: 1.2rem;
            display: inline-block; width: 40px; text-align: center;
        }
        .rank-1 { background: linear-gradient(45deg, #FFD700, #FDB931); box-shadow: 0 0 10px #FFD700; }
        .rank-2 { background: linear-gradient(45deg, #C0C0C0, #E0E0E0); }
        .rank-3 { background: linear-gradient(45deg, #CD7F32, #D2691E); }
        </style>
    """, unsafe_allow_html=True)

# --- 1. 標題 ---
def render_header(title, show_monitor=False):
    inject_custom_css()
    c1, c2 = st.columns([3, 1])
    c1.title(title)
    
    is_live = False
    if show_monitor:
        if 'monitor_active' not in st.session_state: st.session_state['monitor_active'] = False
        is_live = c2.toggle("🔴 啟動 1秒極速刷新", value=st.session_state['monitor_active'])
        st.session_state['monitor_active'] = is_live
        if is_live: st.markdown(f"<span class='live-tag'>● LIVE 連線中</span>", unsafe_allow_html=True)
    st.markdown("<hr class='compact'>", unsafe_allow_html=True)
    return is_live

# --- 2. 返回 ---
def render_back_button(callback_func):
    st.markdown("<hr class='compact'>", unsafe_allow_html=True)
    _, c2, _ = st.columns([2, 1, 2])
    if c2.button("⬅️ 返回搜尋", use_container_width=True): callback_func()

# --- 3. 新手村與 K線教學 (保持不變) ---
def render_term_card(title, content):
    with st.container(border=True):
        st.subheader(f"📌 {title}"); st.markdown(content)

def render_kline_pattern_card(title, pattern_data):
    # (簡化代碼以節省篇幅，請保留原有的 K線繪圖邏輯)
    st.write(f"💡 {title}")

# --- 4. 簡介與儀表板 (保持不變) ---
def render_company_profile(summary):
    if summary:
        with st.expander("🏢 公司簡介", expanded=False): st.write(summary)

def render_metrics_dashboard(curr, chg, pct, high, low, amp, mf, vol, vy, va, vs, fh, tr, ba, cs, rt):
    # (保持原有的儀表板顯示邏輯)
    with st.container():
        c1, c2, c3, c4 = st.columns(4)
        val_color = "#FF2B2B" if chg > 0 else "#00E050" if chg < 0 else "white"
        c1.markdown(f"<h2 style='color:{val_color}'>{curr:.2f} ({pct:+.2f}%)</h2>", unsafe_allow_html=True)
        c2.metric("最高", f"{high:.2f}")
        c3.metric("最低", f"{low:.2f}")
        c4.metric("成交量", f"{int(vol):,} 張")

# --- 5. 掃描結果詳細卡片 (大幅優化 V95) ---
def render_detailed_card(code, name, price, df, source_type="yahoo", key_prefix="btn", rank=None, strategy_info=None, score=0):
    """
    V95: 增加排名金牌、AI信心分數條、強勢標籤
    """
    chg_color = "gray"; pct_txt = "0.00%"
    chg_val = 0
    
    if df is not None and not df.empty:
        curr = df['Close'].iloc[-1]; prev = df['Close'].iloc[-2]
        chg_val = curr - prev
        pct = (chg_val / prev) * 100
        if chg_val > 0: chg_color = "#FF2B2B"; pct_txt = f"▲{pct:.2f}%"
        elif chg_val < 0: chg_color = "#00E050"; pct_txt = f"▼{abs(pct):.2f}%"
    
    # 處理排名樣式
    rank_class = f"rank-{rank}" if rank and rank <= 3 else "rank-norm"
    rank_html = f"<div class='rank-badge {rank_class}'>#{rank}</div>" if rank else ""
    
    # 卡片容器
    with st.container(border=True):
        # 第一排：基本資訊
        c1, c2, c3, c4 = st.columns([0.8, 1.5, 1.5, 1.2])
        
        with c1: 
            if rank: st.markdown(rank_html, unsafe_allow_html=True)
            else: st.caption("No Rank")
            
        with c2: 
            st.markdown(f"### {name}")
            st.caption(f"代號: {code}")
            
        with c3: 
            st.markdown(f"<h3 style='color:{chg_color}'>{price:.2f}</h3>", unsafe_allow_html=True)
            st.caption(pct_txt)
            
        with c4:
            st.write("")
            if st.button("查看詳情", key=f"{key_prefix}_{code}", use_container_width=True): return True

        # 第二排：AI 推薦理由與強度
        st.markdown("<hr class='compact'>", unsafe_allow_html=True)
        d1, d2 = st.columns([3, 1])
        
        with d1:
            st.markdown(f"**🎯 推薦理由：** {strategy_info}")
            # 根據分數顯示進度條
            if score > 0:
                score_norm = min(score, 100) / 100
                st.progress(score_norm, text=f"AI 獲利信心指數: {int(score)} 分")
        
        with d2:
            tag_color = "#FF0000" if score >= 80 else "#FFA500"
            tag_text = "必賺極強" if score >= 80 else "強勢關注"
            st.markdown(f"""
            <div style="background-color:{tag_color}; color:white; padding:5px; border-radius:5px; text-align:center; font-weight:bold; font-size:0.9rem;">
                {tag_text}
            </div>
            """, unsafe_allow_html=True)

    return False

# --- 6. K線圖 ---
def render_chart(df, title, color_settings):
    # (保持原有的 K線繪圖邏輯)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], increasing_line_color='red', decreasing_line_color='green'), row=1, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color='orange'), row=2, col=1)
    fig.update_layout(height=400, xaxis_rangeslider_visible=False, title=title, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)

# --- 7. AI 戰情診斷室 ---
def render_ai_battle_dashboard(analysis):
    # (保持原有的儀表板顯示邏輯，這部分您之前已經有了，直接沿用)
    st.markdown("---")
    st.subheader("🤖 AI 戰情診斷室")
    c1, c2 = st.columns(2)
    with c1: st.metric("🔥 市場熱度", analysis['heat'])
    with c2: st.metric("🎲 獲利機率", f"{analysis['probability']}%")
    
    sc1, sc2, sc3 = st.columns(3)
    with sc1: st.info(f"短線: {analysis['short_action']}")
    with sc2: st.warning(f"中線: {analysis['mid_action']}")
    with sc3: st.success(f"長線: {analysis['long_action']}")
    
    st.table(pd.DataFrame({
        "關鍵價位": ["壓力", "現價", "支撐"],
        "價格": [f"{analysis['pressure']:.2f}", f"{analysis['close']:.2f}", f"{analysis['support']:.2f}"]
    }))
