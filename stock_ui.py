import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone

# --- CSS 優化 ---
def inject_custom_css():
    st.markdown("""
        <style>
        .metric-container { background-color: #1E1E1E; border-radius: 10px; padding: 15px; border: 1px solid #333; margin-bottom: 10px; }
        .big-price { font-size: 2.5rem; font-weight: 900; line-height: 1; }
        .live-tag { color: #00FF00; font-weight: bold; font-size: 0.8rem; animation: blink 1s infinite; }
        @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.4; } 100% { opacity: 1; } }
        /* 雷達圖背景 */
        .radar-box { background-color: #111; border-radius: 10px; padding: 10px; border: 1px solid #444; }
        </style>
    """, unsafe_allow_html=True)

# --- 標題 ---
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
    st.markdown("---")
    return is_live

def render_back_button(callback_func):
    if st.button("⬅️ 返回列表", use_container_width=True): callback_func()

# --- 2. 六大指標運算核心 (模仿投資先生) ---
def calculate_six_indicators(df, info):
    # 初始化分數 (滿分 10 分)
    scores = {"籌碼": 5, "價量": 5, "基本": 5, "動能": 5, "風險": 5, "價值": 5}
    
    if df is None or df.empty: return scores

    try:
        # 1. 價量 (Trend): 均線多頭排列
        curr = df['Close'].iloc[-1]
        ma5 = df['Close'].rolling(5).mean().iloc[-1]
        ma20 = df['Close'].rolling(20).mean().iloc[-1]
        ma60 = df['Close'].rolling(60).mean().iloc[-1]
        if curr > ma20: scores["價量"] += 2
        if ma5 > ma20 > ma60: scores["價量"] += 3
        
        # 2. 動能 (Momentum): RSI & 成交量
        delta = df['Close'].diff()
        u = delta.copy(); d = delta.copy(); u[u<0]=0; d[d>0]=0
        rs = u.rolling(14).mean() / d.abs().rolling(14).mean()
        rsi = (100 - 100/(1+rs)).iloc[-1]
        
        if 50 < rsi < 80: scores["動能"] += 3
        vol_ratio = df['Volume'].iloc[-1] / (df['Volume'].rolling(5).mean().iloc[-1] + 1)
        if vol_ratio > 1.2: scores["動能"] += 2

        # 3. 籌碼 (Chips): 簡易模擬 (量價配合度)
        # 由於 yfinance 無法取得即時分點籌碼，我們用 OBV 概念模擬
        if df['Close'].iloc[-1] > df['Open'].iloc[-1] and vol_ratio > 1: scores["籌碼"] += 3
        
        # 4. 風險 (Risk): 乖離率
        bias = (curr - ma60) / ma60 * 100
        if 0 < bias < 15: scores["風險"] += 3 # 乖離適中
        elif bias > 20: scores["風險"] -= 2 # 乖離過大
        
        # 5. 基本 (Fundamental) & 6. 價值 (Value)
        # 從 info 取得 (若無資料則維持 5 分)
        if info:
            pe = info.get('trailingPE', 0)
            if 0 < pe < 20: scores["價值"] += 3
            elif pe > 40: scores["價值"] -= 2
            
            # 營收成長或毛利 (模擬)
            margins = info.get('grossMargins', 0)
            if margins > 0.2: scores["基本"] += 3

    except: pass
    
    # 限制分數在 0-10
    for k in scores: scores[k] = max(0, min(10, scores[k]))
    return scores

# --- 3. 繪製雷達圖 (Plotly) ---
def render_radar_chart(scores):
    categories = list(scores.keys())
    values = list(scores.values())
    
    # 封閉圖形
    categories.append(categories[0])
    values.append(values[0])

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values,
        theta=categories,
        fill='toself',
        fillcolor='rgba(255, 43, 43, 0.4)',
        line=dict(color='#FF2B2B', width=2),
        name='個股評分'
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 10],
                showticklabels=False,
                linecolor='#444'
            ),
            bgcolor='rgba(0,0,0,0)'
        ),
        margin=dict(l=20, r=20, t=20, b=20),
        height=250,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

# --- 4. 儀表板 (整合雷達圖) ---
def render_metrics_dashboard(curr, chg, pct, high, low, amp, main_force, 
                             vol, vol_yest, vol_avg, vol_status, foreign_held, 
                             turnover_rate, bid_ask_data, color_settings, 
                             realtime_data=None, stock_info=None, df=None):
    
    if realtime_data:
        curr = realtime_data['latest_trade_price']
        vol = int(float(realtime_data['accumulate_trade_volume']))
    
    # 計算六大指標
    radar_scores = calculate_six_indicators(df, stock_info)
    
    # 顏色定義
    color = "#FF2B2B" if chg > 0 else ("#00E050" if chg < 0 else "white")
    
    with st.container():
        # 佈局：左側價格，右側雷達圖
        c_main, c_radar = st.columns([1.8, 1])
        
        with c_main:
            st.markdown(f"<div style='font-size:1rem; color:#aaa'>成交價</div>", unsafe_allow_html=True)
            st.markdown(f"<span class='big-price' style='color:{color}'>{curr:.2f}</span> <span style='font-size:1.2rem; color:{color}'>{chg:+.2f} ({pct:+.2f}%)</span>", unsafe_allow_html=True)
            
            m1, m2, m3 = st.columns(3)
            m1.metric("最高", f"{high:.2f}")
            m2.metric("最低", f"{low:.2f}")
            m3.metric("成交量", f"{int(vol/1000)}K")
            
            st.caption(f"主力動向: {main_force} | 量能: {vol_status}")

        with c_radar:
            st.markdown("**📊 AI 六大指標**")
            render_radar_chart(radar_scores)

    st.markdown("---")

# --- 5. K線圖 (含 Supertrend) ---
def calculate_supertrend(df, period=10, multiplier=3):
    high = df['High'].values; low = df['Low'].values; close = df['Close'].values
    m1 = high - low; m2 = np.abs(high - np.roll(close, 1)); m3 = np.abs(low - np.roll(close, 1))
    tr = np.maximum(m1, np.maximum(m2, m3)); tr[0] = 0
    atr = np.zeros_like(close); atr[period-1] = np.mean(tr[:period])
    for i in range(period, len(close)): atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period
    hl2 = (high + low) / 2
    basic_upper = hl2 + (multiplier * atr); basic_lower = hl2 - (multiplier * atr)
    final_upper = np.zeros_like(close); final_lower = np.zeros_like(close)
    supertrend = np.zeros_like(close); trend = np.zeros_like(close)
    
    for i in range(period, len(close)):
        if basic_upper[i] < final_upper[i-1] or close[i-1] > final_upper[i-1]: final_upper[i] = basic_upper[i]
        else: final_upper[i] = final_upper[i-1]
        if basic_lower[i] > final_lower[i-1] or close[i-1] < final_lower[i-1]: final_lower[i] = basic_lower[i]
        else: final_lower[i] = final_lower[i-1]
        if len(close) > 0:
            if trend[i-1] == 1:
                trend[i] = -1 if close[i] < final_lower[i] else 1
            else:
                trend[i] = 1 if close[i] > final_upper[i] else -1
        supertrend[i] = final_lower[i] if trend[i] == 1 else final_upper[i]
    return supertrend, trend

def render_chart(df, title, color_settings):
    df['MA5'] = df['Close'].rolling(5).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA60'] = df['Close'].rolling(60).mean()
    st_line, st_dir = calculate_supertrend(df)
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
    
    # 主圖
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='K線', increasing_line_color=color_settings['up'], decreasing_line_color=color_settings['down']), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='#FFA500', width=1), name='月線'), row=1, col=1)
    
    # Supertrend
    st_green = st_line.copy(); st_green[st_dir != 1] = np.nan
    st_red = st_line.copy(); st_red[st_dir != -1] = np.nan
    fig.add_trace(go.Scatter(x=df.index, y=st_green, line=dict(color='#00E050', width=2), name='支撐'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=st_red, line=dict(color='#FF2B2B', width=2), name='壓力'), row=1, col=1)

    # 成交量
    vol_colors = [color_settings['up'] if c >= o else color_settings['down'] for c, o in zip(df['Close'], df['Open'])]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=vol_colors, name='成交量'), row=2, col=1)
    
    fig.update_layout(height=500, xaxis_rangeslider_visible=False, title=title, margin=dict(l=10, r=10, t=30, b=10), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

# --- 舊有函式保留 (避免報錯) ---
def render_company_profile(summary): 
    if summary: 
        with st.expander("🏢 公司簡介"): st.write(summary)
def render_ai_report(*args): pass 
def render_detailed_card(*args, **kwargs): return False
def render_term_card(t, c): st.info(f"{t}: {c}")
def render_kline_pattern_card(t, d): st.write(t)
