import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

# --- 1. 標題與即時監控 ---
def render_header(title, show_monitor=False):
    c1, c2 = st.columns([3, 1])
    c1.title(title)
    is_live = False
    if show_monitor:
        st.caption("數據來源: Yahoo Finance / TWSE")
        is_live = c2.toggle("🔴 啟動即時盤面", value=False)
    st.divider()
    return is_live

# --- 2. 返回按鈕 (放在底部) ---
def render_back_button(callback_func):
    st.divider()
    # 使用 columns 讓按鈕不要太寬
    _, c2, _ = st.columns([2, 1, 2])
    if c2.button("⬅️ 返回上一頁", use_container_width=True):
        callback_func()

# --- 3. 新手村卡片 ---
def render_term_card(title, content):
    with st.container(border=True):
        st.markdown(f"### 📌 {title}")
        st.info(content)

# --- 4. 公司簡介 ---
def render_company_profile(summary):
    if summary and summary != "暫無詳細描述":
        with st.expander("🏢 公司簡介與業務", expanded=False):
            st.write(summary)

# --- 5. 數據儀表板 ---
def render_metrics_dashboard(curr, chg, pct, high, low, amp, main_force, 
                             vol, vol_yest, vol_avg, vol_status, foreign_held, 
                             color_settings):
    # 第一排：價格與動能
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("成交價", f"{curr:.2f}", f"{chg:.2f} ({pct:.2f}%)", delta_color=color_settings['delta'])
    m2.metric("最高價", f"{high:.2f}")
    m3.metric("最低價", f"{low:.2f}")
    m4.metric("振幅", f"{amp:.2f}%")
    m5.metric("主力動向", main_force)
    
    # 第二排：籌碼與量能
    v1, v2, v3, v4, v5 = st.columns(5)
    v1.metric("今日總量", f"{int(vol/1000):,} 張")
    v2.metric("昨日總量", f"{int(vol_yest/1000):,} 張", f"{int((vol-vol_yest)/1000)} 張")
    v3.metric("5日均量", f"{int(vol_avg/1000):,} 張")
    v4.metric("量能狀態", vol_status)
    v5.metric("外資持股", f"{foreign_held:.1f}%")

# --- 6. 詳細診斷卡 (列表用) ---
def render_detailed_card(code, name, price, df, source_type="yahoo", key_prefix="btn", rank=None, strategy_info=None):
    status_color = "gray"
    trend_txt = "數據分析中..."
    sub_txt = ""
    
    display_name = f"#{rank} {name}" if rank else name
    
    if df is not None:
        try:
            if source_type == "yahoo" and not df.empty and len(df) > 20:
                curr = df['Close'].iloc[-1]
                m5 = df['Close'].rolling(5).mean().iloc[-1]
                m20 = df['Close'].rolling(20).mean().iloc[-1]
                m60 = df['Close'].rolling(60).mean().iloc[-1]
                
                # 簡單趨勢邏輯
                if curr > m5 and m5 > m20: 
                    trend_txt = "🔥 短線強勢"; status_color = "red"
                    sub_txt = "沿5日線上攻"
                elif curr > m20 and m20 > m60: 
                    trend_txt = "📈 多頭排列"; status_color = "orange"
                    sub_txt = "波段趨勢向上"
                elif curr < m20 and m20 < m60: 
                    trend_txt = "❄️ 空頭修正"; status_color = "green" # 台股綠是跌
                    sub_txt = "需留意壓力"
                elif curr < m5:
                    trend_txt = "📉 短線回檔"; status_color = "blue"
                    sub_txt = "跌破5日線"
                else:
                    trend_txt = "⚖️ 區間震盪"; status_color = "gray"
                    sub_txt = "方向不明"
            else:
                trend_txt = "即時報價"; status_color = "blue"
                sub_txt = "TWSE 來源"
        except: pass

    # 卡片外觀
    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns([1, 1.5, 2, 2.5, 1])
        c1.markdown(f"### {code}")
        c2.markdown(f"**{display_name}**")
        c3.metric("現價", f"{price:.2f}")
        
        # 顯示策略資訊或趨勢
        if strategy_info:
            c4.markdown(f"**{strategy_info}**")
            c4.caption(f"{trend_txt}")
        else:
            c4.markdown(f":{status_color}[{trend_txt}]")
            c4.caption(sub_txt)
            
        return c5.button("分析", key=f"{key_prefix}_{code}", use_container_width=True)

# --- 7. K線圖 ---
def render_chart(df, title, color_settings):
    df['MA5'] = df['Close'].rolling(5).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA60'] = df['Close'].rolling(60).mean()
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
    
    # K線
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], 
        name='K線',
        increasing_line_color=color_settings['up'],
        decreasing_line_color=color_settings['down']
    ), row=1, col=1)
    
    # 均線
    fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='#FF00FF', width=1), name='MA5 (週)'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='#FFA500', width=1), name='MA20 (月)'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA60'], line=dict(color='#0000FF', width=1), name='MA60 (季)'), row=1, col=1)
    
    # 成交量
    vol_colors = [color_settings['up'] if c >= o else color_settings['down'] for c, o in zip(df['Close'], df['Open'])]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=vol_colors, name='成交量'), row=2, col=1)
    
    fig.update_layout(
        height=550, 
        xaxis_rangeslider_visible=False, 
        title=dict(text=title, x=0.01),
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", y=1, x=0, yanchor="bottom")
    )
    st.plotly_chart(fig, use_container_width=True)

# --- 8. AI 專業診斷報告 (優化版) ---
def render_ai_report(curr, m5, m20, m60, rsi, bias, high, low):
    st.subheader("🤖 AI 深度戰略分析")
    
    # 計算簡單支撐壓力 (Pivot 概念)
    pivot = (high + low + curr) / 3
    r1 = 2 * pivot - low
    s1 = 2 * pivot - high
    
    # 建立三個頁籤：總評、技術指標、關鍵價位
    t1, t2, t3 = st.tabs(["📊 綜合總評", "⚡ 技術指標", "🎯 關鍵價位"])
    
    with t1:
        score = 0
        if curr > m20: score += 1
        if curr > m60: score += 1
        if rsi < 80: score += 1
        
        st.write("根據多重指標綜合運算：")
        if score == 3:
            st.success("🔥 **極度強勢**：股價位於生命線之上，且動能充沛，適合順勢操作。")
        elif score == 2:
            st.warning("📈 **偏多震盪**：長線保護短線，但需留意短線回檔壓力。")
        else:
            st.error("📉 **弱勢整理**：空方控盤機率高，建議保守觀望，等待打底。")
            
    with t2:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**趨勢研判**")
            if curr > m20: st.write("✅ 站上月線 (多)")
            else: st.write("🔻 跌破月線 (空)")
            if curr > m60: st.write("✅ 站上季線 (多)")
            else: st.write("🔻 跌破季線 (空)")
            
        with c2:
            st.markdown("**動能指標 (RSI)**")
            st.metric("RSI (14)", f"{rsi:.1f}")
            if rsi > 80: st.caption("⚠️ 過熱區")
            elif rsi < 20: st.caption("💎 超賣區")
            else: st.caption("正常區間")
            
        with c3:
            st.markdown("**乖離率 (BIAS)**")
            st.metric("季線乖離", f"{bias:.2f}%")
            if bias > 20: st.caption("⚠️ 正乖離過大")
            elif bias < -20: st.caption("💎 負乖離過大")
    
    with t3:
        c1, c2 = st.columns(2)
        c1.metric("上方壓力 (預估)", f"{r1:.2f}")
        c2.metric("下方支撐 (預估)", f"{s1:.2f}")
        st.caption("*僅供參考，基於今日高低點計算之 Pivot Point")
