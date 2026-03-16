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
        
        .signal-box { background-color: #262730; padding: 10px; border-radius: 5px; margin-bottom: 5px; display: flex; justify-content: space-between; align-items: center; border-left: 4px solid #555; }
        .signal-box.bull { border-left-color: #FF2B2B; background-color: #2e1a1a; }
        .signal-box.bear { border-left-color: #00E050; background-color: #1a2e1a; }
        .signal-label { font-size: 0.9rem; color: #ccc; }
        .signal-value { font-weight: bold; font-size: 1rem; }
        
        .tactic-card { background-color: #1E1E1E; border: 1px solid #444; border-radius: 8px; padding: 15px; }
        .tactic-header { color: #FF9F1C; font-weight: bold; font-size: 1.1rem; margin-bottom: 10px; border-bottom: 1px solid #444; padding-bottom: 5px;}
        .tactic-row { display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 1rem; }
        .tactic-val { color: #eee; font-weight: bold; font-family: monospace; }
        
        .chip-bar-label { display: flex; justify-content: space-between; font-size: 0.9rem; color: #ddd; margin-bottom: 2px;}
        .chip-progress { height: 8px; background-color: #333; border-radius: 4px; overflow: hidden; margin-bottom: 10px; }
        .chip-fill { height: 100%; border-radius: 4px; }
        </style>
    """, unsafe_allow_html=True)

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
    if st.button("⬅️ 返回", use_container_width=True): callback_func()

def calculate_chart_indicators(df):
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    
    low_min = df['Low'].rolling(window=9).min()
    high_max = df['High'].rolling(window=9).max()
    rsv = (df['Close'] - low_min) / (high_max - low_min) * 100
    k = rsv.ewm(com=2, adjust=False).mean()
    d = k.ewm(com=2, adjust=False).mean()
    
    delta = df['Close'].diff()
    u = delta.copy(); u[u < 0] = 0
    d_loss = delta.copy(); d_loss[d_loss > 0] = 0
    rs = u.rolling(window=14).mean() / d_loss.abs().rolling(window=14).mean()
    rsi = 100 - 100 / (1 + rs)
    
    return { "MACD": {"macd": macd, "signal": signal, "hist": hist}, "KD": {"k": k, "d": d}, "RSI": {"rsi": rsi} }

def calculate_advanced_indicators(df):
    try:
        close = df['Close']
        exp1 = close.ewm(span=12, adjust=False).mean()
        exp2 = close.ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        hist = macd - signal
        low_min = df['Low'].rolling(window=9).min()
        high_max = df['High'].rolling(window=9).max()
        rsv = (close - low_min) / (high_max - low_min) * 100
        k = rsv.ewm(com=2, adjust=False).mean()
        d = k.ewm(com=2, adjust=False).mean()
        sma20 = close.rolling(window=20).mean()
        std20 = close.rolling(window=20).std()
        upper = sma20 + (std20 * 2)
        lower = sma20 - (std20 * 2)
        return { "macd": macd.iloc[-1], "signal": signal.iloc[-1], "hist": hist.iloc[-1], "k": k.iloc[-1], "d": d.iloc[-1], "bb_upper": upper.iloc[-1], "bb_lower": lower.iloc[-1], "sma20": sma20.iloc[-1] }
    except: return None

def calculate_six_indicators(df, info, chip_data=None):
    scores = {"籌碼": 5, "價量": 5, "基本": 5, "動能": 5, "風險": 5, "價值": 5}
    if df is None or df.empty or len(df) < 60: return scores
    try:
        curr = df['Close'].iloc[-1]
        ma5 = df['Close'].rolling(5).mean().iloc[-1]
        ma20 = df['Close'].rolling(20).mean().iloc[-1]
        ma60 = df['Close'].rolling(60).mean().iloc[-1]
        if curr > ma5 > ma20 > ma60: scores["價量"] = 9 
        elif curr > ma20 and ma20 > ma60: scores["價量"] = 7 
        elif curr < ma5 < ma20 < ma60: scores["價量"] = 2 
        else: scores["價量"] = 4 
        
        delta = df['Close'].diff()
        u = delta.copy(); d = delta.copy(); u[u<0]=0; d[d>0]=0
        rs = u.rolling(14).mean() / d.abs().rolling(14).mean()
        rsi = (100 - 100/(1+rs)).iloc[-1]
        if 60 <= rsi <= 80: scores["動能"] = 9 
        elif 40 < rsi < 60: scores["動能"] = 6 
        elif rsi > 80: scores["動能"] = 4 
        else: scores["動能"] = 3 

        if chip_data:
            f_buy = chip_data.get('foreign', 0)
            if f_buy > 2000: scores["籌碼"] = 10 
            elif f_buy > 500: scores["籌碼"] = 8 
            elif f_buy < -2000: scores["籌碼"] = 1 
            else: scores["籌碼"] = 3 
        
        bias = ((curr - ma60) / ma60) * 100
        if 0 < bias < 10: scores["風險"] = 8 
        elif 10 <= bias < 20: scores["風險"] = 6
        elif bias >= 20: scores["風險"] = 2 
        else: scores["風險"] = 3 
        
        if info:
            pe = info.get('trailingPE', 0)
            if 0 < pe <= 15: scores["價值"] = 8 
            elif 15 < pe <= 25: scores["價值"] = 6 
            else: scores["價值"] = 4 
            roe = info.get('returnOnEquity', 0)
            if roe > 0.15: scores["基本"] = 8
            elif roe > 0.05: scores["基本"] = 6
            else: scores["基本"] = 2
    except: pass
    return scores

def render_radar_chart(scores):
    categories = list(scores.keys()); values = list(scores.values())
    categories.append(categories[0]); values.append(values[0])
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=values, theta=categories, fill='toself', fillcolor='rgba(255, 43, 43, 0.4)', line=dict(color='#FF2B2B', width=2), name='個股評分'))
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 10], showticklabels=False, linecolor='#444'), bgcolor='rgba(0,0,0,0)'), margin=dict(l=20, r=20, t=20, b=20), height=250, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

def generate_detailed_advice(price, m5, m20, m60, rsi, tech_ind, chip_data=None):
    advice = {"action": "觀望", "color": "#888", "entry": "-", "exit": "-", "reason": "數據整理中", "signals": []}
    score = 0; signals = []
    
    if price > m20: score += 1; signals.append(("均線", "站上月線", "bull"))
    else: signals.append(("均線", "月線反壓", "bear"))
    if m5 > m20: score += 1; signals.append(("短趨勢", "多頭排列", "bull"))
    
    if tech_ind:
        if tech_ind['hist'] > 0: score += 1; signals.append(("MACD", "紅柱擴大", "bull"))
        else: signals.append(("MACD", "綠柱修正", "bear"))
        if tech_ind['k'] > tech_ind['d']: signals.append(("KD", "黃金交叉", "bull"))
        else: signals.append(("KD", "死亡交叉", "bear"))
        if price > tech_ind['bb_upper']: signals.append(("布林", "觸及上軌", "bull"))
        elif price < tech_ind['bb_lower']: signals.append(("布林", "觸及下軌", "bear"))
        else: signals.append(("布林", "通道內", "neutral"))
        
    if chip_data:
        if chip_data['foreign'] > 500: score += 1; signals.append(("外資", "積極買超", "bull"))
        elif chip_data['foreign'] < -500: score -= 1; signals.append(("外資", "大幅調節", "bear"))
        else: signals.append(("外資", "動作不大", "neutral"))
    
    if score >= 3:
        advice["action"] = "🚀 強力買進"
        advice["color"] = "#FF2B2B"
        advice["entry"] = f"拉回 {m5:.1f} ~ {m20:.1f} 佈局"
        advice["exit"] = f"跌破 {m20:.1f} 停損"
        advice["reason"] = "多項技術指標與籌碼面共振，趨勢強勁，適合順勢操作。"
    elif score >= 1:
        advice["action"] = "📈 偏多操作"
        advice["color"] = "#FF9F1C"
        advice["entry"] = f"接近 {m20:.1f} 承接"
        advice["exit"] = f"跌破 {m60:.1f} 停損"
        advice["reason"] = "趨勢偏多但力道未滿，建議逢低承接，避免追高。"
    elif price < m60:
        advice["action"] = "📉 反彈空"
        advice["color"] = "#00E050"
        advice["entry"] = f"反彈 {m20:.1f} 不過"
        advice["exit"] = f"站上 {m60:.1f}"
        advice["reason"] = "空頭架構未變，反彈遇壓容易回落。"
    
    advice["signals"] = signals
    return advice

def render_ai_report(curr, m5, m20, m60, rsi, bias, high, low, df=None, chip_data=None):
    tech_ind = calculate_advanced_indicators(df)
    advice = generate_detailed_advice(curr, m5, m20, m60, rsi, tech_ind, chip_data)
    
    st.subheader("🤖 AI 深度戰略診斷")
    c_left, c_right = st.columns([1.5, 1])
    with c_left:
        st.markdown(f"""<div class='strategy-card'><div style='display:flex; justify-content:space-between;'><h2 style='color:{advice['color']}; margin:0;'>{advice['action']}</h2><span style='background:#333; padding:2px 8px; border-radius:4px;'>信心度: 高</span></div><p style='font-size:1.1rem; margin-top:10px;'>{advice['reason']}</p></div>""", unsafe_allow_html=True)
        st.markdown(f"""<div class='tactic-card'><div class='tactic-header'>🎯 關鍵戰術</div><div class='tactic-row'><span>📥 建議進場</span><span class='tactic-val' style='color:#FF9F1C'>{advice['entry']}</span></div><div class='tactic-row'><span>🛡️ 停損防守</span><span class='tactic-val' style='color:#00E050'>{advice['exit']}</span></div><div class='tactic-row'><span>🚧 月線壓力</span><span class='tactic-val'>{m20:.2f}</span></div><div class='tactic-row'><span>🌊 季線支撐</span><span class='tactic-val'>{m60:.2f}</span></div></div>""", unsafe_allow_html=True)
    with c_right:
        st.markdown("#### 📡 訊號矩陣")
        if advice['signals']:
            for name, value, status in advice['signals']:
                color_cls = "bull" if status == "bull" else ("bear" if status == "bear" else "neutral")
                icon = "🟢" if status == "bull" else ("🔴" if status == "bear" else "⚪")
                st.markdown(f"""<div class='signal-box {color_cls}'><span class='signal-label'>{name}</span><span class='signal-value'>{icon} {value}</span></div>""", unsafe_allow_html=True)
        else:
            st.info("數據計算中...")
            
    if df is not None and len(df) >= 3:
        c1 = df.iloc[-1]; c2 = df.iloc[-2]
        if c1['Close'] > c1['Open'] and c2['Close'] < c2['Open'] and c1['Close'] > c2['Open']: st.info("💡 K線偵測：今日出現 **多頭吞噬** 型態，短線轉強訊號。")

def render_metrics_dashboard(curr, chg, pct, high, low, amp, main_force, 
                             vol, vol_yest, vol_avg, vol_status, foreign_held, 
                             turnover_rate, bid_ask_data, color_settings, 
                             realtime_data=None, stock_info=None, df=None, chip_data=None, 
                             metrics=None):
    
    if realtime_data:
        curr = realtime_data['latest_trade_price']
        vol = int(float(realtime_data['accumulate_trade_volume']))
    
    radar_scores = calculate_six_indicators(df, stock_info, chip_data)
    color = "#FF2B2B" if chg > 0 else ("#00E050" if chg < 0 else "white")
    
    if metrics is None: metrics = {}
    cash_div = metrics.get('cash_div', 0)
    yield_val = metrics.get('yield', 0)
    
    pe = metrics.get('pe'); pe_str = f"{pe:.2f}" if pe else "-"
    pb = metrics.get('pb'); pb_str = f"{pb:.2f}" if pb else "-"
    
    cap_val = metrics.get('mkt_cap')
    if cap_val is None: cap_val = 0
    if cap_val > 1000000000000: cap_str = f"{cap_val/1000000000000:.2f}兆"
    elif cap_val > 100000000: cap_str = f"{cap_val/100000000:.2f}億"
    else: cap_str = "-"

    with st.container():
        c_main, c_radar = st.columns([1.8, 1])
        with c_main:
            st.markdown(f"<span class='big-price' style='color:{color}'>{curr:.2f}</span> <span style='font-size:1.2rem; color:{color}'>{chg:+.2f} ({pct:+.2f}%)</span>", unsafe_allow_html=True)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("最高", f"{high:.2f}")
            m2.metric("最低", f"{low:.2f}")
            m3.metric("成交量", f"{int(vol/1000):,} 張")
            m4.metric("總市值", cap_str)
            
            b1, b2, b3, b4 = st.columns(4)
            b1.metric("本益比", pe_str)
            b2.metric("淨值比", pb_str)
            b3.metric("現金股利", f"${cash_div:.2f}")
            b4.metric("殖利率 (動態)", f"{yield_val:.2f}%")

            mf_color = "red" if "🔴" in main_force else ("green" if "🟢" in main_force else "gray")
            st.markdown(f"主力動向: <span style='color:{mf_color}; font-weight:bold'>{main_force}</span> | 量能: {vol_status}", unsafe_allow_html=True)
            
        with c_radar:
            st.markdown("**📊 AI 六大指標**")
            render_radar_chart(radar_scores)
    st.markdown("---")

def render_chip_structure(chip_dist):
    if not chip_dist: 
        st.warning("⚠️ 籌碼資料暫時無法取得，請稍後再試。")
        return

    st.subheader(f"🍰 籌碼結構分析 (外資/法人/散戶)")
    
    items = [
        ("外資持股", chip_dist.get("foreign", 0), "#FF9F1C"),
        ("國內法人 (投信/自營/其他)", chip_dist.get("domestic_inst", 0), "#2B908F"), 
        ("董監持股", chip_dist.get("directors", 0), "#F45B69")
    ]
    
    known = sum([val for _, val, _ in items])
    retail = max(0, 100 - known)
    items.append(("散戶/其他", retail, "#555555"))
    
    c1, c2 = st.columns([1, 1])
    with c1:
        for label, val, color in items:
            if val > 0:
                st.markdown(f"""
                <div class='chip-bar-label'><span>{label}</span><span>{val:.2f}%</span></div>
                <div class='chip-progress'><div class='chip-fill' style='width:{min(val, 100)}%; background-color:{color};'></div></div>
                """, unsafe_allow_html=True)
    
    with c2:
        labels = [i[0] for i in items if i[1]>0.1]
        values = [i[1] for i in items if i[1]>0.1]
        colors = [i[2] for i in items if i[1]>0.1]
        fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.4, marker=dict(colors=colors))])
        fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=220, showlegend=True)
        st.plotly_chart(fig, use_container_width=True)
        
    st.info("💡 **數據說明**：結合 FinMind 外資申報資料與 Yahoo 機構持股，自動補足缺漏數據，確保圖表完整。")

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
    
    ind_data = calculate_chart_indicators(df)
    
    st.write("### 📉 進階技術線圖")
    options = ["成交量", "MACD", "RSI", "KD"]
    defaults = ["成交量"] 
    
    selected_inds = st.multiselect("🛠️ 選擇副圖指標 (可多選，由上而下排列)", options=options, default=defaults, key="chart_ind_selector")
    
    num_sub = len(selected_inds)
    num_rows = 1 + num_sub
    total_height = 500 + (num_sub * 150)
    
    if num_sub == 0: row_heights = [1.0]
    else:
        main_ratio = 0.5 
        sub_ratio = 0.5 / num_sub
        row_heights = [main_ratio] + [sub_ratio] * num_sub

    fig = make_subplots(rows=num_rows, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=row_heights, subplot_titles=[title] + selected_inds)
    
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='K線', increasing_line_color=color_settings['up'], decreasing_line_color=color_settings['down']), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='#AAD3FF', width=1), name='5日線'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='#FFA500', width=1.5), name='月線'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA60'], line=dict(color='#888888', width=1), name='季線'), row=1, col=1)
    
    st_green = st_line.copy(); st_green[st_dir != 1] = np.nan
    st_red = st_line.copy(); st_red[st_dir != -1] = np.nan
    fig.add_trace(go.Scatter(x=df.index, y=st_green, line=dict(color='#00E050', width=2), name='支撐'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=st_red, line=dict(color='#FF2B2B', width=2), name='壓力'), row=1, col=1)
    
    for i, ind in enumerate(selected_inds):
        r = i + 2
        if ind == "成交量":
            colors = [color_settings['up'] if c >= o else color_settings['down'] for c, o in zip(df['Close'], df['Open'])]
            fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors, name='成交量'), row=r, col=1)
        elif ind == "MACD":
            m = ind_data["MACD"]
            hist_colors = ['#FF2B2B' if v >= 0 else '#00E050' for v in m['hist']]
            fig.add_trace(go.Bar(x=df.index, y=m['hist'], marker_color=hist_colors, name='MACD柱'), row=r, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=m['macd'], line=dict(color='#FFD700', width=1), name='DIF'), row=r, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=m['signal'], line=dict(color='#00FFFF', width=1), name='DEA'), row=r, col=1)
        elif ind == "KD":
            k_val = ind_data["KD"]["k"]; d_val = ind_data["KD"]["d"]
            fig.add_trace(go.Scatter(x=df.index, y=k_val, line=dict(color='#FFA500', width=1), name='K值'), row=r, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=d_val, line=dict(color='#00FFFF', width=1), name='D值'), row=r, col=1)
        elif ind == "RSI":
            r_val = ind_data["RSI"]["rsi"]
            fig.add_trace(go.Scatter(x=df.index, y=r_val, line=dict(color='#D8BFD8', width=1), name='RSI'), row=r, col=1)
            fig.add_hline(y=70, line_dash="dot", line_color="red", row=r, col=1)
            fig.add_hline(y=30, line_dash="dot", line_color="green", row=r, col=1)

    fig.update_layout(height=total_height, margin=dict(l=10, r=10, t=30, b=10), showlegend=True, xaxis_rangeslider_visible=False, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

def render_company_profile(summary):
    if summary:
        with st.expander("🏢 公司簡介 (AI 自動翻譯)"): st.write(summary)

def render_detailed_card(*args, **kwargs): return False
def render_term_card(t, c): st.info(f"{t}: {c}")

def render_kline_pattern_card(name, details):
    with st.container():
        st.subheader(f"🕯️ {name}")
        c1, c2 = st.columns([1.5, 1])
        
        with c1:
            st.markdown(f"**【型態特徵】**")
            st.write(details['morphology'])
            st.markdown(f"**【投資心理】**")
            st.write(details['psychology'])
            st.markdown(f"**【操作策略】**")
            st.markdown(details['action'], unsafe_allow_html=True)

        with c2:
            raw = details['data']
            opens = [d[0] for d in raw]
            highs = [d[1] for d in raw]
            lows = [d[2] for d in raw]
            closes = [d[3] for d in raw]
            dates = [f"D{i+1}" for i in range(len(raw))]
            
            fig = go.Figure(data=[go.Candlestick(
                x=dates, open=opens, high=highs, low=lows, close=closes,
                increasing_line_color='#FF2B2B', decreasing_line_color='#00E050'
            )])
            
            fig.update_layout(
                margin=dict(t=20, b=20, l=20, r=20),
                height=300,
                xaxis_rangeslider_visible=False,
                plot_bgcolor='#1E1E1E',
                paper_bgcolor='#1E1E1E',
                font=dict(color='white'),
                xaxis=dict(showgrid=False, visible=False),
                yaxis=dict(showgrid=True, gridcolor='#333')
            )
            st.plotly_chart(fig, use_container_width=True)
        st.divider()

# --- V110 新增：證交所 注意/處置股 監控版面 ---
def render_warning_dashboard(df_warnings):
    st.subheader("⚠️ 注意與處置股票監控 (上市)")
    st.info("💡 **名詞解釋**：當股票漲跌幅或交易量異常時，會先被列為「🟡 注意股」。若連續多日達標，則會被關入「🔴 處置股」進行分盤交易（俗稱關緊閉）。")
    
    if df_warnings is None or df_warnings.empty:
        st.success("🎉 今日目前無上市注意或處置股票，或證交所連線維護中。")
        return
        
    c1, c2 = st.columns(2)
    disp_count = len(df_warnings[df_warnings['狀態'].str.contains('處置')])
    att_count = len(df_warnings[df_warnings['狀態'].str.contains('注意')])
    
    c1.metric("🔴 目前處置股數量", f"{disp_count} 檔")
    c2.metric("🟡 目前注意股數量", f"{att_count} 檔")
    
    st.markdown("#### 📋 最新監控清單")
    # 將 DataFrame 的樣式做一點簡單的顏色區分
    def color_status(val):
        if '處置' in val: return 'color: #FF2B2B; font-weight: bold'
        elif '注意' in val: return 'color: #FF9F1C; font-weight: bold'
        return ''
        
    styled_df = df_warnings.style.map(color_status, subset=['狀態'])
    
    st.dataframe(
        styled_df,
        use_container_width=True,
        hide_index=True,
        height=600
    )
