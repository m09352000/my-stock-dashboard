import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone

# --- CSS: V79 UI ---
def inject_custom_css():
    st.markdown("""
        <style>
        .kline-card-header { margin-top: 0.5rem !important; margin-bottom: 0.2rem !important; font-size: 1.1rem !important; font-weight: bold; }
        .action-list ul { padding-left: 1.2rem !important; margin-bottom: 0rem !important; }
        .action-list li { margin-bottom: 0.3rem !important; line-height: 1.6 !important; font-size: 1rem !important; }
        .strategy-title { font-size: 1.4rem; font-weight: 900; margin-bottom: 10px; display: block; }
        .strategy-text { font-size: 1.05rem; color: #EEE; line-height: 1.7; }
        .bull-box { background-color: #2e1a1a; border-left: 6px solid #FF2B2B; padding: 15px; border-radius: 8px; margin-bottom: 10px; }
        .bear-box { background-color: #1a2e1a; border-left: 6px solid #00E050; padding: 15px; border-radius: 8px; margin-bottom: 10px; }
        .neutral-box { background-color: #262730; border-left: 6px solid #888; padding: 15px; border-radius: 8px; margin-bottom: 10px; }
        div[data-testid="stVerticalBlock"] > div { padding-top: 0.1rem; padding-bottom: 0.1rem; gap: 0.3rem; }
        button { height: auto !important; padding-top: 0.2rem !important; padding-bottom: 0.2rem !important; }
        div[data-testid="stMetricValue"] { font-size: 1.35rem !important; font-weight: 800 !important; }
        div[data-testid="stMetricLabel"] { font-size: 0.9rem !important; color: #d0d0d0 !important; }
        hr.compact { margin: 8px 0px !important; border: 0; border-top: 1px solid #444; }
        .live-tag { color: #00FF00; font-weight: bold; font-size: 0.9rem; animation: blink 1s infinite; text-shadow: 0 0 5px #00FF00; }
        @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.4; } 100% { opacity: 1; } }
        
        @media only screen and (max-width: 768px) {
            div[data-testid="stVerticalBlock"] > div { gap: 0.8rem !important; padding-top: 0.5rem !important; }
            button { padding: 0.5rem 1rem !important; font-size: 1rem !important; width: 100% !important; margin-top: 5px !important; }
            .js-plotly-plot { height: 300px !important; }
        }
        </style>
    """, unsafe_allow_html=True)

# --- 1. 標題 (V79: 顯示登入狀態) ---
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
            st.caption(f"最後更新: {now_tw.strftime('%Y-%m-%d %H:%M:%S')} (TW) | V79 自動登入版")
            
    st.markdown("<hr class='compact'>", unsafe_allow_html=True)
    return is_live

# --- 2. 返回 ---
def render_back_button(callback_func):
    st.markdown("<hr class='compact'>", unsafe_allow_html=True)
    _, c2, _ = st.columns([2, 1, 2])
    if c2.button("⬅️ 返回列表", use_container_width=True):
        callback_func()

# --- 3. 新手村卡片 ---
def render_term_card(title, content):
    with st.container(border=True):
        st.subheader(f"📌 {title}")
        st.markdown("<hr class='compact'>", unsafe_allow_html=True)
        st.markdown(f"<div class='term-content'>{content}</div>", unsafe_allow_html=True)

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
            fig.update_layout(margin=dict(l=2, r=2, t=10, b=2), height=180, xaxis=dict(visible=False, fixedrange=True), yaxis=dict(visible=False, fixedrange=True), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False, dragmode=False)
            st.write(""); st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        with c2:
            st.markdown(f"### 💡 {title}")
            st.markdown("<hr class='compact'>", unsafe_allow_html=True)
            st.markdown("<div class='kline-card-header'>【型態特徵】</div>", unsafe_allow_html=True)
            st.caption(morph)
            st.markdown("<div class='kline-card-header'>【多空心理】</div>", unsafe_allow_html=True)
            st.caption(psycho)
            st.markdown("<div class='kline-card-header'>【實戰操作建議】</div>", unsafe_allow_html=True)
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
        
        t_label = "正常"
        if turnover_rate > 20: t_label = "🔥 過熱"
        elif turnover_rate > 10: t_label = "熱絡"
        elif turnover_rate < 0.5: t_label = "❄️ 冷門"
        
        v2.metric("週轉率", f"{turnover_rate:.2f}%", t_label)
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

# --- 6. 戰術建議 ---
def generate_trade_advice(price, high, low, m5, m20, m60, rsi, strategy_type="general"):
    pivot = (high + low + price) / 3
    r1 = 2 * pivot - low; s1 = 2 * pivot - high
    action = "觀望"; color_hex = "#aaaaaa"
    target_price = 0.0; stop_price = 0.0
    entry_price_txt = "-"; exit_price_txt = "-"
    hold_time = "-"; reasoning = "數據盤整中"

    if strategy_type == 'day': 
        stop_price = low * 0.99; target_price = high * 1.02; hold_time = "當日沖銷"
        if price > m5 and price > pivot:
            action = "🔥 強力作多"; color_hex = "#FF2B2B"
            entry_price_txt = f"{pivot:.1f} 附近"; exit_price_txt = f"跌破 {m5:.1f}"
            reasoning = "量價齊揚站上樞紐，多方動能強勁，適合順勢操作。"
        elif price < pivot:
            action = "🧊 偏空操作"; color_hex = "#00E050"
            entry_price_txt = f"反彈 {pivot:.1f} 不過"; exit_price_txt = "急殺出量"
            reasoning = "股價受制於樞紐之下，上方賣壓重，建議偏空思考。"
        else:
            action = "⚖️ 區間震盪"; color_hex = "#FF9F1C"
            entry_price_txt = f"{s1:.1f} 支撐"; exit_price_txt = f"{r1:.1f} 壓力"
            reasoning = "多空膠著，建議區間來回操作或觀望。"
    elif strategy_type == 'short':
        stop_price = m20; target_price = price * 1.08; hold_time = "3-5 天"
        if price > m5 and m5 > m20:
            action = "🚀 穩健買進"; color_hex = "#FF2B2B"
            entry_price_txt = f"回測 {m5:.1f}"; exit_price_txt = f"跌破 {m20:.1f}"
            reasoning = "均線多頭排列，短線趨勢向上，拉回找買點勝率高。"
        elif price < m5:
            action = "📉 等待止穩"; color_hex = "#FF9F1C"
            entry_price_txt = f"接近 {m20:.1f}"; exit_price_txt = "有效跌破月線"
            reasoning = "短線漲多乖離修正，等待回測月線支撐確認後再進場。"
    elif strategy_type == 'long':
        stop_price = m60; target_price = price * 1.20; hold_time = "1-3 個月"
        if price > m60:
            action = "🐢 長線續抱"; color_hex = "#FF2B2B"
            entry_price_txt = f"{m60:.1f} 附近"; exit_price_txt = "季線下彎"
            reasoning = "股價站穩生命線，長線保護短線，適合波段持有。"
        else:
            action = "⏳ 觀望"; color_hex = "#aaaaaa"
            entry_price_txt = "突破季線"; exit_price_txt = "續破底"
            reasoning = "目前仍處於空頭或整理架構，建議等待趨勢翻多。"
    else: 
        stop_price = m20; target_price = price * 1.05; hold_time = "視情況"
        if price > m20: 
            action = "💪 強勢持有"; color_hex = "#FF2B2B"
            entry_price_txt = "量縮不破低"; exit_price_txt = "爆量收黑"
            reasoning = "人氣匯聚強勢股，沿著趨勢操作，轉弱即跑。"
        else: 
            action = "⚠️ 轉弱減碼"; color_hex = "#00E050"
            entry_price_txt = "暫不建議"; exit_price_txt = f"反彈 {m20:.1f}"
            reasoning = "籌碼鬆動轉弱，建議反彈減碼降低風險。"
    return action, color_hex, target_price, stop_price, entry_price_txt, exit_price_txt, hold_time, reasoning

# --- 7. 詳細診斷卡 ---
def render_detailed_card(code, name, price, df, source_type="yahoo", key_prefix="btn", rank=None, strategy_info=None):
    chg_color = "black"; pct_txt = ""
    action_title = "計算中"; action_color_hex = "#aaaaaa"
    target_val = 0.0; stop_val = 0.0
    entry_txt = "-"; exit_txt = "-"; hold_txt = "-"; reason_txt = "資料不足"
    strat_type = "general"
    if strategy_info:
        if "當沖" in strategy_info or "量" in strategy_info: strat_type = "day"
        elif "短線" in strategy_info or "RSI" in strategy_info: strat_type = "short"
        elif "長線" in strategy_info or "季" in strategy_info: strat_type = "long"
        elif "強勢" in strategy_info: strat_type = "top"

    if df is not None and not df.empty:
        try:
            curr = df['Close'].iloc[-1]; prev = df['Close'].iloc[-2] if len(df) > 1 else curr
            chg = curr - prev; pct = (chg / prev) * 100
            high = df['High'].iloc[-1]; low = df['Low'].iloc[-1]
            if chg > 0: chg_color = "red"; pct_txt = f"▲{pct:.2f}%"
            elif chg < 0: chg_color = "green"; pct_txt = f"▼{abs(pct):.2f}%"
            else: chg_color = "gray"; pct_txt = "0.00%"
            
            if len(df) > 20:
                m5 = df['Close'].rolling(5).mean().iloc[-1]
                m20 = df['Close'].rolling(20).mean().iloc[-1]
                m60 = df['Close'].rolling(60).mean().iloc[-1]
                delta = df['Close'].diff(); u = delta.copy(); d = delta.copy(); u[u<0]=0; d[d>0]=0
                rs = u.rolling(14).mean() / d.abs().rolling(14).mean()
                rsi = (100 - 100/(1+rs)).iloc[-1] if not rs.isna().iloc[-1] else 50
                action_title, action_color_hex, target_val, stop_val, entry_txt, exit_txt, hold_txt, reason_txt = generate_trade_advice(
                    curr, high, low, m5, m20, m60, rsi, strat_type
                )
        except: pass
    
    rank_tag = f"#{rank}" if rank else ""
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([1.3, 1.3, 3.5, 0.8])
        with c1: st.markdown(f"#### {rank_tag} {name}"); st.caption(f"代號: {code}")
        with c2: st.markdown(f"#### {price:.2f}"); st.markdown(f":{chg_color}[{pct_txt}]")
        with c3: st.markdown(f"<div style='display:flex;flex-direction:column;justify-content:center;height:100%;'><div style='color:{action_color_hex};font-weight:900;font-size:1.3rem;'>{action_title}</div><div style='color:#888;font-size:0.85rem;'>{strategy_info if strategy_info else '監控中'}</div></div>", unsafe_allow_html=True)
        with c4:
            st.write(""); 
            if st.button("分析", key=f"{key_prefix}_{code}", use_container_width=True): return True
        st.markdown("<hr class='compact'>", unsafe_allow_html=True)
        d1, d2, d3, d4 = st.columns(4)
        with d1: st.markdown(f"🎯 **目標** `{target_val:.2f}`")
        with d2: st.markdown(f"🛡️ **停損** `{stop_val:.2f}`")
        with d3: st.caption(f"📥 **入場**\n{entry_txt}")
        with d4: st.caption(f"📤 **離場**\n{exit_txt}")
        st.markdown("<hr class='compact'>", unsafe_allow_html=True)
        e1, e2 = st.columns([3, 1])
        with e1: st.info(f"💡 **AI觀點**: {reason_txt}")
        with e2: st.markdown(f"📅 **持股**: `{hold_txt}`")
    return False

# --- 輔助: Supertrend 計算 (NumPy版) ---
def calculate_supertrend(df, period=10, multiplier=3):
    high = df['High'].values
    low = df['Low'].values
    close = df['Close'].values
    
    # 1. 計算 TR
    m1 = high - low
    m2 = np.abs(high - np.roll(close, 1))
    m3 = np.abs(low - np.roll(close, 1))
    tr = np.maximum(m1, np.maximum(m2, m3))
    tr[0] = 0
    
    # 2. 計算 ATR (RMA 平滑)
    atr = np.zeros_like(close)
    atr[period-1] = np.mean(tr[:period])
    for i in range(period, len(close)):
        atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period
        
    # 3. 計算基本上下軌
    hl2 = (high + low) / 2
    basic_upper = hl2 + (multiplier * atr)
    basic_lower = hl2 - (multiplier * atr)
    
    # 4. 計算最終上下軌與趨勢
    final_upper = np.zeros_like(close)
    final_lower = np.zeros_like(close)
    supertrend = np.zeros_like(close)
    trend = np.zeros_like(close) # 1: Up, -1: Down
    
    for i in range(period, len(close)):
        # Final Upper
        if basic_upper[i] < final_upper[i-1] or close[i-1] > final_upper[i-1]:
            final_upper[i] = basic_upper[i]
        else:
            final_upper[i] = final_upper[i-1]
            
        # Final Lower
        if basic_lower[i] > final_lower[i-1] or close[i-1] < final_lower[i-1]:
            final_lower[i] = basic_lower[i]
        else:
            final_lower[i] = final_lower[i-1]
            
        # Trend
        if len(close) > 0:
            if trend[i-1] == 1:
                if close[i] < final_lower[i]:
                    trend[i] = -1
                else:
                    trend[i] = 1
            else:
                if close[i] > final_upper[i]:
                    trend[i] = 1
                else:
                    trend[i] = -1
        
        if trend[i] == 1:
            supertrend[i] = final_lower[i]
        else:
            supertrend[i] = final_upper[i]
            
    return supertrend, trend

# --- 8. K線圖 (V91: 加入 Supertrend) ---
def render_chart(df, title, color_settings):
    # MA 計算
    df['MA5'] = df['Close'].rolling(5).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA60'] = df['Close'].rolling(60).mean()
    
    # Supertrend 計算 (參數: ATR 10, 倍數 3)
    st_line, st_dir = calculate_supertrend(df, 10, 3)
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
    
    # K線
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='K線', increasing_line_color=color_settings['up'], decreasing_line_color=color_settings['down']), row=1, col=1)
    
    # 均線
    fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='#FF00FF', width=1), name='MA5'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='#FFA500', width=1), name='MA20'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA60'], line=dict(color='#0000FF', width=1), name='MA60'), row=1, col=1)
    
    # Supertrend 繪圖邏輯
    # 我們將線段拆成綠色(多)和紅色(空)兩段來畫，以便視覺區分
    st_green = st_line.copy(); st_green[st_dir != 1] = np.nan
    st_red = st_line.copy(); st_red[st_dir != -1] = np.nan
    
    fig.add_trace(go.Scatter(x=df.index, y=st_green, line=dict(color='#00E050', width=2, dash='solid'), name='超級趨勢(多)'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=st_red, line=dict(color='#FF2B2B', width=2, dash='solid'), name='超級趨勢(空)'), row=1, col=1)

    # 成交量
    vol_colors = [color_settings['up'] if c >= o else color_settings['down'] for c, o in zip(df['Close'], df['Open'])]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=vol_colors, name='量'), row=2, col=1)
    
    fig.update_layout(height=450, xaxis_rangeslider_visible=False, title=title, margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

# --- 9. AI 報告 ---
def render_ai_report(curr, m5, m20, m60, rsi, bias, high, low, df=None):
    st.subheader("🤖 AI 戰略分析報告")
    pivot = (high + low + curr) / 3
    r1 = 2 * pivot - low; s1 = 2 * pivot - high
    
    t1, t2, t3 = st.tabs(["📊 詳細趨勢診斷", "🎯 關鍵價位試算", "🕯️ K線型態戰法"])
    with t1:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("#### 📈 趨勢研判")
            if curr > m20 and m20 > m60: st.success("🔥 **多頭排列**：均線向上，多方控盤。")
            elif curr < m20 and m20 < m60: st.error("❄️ **空頭排列**：均線反壓，建議保守。")
            elif curr > m20: st.warning("🌤️ **震盪偏多**：站上月線，但需留意前高。")
            else: st.info("🌧️ **震盪偏空**：月線之下，等待底部。")
        with c2:
            st.markdown("#### ⚡ 動能指標")
            st.metric("RSI (14)", f"{rsi:.1f}")
            if rsi > 80: st.write("⚠️ **過熱警戒**")
            elif rsi < 20: st.write("💎 **超賣區**")
            else: st.write("✅ **動能中性**")
        with c3:
            st.markdown("#### 📏 乖離率")
            st.metric("季線乖離", f"{bias:.2f}%")
            if bias > 20: st.write("⚠️ **正乖離大**")
            elif bias < -20: st.write("💎 **負乖離大**")
            else: st.write("✅ **乖離正常**")
    with t2:
        st.markdown("#### 🎯 關鍵價位 (Pivot)")
        st.info("計算基礎：(最高+最低+收盤)/3")
        cp1, cp2, cp3 = st.columns(3)
        cp1.metric("壓力 (R1)", f"{r1:.2f}")
        cp2.metric("中軸 (P)", f"{pivot:.2f}")
        cp3.metric("支撐 (S1)", f"{s1:.2f}")
    with t3:
        if df is not None and len(df) >= 5:
            try:
                # 這裡直接實作簡單版分析邏輯，以避免循環匯入或未定義錯誤
                c1 = df.iloc[-1]; c2 = df.iloc[-2]; c3 = df.iloc[-3]
                is_red = lambda c: c['Close'] > c['Open']
                title = "盤整待變"; advice = "近期 K 線無明顯反轉訊號。"; box = "neutral-box"
                
                if is_red(c3) and is_red(c2) and is_red(c1) and c1['Close']>c2['Close']>c3['Close']:
                    title = "💂‍♂️ 紅三兵 (Three White Soldiers)"
                    box = "bull-box"
                    advice = "連續三根紅K穩步上攻，多頭部隊集結完畢，趨勢由空翻多。"
                
                st.markdown(f"""<div class='{box}'><span class='strategy-title'>{title}</span><div class='strategy-text'>{advice}</div></div>""", unsafe_allow_html=True)
            except: st.warning("分析中...")
        else: st.warning("資料不足")
