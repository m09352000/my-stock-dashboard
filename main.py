import streamlit as st
import time
import pandas as pd
from datetime import datetime, timedelta

# 匯入我們拆分好的模組
import logic_database as db
import logic_ai as ai
import ui_components as ui
import config_data as config

st.set_page_config(page_title="全球股市戰情室 V104", layout="wide", page_icon="🌎")

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
        groups = sorted(list(set(c.group for c in all_codes if c.group)))
        st.session_state['all_groups_tw'] = ["🔍 全部上市櫃"] + groups
    except:
        st.session_state['scan_pool_tw'] = ['2330', '2317', '2454']
        st.session_state['all_groups_tw'] = ["全部"]

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
        if st.session_state['market_type'] == 'TW':
            sel_group = st.selectbox("1️⃣ 範圍", st.session_state.get('all_groups_tw', ["全部"]))
        else:
            sel_group = st.selectbox("1️⃣ 範圍", ["🔥 美股熱門百大"])

        strat_map = {
            "🌅 明日之星潛力股": "tomorrow_star",
            "💎 超強力推薦必賺": "super_win",
            "⚡ 強力當沖": "day",
            "📈 穩健短線": "short",
            "🐢 長線安穩": "long",
            "🏆 熱門強勢": "top"
        }
        sel_strat_name = st.selectbox("2️⃣ 策略", list(strat_map.keys()))
        scan_limit = st.slider("3️⃣ 上限", 10, 100, 30)
        
        if st.button("🚀 啟動掃描", use_container_width=True):
            st.session_state['scan_target_group'] = sel_group
            st.session_state['current_stock'] = strat_map[sel_strat_name]
            st.session_state['scan_limit'] = scan_limit
            st.session_state['scan_results'] = []
            nav_to('scan', strat_map[sel_strat_name])
            st.rerun()

    st.divider()
    if st.button("📖 股市新手村"): nav_to('learn'); st.rerun()
    if st.button("🏠 回首頁"): nav_to('welcome'); st.rerun()
    st.caption("Ver: 104.0 (模組化重構版)")

# --- 主頁面邏輯 ---
mode = st.session_state['view_mode']
m_type = st.session_state['market_type']

if mode == 'welcome':
    ui.render_header(f"👋 {m_type} 戰情室 V104")
    if m_type == 'TW': st.info("🇹🇼 台股模式啟用。資料來源：TWSE / Yahoo Finance。")
    else: st.success("🇺🇸 美股模式啟用。資料來源：Yahoo Finance (Realtime)。")

elif mode == 'analysis':
    code = st.session_state['current_stock']
    name = st.session_state['current_name']
    
    main_placeholder = st.empty()
    with main_placeholder.container():
        ui.render_header(f"{name} ({code})", show_monitor=True)
        fid, stock, df, src = db.get_stock_data(code)
        
        if src == "fail":
            st.error(f"⚠️ 無法取得 {code} 資料。")
        else:
            df, _, rt_pack = db.get_realtime_data(df, code)
            
            curr = df['Close'].iloc[-1]; prev = df['Close'].iloc[-2]
            chg = curr - prev; pct = (chg/prev)*100
            high = df['High'].iloc[-1]; low = df['Low'].iloc[-1]
            amp = ((high - low) / prev) * 100
            vol = df['Volume'].iloc[-1]
            vy = df['Volume'].iloc[-2]
            va = df['Volume'].rolling(5).mean().iloc[-1]
            vs = "爆量" if vol > vy*1.5 else "量縮" if vol < vy*0.6 else "正常"
            
            unit = "股" if not code.isdigit() else "張"
            vol_disp = vol if unit == "股" else vol/1000
            
            info = stock.info.get('longBusinessSummary', '')
            ui.render_company_profile(db.translate_text(info))
            ui.render_metrics_dashboard(curr, chg, pct, high, low, amp, "一般", vol_disp, vy, va, vs, 0, 0, None, None, rt_pack, unit=unit, code=code)
            ui.render_chart(df, f"{name} K線圖", db.get_color_settings(code))
            
            battle = ai.analyze_stock_battle_data(df)
            if battle: ui.render_ai_battle_dashboard(battle)

    ui.render_back_button(lambda: nav_to('welcome'))

elif mode == 'scan':
    stype = st.session_state['current_stock']
    target = st.session_state.get('scan_target_group', '全部')
    title_map = {'tomorrow_star': '🌅 明日之星', 'super_win': '💎 超強力必賺', 'day': '⚡ 強力當沖'}
    ui.render_header(f"🤖 {m_type} {target} ⨉ {title_map.get(stype, stype)}")
    
    display_list = st.session_state.get('scan_results', [])
    
    if not display_list:
        if m_type == 'TW':
            pool = st.session_state['scan_pool_tw']
            if target != "🔍 全部上市櫃": 
                import twstock
                pool = [c for c in pool if c in twstock.codes and twstock.codes[c].group == target]
        else: pool = config.US_STOCK_POOL
        
        limit = st.session_state.get('scan_limit', 30)
        bar = st.progress(0); raw_results = []; count = 0
        
        for i, c in enumerate(pool):
            if count >= limit: break
            bar.progress(min((count+1)/limit, 1.0))
            try:
                _, _, df, src = db.get_stock_data(c)
                if df is not None and len(df) > 30:
                    battle = ai.analyze_stock_battle_data(df)
                    score = battle['score']
                    w_prob = battle['weekly_prob']
                    
                    close = df['Close'].iloc[-1]; open_p = df['Open'].iloc[-1]
                    high = df['High'].iloc[-1]; vol = df['Volume'].iloc[-1]
                    vol_ma5 = df['Volume'].rolling(5).mean().iloc[-1]
                    ma5 = df['Close'].rolling(5).mean().iloc[-1]
                    
                    scan_reason = ai.generate_scan_reason(df)
                    valid = False
                    
                    if stype == 'tomorrow_star':
                        if close > open_p and close > high * 0.985 and vol > vol_ma5 and close > ma5: valid = True; score += 10
                    elif stype == 'super_win':
                        if score >= 60: valid = True
                    elif stype == 'day':
                        if vol > df['Volume'].iloc[-2]*1.5: valid = True
                    elif stype == 'short':
                        if score >= 40: valid = True
                    elif stype == 'top':
                         thresh = 2000 if m_type == 'TW' else 1000000 
                         if vol > thresh: valid = True
                         
                    if valid:
                        n = c
                        if m_type == 'TW':
                            import twstock
                            if c in twstock.codes: n = twstock.codes[c].name
                        raw_results.append({'c': c, 'n': n, 'p': close, 'info': scan_reason, 'score': score, 'w_prob': w_prob, 'd': df, 'src': src})
                        count += 1
                time.sleep(0.01)
            except: pass
            
        bar.empty()
        raw_results.sort(key=lambda x: x['score'], reverse=True)
        st.session_state['scan_results'] = raw_results
        display_list = raw_results

    if display_list:
        st.success(f"已篩選出 {len(display_list)} 檔標的")
        for i, item in enumerate(display_list):
            if ui.render_detailed_card(item['c'], item['n'], item['p'], item['d'], item['src'], key_prefix=f"scan_{stype}", rank=i+1, strategy_info=item['info'], score=item['score'], w_prob=item.get('w_prob', 50)): 
                nav_to('analysis', item['c'], item['n']); st.rerun()
    else: st.warning("無符合條件標的")
    ui.render_back_button(lambda: nav_to('welcome'))

elif mode == 'learn':
    ui.render_header("📖 股市新手村 (終極版)")
    t1, t2, t3 = st.tabs(["策略解密", "名詞百科", "K線戰法 SOP"])
    with t1: st.markdown(config.STRATEGY_DESC)
    with t2:
        for cat, items in config.STOCK_TERMS.items():
            with st.expander(cat, expanded=True):
                for k, v in items.items(): ui.render_term_card(k, v)
    with t3:
        st.info("💡 K 線反轉訊號與操作 SOP")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🔥 多方訊號")
            for k, v in config.KLINE_PATTERNS.get('bull', {}).items(): ui.render_kline_pattern_card(k, v)
        with c2:
            st.subheader("❄️ 空方訊號")
            for k, v in config.KLINE_PATTERNS.get('bear', {}).items(): ui.render_kline_pattern_card(k, v)
    ui.render_back_button(lambda: nav_to('welcome'))
