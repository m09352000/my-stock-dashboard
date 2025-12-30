import streamlit as st
import time
import pandas as pd
from datetime import datetime, timedelta, timezone

# 匯入模組
import logic_database as db
import logic_ai as ai
import ui_components as ui
import config_data as config

st.set_page_config(page_title="全球股市戰情室 V115", layout="wide", page_icon="🌎")

# --- Session 初始化 ---
if 'market_type' not in st.session_state: st.session_state['market_type'] = 'TW'
if 'view_mode' not in st.session_state: st.session_state['view_mode'] = 'welcome'
if 'current_stock' not in st.session_state: st.session_state['current_stock'] = ''
if 'current_name' not in st.session_state: st.session_state['current_name'] = ''
if 'scan_results' not in st.session_state: st.session_state['scan_results'] = []
if 'scan_pool_tw' not in st.session_state:
    try:
        import twstock
        all_codes = [c for c in twstock.codes.values() if c.type in ["股票", "ETF"]]
        st.session_state['scan_pool_tw'] = sorted([c.code for c in all_codes])
    except:
        st.session_state['scan_pool_tw'] = ['2330', '2317', '2454']

def nav_to(mode, code=None, name=None):
    if code: 
        st.session_state['current_stock'] = code
        st.session_state['current_name'] = name
    st.session_state['view_mode'] = mode

def handle_search():
    val = st.session_state.search_input_val
    code, name = db.solve_stock_id(val)
    if code:
        nav_to('analysis', code, name)
        st.session_state.search_input_val = ""
    else:
        st.toast(f"找不到 '{val}'", icon="⚠️")

# --- 側邊欄 ---
with st.sidebar:
    market = st.radio("🌍 選擇戰情室", ["🇹🇼 台股戰情室", "🇺🇸 美股戰情室"], index=0 if st.session_state['market_type']=='TW' else 1)
    st.session_state['market_type'] = 'TW' if "台股" in market else 'US'
    st.divider()
    ph = "輸入代號 (2330)" if st.session_state['market_type'] == 'TW' else "輸入代號 (NVDA, TSLA)"
    st.text_input("🔍 搜尋", placeholder=ph, key="search_input_val", on_change=handle_search)
    
    with st.container(border=True):
        st.markdown(f"### 🤖 {st.session_state['market_type']} AI 掃描")
        if st.button("🚀 啟動掃描", use_container_width=True):
            st.session_state['current_stock'] = "tomorrow_star" # 預設
            nav_to('scan', "tomorrow_star")
            st.rerun()

    st.divider()
    if st.button("📖 股市新手村"): nav_to('learn'); st.rerun()
    if st.button("🏠 回首頁"): nav_to('welcome'); st.rerun()
    st.caption("Ver: 115.0 (絕對防禦版)")

# --- 主程式 ---
mode = st.session_state['view_mode']
m_type = st.session_state['market_type']

if mode == 'welcome':
    ui.render_header(f"👋 {m_type} 戰情室")
    if m_type == 'TW': st.info("🇹🇼 台股模式啟用")
    else: st.success("🇺🇸 美股模式啟用")

elif mode == 'analysis':
    code = st.session_state['current_stock']
    name = st.session_state['current_name']
    
    # Toggle 移出迴圈 (關鍵修正)
    col_h, col_t = st.columns([3, 1])
    with col_h: st.subheader(f"{name} ({code})")
    with col_t: monitor = st.toggle("🔴 1秒極速刷新", key="monitor_toggle")

    # 1. 抓取歷史與基本面 (Cache)
    fid, stock_info, df_hist, src = db.get_stock_data(code)
    
    main_placeholder = st.empty()
    
    if src == "fail":
        st.error(f"⚠️ 無法取得 {code} 資料。")
    else:
        while True:
            # 2. 抓取即時
            df_display, _, rt_pack = db.get_realtime_data(df_hist, code)
            
            with main_placeholder.container():
                tz = timezone(timedelta(hours=8)) if m_type == 'TW' else timezone(timedelta(hours=-4))
                now_str = datetime.now(tz).strftime('%H:%M:%S')
                ui.render_header("", is_live=monitor, time_str=now_str)
                
                if df_display is not None:
                    curr = df_display['Close'].iloc[-1]
                    prev = df_display['Close'].iloc[-2]
                    chg = curr - prev; pct = (chg/prev)*100
                    high = df_display['High'].iloc[-1]; low = df_display['Low'].iloc[-1]
                    amp = ((high - low) / prev) * 100
                    vol = df_display['Volume'].iloc[-1]
                    vy = df_display['Volume'].iloc[-2]
                    va = df_display['Volume'].rolling(5).mean().iloc[-1]
                    vs = "爆量" if vol > vy*1.5 else "量縮" if vol < vy*0.6 else "正常"
                    
                    unit = "股" if not code.isdigit() else "張"
                    vol_disp = vol if unit == "股" else vol/1000
                    
                    # 這裡會自動翻譯
                    ui.render_fundamental_panel(stock_info)
                    
                    ui.render_metrics_dashboard(curr, chg, pct, high, low, amp, "一般", vol_disp, vy, va, vs, 0, 0, None, None, rt_pack, unit=unit, code=code)
                    
                    # 動態 Key
                    chart_key = f"chart_{code}_{int(time.time())}"
                    ui.render_chart(df_display, f"{name} K線圖", db.get_color_settings(code), key=chart_key)
                    
                    battle = ai.analyze_stock_battle_data(df_display)
                    if battle: ui.render_ai_battle_dashboard(battle)
                else:
                    st.warning("數據載入中...")

            if not monitor: break
            time.sleep(1)

    ui.render_back_button(lambda: nav_to('welcome'))

# Scan 與 Learn 區塊請務必保留 (複製上一版)，此處為節省篇幅省略
elif mode == 'scan':
    # ... (請貼上 scan 程式碼) ...
    st.info("掃描功能")
    ui.render_back_button(lambda: nav_to('welcome'))

elif mode == 'learn':
    ui.render_header("📖 股市新手村")
    # ... (請貼上 learn 程式碼，使用 config.STOCK_TERMS) ...
    ui.render_back_button(lambda: nav_to('welcome'))
