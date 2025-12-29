import streamlit as st
import time
import twstock
import pandas as pd
import re
import importlib
from datetime import datetime, timedelta, timezone

import stock_db as db
import stock_ui as ui

# 嘗試載入知識庫，若失敗則給空值，避免程式崩潰
try:
    import knowledge
    importlib.reload(knowledge)
    from knowledge import STOCK_TERMS, STRATEGY_DESC, KLINE_PATTERNS
except ImportError:
    STOCK_TERMS = {}; STRATEGY_DESC = "知識庫載入失敗，請檢查 knowledge.py"; KLINE_PATTERNS = {}

st.set_page_config(page_title="股市戰情室 V96", layout="wide", page_icon="📈")

# --- 核心運算引擎 ---
def analyze_stock_battle_data(df):
    if df is None or len(df) < 30: return None
    latest = df.iloc[-1]
    close = latest['Close']
    
    # 技術指標計算
    ma5 = df['Close'].rolling(5).mean().iloc[-1]
    ma20 = df['Close'].rolling(20).mean().iloc[-1]
    ma60 = df['Close'].rolling(60).mean().iloc[-1]
    std20 = df['Close'].rolling(20).std().iloc[-1]
    
    exp12 = df['Close'].ewm(span=12, adjust=False).mean()
    exp26 = df['Close'].ewm(span=26, adjust=False).mean()
    macd = exp12 - exp26
    signal = macd.ewm(span=9, adjust=False).mean()
    
    delta = df['Close'].diff()
    u = delta.copy(); d = delta.copy()
    u[u < 0] = 0; d[d > 0] = 0
    rs = u.rolling(14).mean() / d.abs().rolling(14).mean()
    rsi = (100 - 100/(1+rs)).iloc[-1]
    
    vol_ma5 = df['Volume'].rolling(5).mean().iloc[-1]
    vol_ratio = latest['Volume'] / vol_ma5 if vol_ma5 > 0 else 1
    
    # 評分系統
    score = 0
    reasons = []
    
    if close > ma20: score += 20; reasons.append("股價站上月線")
    if ma5 > ma20: score += 10; reasons.append("短均線黃金交叉")
    if macd.iloc[-1] > signal.iloc[-1]: score += 15; reasons.append("MACD 多頭")
    if 50 <= rsi <= 75: score += 15; reasons.append("RSI 強勢區")
    if vol_ratio > 1.2: score += 20; reasons.append("量能放大")
    if ma20 > ma60: score += 10; reasons.append("中長線多頭排列")
    
    # 包裝結果
    heat = "🔥🔥🔥 極熱" if vol_ratio > 2.0 else ("🔥 溫熱" if vol_ratio > 1.3 else "☁️ 普通")
    heat_color = "#FF0000" if vol_ratio > 2.0 else "#FF4500"
    
    short_action = "積極買進" if score >= 70 else "拉回佈局" if score >= 50 else "觀望"
    mid_trend = "多頭" if ma20 > ma60 else "整理"
    long_bias = ((close - ma60) / ma60) * 100
    long_action = "乖離過大" if long_bias > 20 else "超跌" if long_bias < -15 else "合理"
    
    return {
        "score": score,
        "probability": min(score + 10, 95),
        "heat": heat, "heat_color": heat_color, "reasons": reasons,
        "short_action": short_action, "short_target": f"{close*1.05:.2f}",
        "mid_trend": mid_trend, "mid_action": "續抱" if close > ma20 else "減碼", "mid_support": f"{ma20:.2f}",
        "long_action": long_action, "long_ma60": f"{ma60:.2f}",
        "pressure": ma20 + 2*std20, "support": ma20 - 2*std20, 
        "suggest_price": close if score > 70 else ma20, "close": close
    }

def inject_realtime_data(df, code):
    # 簡單封裝，直接使用 DB 抓回來的資料
    if df is None or df.empty: return df, None, None
    latest = df.iloc[-1]
    rt_pack = {
        'latest_trade_price': latest['Close'],
        'high': latest['High'],
        'low': latest['Low'],
        'accumulate_trade_volume': latest['Volume'] / 1000,
        'previous_close': df.iloc[-2]['Close'] if len(df)>1 else latest['Open']
    }
    return df, None, rt_pack

def solve_stock_id(val):
    """
    V96 修復版搜尋邏輯：
    1. 清理輸入
    2. 如果是4碼數字 -> 直接回傳
    3. 如果是中文 -> 遍歷 twstock 代號庫反查
    """
    val = str(val).strip()
    if not val: return None, None
    
    # 1. 嘗試直接當作代號
    clean_code = re.sub(r'[^\d]', '', val)
    if len(clean_code) == 4:
        # 嘗試找名稱 (選用)
        name = clean_code
        if clean_code in twstock.codes:
            name = twstock.codes[clean_code].name
        return clean_code, name
        
    # 2. 嘗試當作中文名稱搜尋
    for code, data in twstock.codes.items():
        if data.type in ["股票", "ETF"]:
            if val == data.name: # 完全符合
                return code, data.name
            
    # 3. 模糊搜尋 (如果完全符合沒找到)
    for code, data in twstock.codes.items():
        if data.type in ["股票", "ETF"]:
            if val in data.name:
                return code, data.name
                
    return None, None

# --- Session 初始化 ---
if 'scan_pool' not in st.session_state:
    try:
        all_codes = [c for c in twstock.codes.values() if c.type in ["股票", "ETF"]]
        st.session_state['scan_pool'] = sorted([c.code for c in all_codes])
        groups = sorted(list(set(c.group for c in all_codes if c.group)))
        st.session_state['all_groups'] = ["🔍 全部上市櫃"] + groups
    except:
        st.session_state['scan_pool'] = ['2330', '2317', '2454']
        st.session_state['all_groups'] = ["全部"]

if 'view_mode' not in st.session_state: st.session_state['view_mode'] = 'welcome'
if 'current_stock' not in st.session_state: st.session_state['current_stock'] = ''
if 'current_name' not in st.session_state: st.session_state['current_name'] = ''
if 'scan_results' not in st.session_state: st.session_state['scan_results'] = []

def nav_to(mode, code=None, name=None):
    if code: 
        st.session_state['current_stock'] = code
        st.session_state['current_name'] = name
    st.session_state['view_mode'] = mode

def handle_search():
    val = st.session_state.search_input_val
    code, name = solve_stock_id(val)
    if code:
        nav_to('analysis', code, name)
        st.session_state.search_input_val = "" # 清空
    else:
        st.toast(f"找不到 '{val}'，請確認名稱或代號", icon="⚠️")

# --- 側邊欄 ---
with st.sidebar:
    st.title("🎮 戰情控制台")
    st.divider()
    st.text_input("🔍 搜尋 (代號/名稱)", key="search_input_val", on_change=handle_search)
    
    with st.container(border=True):
        st.markdown("### 🤖 AI 掃描雷達")
        sel_group = st.selectbox("1️⃣ 範圍", st.session_state.get('all_groups', ["全部"]))
        
        strat_map = {
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
            st.session_state['scan_results'] = [] # 清空舊結果
            nav_to('scan', strat_map[sel_strat_name])
            st.rerun()

    st.divider()
    if st.button("📖 股市新手村"): nav_to('learn'); st.rerun()
    if st.button("🏠 回首頁"): nav_to('welcome'); st.rerun()
    st.caption("Ver: 96.0 (修復版)")

# --- 主程式 ---
mode = st.session_state['view_mode']

if mode == 'welcome':
    ui.render_header("👋 股市戰情室 V96")
    st.success("✅ 系統修復報告：\n1. 排名徽章樣式已優化 (Flexbox置中)。\n2. 搜尋功能已修復 (支援代號與中文名稱)。\n3. 新手村內容已回歸。")

elif mode == 'analysis':
    code = st.session_state['current_stock']
    name = st.session_state['current_name']
    
    # 畫面容器
    main_placeholder = st.empty()
    
    with main_placeholder.container():
        ui.render_header(f"{name} ({code})", show_monitor=True)
        
        # 1. 抓資料
        fid, stock, df, src = db.get_stock_data(code)
        
        if src == "fail":
            st.error(f"⚠️ 無法取得 {code} 資料。")
        else:
            # 2. 數據處理
            df, _, rt_pack = inject_realtime_data(df, code)
            
            curr = df['Close'].iloc[-1]; prev = df['Close'].iloc[-2]
            chg = curr - prev; pct = (chg/prev)*100
            high = df['High'].iloc[-1]; low = df['Low'].iloc[-1]
            amp = ((high - low) / prev) * 100
            vol = df['Volume'].iloc[-1]
            
            vy = df['Volume'].iloc[-2]
            va = df['Volume'].rolling(5).mean().iloc[-1]
            vs = "爆量" if vol > vy*1.5 else "量縮" if vol < vy*0.6 else "正常"
            
            # 3. 渲染
            info = stock.info.get('longBusinessSummary', '')
            ui.render_company_profile(db.translate_text(info))
            
            ui.render_metrics_dashboard(curr, chg, pct, high, low, amp, "一般", vol, vy, va, vs, 0, 0, None, None, rt_pack)
            ui.render_chart(df, f"{name} K線圖", db.get_color_settings(code))
            
            battle = analyze_stock_battle_data(df)
            if battle: ui.render_ai_battle_dashboard(battle)

    ui.render_back_button(lambda: nav_to('welcome'))

elif mode == 'learn':
    ui.render_header("📖 股市新手村")
    t1, t2, t3 = st.tabs(["策略說明", "名詞解釋", "K線型態"])
    
    with t1: st.markdown(STRATEGY_DESC)
    with t2:
        for cat, items in STOCK_TERMS.items():
            with st.expander(cat, expanded=True):
                for k, v in items.items(): ui.render_term_card(k, v)
    with t3:
        st.info("常見反轉訊號教學")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🔥 多方訊號")
            for k, v in KLINE_PATTERNS.get('bull', {}).items(): ui.render_kline_pattern_card(k, v)
        with c2:
            st.subheader("❄️ 空方訊號")
            for k, v in KLINE_PATTERNS.get('bear', {}).items(): ui.render_kline_pattern_card(k, v)
            
    ui.render_back_button(lambda: nav_to('welcome'))

elif mode == 'scan':
    stype = st.session_state['current_stock']
    target = st.session_state.get('scan_target_group', '全部')
    title_map = {'super_win': '💎 超強力推薦必賺', 'day': '⚡ 強力當沖', 'short': '📈 穩健短線'}
    ui.render_header(f"🤖 {target} ⨉ {title_map.get(stype, stype)}")
    
    display_list = st.session_state.get('scan_results', [])
    
    # 如果列表是空的，執行掃描
    if not display_list:
        pool = st.session_state['scan_pool']
        # 根據群組篩選
        if target != "🔍 全部上市櫃":
            pool = [c for c in pool if c in twstock.codes and twstock.codes[c].group == target]
        
        limit = st.session_state.get('scan_limit', 30)
        bar = st.progress(0)
        raw_results = []
        count = 0
        
        for i, c in enumerate(pool):
            if count >= limit: break
            bar.progress(min((count+1)/limit, 1.0))
            
            try:
                # 這裡使用 db.get_stock_data
                _, _, df, src = db.get_stock_data(c)
                if df is not None and len(df) > 30:
                    battle = analyze_stock_battle_data(df)
                    score = battle['score']
                    
                    valid = False
                    info_txt = ""
                    
                    if stype == 'super_win':
                        if score >= 60: valid = True; info_txt = f"趨勢強 | 評分 {score}"
                    elif stype == 'day':
                        vol = df['Volume'].iloc[-1]; vy = df['Volume'].iloc[-2]
                        if vol > vy*1.5: valid = True; info_txt = "爆量攻擊"
                    elif stype == 'short':
                        if score >= 40: valid = True; info_txt = "多頭排列"
                    elif stype == 'top':
                         if df['Volume'].iloc[-1] > 2000: valid = True; info_txt = "熱門股"
                         
                    if valid:
                        n = twstock.codes[c].name if c in twstock.codes else c
                        raw_results.append({'c': c, 'n': n, 'p': df['Close'].iloc[-1], 'info': info_txt, 'score': score, 'd': df, 'src': src})
                        count += 1
                time.sleep(0.01)
            except: pass
            
        bar.empty()
        # 排序：高分在前
        raw_results.sort(key=lambda x: x['score'], reverse=True)
        st.session_state['scan_results'] = raw_results
        display_list = raw_results

    if display_list:
        st.success(f"已篩選出 {len(display_list)} 檔標的")
        for i, item in enumerate(display_list):
            if ui.render_detailed_card(item['c'], item['n'], item['p'], item['d'], item['src'], 
                                     key_prefix=f"scan_{stype}", rank=i+1, 
                                     strategy_info=item['info'], score=item['score']):
                nav_to('analysis', item['c'], item['n'])
                st.rerun()
    else:
        st.warning("無符合條件標的")

    ui.render_back_button(lambda: nav_to('welcome'))
