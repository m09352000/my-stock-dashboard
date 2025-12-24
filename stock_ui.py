import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

# --- CSS: V63 暴力壓縮版面 (關鍵修正) ---
def inject_custom_css():
    st.markdown("""
        <style>
        /* 1. 全局縮減垂直間距 */
        div[data-testid="stVerticalBlock"] > div {
            padding-top: 0rem !important;
            padding-bottom: 0rem !important;
            gap: 0.1rem !important; /* 元件間距縮到最小 */
        }
        
        /* 2. 縮減卡片內部留白 */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            padding: 5px !important;
        }
        
        /* 3. 按鈕縮小與對齊 */
        button {
            height: auto !important;
            padding: 2px 10px !important;
            font-size: 0.8rem !important;
            margin-top: 5px !important;
        }
        
        /* 4. 強制縮減文字行高 */
        p, .stMarkdown, .stCaption {
            margin-bottom: 0px !important;
            font-size: 0.9rem !important;
            line-height: 1.2 !important;
        }
        
        /* 5. 數據指標緊湊化 */
        div[data-testid="stMetricValue"] {
            font-size: 1.1rem !important;
            padding: 0px !important;
        }
        div[data-testid="stMetricLabel"] {
            font-size: 0.8rem !important;
            padding: 0px !important;
        }
        
        /* 6. 自定義分隔線樣式 */
        hr.compact {
            margin: 3px 0px !important;
            border: 0;
            border-top: 1px solid #333;
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
        st.caption("V63 極致緊湊版 | 資料來源: Yahoo/TWSE")
        is_live = c2.toggle("🔴 即時盤面", value=False)
    st.markdown("<hr class='compact'>", unsafe_allow_html=True)
    return is_live

# --- 2. 返回 ---
def render_back_button(callback_func):
    st.markdown("<hr class='compact'>", unsafe_allow_html=True)
    _, c2, _ = st.columns([2, 1, 2])
    if c2.button("⬅️ 返回列表", use_container_width=True):
        callback_func()

# --- 3. 新手村 ---
def render_term_card(title, content):
    with st.container(border=True):
        st.markdown(f"**{title}**")
        st.caption(content)

# --- 4. 簡介 ---
def render_company_profile(summary):
    if summary and summary != "暫無詳細描述":
        with st.expander("🏢 公司簡介與業務", expanded=False):
            st.write(summary)

# --- 5. 儀表板 ---
def render_metrics_dashboard(curr, chg, pct, high, low, amp, main_force, 
                             vol, vol_yest, vol_avg, vol_status, foreign_held, 
                             color_settings):
    with st.container():
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("成交價", f"{curr:.2f}", f"{chg:.2f} ({pct:.2f}%)", delta_color=color_settings['delta'])
        m2.metric("最高價", f"{high:.2f}")
        m3.metric("最低價", f"{low:.2f}")
        m4.metric("振幅", f"{amp:.2f}%")
        m5.metric("主力動向", main_force)
        
        v1, v2, v3, v4, v5 = st.columns(5)
        v1.metric("今日量", f"{int(vol/1000):,}張")
        v2.metric("昨日量", f"{int(vol_yest/1000):,}張")
        v3.metric("五日均量", f"{int(vol_avg/1000):,}張")
        v4.metric("量能狀態", vol_status)
        v5.metric("外資持股", f"{foreign_held:.1f}%")

# --- 6. 戰術建議生成 (V63: 邏輯不變，維持詳細) ---
def generate_trade_advice(price, high, low, m5, m20, m60, rsi, strategy_type="general"):
    pivot = (high + low + price) / 3
    r1 = 2 * pivot - low
    s1 = 2 * pivot - high
    
    action = "觀望"
    color = "gray"
    # 預設值
    entry_txt = "-"
    exit_txt = "-"
    target_val = 0.0
    stop_val = 0.0
    reasoning = "數據不足"
    hold_time = "-"

    if strategy_type == 'day': # 當沖
        stop_price = low * 0.99
        target_price = r1 if r1 > price else price * 1.02
        hold_time = "當日沖銷"
        if price > m5 and price > pivot:
            action = "🔥 強力作多"; color = "red"
            entry_txt = f"平盤上 {pivot:.1f} 承接"
            exit_txt = f"跌破均價 {m5:.1f}"
            reasoning = "爆量站上樞紐，多方強勢，順勢操作。"
        elif price < pivot:
            action = "🧊 偏空操作"; color = "green"
            entry_txt = f"反彈 {pivot:.1f} 不過"
            exit_txt = "急殺出量/尾盤"
            reasoning = "受制樞紐之下，賣壓重，偏空思考。"
        else:
            action = "⚖️ 區間震盪"; color = "orange"
            entry_txt = f"支撐 {s1:.1f} 附近"
            exit_txt = f"壓力 {r1:.1f} 附近"
            reasoning = "多空膠著，區間操作。"
            
    elif strategy_type == 'short': # 短線
        stop_price = m20
        target_price = price * 1.08
        hold_time = "3-5 天"
        if price > m5 and m5 > m20:
            action = "🚀 穩健買進"; color = "red"
            entry_txt = f"回測5日線 {m5:.1f}"
            exit_txt = f"破10日線"
            reasoning = "均線多頭，短線趨勢向上，拉回找買點。"
        elif price < m5:
            action = "📉 等待止穩"; color = "orange"
            entry_txt = f"近月線 {m20:.1f}"
            exit_txt = "破月線"
            reasoning = "短線乖離修正，等待回測月線支撐。"
            
    elif strategy_type == 'long': # 長線
        stop_price = m60
        target_price = price * 1.20
        hold_time = "1-3 個月"
        if price > m60:
            action = "🐢 長線續抱"; color = "red"
            entry_txt = f"季線 {m60:.1f} 上"
            exit_txt = "季線下彎"
            reasoning = "站穩生命線，長線保護短線，波段持有。"
        else:
            action = "⏳ 觀望"; color = "gray"
            entry_txt = "突破季線"
            exit_txt = "破底"
            reasoning = "空頭或整理架構，等待趨勢翻多。"
            
    else: # 強勢
        stop_price = m20
        target_price = price * 1.05
        hold_time = "視情況"
        if price > m20: 
            action = "💪 強勢持有"; color = "red"
            entry_txt = "量縮不破低"
            exit_txt = "爆量收黑"
            reasoning = "人氣匯聚，沿趨勢操作，轉弱即跑。"
        else: 
            action = "⚠️ 轉弱減碼"; color = "green"
            entry_txt = "暫不建議"
            exit_txt = f"反彈 {m20:.1f}"
            reasoning = "籌碼鬆動，建議反彈減碼。"

    return action, color, target_price, stop_price, entry_txt, exit_txt, hold_time, reasoning

# --- 7. 詳細診斷卡 (V63: 變態級壓縮 + 資訊滿載) ---
def render_detailed_card(code, name, price, df, source_type="yahoo", key_prefix="btn", rank=None, strategy_info=None):
    chg_color = "black"
    pct_txt = ""
    action_title = "計算中"
    action_color = "gray"
    target_val = 0.0
    stop_val = 0.0
    entry_txt = "-"
    exit_txt = "-"
    hold_txt = "-"
    reason_txt = "資料不足"
    
    # 策略判斷
    strat_type = "general"
    if strategy_info:
        if "當沖" in strategy_info or "量" in strategy_info: strat_type = "day"
        elif "短線" in strategy_info or "RSI" in strategy_info: strat_type = "short"
        elif "長線" in strategy_info or "季" in strategy_info: strat_type = "long"
        elif "強勢" in strategy_info: strat_type = "top"

    if df is not None and not df.empty:
        try:
            curr = df['Close'].iloc[-1]
            prev = df['Close'].iloc[-2] if len(df) > 1 else curr
            chg = curr - prev
            pct = (chg / prev) * 100
            high = df['High'].iloc[-1]
            low = df['Low'].iloc[-1]
            
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
                
                action_title, action_color, target_val, stop_val, entry_txt, exit_txt, hold_txt, reason_txt = generate_trade_advice(
                    curr, high, low, m5, m20, m60, rsi, strat_type
                )
        except: pass
    
    rank_tag = f"#{rank}" if rank else ""
    
    # --- V63 卡片佈局 (利用 Markdown HTML 進行細部排版) ---
    with st.container(border=True):
        # 第一列：股票資訊 + 價格 + 核心建議 + 按鈕
        c1, c2, c3, c4 = st.columns([1.3, 1.3, 3.5, 0.8])
        with c1:
            st.markdown(f"**{rank_tag} {name}**")
            st.caption(f"{code}")
        with c2:
            st.markdown(f"**{price:.2f}**")
            st.markdown(f":{chg_color}[{pct_txt}]")
        with c3:
            # 使用 HTML span 調整字體大小和顏色，節省空間
            st.markdown(f"<span style='color:{action_color}; font-weight:bold; font-size:1.1rem'>{action_title}</span> <span style='font-size:0.8rem; color:gray'>({strategy_info if strategy_info else '監控中'})</span>", unsafe_allow_html=True)
            st.caption(f"💡 {reason_txt}")
        with c4:
            if st.button("分析", key=f"{key_prefix}_{code}", use_container_width=True):
                return True
        
        # 插入微型分隔線
        st.markdown("<hr class='compact'>", unsafe_allow_html=True)
        
        # 第二列：詳細戰術數據 (4欄，數據與標題同行顯示以省空間)
        d1, d2, d3, d4 = st.columns(4)
        with d1:
            st.markdown(f"🎯 **目標:** {target_val:.2f}")
            st.caption(f"🛡️ **停損:** {stop_val:.2f}")
        with d2:
            st.markdown(f"📥 **入場:** {entry_txt}")
        with d3:
            st.markdown(f"📤 **離場:** {exit_txt}")
        with d4:
            st.markdown(f"📅 **持股:** {hold_txt}")

    return False

# --- 8. K線圖 ---
def render_chart(df, title, color_settings):
    df['MA5'] = df['Close'].rolling(5).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA60'] = df['Close'].rolling(60).mean()
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
    
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], 
        name='K線', increasing_line_color=color_settings['up'], decreasing_line_color=color_settings['down']
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='#FF00FF', width=1), name='MA5'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='#FFA500', width=1), name='MA20'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA60'], line=dict(color='#0000FF', width=1), name='MA60'), row=1, col=1)
    
    vol_colors = [color_settings['up'] if c >= o else color_settings['down'] for c, o in zip(df['Close'], df['Open'])]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=vol_colors, name='成交量'), row=2, col=1)
    
    fig.update_layout(height=450, xaxis_rangeslider_visible=False, title=title, 
                      margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

# --- 9. AI 報告 ---
def render_ai_report(curr, m5, m20, m60, rsi, bias, high, low):
    st.subheader("🤖 AI 戰略分析報告")
    
    pivot = (high + low + curr) / 3
    r1 = 2 * pivot - low
    s1 = 2 * pivot - high
    
    t1, t2 = st.tabs(["📊 詳細趨勢診斷", "🎯 關鍵價位試算"])
    
    with t1:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("#### 📈 趨勢研判")
            if curr > m20 and m20 > m60: st.success("🔥 **多頭排列**：均線向上，多方控盤。")
            elif curr < m20 and m20 < m60: st.error("❄️ **空頭排列**：均線反壓，建議保守。")
            elif curr > m20: st.warning("🌤️ **震盪偏多**：站上月線，但需留意前高。")
            else: st.info("🌧️ **震盪偏空**：月線之下，等待底部。")
                
        with c2:
            st.markdown("#### ⚡ 動能指標 (RSI)")
            st.metric("RSI (14)", f"{rsi:.1f}")
            if rsi > 80: st.write("⚠️ **過熱警戒**：短線有回檔風險。")
            elif rsi < 20: st.write("💎 **超賣區**：隨時可能出現反彈。")
            else: st.write("✅ **動能中性**：無明顯過熱或超賣。")
            
        with c3:
            st.markdown("#### 📏 乖離率分析")
            st.metric("季線乖離", f"{bias:.2f}%")
            if bias > 20: st.write("⚠️ **正乖離過大**：股價衝太快，容易拉回。")
            elif bias < -20: st.write("💎 **負乖離過大**：超跌，有機會反彈。")
            else: st.write("✅ **乖離正常**：股價沿著趨勢線運行。")

    with t2:
        st.markdown("#### 🎯 關鍵價位 (Pivot Points)")
        st.info("計算基礎：(最高+最低+收盤)/3")
        cp1, cp2, cp3 = st.columns(3)
        cp1.metric("壓力位 (R1)", f"{r1:.2f}", help="預估上方第一道壓力")
        cp2.metric("中軸 (Pivot)", f"{pivot:.2f}", help="多空分水嶺")
        cp3.metric("支撐位 (S1)", f"{s1:.2f}", help="預估下方第一道支撐")
