import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone

# --- CSS 優化: V102 戰情室風格 ---
def inject_custom_css():
    st.markdown("""
        <style>
        .metric-container { background-color: #1E1E1E; border-radius: 10px; padding: 15px; border: 1px solid #333; margin-bottom: 10px; }
        .big-price { font-size: 2.5rem; font-weight: 900; line-height: 1; }
        .live-tag { color: #00FF00; font-weight: bold; font-size: 0.8rem; animation: blink 1s infinite; }
        @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.4; } 100% { opacity: 1; } }
        
        /* 訊號矩陣風格 */
        .signal-box {
            background-color: #262730;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 5px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-left: 4px solid #555;
        }
        .signal-box.bull { border-left-color: #FF2B2B; background-color: #2e1a1a; }
        .signal-box.bear { border-left-color: #00E050; background-color: #1a2e1a; }
        .signal-label { font-size: 0.9rem; color: #ccc; }
        .signal-value { font-weight: bold; font-size: 1rem; }
        
        /* 戰術板風格 */
        .tactic-card {
            background-color: #1E1E1E;
            border: 1px solid #444;
            border-radius: 8px;
            padding: 15px;
        }
        .tactic-header { color: #FF9F1C; font-weight: bold; font-size: 1.1rem; margin-bottom: 10px; border-bottom: 1px solid #444; padding-bottom: 5px;}
        .tactic-row { display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 1rem; }
        .tactic-val { color: #eee; font-weight: bold; font-family: monospace; }
        
        /* 籌碼分佈條風格 */
        .chip-bar-label { display: flex; justify-content: space-between; font-size: 0.9rem; color: #ddd; margin-bottom: 2px;}
        .chip-progress { height: 8px; background-color: #333; border-radius: 4px; overflow: hidden; margin-bottom: 10px; }
        .chip-fill { height: 100%; border-radius: 4px; }
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

# --- V96: 進階技術指標計算核心 ---
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
        
        return {
            "macd": macd.iloc[-1], "signal": signal.iloc[-1], "hist": hist.iloc[-1],
            "k": k.iloc[-1], "d": d.iloc[-1],
            "bb_upper": upper.iloc[-1], "bb_lower": lower.iloc[-1], "sma20": sma20.iloc[-1]
        }
    except:
        return None

# --- 六大指標真實演算法 ---
def calculate_six_indicators(df, info, chip_data=None):
    scores = {"籌碼": 5, "價量": 5, "基本": 5, "動能": 5, "風險": 5, "價值": 5}
    if df is None or df.empty or len(df) < 60: return scores
    try:
        curr = df['Close'].iloc[-1]
        ma5 = df['Close'].rolling(5).mean().iloc[-1]
        ma20 = df['Close'].rolling(20).mean().iloc[-1]
        ma60 = df['Close'].rolling(60).mean().iloc[-1]
        
        trend_score = 5
        if curr > ma5 > ma20 > ma60: trend_score = 9 
        elif curr > ma20 and ma20 > ma60: trend_score = 7 
        elif curr < ma5 < ma20 < ma60: trend_score = 2 
        elif curr < ma20: trend_score = 4 
        scores["價量"] = trend_score
        
        delta = df['Close'].diff()
        u = delta.copy(); d = delta.copy(); u[u<0]=0; d[d>0]=0
        rs = u.rolling(14).mean() / d.abs().rolling(14).mean()
        rsi = (100 - 100/(1+rs)).iloc[-1]
        mom_score = 5
        if 60 <= rsi <= 80: mom_score = 9 
        elif 40 < rsi < 60: mom_score = 6 
        elif rsi > 80: mom_score = 4 
        elif rsi < 30: mom_score = 3 
        scores["動能"] = mom_score

        chip_score = 5
        if chip_data:
            f_buy = chip_data.get('foreign', 0); t_buy = chip_data.get('trust', 0)
            if f_buy > 2000 or t_buy > 500: chip_score = 10 
            elif f_buy > 500 or t_buy > 100: chip_score = 8 
            elif f_buy < -2000 or t_buy < -500: chip_score = 1 
            elif f_buy < 0: chip_score = 3 
        else:
            vol_avg = df['Volume'].rolling(5).mean().iloc[-1]; vol_curr = df['Volume'].iloc[-1]
            if vol_curr > vol_avg * 1.5 and curr > df['Open'].iloc[-1]: chip_score = 7
            elif vol_curr > vol_avg * 1.5 and curr < df['Open'].iloc[-1]: chip_score = 3
        scores["籌碼"] = chip_score
        
        bias = ((curr - ma60) / ma60) * 100
        risk_score = 5
        if 0 < bias < 10: risk_score = 8 
        elif 10 <= bias < 20: risk_score = 6
        elif bias >= 20: risk_score = 2 
        elif bias < -20: risk_score = 3 
        scores["風險"] = risk_score
        
        if info:
            pe = info.get('trailingPE', 0)
            val_score = 5
            if 0 < pe <= 15: val_score = 8 
            elif 15 < pe <= 25: val_score = 6 
            elif pe > 25: val_score = 4 
            scores["價值"] = val_score
            roe = info.get('returnOnEquity', 0)
            fund_score = 5
            if roe > 0.15: fund_score = 8
            elif roe > 0.05: fund_score = 6
            elif roe < 0: fund_score = 2
            scores["基本"] = fund_score
    except: pass
    return scores

def render_radar_chart(scores):
    categories = list(scores.keys()); values = list(scores.values())
    categories.append(categories[0]); values.append(values[0])
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=values, theta=categories, fill='toself', fillcolor='rgba(255, 43, 43, 0.4)', line=dict(color='#FF2B2B', width=2), name='個股評分'))
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 10], showticklabels=False, linecolor='#444'), bgcolor='rgba(0,0,0,0)'), margin=dict(l=20, r=20, t=20, b=20), height=250, paper_bgcolor='rgba(0,0,0,0)', showlegend=False)
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

# --- V96: 專業戰術分析引擎 ---
def generate_detailed_advice(price, m5, m20, m60, rsi, tech_ind, chip_data=None):
    advice = {"action": "觀望", "color": "#888", "entry": "-", "exit": "-", "reason": "數據整理中", "signals": []}
    
    score = 0
    signals = []
    
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

# --- V101: 全方位基本面儀表板 ---
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
    
    # 格式化
    y_str = f"{metrics['yield']:.2f}%" if metrics and metrics.get('yield') is not None else "-"
    pe_str = f"{metrics['pe']:.2f}" if metrics and metrics.get('pe') else "-"
    pb_str = f"{metrics['pb']:.2f}" if metrics and metrics.get('pb') else "-"
    rev_str = f"{metrics['rev_growth']*100:.2f}%" if metrics and metrics.get('rev_growth') else "-"
    
    cap_val = metrics.get('mkt_cap', 0) if metrics else 0
    if cap_val > 1000000000000: cap_str = f"{cap_val/1000000000000:.2f}兆"
    elif cap_val > 100000000: cap_str = f"{cap_val/100000000:.2f}億"
    else: cap_str = f"{cap_val}" if cap_val else "-"

    with st.container():
        c_main, c_radar = st.columns([1.8, 1])
        with c_main:
            st.markdown(f"<span class='big-price' style='color:{color}'>{curr:.2f}</span> <span style='font-size:1.2rem; color:{color}'>{chg:+.2f} ({pct:+.2f}%)</span>", unsafe_allow_html=True)
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("最高", f"{high:.2f}")
            m2.metric("最低", f"{low:.2f}")
            m3.metric("成交量", f"{int(vol/1000)}K")
            m4.metric("總市值", cap_str)
            
            b1, b2, b3, b4 = st.columns(4)
            b1.metric("本益比 P/E", pe_str)
            b2.metric("淨值比 P/B", pb_str)
            b3.metric("殖利率", y_str)
            b4.metric("營收成長", rev_str)

            mf_color = "red" if "🔴" in main_force else ("green" if "🟢" in main_force else "gray")
            st.markdown(f"主力動向: <span style='color:{mf_color}; font-weight:bold'>{main_force}</span> | 量能: {vol_status}", unsafe_allow_html=True)
            
        with c_radar:
            st.markdown("**📊 AI 六大指標**")
            render_radar_chart(radar_scores)
    st.markdown("---")

def render_ai_report(curr, m5, m20, m60, rsi, bias, high, low, df=None, chip_data=None):
    tech_ind = calculate_advanced_indicators(df)
    advice = generate_detailed_advice(curr, m5, m20, m60, rsi, tech_ind, chip_data)
    
    st.subheader("🤖 AI 深度戰略診斷")
    c_left, c_right = st.columns([1.5, 1])
    with c_left:
        st.markdown(f"""<div class='strategy-card'><h2 style='color:{advice['color']}'>{advice['action']}</h2><p style='font-size:1.1rem;'>{advice['reason']}</p></div>""", unsafe_allow_html=True)
        st.markdown(f"""<div class='tactic-card'><div class='tactic-header'>🎯 關鍵戰術</div><div class='tactic-row'><span>📥 進場</span><span class='tactic-val' style='color:#FF9F1C'>{advice['entry']}</span></div><div class='tactic-row'><span>🛡️ 停損</span><span class='tactic-val' style='color:#00E050'>{advice['exit']}</span></div><div class='tactic-row'><span>🚧 月線</span><span class='tactic-val'>{m20:.2f}</span></div><div class='tactic-row'><span>🌊 季線</span><span class='tactic-val'>{m60:.2f}</span></div></div>""", unsafe_allow_html=True)
    with c_right:
        st.markdown("#### 📡 訊號矩陣")
        for name, value, status in advice['signals']:
            color_cls = "bull" if status == "bull" else ("bear" if status == "bear" else "neutral")
            icon = "🟢" if status == "bull" else ("🔴" if status == "bear" else "⚪")
            st.markdown(f"""<div class='signal-box {color_cls}'><span class='signal-label'>{name}</span><span class='signal-value'>{icon} {value}</span></div>""", unsafe_allow_html=True)
    if df is not None and len(df) >= 3:
        st.write("")
        c1 = df.iloc[-1]; c2 = df.iloc[-2]
        if c1['Close'] > c1['Open'] and c2['Close'] < c2['Open'] and c1['Close'] > c2['Open']: st.info("💡 K線偵測：多頭吞噬")

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

# --- V102: 籌碼分佈渲染 (四大法人% - 修正版) ---
def render_shareholding_distribution(sh_data):
    if not sh_data: return

    st.subheader(f"🍰 籌碼結構分佈 (單位:%)")
    
    # 建立數據：為了確保正確性，不顯示猜測的投信/自營拆分，改為合併顯示「國內機構」
    # 若未來有 API 支援精確拆分，可再展開
    items = [
        ("外資持股", sh_data.get("Foreign", 0), "#FF9F1C"),
        ("國內機構 (投信/自營)", sh_data.get("Domestic_Inst", 0), "#2B908F"),
        ("董監持股", sh_data.get("Directors", 0), "#F45B69")
    ]
    
    c1, c2 = st.columns([1, 1])
    
    with c1:
        for label, val, color in items:
            if val > 0: # 只顯示有數值的
                st.markdown(f"""
                <div class='chip-bar-label'><span>{label}</span><span>{val:.2f}%</span></div>
                <div class='chip-progress'><div class='chip-fill' style='width:{min(val, 100)}%; background-color:{color};'></div></div>
                """, unsafe_allow_html=True)

    with c2:
        # 繪製圓餅圖
        labels = [i[0] for i in items if i[1] > 0]
        values = [i[1] for i in items if i[1] > 0]
        
        # 計算"散戶/其他" (100% - 已知法人/董監)
        total_known = sum(values)
        if total_known < 100:
            labels.append("散戶/其他")
            values.append(100 - total_known)
            
        fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.4, marker=dict(colors=['#FF9F1C', '#2B908F', '#F45B69', '#555555']))])
        fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=200, showlegend=True)
        st.plotly_chart(fig, use_container_width=True)
        
    st.info("💡 **數據說明**：外資與董監持股為精確申報值；「國內機構」包含投信、自營商及其他國內法人機構。")
