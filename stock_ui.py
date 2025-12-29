import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime, timedelta, timezone

# --- CSS: V96 UI (完美排名樣式修正版) ---
def inject_custom_css():
    st.markdown("""
        <style>
        /* 全局字體優化 */
        .stApp { font-family: "Microsoft JhengHei", sans-serif; }
        
        /* 戰情室卡片風格 */
        .battle-card { 
            background-color: #1e1e1e; 
            padding: 20px; 
            border-radius: 12px; 
            border: 1px solid #333; 
            margin-bottom: 15px; 
            box-shadow: 0 4px 6px rgba(0,0,0,0.3); 
        }
        .battle-title { 
            font-size: 1.2rem; 
            font-weight: 900; 
            color: #fff; 
            margin-bottom: 10px; 
            border-bottom: 2px solid #444; 
            padding-bottom: 5px; 
        }
        
        /* 直播標籤動畫 */
        .live-tag { 
            color: #00FF00; 
            font-weight: bold; 
            font-size: 0.9rem; 
            animation: blink 1s infinite; 
            text-shadow: 0 0 5px #00FF00; 
        }
        @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.4; } 100% { opacity: 1; } }
        
        /* 指標數字加大 */
        div[data-testid="stMetricValue"] { font-size: 1.35rem !important; font-weight: 800 !important; }
        
        /* 分隔線微調 */
        hr.compact { margin: 8px 0px !important; border: 0; border-top: 1px solid #444; }
        
        /* 排名徽章 (Flexbox 完美置中) */
        .rank-badge {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 45px;
            height: 45px;
            border-radius: 50%;
            font-weight: 900;
            font-size: 1.4rem;
            color: #000;
            margin: auto;
            box-shadow: 0 2px 5px rgba(0,0,0,0.5);
        }
        .rank-1 { background: linear-gradient(135deg, #FFD700, #FDB931); border: 2px solid #FFF; box-shadow: 0 0 15px #FFD700; }
        .rank-2 { background: linear-gradient(135deg, #E0E0E0, #B0B0B0); border: 2px solid #FFF; }
        .rank-3 { background: linear-gradient(135deg, #CD7F32, #A0522D); border: 2px solid #FFF; }
        .rank-norm { background-color: #333; color: #EEE; font-size: 1rem; width: 35px; height: 35px; }
        
        /* 標籤樣式 */
        .status-tag {
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: bold;
            font-size: 0.85rem;
            text-align: center;
            display: inline-block;
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
    if c2.button("⬅️ 返回搜尋 / 列表", use_container_width=True): callback_func()

# --- 3. 新手村卡片 ---
def render_term_card(title, content):
    with st.container(border=True):
        st.subheader(f"📌 {title}")
        st.markdown("<hr class='compact'>", unsafe_allow_html=True)
        st.markdown(content)

# --- K線型態繪圖 ---
def render_kline_pattern_card(title, pattern_data):
    morph = pattern_data.get('morphology', '無資料')
    psycho = pattern_data.get('psychology', '無資料')
    action_html = pattern_data.get('action', '無資料')
    raw_data = pattern_data.get('data', [])
    with st.container(border=True):
        c1, c2 = st.columns([1, 2.5]) 
        with c1:
            idx = list(range(len(raw_data)))
            opens = [x[0] for x in raw_data]; highs = [x[1] for x in raw_data]
            lows = [x[2] for x in raw_data]; closes = [x[3] for x in raw_data]
            fig = go.Figure(data=[go.Candlestick(x=idx, open=opens, high=highs, low=lows, close=closes, increasing_line_color='#FF2B2B', decreasing_line_color='#00E050')])
            fig.update_layout(margin=dict(l=2, r=2, t=10, b=2), height=180, xaxis=dict(visible=False), yaxis=dict(visible=False), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        with c2:
            st.markdown(f"### 💡 {title}")
            st.caption(morph)
            st.markdown(f"<div class='action-list'>{action_html}</div>", unsafe_allow_html=True)

# --- 4. 公司簡介 ---
def render_company_profile(summary):
    if summary:
        with st.expander("🏢 公司簡介", expanded=False): st.write(summary)

# --- 5. 儀表板 ---
def render_metrics_dashboard(curr, chg, pct, high, low, amp, mf, vol, vy, va, vs, fh, tr, ba, cs, rt):
    with st.container():
        c1, c2, c3, c4 = st.columns(4)
        val_color = "#FF2B2B" if chg > 0 else "#00E050" if chg < 0 else "white"
        c1.markdown(f"<div style='font-size:0.9rem; color:#aaa'>成交價</div><div style='font-size:2rem; font-weight:bold; color:{val_color}'>{curr:.2f} <span style='font-size:1rem'>({pct:+.2f}%)</span></div>", unsafe_allow_html=True)
        c2.metric("最高", f"{high:.2f}")
        c3.metric("最低", f"{low:.2f}")
        c4.metric("成交量", f"{int(vol):,} 張")
        
        st.markdown("<hr class='compact'>", unsafe_allow_html=True)
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("振幅", f"{amp:.2f}%")
        d2.metric("量能狀態", vs)
        d3.metric("五日均量", f"{int(va/1000)} 張")
        d4.metric("外資持股", f"{fh:.1f}%")

# --- 6. 掃描結果詳細卡片 (V96 修復排版) ---
def render_detailed_card(code, name, price, df, source_type="yahoo", key_prefix="btn", rank=None, strategy_info=None, score=0):
    chg_color = "gray"; pct_txt = "0.00%"
    if df is not None and not df.empty:
        curr = df['Close'].iloc[-1]; prev = df['Close'].iloc[-2]
        chg_val = curr - prev
        pct = (chg_val / prev) * 100
        if chg_val > 0: chg_color = "#FF2B2B"; pct_txt = f"▲{pct:.2f}%"
        elif chg_val < 0: chg_color = "#00E050"; pct_txt = f"▼{abs(pct):.2f}%"
    
    # 排名徽章 HTML
    rank_class = f"rank-{rank}" if rank and rank <= 3 else "rank-norm"
    rank_content = f"{rank}" if rank else "-"
    rank_html = f"<div class='rank-badge {rank_class}'>{rank_content}</div>"
    
    # 卡片容器
    with st.container(border=True):
        # 使用更寬的比例給標題，避免擠壓
        c1, c2, c3, c4 = st.columns([0.6, 2.0, 1.2, 1.0])
        
        with c1: 
            st.markdown(rank_html, unsafe_allow_html=True)
            
        with c2: 
            st.markdown(f"### {name}")
            st.caption(f"代號: {code}")
            
        with c3: 
            st.markdown(f"<div style='text-align:right; font-weight:bold; font-size:1.2rem; color:{chg_color}'>{price:.2f}<br><span style='font-size:0.9rem'>{pct_txt}</span></div>", unsafe_allow_html=True)
            
        with c4:
            st.write("") # Spacer
            if st.button("查看", key=f"{key_prefix}_{code}", use_container_width=True): return True

        # 第二排：策略與信心
        st.markdown("<hr class='compact'>", unsafe_allow_html=True)
        d1, d2 = st.columns([3, 1])
        
        with d1:
            st.markdown(f"**🎯 理由：** {strategy_info}")
            if score > 0:
                st.progress(min(score, 100)/100, text=f"AI 獲利信心: {int(score)} 分")
        
        with d2:
            tag_color = "#FF0000" if score >= 80 else "#FFA500" if score >= 60 else "#888"
            tag_text = "必賺極強" if score >= 80 else "強勢關注" if score >= 60 else "普通"
            st.markdown(f"<div class='status-tag' style='background-color:{tag_color}; color:white; width:100%; margin-top:10px;'>{tag_text}</div>", unsafe_allow_html=True)

    return False

# --- 7. K線圖 ---
def render_chart(df, title, color_settings):
    df['MA5'] = df['Close'].rolling(5).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
    
    # K線
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], 
                                 name='K線', increasing_line_color='#FF2B2B', decreasing_line_color='#00E050'), row=1, col=1)
    # 均線
    fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='#FF00FF', width=1), name='5日線'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='#FFA500', width=1), name='20日線'), row=1, col=1)
    
    # 成交量
    colors = ['#FF2B2B' if c >= o else '#00E050' for c, o in zip(df['Close'], df['Open'])]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors, name='成交量'), row=2, col=1)
    
    fig.update_layout(height=450, xaxis_rangeslider_visible=False, title=title, 
                      margin=dict(l=10, r=10, t=30, b=10), showlegend=True, 
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig, use_container_width=True)

# --- 8. AI 戰情診斷室 ---
def render_ai_battle_dashboard(analysis):
    st.markdown("---")
    st.subheader("🤖 AI 戰情診斷室")
    
    c1, c2 = st.columns(2)
    with c1: 
        st.markdown(f"""
        <div class="battle-card">
            <div class="battle-title">🔥 市場熱度</div>
            <div style="font-size: 2rem; color: {analysis['heat_color']}; font-weight: bold;">{analysis['heat']}</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        prob_color = "#FF2B2B" if analysis['probability'] > 60 else "#FFA500"
        st.markdown(f"""
        <div class="battle-card">
            <div class="battle-title">🎲 獲利機率</div>
            <div style="font-size: 2rem; color: {prob_color}; font-weight: bold;">{analysis['probability']:.1f}%</div>
        </div>
        """, unsafe_allow_html=True)
    
    sc1, sc2, sc3 = st.columns(3)
    with sc1: 
        st.info(f"⚡ 短線: {analysis['short_action']}")
        st.caption(f"目標: {analysis['short_target']}")
    with sc2: 
        st.warning(f"🌊 中線: {analysis['mid_action']}")
        st.caption(f"支撐: {analysis['mid_support']}")
    with sc3: 
        st.success(f"🐢 長線: {analysis['long_action']}")
        st.caption(f"季線: {analysis['long_ma60']}")
    
    st.markdown("#### 🛡️ 關鍵價位")
    st.table(pd.DataFrame({
        "類型": ["壓力位 (布林上軌)", "現價", "建議進場", "支撐位 (布林下軌)"],
        "價格": [f"{analysis['pressure']:.2f}", f"{analysis['close']:.2f}", f"{analysis['suggest_price']:.2f}", f"{analysis['support']:.2f}"]
    }))
