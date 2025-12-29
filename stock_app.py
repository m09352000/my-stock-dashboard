import streamlit as st
import time
import twstock
import pandas as pd
import re
import importlib
from datetime import datetime, time as dt_time, timedelta, timezone

import stock_db as db
import stock_ui as ui

try:
    import knowledge
    importlib.reload(knowledge)
    from knowledge import STOCK_TERMS, STRATEGY_DESC, KLINE_PATTERNS
except:
    STOCK_TERMS = {}; STRATEGY_DESC = "System Loading..."; KLINE_PATTERNS = {}

st.set_page_config(page_title="股市戰情室 V94", layout="wide", page_icon="📈")

# --- 核心：AI 戰情運算引擎 ---
def analyze_stock_battle_data(df):
    if df is None or len(df) < 30: return None
    latest = df.iloc[-1]
    close = latest['Close']
    
    # 指標計算
    exp12 = df['Close'].ewm(span=12, adjust=False).mean()
    exp26 = df['Close'].ewm(span=26, adjust=False).mean()
    macd = exp12 - exp26
    signal = macd.ewm(span=9, adjust=False).mean()
    
    delta = df['Close'].diff()
    u = delta.copy(); d = delta.copy()
    u[u < 0] = 0; d[d > 0] = 0
    rs = u.rolling(14).mean() / d.abs().rolling(14).mean()
    rsi = (100 - 100/(1+rs)).iloc[-1]
    
    ma5 = df['Close'].rolling(5).mean().iloc[-1]
    ma20 = df['Close'].rolling(20).mean().iloc[-1]
    ma60 = df['Close'].rolling(60).mean().iloc[-1]
    
    std20 = df['Close'].rolling(20).std().iloc[-1]
    bbu = ma20 + 2 * std20
    bbl = ma20 - 2 * std20

    # 評分
    score = 0; reasons = []
    if close > ma20: score += 20; reasons.append("股價站上月線")
    if ma5 > ma20: score += 10; reasons.append("短均線黃金交叉")
    if macd.iloc[-1] > signal.iloc[-1]: score += 10; reasons.append("MACD 多頭")
    if 50 <= rsi <= 75: score += 20; reasons.append("RSI 強勢區")
    
    vol_ma5 = df['Volume'].rolling(5).mean().iloc[-1]
    vol_ratio = latest['Volume'] / vol_ma5 if vol_ma5 > 0 else 1
    if vol_ratio > 1.2: score += 20; reasons.append("量能放大")
    
    # 結果包裝
    heat = "🔥🔥🔥 極熱" if vol_ratio > 2.0 else ("🔥 溫熱" if vol_ratio > 1.3 else "☁️ 普通")
    heat_color = "#FF0000" if vol_ratio > 2.0 else "#FF4500"
    
    short_action = "積極買進" if score >= 70 else ("拉回佈局" if score >= 50 else "觀望")
    mid_trend = "多頭" if ma20 > ma60 else "整理"
    long_bias = ((close - ma60) / ma60) * 100
    long_action = "乖離過大" if long_bias > 20 else ("超跌" if long_bias < -15 else "合理")
    
    return {
        "score": score, "probability": min(score + 10, 95),
        "heat": heat, "heat_color": heat_color, "reasons": reasons,
        "short_action": short_action, "short_entry": "5日線", "short_target": f"{close*1.05:.2f}",
        "mid_trend": mid_trend, "mid_action": "續抱" if close>ma20 else "減碼", "mid_support": f"{ma20:.2f}",
        "long_bias": long_bias, "long_action": long_action, "long_ma60": f"{ma60:.2f}",
        "pressure": bbu, "support": bbl, "suggest_price": close if score > 70 else ma20, "close": close
    }

# --- 容錯版即時資料注入 ---
def inject_realtime_data(df, code):
    if df is None or df.empty: return df, None, None
    try:
        last_date = df.index[-1].date()
        today = datetime.now(timezone(timedelta(hours=8))).date()
        
        real = twstock.realtime.get(code)
        if real['success']:
            rt = real['realtime']
            if rt['latest_trade_price'] != '-' and rt['latest_trade_price'] is not None:
                latest = float(rt['latest_trade_price'])
                high = float(rt['high']); low = float(rt['low']); open_p = float(rt['open'])
                vol = float(rt['accumulate_trade_volume'])
                
                if last_date < today:
                    pass # Yahoo 尚未更新今日K棒，暫不強制補入，避免索引衝突
                else:
                    last_idx = df.index[-1]
                    df.at[last_idx, 'Close'] = latest
                    df.at[last_idx, 'High'] = max(high, df.at[last_idx, 'High'])
                    df.at[last_idx, 'Low'] = min(low, df.at[last_idx, 'Low'])
                    df.at[last_idx, 'Volume'] = int(vol) * 1000
                
                rt_pack = {'latest_trade_price': latest, 'high': high, 'low': low, 'accumulate_trade_volume': vol, 'previous_close': open_p}
                bid_ask = {'bid_price': rt.get('best_bid_price', []), 'bid_volume': rt.get('best_bid_volume', []), 'ask_price': rt.get('best_ask_price', []), 'ask_volume': rt.get('best_ask_volume', [])}
                return df, bid_ask, rt_pack
    except: pass
    
    # Fallback
    latest_row = df.iloc[-1]
    rt_pack_fake = {
        'latest_trade_price': latest_row['Close'],
        'high': latest_row['High'],
        'low': latest_row['Low'],
        'accumulate_trade_volume': latest_row['Volume'] / 1000,
        'previous_close': df.iloc[-2]['Close'] if len(df) > 1 else latest_row['Open']
    }
    return df, None, rt_pack_fake

def solve_stock_id(val):
    val = str(val).strip()
    if not val: return None, None
    clean_val = re.sub(r'[^\w]', '', val)
    if clean_val.isdigit() and len(clean_val) == 4:
        return clean_val, clean_val
    return None, None

# --- Session State 初始化 (V94: 預載所有代號) ---
defaults = {
    'view_mode': 'welcome', 'user_id': None, 'page_stack': ['welcome'],
    'current_stock': "", 'current_name': "", 'scan_pool': [], 
    'scan_target_group': "🔍 全部上市櫃", 'scan_results': [], 'monitor_active': False
}
for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

# 初始化掃描池 (只做一次)
if not st.session_state['scan_pool']:
    try:
        # 讀取 twstock 所有代號，過濾出股票與ETF
        all_codes = [c for c in twstock.codes.values() if c.type in ["股票", "ETF"]]
        st.session_state['scan_pool'] = sorted([c.code for c in all_codes])
        
        # 建立分類選單
        groups = sorted(list(set(c.group for c in all_codes if c.group)))
        st.session_state['all_groups'] = ["🔍 全部上市櫃"] + groups
    except:
        # 如果 twstock 連代號庫都讀不到，就用備用清單
        st.session_state['scan_pool'] = ['2330', '2317', '2454', '2603', '2609', '4967', '3231']
        st.session_state['all_groups'] = ["🔍 全部上市櫃"]

def nav_to(mode, code=None, name=None):
    if code:
        st.session_state['current_stock'] = code
        st.session_state['current_name'] = name
    st.session_state['view_mode'] = mode

def go_back():
    st.session_state['view_mode'] = 'welcome'

def handle_search():
    raw = st.session_state.search_input_val
    if raw:
        code, name = solve_stock_id(raw)
        if code: nav_to('analysis', code, name); st.session_state.search_input_val = ""
        else: st.toast(f"請輸入4碼代號", icon="⚠️")

# --- 側邊欄 Sidebar ---
with st.sidebar:
    st.title("🎮 戰情控制台")
    st.divider()
    st.text_input("🔍 輸入代號 (如 4967)", key="search_input_val", on_change=handle_search)
    
    with st.container(border=True):
        st.markdown("### 🤖 AI 掃描雷達")
        
        # V94: 恢復分類與策略選擇
        sel_group = st.selectbox("1️⃣ 範圍", st.session_state.get('all_groups', ["全部"]), index=0)
        strat_map = {"⚡ 強力當沖": "day", "📈 穩健短線": "short", "🐢 長線安穩": "long", "🏆 熱門強勢": "top"}
        sel_strat_name = st.selectbox("2️⃣ 策略", list(strat_map.keys()))
        
        # V94: 新增數量限制，避免跑太久
        scan_limit = st.slider("3️⃣ 掃描數量上限", 10, 200, 50)
        
        if st.button("🚀 啟動掃描", use_container_width=True):
            st.session_state['scan_target_group'] = sel_group
            st.session_state['current_stock'] = strat_map[sel_strat_name]
            st.session_state['scan_limit'] = scan_limit # 存入 session
            st.session_state['scan_results'] = []
            nav_to('scan', strat_map[sel_strat_name]); st.rerun()

    st.divider()
    if st.button("📖 股市新手村"): nav_to('learn'); st.rerun()
    if st.button("💬 戰友留言板"): nav_to('chat'); st.rerun()
    if st.button("🏠 回首頁"): nav_to('welcome'); st.rerun()
    st.caption("Ver: 94.0 (全面解鎖版)")

# --- 主程式 ---
mode = st.session_state['view_mode']

if mode == 'welcome':
    ui.render_header("👋 股市戰情室 V94")
    st.info("Yahoo Finance 引擎運作正常。已解鎖「全市場」與「分類」掃描功能。")
    st.markdown("""
    **🚀 使用說明：**
    1. 左側可選擇 **「分類」** (如 半導體、航運) 縮小範圍。
    2. 使用 **「數量上限」** 滑桿控制掃描時間 (建議 50-100 檔)。
    3. 點擊 **「啟動掃描」** 開始 AI 選股。
    """)

elif mode == 'analysis':
    code = st.session_state['current_stock']; name = st.session_state['current_name']
    main_placeholder = st.empty()
    
    def render_content():
        with main_placeholder.container():
            is_live = ui.render_header(f"{code} 個股分析", show_monitor=True)
            
            full_id, stock, df, src = db.get_stock_data(code)
            
            if src == "fail":
                st.error(f"⚠️ 無法取得 {code} 資料。可能原因：代號錯誤或 API 異常。")
                return False
            
            df, bid_ask, rt_pack = inject_realtime_data(df, code)
            
            curr = df['Close'].iloc[-1]; prev = df['Close'].iloc[-2]
            chg = curr - prev; pct = (chg/prev)*100
            high = df['High'].iloc[-1]; low = df['Low'].iloc[-1]; amp = ((high - low) / prev) * 100
            vol = df['Volume'].iloc[-1]
            color_settings = db.get_color_settings(code)
            
            info_text = stock.info.get('longBusinessSummary', '資料來源: Yahoo Finance')
            ui.render_company_profile(db.translate_text(info_text))
            
            mf = "一般"; vs = "正常"; fh = 0.0; turnover = 0.0
            
            ui.render_metrics_dashboard(curr, chg, pct, high, low, amp, mf, vol, vol, vol, vs, fh, turnover, bid_ask, color_settings, rt_pack)
            ui.render_chart(df, f"{code} K線圖", color_settings)
            
            battle_analysis = analyze_stock_battle_data(df)
            if battle_analysis: ui.render_ai_battle_dashboard(battle_analysis)

            ui.render_back_button(go_back)
            return is_live

    is_live_mode = render_content()
    if is_live_mode:
        while True:
            time.sleep(1)
            still_live = render_content()
            if not still_live: break

elif mode == 'learn':
    ui.render_header("📖 股市新手村"); t1, t2 = st.tabs(["策略", "名詞"])
    with t1: st.markdown(STRATEGY_DESC)
    with t2: 
        for cat, items in STOCK_TERMS.items():
            with st.expander(cat):
                for k, v in items.items(): ui.render_term_card(k, v)
    ui.render_back_button(go_back)

elif mode == 'chat':
    ui.render_header("💬 留言板")
    with st.form("msg"):
        nick = st.text_input("暱稱", value="股神")
        m = st.text_input("內容")
        if st.form_submit_button("送出") and m: db.save_comment(nick, m); st.rerun()
    df_chat = db.get_comments()
    for i, r in df_chat.iloc[::-1].head(10).iterrows(): st.info(f"**{r['Nickname']}**: {r['Message']}")
    ui.render_back_button(go_back)

elif mode == 'scan': 
    # V94: 全面掃描邏輯回歸
    stype = st.session_state['current_stock']; target_group = st.session_state.get('scan_target_group', '全部')
    title_map = {'day': '⚡ 強力當沖', 'short': '📈 穩健短線', 'long': '🐢 長線安穩', 'top': '🏆 熱門強勢'}
    ui.render_header(f"🤖 {target_group} ⨉ {title_map.get(stype, stype)}")
    
    saved_codes = db.load_scan_results(stype) 
    c1, c2 = st.columns([1, 4]); do_scan = c1.button("🔄 開始智能篩選", type="primary")
    if saved_codes and not do_scan: c2.info(f"上次記錄: 共 {len(saved_codes)} 檔")
    else: c2.info(f"目標範圍: {target_group} (上限 {st.session_state.get('scan_limit', 50)} 檔)")

    if do_scan:
        st.session_state['scan_results'] = []; raw_results = []
        full_pool = st.session_state['scan_pool']
        
        # 1. 篩選目標群組
        if target_group != "🔍 全部上市櫃":
             target_pool = [c for c in full_pool if c in twstock.codes and twstock.codes[c].group == target_group]
        else:
             target_pool = full_pool

        # 2. 設定進度條與上限
        limit = st.session_state.get('scan_limit', 50)
        bar = st.progress(0)
        
        count = 0
        # 為了展示效果，這裡只遍歷前 N 個符合條件的股票
        # 若要真全掃描，可以把切片去掉，但時間會很久
        
        for i, c in enumerate(target_pool):
            if count >= limit: break
            
            # 更新進度條
            prog = (count + 1) / limit
            bar.progress(min(prog, 1.0))
            
            try:
                # 取得資料 (自動使用 Yahoo)
                fid, _, d, src = db.get_stock_data(c)
                
                if d is not None and len(d) > 20:
                    # 注入即時
                    d_real, _, _ = inject_realtime_data(d, c)
                    p = d_real['Close'].iloc[-1]; prev = d_real['Close'].iloc[-2]
                    vol = d_real['Volume'].iloc[-1]
                    m5 = d_real['Close'].rolling(5).mean().iloc[-1]
                    m20 = d_real['Close'].rolling(20).mean().iloc[-1]
                    m60 = d_real['Close'].rolling(60).mean().iloc[-1]
                    
                    valid = False
                    info_txt = ""
                    
                    if stype == 'day': 
                        if vol > d_real['Volume'].iloc[-2]*1.5 and p > m5: 
                            valid = True; info_txt = "爆量攻擊"
                    elif stype == 'short': 
                        if p > m20 and m5 > m20: 
                            valid = True; info_txt = "多頭排列"
                    elif stype == 'long': 
                        if p > m60 and ((p-m60)/m60) < 0.1: 
                            valid = True; info_txt = "季線支撐"
                    elif stype == 'top': 
                        if vol > 2000: 
                            valid = True; info_txt = "熱門股"
                    
                    if valid:
                        n = twstock.codes[c].name if c in twstock.codes else c
                        raw_results.append({'c': c, 'n': n, 'p': p, 'd': d_real, 'src': src, 'info': info_txt})
                        count += 1
                        
                # 稍微冷卻一下，雖然 Yahoo 比較快，但不要太暴力
                time.sleep(0.05) 
                
            except: pass
            
        bar.empty()
        st.session_state['scan_results'] = raw_results
        db.save_scan_results(stype, [x['c'] for x in raw_results])
        st.rerun()

    display_list = st.session_state['scan_results']
    if not display_list and not do_scan and saved_codes:
         # 如果沒有掃描但有舊紀錄，嘗試載入
         # 為了效能，舊紀錄只載入代號，不即時抓報價 (使用者點進去再抓)
         temp_list = [{'c':c, 'n':c, 'p':0, 'd':None, 'src':'', 'info':'歷史紀錄'} for c in saved_codes[:20]]
         display_list = temp_list

    if display_list:
        for item in display_list:
            # 這裡為了效能，卡片只顯示基本資訊，點擊才進行詳細分析
            if ui.render_detailed_card(item['c'], item['n'], item.get('p',0), item.get('d'), item.get('src'), key_prefix=f"scan_{stype}", strategy_info=item.get('info')):
                nav_to('analysis', item['c'], item['n']); st.rerun()
    elif do_scan:
        st.warning("掃描完成，但在限制數量內未發現符合策略的標的。請嘗試放寬條件或增加掃描數量。")
        
    ui.render_back_button(go_back)
