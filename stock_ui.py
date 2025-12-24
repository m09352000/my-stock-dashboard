import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

# --- CSS: V66 排版微調 ---
def inject_custom_css():
    st.markdown("""
        <style>
        /* 容器間距 */
        div[data-testid="stVerticalBlock"] > div {
            padding-top: 0.1rem;
            padding-bottom: 0.1rem;
            gap: 0.4rem;
        }
        /* 按鈕樣式 */
        button {
            height: auto !important;
            padding: 2px 10px !important;
            font-size: 0.85rem !important;
        }
        /* 數據指標文字 */
        div[data-testid="stMetricValue"] {
            font-size: 1.25rem !important;
            font-weight: 700 !important;
        }
        div[data-testid="stMetricLabel"] {
            font-size: 0.9rem !important;
            color: #ccc !important;
        }
        /* 分隔線 */
        hr.compact {
            margin: 8px 0px !important;
            border: 0;
            border-top: 1px solid #444;
        }
        /* 新手村卡片文字優化 */
        .term-content p {
            font-size: 1rem !important;
            line-height: 1.6 !important;
            margin-bottom: 0.5rem !important;
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
        st.caption("資料來源: Yahoo Finance / TWSE | V66 知識庫重製版")
        is_live = c2.toggle("🔴 即時盤面", value=False)
    st.markdown("<hr class='compact'>", unsafe_allow_html=True)
    return is_live

# --- 2. 返回 ---
def render_back_button(callback_func):
    st.markdown("<hr class='compact'>", unsafe_allow_html=True)
    _, c2, _ = st.columns([2, 1, 2])
    if c2.button("⬅️ 返回列表", use_container_width=True):
        callback_func()

# --- 3. 新手村卡片 (V66: 重寫渲染邏輯) ---
def render_term_card(title, content):
    with st.container(border=True):
        # 使用子標題讓名稱更突出
        st.subheader(f"📌 {title}")
        st.markdown("<hr class='compact'>", unsafe_allow_html=True)
        # 使用 markdown 並加入 class 以利 CSS 控制
        st.markdown(f"<div class='term-content'>{content}</div>", unsafe_allow_html=True)

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
        m1.metric("成交價 (Price)", f"{curr:.2f}", f"{chg:.2f} ({pct:.2f}%)", delta_color=color_settings['delta'])
        m2.metric("最高價 (High)", f"{high:.2f}")
        m3.metric("最低價 (Low)", f"{low:.2f}")
        m4.metric("振幅 (Amp)", f"{amp:.2f}%")
        m5.metric("主力動向", main_force)
        
        v1, v2, v3, v4, v5 = st.columns(5)
        v1.metric("今日量 (Vol)", f"{int(vol/1000):,} 張")
        diff_vol = int((vol - vol_yest)/1000)
        v2.metric("昨日量 (Prev)", f"{int(vol_yest/1000):,} 張", f"{diff_vol} 張")
        v3.metric("五日均量 (Avg)", f"{int(vol_avg/1000):,} 張")
        v4.metric("量能狀態", vol_status)
        v5.metric("外資持股", f"{foreign_held:.1f}%")

# --- 6. 戰術建議生成 ---
def generate_trade_advice(price, high, low, m5, m20, m60, rsi, strategy_type="general"):
    pivot = (high + low + price) / 3
    r1 = 2 * pivot - low
    s1 = 2 * pivot - high
    
    action = "觀望"
    color_hex = "#aaaaaa"
    
    entry_price_txt = "-"
    exit_price_txt = "-"
    target_price = 0.0
    stop_price = 0.0
    reasoning = "數據盤整中"
    hold_time = "-"

    if strategy_type == 'day': 
        stop_price = low * 0.99
        target_price = r1 if r1 > price else price * 1.02
        hold_time = "當日沖銷"
        if price > m5 and price > pivot:
            action = "🔥 強力作多"; color_hex = "#FF2B2B"
            entry_price_txt = f"{pivot:.1f} 附近 (平盤上)"
            exit_price_txt = f"跌破 {m5:.1f} (均價線)"
            reasoning = "量價齊揚站上樞紐，多方動能強勁，適合順勢操作。"
        elif price < pivot:
            action = "🧊 偏空操作"; color_hex = "#00E050"
            entry_price_txt = f"反彈 {pivot:.1f} 不過"
            exit_price_txt = "急殺出量或尾盤"
            reasoning = "股價受制於樞紐之下，上方賣壓重，建議偏空思考。"
        else:
            action = "⚖️ 區間震盪"; color_hex = "#FF9F1C"
            entry_price_txt = f"{s1:.1f} 支撐處"
            exit_price_txt = f"{r1:.1f} 壓力處"
            reasoning = "多空膠著，建議區間來回操作或觀望。"
            
    elif strategy_type == 'short':
        stop_price = m20
        target_price = price * 1.08
        hold_time = "3-5 天"
        if price > m5 and m5 > m20:
            action = "🚀 穩健買進"; color_hex = "#FF2B2B"
            entry_price_txt = f"回測 {m5:.1f} (5日線)"
            exit_price_txt = f"跌破 {m20:.1f} (月線)"
            reasoning = "均線多頭排列，短線趨勢向上，拉回找買點勝率高。"
        elif price < m5:
            action = "📉 等待止穩"; color_hex = "#FF9F1C"
            entry_price_txt = f"接近 {m20:.1f} 收紅K"
            exit_price_txt = "有效跌破月線"
            reasoning = "短線漲多乖離修正，等待回測月線支撐確認後再進場。"
            
    elif strategy_type == 'long':
        stop_price = m60
        target_price = price * 1.20
        hold_time = "1-3 個月"
        if price > m60:
            action = "🐢 長線續抱"; color_hex = "#FF2B2B"
            entry_price_txt = f"{m60:.1f} (季線) 附近"
            exit_price_txt = "季線下彎且股價跌破"
            reasoning = "股價站穩生命線(季線)，長線保護短線，適合波段持有。"
        else:
            action = "⏳ 觀望"; color_hex = "#aaaaaa"
            entry_price_txt = "突破季線帶量"
            exit_price_txt = "續破底"
            reasoning = "目前仍處於空頭或整理架構，建議等待趨勢翻多。"
            
    else: 
        stop_price = m20
        target_price = price * 1.05
        hold_time = "視情況"
        if price > m20: 
            action = "💪 強勢持有"; color_hex = "#FF2B2B"
            entry_price_txt = "量縮不破低"
            exit_price_txt = "爆量收黑"
            reasoning = "人氣匯聚強勢股，沿著趨勢操作，轉弱即跑。"
        else: 
            action = "⚠️ 轉弱減碼"; color_hex = "#00E050"
            entry_price_txt = "暫不建議"
            exit_price_txt = f"反彈 {m20:.1f} 減碼"
            reasoning = "籌碼鬆動轉弱，建議反彈減碼降低風險。"

    return action, color_hex, target_price, stop_price, entry_price_txt, exit_price_txt, hold_time, reasoning

# --- 7. 詳細診斷卡 ---
def render_detailed_card(code, name, price, df, source_type="yahoo", key_prefix="btn", rank=None, strategy_info=None):
    chg_color = "black"
    pct_txt = ""
    action_title = "計算中"
    action_color_hex = "#aaaaaa"
    target_val = 0.0
    stop_val = 0.0
    entry_txt = "-"
    exit_txt = "-"
    hold_txt = "-"
    reason_txt = "資料不足"
    
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
                
                action_title, action_color_hex, target_val, stop_val, entry_txt, exit_txt, hold_txt, reason_txt = generate_trade_advice(
                    curr, high, low, m5, m20, m60, rsi, strat_type
                )
        except: pass
    
    rank_tag = f"#{rank}" if rank else ""
    
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([1.3, 1.3, 3.5, 0.8])
        with c1:
            st.markdown(f"#### {rank_tag} {name}")
            st.caption(f"代號: {code}")
        with c2:
            st.markdown(f"#### {price:.2f}")
            st.markdown(f":{chg_color}[{pct_txt}]")
        with c3:
            st.markdown(
                f"""
                <div style="display:flex; flex-direction:column; justify-content:center; height:100%;">
                    <div style="color:{action_color_hex}; font-weight:900; font-size:1.3rem;">{action_title}</div>
                    <div style="color:#888; font-size:0.85rem;">{strategy_info if strategy_info else '監控中'}</div>
                </div>
                """, 
                unsafe_allow_html=True
            )
        with c4:
            st.write("") 
            if st.button("分析", key=f"{key_prefix}_{code}", use_container_width=True):
                return True
        
        st.markdown("<hr class='compact'>", unsafe_allow_html=True)
        
        d1, d2, d3, d4 = st.columns(4)
        with d1:
            st.markdown(f"🎯 **目標價** : `{target_val:.2f}`")
        with d2:
            st.markdown(f"🛡️ **停損價** : `{stop_val:.2f}`")
        with d3:
            st.caption(f"📥 **建議入場**\n{entry_txt}")
        with d4:
            st.caption(f"📤 **建議離場**\n{exit_txt}")
            
        st.markdown("<hr class='compact'>", unsafe_allow_html=True)
        e1, e2 = st.columns([3, 1])
        with e1:
            st.info(f"💡 **AI觀點**: {reason_txt}")
        with e2:
            st.markdown(f"📅 **持股**: `{hold_txt}`")

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
    
    fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='#FF00FF', width=1), name='MA5 (週)'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='#FFA500', width=1), name='MA20 (月)'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA60'], line=dict(color='#0000FF', width=1), name='MA60 (季)'), row=1, col=1)
    
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
        st.info("計算基礎：(最高+最低+收盤)/3，適用於隔日沖參考")
        cp1, cp2, cp3 = st.columns(3)
        cp1.metric("壓力位 (R1)", f"{r1:.2f}", help="預估上方第一道壓力")
        cp2.metric("中軸 (Pivot)", f"{pivot:.2f}", help="多空分水嶺，站上偏多")
        cp3.metric("支撐位 (S1)", f"{s1:.2f}", help="預估下方第一道支撐")
