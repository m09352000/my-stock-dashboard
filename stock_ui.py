import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime, timedelta, timezone

# --- CSS: V90 UI (戰情室風格) ---
def inject_custom_css():
    st.markdown("""
        <style>
        .kline-card-header { margin-top: 0.5rem !important; margin-bottom: 0.2rem !important; font-size: 1.1rem !important; font-weight: bold; }
        .action-list ul { padding-left: 1.2rem !important; margin-bottom: 0rem !important; }
        .action-list li { margin-bottom: 0.3rem !important; line-height: 1.6 !important; font-size: 1rem !important; }
        
        /* 戰情室卡片風格 */
        .battle-card {
            background-color: #1e1e1e;
            padding: 20px;
            border-radius: 12px;
            border: 1px solid #333;
            margin-bottom: 15px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        .battle-title { font-size: 1.2rem; font-weight: 900; color: #fff; margin-bottom: 10px; border-bottom: 2px solid #444; padding-bottom: 5px; }
        .success-text { color: #28a745 !important; font-weight: bold; }
        .danger-text { color: #dc3545 !important; font-weight: bold; }
        .warning-text { color: #ffc107 !important; font-weight: bold; }
        .info-text { color: #17a2b8 !important; font-weight: bold; }
        
        .live-tag { color: #00FF00; font-weight: bold; font-size: 0.9rem; animation: blink 1s infinite; text-shadow: 0 0 5px #00FF00; }
        @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.4; } 100% { opacity: 1; } }
        
        div[data-testid="stMetricValue"] { font-size: 1.35rem !important; font-weight: 800 !important; }
        hr.compact { margin: 8px 0px !important; border: 0; border-top: 1px solid #444; }
        </style>
    """, unsafe_allow_html=True)

# --- 1. 標題 ---
def render_header(title, show_monitor=False):
    inject_custom_css()
    c1, c2 = st.columns([3, 1])
    c1.title(title)
    
    is_live = False
    tw_tz = timezone(timedelta(hours=8))
    now_tw = datetime.now(tw_tz)
    
    if show_monitor:
        if 'monitor_active' not in st.session_state: st.session_state['monitor_active'] = False
        is_live = c2.toggle("🔴 啟動 1秒極速刷新", value=st.session_state['monitor_active'], key="live_toggle_btn")
        st.session_state['monitor_active'] = is_live
        
        if is_live:
            time_str = now_tw.strftime("%H:%M:%S")
            st.markdown(f"<span class='live-tag'>● LIVE 連線中 (台灣時間 {time_str})</span>", unsafe_allow_html=True)
        else:
            st.caption(f"最後更新: {now_tw.strftime('%Y-%m-%d %H:%M:%S')} (TW)")
            
    st.markdown("<hr class='compact'>", unsafe_allow_html=True)
    return is_live

# --- 2. 返回 ---
def render_back_button(callback_func):
    st.markdown("<hr class='compact'>", unsafe_allow_html=True)
    _, c2, _ = st.columns([2, 1, 2])
    if c2.button("⬅️ 返回搜尋", use_container_width=True):
        callback_func()

# --- 3. 新手村卡片 ---
def render_term_card(title, content):
    with st.container(border=True):
        st.subheader(f"📌 {title}")
        st.markdown("<hr class='compact'>", unsafe_allow_html=True)
        st.markdown(f"<div>{content}</div>", unsafe_allow_html=True)

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

# --- 4. 簡介 ---
def render_company_profile(summary):
    if summary and summary != "暫無詳細描述":
        with st.expander("🏢 公司簡介與業務", expanded=False):
            st.write(summary)

# --- 5. 儀表板 ---
def render_metrics_dashboard(curr, chg, pct, high, low, amp, main_force, 
                             vol, vol_yest, vol_avg, vol_status, foreign_held, 
                             turnover_rate, bid_ask_data, color_settings, 
                             realtime_data=None):
    
    is_realtime = False
    if realtime_data:
        is_realtime = True
        curr = realtime_data['latest_trade_price']
        high = realtime_data['high']
        low = realtime_data['low']
        vol = int(float(realtime_data['accumulate_trade_volume']))
        prev_close = realtime_data['previous_close']
        if prev_close > 0:
            chg = curr - prev_close
            pct = (chg / prev_close) * 100
            amp = ((high - low) / prev_close) * 100
        
        if chg > 0: val_color = "#FF2B2B"
        elif chg < 0: val_color = "#00E050"
        else: val_color = "#FFFFFF"
    else:
        val_color = "white"

    with st.container():
        m1, m2, m3, m4, m5 = st.columns(5)
        live_indicator = f"<span class='live-tag' style='font-size:0.7rem; vertical-align:middle; margin-left:5px;'>● LIVE</span>" if is_realtime else ""
        m1.markdown(f"""
            <div style='font-size:0.9rem; color:#d0d0d0'>成交價 {live_indicator}</div>
            <div style='font-size:1.6rem; font-weight:800; color:{val_color}; line-height:1.2'>
                {curr:.2f} 
                <span style='font-size:1rem'>({chg:+.2f} / {pct:+.2f}%)</span>
            </div>
            """, unsafe_allow_html=True)
        m2.metric("最高價", f"{high:.2f}")
        m3.metric("最低價", f"{low:.2f}")
        m4.metric("振幅", f"{amp:.2f}%")
        m5.metric("主力動向", main_force)
        
        v1, v2, v3, v4, v5 = st.columns(5)
        v1.metric("今日量", f"{int(vol):,} 張")
        v2.metric("週轉率", f"{turnover_rate:.2f}%")
        v3.metric("五日均量", f"{int(vol_avg/1000):,} 張")
        v4.metric("量能狀態", vol_status)
        v5.metric("外資持股", f"{foreign_held:.1f}%")

    if bid_ask_data:
        st.markdown("---")
        st.caption("📊 即時五檔 (Best Bid/Ask)")
        b_price = bid_ask_data.get('bid_price', ['-'])[0]
        b_vol = bid_ask_data.get('bid_volume', ['-'])[0]
        a_price = bid_ask_data.get('ask_price', ['-'])[0]
        a_vol = bid_ask_data.get('ask_volume', ['-'])[0]
        c1, c2 = st.columns(2)
        c1.metric("最佳買入 (Bid)", f"{b_price}", f"量: {b_vol}", delta_color="off")
        c2.metric("最佳賣出 (Ask)", f"{a_price}", f"量: {a_vol}", delta_color="off")

# --- 6. 詳細診斷卡 (Scan 用) ---
def render_detailed_card(code, name, price, df, source_type="yahoo", key_prefix="btn", rank=None, strategy_info=None):
    # 簡化版卡片，僅用於掃描結果顯示
    chg_color = "black"; pct_txt = ""
    if df is not None and not df.empty:
        curr = df['Close'].iloc[-1]; prev = df['Close'].iloc[-2]
        chg = curr - prev; pct = (chg / prev) * 100
        if chg > 0: chg_color = "red"; pct_txt = f"▲{pct:.2f}%"
        elif chg < 0: chg_color = "green"; pct_txt = f"▼{abs(pct):.2f}%"
        else: chg_color = "gray"; pct_txt = "0.00%"
    
    rank_tag = f"#{rank}" if rank else ""
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([1.5, 1.5, 3, 1])
        with c1: st.markdown(f"#### {rank_tag} {name}"); st.caption(f"{code}")
        with c2: st.markdown(f"#### {price:.2f}"); st.markdown(f":{chg_color}[{pct_txt}]")
        with c3: st.info(strategy_info if strategy_info else "等待分析")
        with c4:
            st.write(""); 
            if st.button("分析", key=f"{key_prefix}_{code}", use_container_width=True): return True
    return False

# --- 7. K線圖 ---
def render_chart(df, title, color_settings):
    df['MA5'] = df['Close'].rolling(5).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA60'] = df['Close'].rolling(60).mean()
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='K線', increasing_line_color=color_settings['up'], decreasing_line_color=color_settings['down']), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='#FF00FF', width=1), name='MA5'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='#FFA500', width=1), name='MA20'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA60'], line=dict(color='#0000FF', width=1), name='MA60'), row=1, col=1)
    vol_colors = [color_settings['up'] if c >= o else color_settings['down'] for c, o in zip(df['Close'], df['Open'])]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=vol_colors, name='量'), row=2, col=1)
    fig.update_layout(height=450, xaxis_rangeslider_visible=False, title=title, margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

# --- 8. 全新 AI 戰情診斷室 (V90 核心) ---
def render_ai_battle_dashboard(analysis):
    st.markdown("---")
    st.markdown("## 🤖 AI 戰情診斷室")
    
    # 第一層：熱度 與 勝率
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"""
        <div class="battle-card">
            <div class="battle-title">🔥 市場熱度</div>
            <div style="font-size: 2rem; color: {analysis['heat_color']}; font-weight: bold;">{analysis['heat']}</div>
            <div style="color: #aaa; font-size: 0.9rem;">基於量能放大倍數與波動率判定</div>
        </div>
        """, unsafe_allow_html=True)
    
    with c2:
        prob_color = "#00E050" if analysis['probability'] < 50 else "#FF2B2B" # 台股紅漲綠跌
        st.markdown(f"""
        <div class="battle-card">
            <div class="battle-title">🎲 進場獲利機率 (Win Rate)</div>
            <div style="font-size: 2rem; color: {prob_color}; font-weight: bold;">{analysis['probability']:.1f}%</div>
            <div style="color: #aaa; font-size: 0.9rem;">多重指標 (MA, RSI, MACD) 綜合權重</div>
        </div>
        """, unsafe_allow_html=True)
        st.progress(int(analysis['probability']))

    # 第二層：多週期戰術建議
    st.subheader("💡 多週期戰術建議")
    sc1, sc2, sc3 = st.columns(3)

    # 短線
    with sc1:
        s_bg = "#2e1a1a" if "買進" in analysis['short_action'] else "#1a2e1a" if "觀望" not in analysis['short_action'] else "#262730"
        st.markdown(f"""
        <div class="battle-card" style="background-color:{s_bg}">
            <div class="battle-title">⚡ 短線 (1-3天)</div>
            <div class="strategy-text">
                <b>建議：</b><span style="font-size:1.2rem">{analysis['short_action']}</span><br>
                <b>進場：</b>{analysis['short_entry']}<br>
                <b>目標：</b>{analysis['short_target']}
            </div>
        </div>
        """, unsafe_allow_html=True)

    # 中線
    with sc2:
        m_bg = "#2e1a1a" if "佈局" in analysis['mid_action'] else "#262730"
        st.markdown(f"""
        <div class="battle-card" style="background-color:{m_bg}">
            <div class="battle-title">🌊 中線 (波段)</div>
            <div class="strategy-text">
                <b>趨勢：</b>{analysis['mid_trend']}<br>
                <b>策略：</b>{analysis['mid_action']}<br>
                <b>支撐：</b>{analysis['mid_support']}
            </div>
        </div>
        """, unsafe_allow_html=True)

    # 長線
    with sc3:
        l_bg = "#2e1a1a" if "價值" in analysis['long_action'] else "#262730"
        st.markdown(f"""
        <div class="battle-card" style="background-color:{l_bg}">
            <div class="battle-title">🐢 長線 (存股)</div>
            <div class="strategy-text">
                <b>乖離率：</b>{analysis['long_bias']:.2f}%<br>
                <b>評價：</b>{analysis['long_action']}<br>
                <b>生命線：</b>{analysis['long_ma60']}
            </div>
        </div>
        """, unsafe_allow_html=True)

    # 第三層：關鍵點位與理由
    xc1, xc2 = st.columns([1.5, 2.5])
    with xc1:
        st.markdown("#### 🛡️ 關鍵價位 (Key Levels)")
        st.table(pd.DataFrame({
            "關卡": ["壓力位 (布林上軌)", "現價", "建議進場", "支撐位 (布林/月線)"],
            "價格": [
                f"{analysis['pressure']:.2f}",
                f"{analysis['close']:.2f}",
                f"{analysis['suggest_price']:.2f}",
                f"{analysis['support']:.2f}"
            ]
        }))
    
    with xc2:
        st.markdown("#### 📝 AI 判斷依據")
        st.markdown('<div class="battle-card">', unsafe_allow_html=True)
        if analysis['reasons']:
            for reason in analysis['reasons']:
                st.markdown(f"✅ {reason}")
        else:
            st.write("⚠️ 目前技術面訊號渾沌，建議多觀察基本面消息。")
        st.markdown('</div>', unsafe_allow_html=True)
