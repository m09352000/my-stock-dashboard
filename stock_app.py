# stock_app.py
# V3.1: 主程式 (修復殘留影像)

import streamlit as st
import time
import pandas as pd
from datetime import datetime, timedelta, timezone

# 匯入模組
import logic_database as db
import logic_ai as ai
import ui_components as ui
import config_data as config

st.set_page_config(page_title="全球股市戰情室 V3.1", layout="wide", page_icon="📈")

# Session 初始化
if 'market_type' not in st.session_state: st.session_state['market_type'] = 'TW'
if 'view_mode' not in st.session_state: st.session_state['view_mode'] = 'welcome'
if 'current_stock' not in st.session_state: st.session_state['current_stock'] = ''
if 'current_name' not in st.session_state: st.session_state['current_name'] = ''

# 主要容器
main_container = st.container()

def nav_to(mode, code=None, name=None):
    if code: 
        st.session_state['current_stock'] = code
        st.session_state['current_name'] = name
    st.session_state['view_mode'] = mode

def handle_search():
    val = st.session_state.search_input_val
    if val:
        code, name = db.solve_stock_id(val)
        nav_to('analysis', code, name)
        st.session_state.search_input_val = ""

# --- 側邊欄 ---
with st.sidebar:
    st.title("📈 戰情控制台")
    mode_sw = st.radio("市場", ["🇹🇼 台股 (FinMind)", "🇺🇸 美股"], index=0)
    st.session_state['market_type'] = 'TW' if "台股" in mode_sw else 'US'
    
    st.text_input("🔍 搜尋代號", key="search_input_val", on_change=handle_search)
    st.divider()
    
    st.markdown("### 🤖 AI 掃描")
    if st.button("🚀 啟動掃描 (測試)"):
        st.toast("為避免 FinMind 流量超限，目前僅展示範例。", icon="🛡️")
        st.session_state['scan_results'] = [{'c':'2330','n':'台積電','p':1000,'info':'均線多頭','score':90}]
        nav_to('scan')
        
    st.divider()
    if st.button("📖 股市新手村"): nav_to('learn')
    if st.button("🏠 回首頁"): nav_to('welcome')

# --- 主畫面 ---
with main_container:
    mode = st.session_state['view_mode']
    
    if mode == 'welcome':
        ui.render_header("👋 歡迎來到股市戰情室 V3.1")
        st.success("✅ 核心引擎已升級為 FinMind + Yahoo 雙刀流")
        st.info("✅ 已修復殘留影像問題，並大幅充實個股情報")

    elif mode == 'analysis':
        code = st.session_state['current_stock']
        name = st.session_state['current_name']
        
        col_title, col_toggle = st.columns([3, 1])
        with col_title: st.subheader(f"{code} 個股分析")
        with col_toggle: monitor = st.toggle("🔴 即時連線", value=True)
        
        fid, stock_info, df_hist, src = db.get_stock_data(code)
        
        # 【關鍵修復】建立一個專用的空白容器，所有會動的東西都放進去
        dynamic_placeholder = st.empty()
        
        if src == 'fail':
            st.error(f"無法取得 {code} 資料")
        else:
            first_run = True
            while first_run or monitor:
                first_run = False
                df_display, _, rt_pack = db.get_realtime_data(df_hist, code)
                
                # 【關鍵修復】使用 .container() 包住所有渲染內容
                # 這樣每次迴圈都會徹底清空這個 container，不會有殘留
                with dynamic_placeholder.container():
                    tz = timezone(timedelta(hours=8))
                    now_str = datetime.now(tz).strftime('%H:%M:%S')
                    ui.render_header("", is_live=monitor, time_str=now_str)
                    
                    if df_display is not None and not df_display.empty:
                        curr = df_display['Close'].iloc[-1]
                        prev = df_display['Close'].iloc[-2] if len(df_display) > 1 else curr
                        open_p = df_display['Open'].iloc[-1]
                        high = df_display['High'].iloc[-1]
                        low = df_display['Low'].iloc[-1]
                        vol = df_display['Volume'].iloc[-1]
                        
                        chg = curr - prev
                        pct = (chg / prev) * 100 if prev != 0 else 0
                        
                        # 1. 顯示基本面 (含公司介紹)
                        ui.render_fundamental_panel(stock_info)
                        
                        # 2. 顯示 8 格儀表板
                        ui.render_metrics_dashboard(
                            curr, chg, pct, high, low, open_p, prev, vol, code, rt_pack
                        )
                        
                        # 3. 顯示圖表
                        ui.render_chart(df_display, f"{code} K線圖", {}, key=f"chart_{time.time()}")
                        
                        # 4. 顯示 AI 分析
                        battle = ai.analyze_stock_battle_data(df_display)
                        if battle: ui.render_ai_battle_dashboard(battle)
                    else: st.warning("數據讀取中...")
                
                if not monitor: break
                time.sleep(3)

    elif mode == 'learn':
        ui.render_header("📖 股市新手村 (百科全書版)")
        t1, t2, t3 = st.tabs(["⚔️ 策略心法", "📚 股市百科", "📈 K線戰法"])
        with t1: st.markdown(config.STRATEGY_DESC)
        with t2:
            for cat, items in config.STOCK_TERMS.items():
                with st.expander(cat, expanded=True):
                    for k, v in items.items():
                        st.markdown(f"#### {k}")
                        st.markdown(v)
                        st.divider()
        with t3:
            st.info("💡 經典反轉型態 SOP")
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("🔥 多方訊號")
                for k, v in config.KLINE_PATTERNS.get('bull', {}).items():
                    ui.render_kline_pattern_card(k, v)
            with c2:
                st.subheader("❄️ 空方訊號")
                for k, v in config.KLINE_PATTERNS.get('bear', {}).items():
                    ui.render_kline_pattern_card(k, v)
        ui.render_back_button(lambda: nav_to('welcome'))
        
    elif mode == 'scan':
        ui.render_header("🤖 AI 掃描結果")
        results = st.session_state.get('scan_results', [])
        for i, item in enumerate(results):
            if ui.render_detailed_card(item['c'], item['n'], item['p'], None, 'FinMind', 'scan', i+1, item['info'], item['score'], 90):
                nav_to('analysis', item['c'], item['n'])
                st.rerun()
        ui.render_back_button(lambda: nav_to('welcome'))
