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
        .strategy-card { background-color: #262730; padding: 15px; border-radius: 8px; border-left: 5px solid #FF9F1C; margin-bottom: 10px; }
        .bull-text { color: #FF2B2B; font-weight: bold; }
        .bear-text { color: #00E050; font-weight: bold; }
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

# --- 2. 六大指標真實演算法 (V94 修正版) ---
def calculate_six_indicators(df, info):
    scores = {"籌碼": 5, "價量": 5, "基本": 5, "動能": 5, "風險": 5, "價值": 5}
    
    if df is None or df.empty or len(df) < 60: return scores

    try:
        curr = df['Close'].iloc[-1]
        ma5 = df['Close'].rolling(5).mean().iloc[-1]
        ma20 = df['Close'].rolling(20).mean().iloc[-1]
        ma60 = df['Close'].rolling(60).mean().iloc[-1]
        
        # 1. 價量 (Trend) - 動態評分
        trend_score = 5
        if curr > ma5 > ma20 > ma60: trend_score = 9 # 強勢多頭
        elif curr > ma20 and ma20 > ma60: trend_score = 7 # 中多
        elif curr < ma5 < ma20 < ma60: trend_score = 2 # 強勢空頭
        elif curr < ma20: trend_score = 4 # 轉弱
        scores["價量"] = trend_score
        
        # 2. 動能 (Momentum) - RSI
        delta = df['Close'].diff()
        u = delta.copy(); d = delta.copy(); u[u<0]=0; d[d>0]=0
        rs = u.rolling(14).mean() / d.abs().rolling(14).mean()
        rsi = (100 - 100/(1+rs)).iloc[-1]
        
        mom_score = 5
        if 60 <= rsi <= 80: mom_score = 9 # 強勢區
        elif 40 < rsi < 60: mom_score = 6 # 整理區
        elif rsi > 80: mom_score = 4 # 過熱風險
        elif rsi < 30: mom_score = 3 # 超賣
        scores["動能"] = mom_score

        # 3. 籌碼 (Chips) - 成交量與 OBV 概念
        vol_avg = df['Volume'].rolling(5).mean().iloc[-1]
        vol_curr = df['Volume'].iloc[-1]
        chip_score = 5
        if vol_curr > vol_avg * 1.5 and curr > df['Open'].iloc[-1]: chip_score = 8 # 價漲量增
        elif vol_curr > vol_avg * 1.5 and curr < df['Open'].iloc[-1]: chip_score = 2 # 爆量長黑
        elif vol_curr < vol_avg * 0.6: chip_score = 4 # 量縮
        scores["籌碼"] = chip_score
        
        # 4. 風險 (Risk) - 乖離率 (Bias)
        bias = ((curr - ma60) / ma60) * 100
        risk_score = 5
        if 0 < bias < 10: risk_score = 8 # 乖離適中，風險低
        elif 10 <= bias < 20: risk_score = 6
        elif bias >= 20: risk_score = 2 # 乖離過大，風險高
        elif bias < -20: risk_score = 3 # 負乖離過大
        scores["風險"] = risk_score
        
        # 5. 基本 & 6. 價值 - 使用 yfinance info
        if info:
            # 價值 (PE)
            pe = info.get('trailingPE', 0)
            val_score = 5
            if 0 < pe <= 15: val_score = 8 # 便宜
            elif 15 < pe <= 25: val_score = 6 # 合理
            elif pe > 25: val_score = 4 # 稍貴
            scores["價值"] = val_score
            
            # 基本 (ROE/Margins) - 簡易判斷
            roe = info.get('returnOnEquity', 0)
            fund_score = 5
            if roe > 0.15: fund_score = 8
            elif roe > 0.05: fund_score = 6
            elif roe < 0: fund_score = 2
            scores["基本"] = fund_score

    except: pass
    
    return scores

# --- 3. 繪製雷達圖 ---
def render_radar_chart(scores):
    categories = list(scores.keys())
    values = list(scores.values())
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
            radialaxis=dict(visible=True, range=[0, 10], showticklabels=False, linecolor='#444'),
            bgcolor='rgba(0,0,0,0)'
        ),
        margin=dict(l=20, r=20, t=20, b=20),
        height=250,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

# --- 4. 戰略建議生成器 (V94 回歸) ---
def generate_trade_advice(price, m5, m20, m60, rsi):
    advice = {"action": "觀望", "color": "#888", "entry": "-", "exit": "-", "reason": "數據整理中"}
    
    # 強力多頭
    if price > m5 > m20 > m60:
        advice = {
            "action": "🚀 強力買進", "color": "#FF2B2B",
            "entry": f"回測 5日線 {m5:.2f}",
            "exit": f"跌破 月線 {m20:.2f}",
            "reason": "均線呈完美多頭排列，趨勢強勁，適合順勢操作。"
        }
    # 震盪偏多
    elif price > m20 and m20 > m60:
        advice = {
            "action": "📈 逢低佈局", "color": "#FF2B2B",
            "entry": f"接近 月線 {m20:.2f}",
            "exit": f"跌破 季線 {m60:.2f}",
            "reason": "長線保護短線，股價在生命線之上，回檔皆是買點。"
        }
    # 空頭排列
    elif price < m5 < m20 < m60:
        advice = {
            "action": "📉 反彈空", "color": "#00E050",
            "entry": f"反彈 月線 {m20:.2f}",
            "exit": f"站上 季線 {m60:.2f}",
            "reason": "均線空頭排列，上方壓力重重，不宜躁進摸底。"
        }
    # 乖離過大
    elif ((price - m20)/m20)*100 > 15:
         advice = {
            "action": "⚠️ 獲利了結", "color": "#FF9F1C",
            "entry": "暫不建議",
            "exit": "分批出場",
            "reason": "短線漲幅過大，乖離率過高，隨時可能回檔修正。"
        }
        
    return advice

# --- 5. 儀表板 (整合雷達圖) ---
def render_metrics_dashboard(curr, chg, pct, high, low, amp, main_force, 
                             vol, vol_yest, vol_avg, vol_status, foreign_held, 
                             turnover_rate, bid_ask_data, color_settings, 
                             realtime_data=None, stock_info=None, df=None):
    
    if realtime_data:
        curr = realtime_data['latest_trade_price']
        vol = int(float(realtime_data['accumulate_trade_volume']))
    
    radar_scores = calculate_six_indicators(df, stock_info)
    color = "#FF2B2B" if chg > 0 else ("#00E050" if chg < 0 else "white")
    
    with st.container():
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

# --- 6. AI 戰略分析報告 (V94 恢復顯示) ---
def render_ai_report(curr, m5, m20, m60, rsi, bias, high, low, df=None):
    # 計算建議
    advice = generate_trade_advice(curr, m5, m20, m60, rsi)
    
    st.subheader("🤖 AI 投資顧問診斷")
    
    # 策略卡片
    st.markdown(f"""
    <div class='strategy-card'>
        <h3 style='color:{advice['color']}; margin-top:0;'>{advice['action']}</h3>
        <p style='font-size:1.1rem;'>{advice['reason']}</p>
        <hr style='border-color:#555;'>
        <div style='display:flex; justify-content:space-between;'>
            <div>📥 建議進場：<span style='font-weight:bold; color:#DDD'>{advice['entry']}</span></div>
            <div>📤 建議停損：<span style='font-weight:bold; color:#DDD'>{advice['exit']}</span></div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 詳細數據
    t1, t2 = st.tabs(["📊 趨勢數據", "🕯️ K線型態"])
    with t1:
        c1, c2, c3 = st.columns(3)
        c1.metric("RSI 動能", f"{rsi:.1f}")
        c2.metric("季線乖離", f"{bias:.2f}%")
        c3.metric("均線狀態", "多頭" if curr>m20 else "空頭")
    with t2:
         if df is not None and len(df) >= 3:
            c1 = df.iloc[-1]; c2 = df.iloc[-2]
            if c1['Close'] > c1['Open'] and c2['Close'] < c2['Open'] and c1['Close'] > c2['Open']:
                st.markdown("✅ **多頭吞噬**：今日紅K吞噬昨日綠K，強勢反轉訊號。")
            else:
                st.markdown("ℹ️ 目前無特殊K線型態。")

# --- 7. K線圖 ---
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
            if trend[i-1] == 1: trend[i] = -1 if close[i] < final_lower[i] else 1
            else: trend[i] = 1 if close[i] > final_upper[i] else -1
        supertrend[i] = final_lower[i] if trend[i] == 1 else final_upper[i]
    return supertrend, trend

def render_chart(df, title, color_settings):
    df['MA5'] = df['Close'].rolling(5).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA60'] = df['Close'].rolling(60).mean()
    st_line, st_dir = calculate_supertrend(df)
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='K線', increasing_line_color=color_settings['up'], decreasing_line_color=color_settings['down']), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='#FFA500', width=1), name='月線'), row=1, col=1)
    st_green = st_line.copy(); st_green[st_dir != 1] = np.nan
    st_red = st_line.copy(); st_red[st_dir != -1] = np.nan
    fig.add_trace(go.Scatter(x=df.index, y=st_green, line=dict(color='#00E050', width=2), name='支撐'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=st_red, line=dict(color='#FF2B2B', width=2), name='壓力'), row=1, col=1)
    vol_colors = [color_settings['up'] if c >= o else color_settings['down'] for c, o in zip(df['Close'], df['Open'])]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=vol_colors, name='成交量'), row=2, col=1)
    fig.update_layout(height=500, xaxis_rangeslider_visible=False, title=title, margin=dict(l=10, r=10, t=30, b=10), showlegend=False)
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

def render_company_profile(summary): 
    if summary: 
        with st.expander("🏢 公司簡介 (AI 自動翻譯)"): st.write(summary)
def render_detailed_card(*args, **kwargs): return False
def render_term_card(t, c): st.info(f"{t}: {c}")
def render_kline_pattern_card(t, d): st.write(t)
