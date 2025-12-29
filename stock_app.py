import streamlit as st
import time
import twstock
import pandas as pd
import re
import importlib
from datetime import datetime, time as dt_time, timedelta, timezone

# 引入自定義模組
import stock_db as db
import stock_ui as ui

# 載入知識庫
try:
    import knowledge
    importlib.reload(knowledge)
    from knowledge import STOCK_TERMS, STRATEGY_DESC, KLINE_PATTERNS
except:
    STOCK_TERMS = {}; STRATEGY_DESC = "System Loading..."; KLINE_PATTERNS = {}

st.set_page_config(page_title="股市戰情室 V90", layout="wide", page_icon="📈")

# --- 核心：AI 戰情運算引擎 (純 Pandas 實作) ---
def analyze_stock_battle_data(df):
    if df is None or len(df) < 30: return None
    
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    close = latest['Close']
    
    # 1. 計算 MACD (12, 26, 9)
    exp12 = df['Close'].ewm(span=12, adjust=False).mean()
    exp26 = df['Close'].ewm(span=26, adjust=False).mean()
    macd = exp12 - exp26
    signal = macd.ewm(span=9, adjust=False).mean()
    
    curr_macd = macd.iloc[-1]
    curr_signal = signal.iloc[-1]
    prev_macd = macd.iloc[-2]
    prev_signal = signal.iloc[-2]

    # 2. 計算 RSI (14)
    delta = df['Close'].diff()
    u = delta.copy(); d = delta.copy()
    u[u < 0] = 0; d[d > 0] = 0
    rs = u.rolling(14).mean() / d.abs().rolling(14).mean()
    rsi = (100 - 100/(1+rs)).iloc[-1]

    # 3. 計算均線
    ma5 = df['Close'].rolling(5).mean().iloc[-1]
    ma20 = df['Close'].rolling(20).mean().iloc[-1]
    ma60 = df['Close'].rolling(60).mean().iloc[-1]
    
    # 4. 計算布林通道 (20, 2)
    std20 = df['Close'].rolling(20).std().iloc[-1]
    bbu = ma20 + 2 * std20
    bbl = ma20 - 2 * std20

    # --- 評分系統 ---
    score = 0
    reasons = []

    # 趨勢面
    if close > ma20: score += 20; reasons.append("股價站上月線 (多頭支撐)")
    if ma5 > ma20: score += 10; reasons.append("短均線黃金交叉 (攻擊型態)")
    if curr_macd > curr_signal: 
        score += 10
        if prev_macd <= prev_signal: reasons.append("MACD 剛翻紅 (起漲訊號)")
        else: reasons.append("MACD 維持多頭")
    
    # 動能面
    if 50 <= rsi <= 75: score += 20; reasons.append(f"RSI ({rsi:.1f}) 位於強勢區")
    elif rsi < 30: score += 15; reasons.append("RSI 超賣 (醞釀反彈)")
    
    # 量能面
    vol_ma5 = df['Volume'].rolling(5).mean().iloc[-1]
    vol_ratio = latest['Volume'] / vol_ma5 if vol_ma5 > 0 else 1
    if vol_ratio > 1.2: score += 20; reasons.append("量能放大 (人氣匯集)")
    
    # --- 輸出結果包裝 ---
    
    # 熱度
    if vol_ratio > 2.0: heat = "🔥🔥🔥 極熱"; heat_color = "#FF0000"
    elif vol_ratio > 1.3: heat = "🔥 溫熱"; heat_color = "#FF4500"
    elif vol_ratio < 0.6: heat = "❄️ 冰冷"; heat_color = "#00BFFF"
    else: heat = "☁️ 普通"; heat_color = "#FFFFFF"
    
    # 建議
    short_action = "觀望"
    if score >= 70: short_action = "🚀 積極買進"; short_entry = "現價 / 5日線"; short_target = f"{close*1.05:.2f}"
    elif score >= 50: short_action = "✅ 拉回佈局"; short_entry = "月線附近"; short_target = f"{close*1.03:.2f}"
    else: short_action = "⚠️ 暫時觀望"; short_entry = "突破月線"; short_target = "-"
    
    mid_trend = "多頭" if ma20 > ma60 else "空頭/整理"
    mid_action = "持有/加碼" if close > ma20 else "減碼/觀望"
    
    long_bias = ((close - ma60) / ma60) * 100
    long_action = "合理區間"
    if long_bias > 20: long_action = "乖離過大 (勿追)"
    elif long_bias < -15: long_action = "超跌 (具價值)"
    
    return {
        "score": score,
        "probability": min(score + 10, 95), # 模擬勝率
        "heat": heat,
        "heat_color": heat_color,
        "reasons": reasons,
        "short_action": short_action,
        "short_entry": short_entry,
        "short_target": short_target,
        "mid_trend": mid_trend,
        "mid_action": mid_action,
        "mid_support": f"{ma20:.2f}",
        "long_bias": long_bias,
        "long_action": long_action,
        "long_ma60": f"{ma60:.2f}",
        "pressure": bbu,
        "support": max(bbl, ma20),
        "suggest_price": close if score > 70 else ma20,
        "close": close
    }

# --- 基礎功能函數 ---
def inject_realtime_data(df, code):
    if df is None or df.empty: return df, None, None
    try:
        real = twstock.realtime.get(code)
        if real['success']:
            rt = real['realtime']
            if rt['latest_trade_price'] == '-' or rt['latest_trade_price'] is None: return df, None, None
            latest = float(rt['latest_trade_price'])
            high = float(rt['high']); low = float(rt['low']); open_p = float(rt['open'])
            vol = float(rt['accumulate_trade_volume'])
            rt_pack = {'latest_trade_price': latest, 'high': high, 'low': low, 'open': open_p, 'accumulate_trade_volume': vol, 'previous_close': float(df['Close'].iloc[-2]) if len(df)>1 else open_p}
            last_idx = df.index[-1]
            df.at[last_idx, 'Close'] = latest
            df.at[last_idx, 'High'] = max(high, df.at[last_idx, 'High'])
            df.at[last_idx, 'Low'] = min(low, df.at[last_idx, 'Low'])
            df.at[last_idx, 'Volume'] = int(vol) * 1000
            bid_ask = {'bid_price': rt.get('best_bid_price', []), 'bid_volume': rt.get('best_bid_volume', []), 'ask_price': rt.get('best_ask_price', []), 'ask_volume': rt.get('best_ask_volume', [])}
            return df, bid_ask, rt_pack
    except: return df, None, None
    return df, None, None

def check_market_hours():
    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz)
    if now.weekday() > 4: return False, "今日為週末休市"
    current_time = now.time()
    start_time = dt_time(8, 30); end_time = dt_time(13, 30)
    if start_time <= current_time <= end_time: return True, "市場開盤中"
    else: return False, f"非交易時間 ({now.strftime('%H:%M')})"

def solve_stock_id(val):
    val = str(val).strip()
    if not val: return None, None
    clean_val = re.sub(r'[^\w\u4e00-\u9fff\-\.]', '', val)
    if clean_val in twstock.codes: return clean_val, twstock.codes[clean_val].name
    for c, d in twstock.codes.items():
        if d.type in ["股票", "ETF"] and d.name == clean_val: return c, d.name
    if len(clean_val) >= 2:
        for c, d in twstock.codes.items():
            if d.type in ["股票", "ETF"] and clean_val in d.name: return c, d.name
    return None, None

# --- Session State 初始化 ---
defaults = {
    'view_mode': 'welcome', 'user_id': None, 'page_stack': ['welcome'],
    'current_stock': "", 'current_name': "", 'scan_pool': [], 
    'scan_target_group': "全部", 'scan_results': [], 'monitor_active': False
}
for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

if not st.session_state['scan_pool']:
    try:
        all_codes = [c for c in twstock.codes.values() if c.type in ["股票", "ETF"]]
        st.session_state['scan_pool'] = sorted([c.code for c in all_codes])
        groups = sorted(list(set(c.group for c in all_codes if c.group)))
        st.session_state['all_groups'] = ["🔍 全部上市櫃"] + groups
    except:
        st.session_state['scan_pool'] = ['2330', '0050']; st.session_state['all_groups'] = ["全部"]

def nav_to(mode, code=None, name=None):
    if code:
        st.session_state['current_stock'] = code
        st.session_state['current_name'] = name
    st.session_state['view_mode'] = mode
    if st.session_state['page_stack'][-1] != mode: st.session_state['page_stack'].append(mode)

def go_back():
    if len(st.session_state['page_stack']) > 1:
        st.session_state['page_stack'].pop(); prev = st.session_state['page_stack'][-1]; st.session_state['view_mode'] = prev
    else: st.session_state['view_mode'] = 'welcome'

def handle_search():
    raw = st.session_state.search_input_val
    if raw:
        code, name = solve_stock_id(raw)
        if code: nav_to('analysis', code, name); st.session_state.search_input_val = ""
        else: st.toast(f"找不到代號 '{raw}'", icon="⚠️")

# --- 側邊欄 Sidebar (移除自選股) ---
with st.sidebar:
    st.title("🎮 戰情控制台")
    st.divider()
    st.text_input("🔍 搜尋 (輸入代號/名稱)", key="search_input_val", on_change=handle_search)
    
    with st.container(border=True):
        st.markdown("### 🤖 AI 掃描雷達")
        sel_group = st.selectbox("1️⃣ 範圍", st.session_state.get('all_groups', ["全部"]), index=0)
        strat_map = {"⚡ 強力當沖": "day", "📈 穩健短線": "short", "🐢 長線安穩": "long", "🏆 熱門強勢": "top"}
        sel_strat_name = st.selectbox("2️⃣ 策略", list(strat_map.keys()))
        if st.button("🚀 啟動掃描", use_container_width=True):
            st.session_state['scan_target_group'] = sel_group
            st.session_state['current_stock'] = strat_map[sel_strat_name]
            st.session_state['scan_results'] = []
            nav_to('scan', strat_map[sel_strat_name]); st.rerun()

    st.divider()
    if st.button("📖 股市新手村"): nav_to('learn'); st.rerun()
    if st.button("💬 戰友留言板"): nav_to('chat'); st.rerun()
    if st.button("🏠 回首頁"): nav_to('welcome'); st.rerun()
    st.caption("Ver: 91.0 (戰情室重構版)")

# --- 主程式邏輯 ---
mode = st.session_state['view_mode']

if mode == 'welcome':
    ui.render_header("👋 歡迎來到 股市戰情室 V91")
    st.info("請在左側輸入股票代號（如 2330）或點擊「AI 掃描雷達」開始使用。")
    st.markdown("### 🚀 V91 更新重點\n* **🗑️ 移除自選股**：介面更簡潔，專注於當下分析。\n* **🤖 AI 戰情診斷室**：新增熱度分析、勝率預測、多週期建議。\n* **🛡️ 關鍵點位**：自動計算布林通道壓力與支撐。")

elif mode == 'analysis':
    code = st.session_state['current_stock']; name = st.session_state['current_name']
    main_placeholder = st.empty()
    
    def render_content():
        with main_placeholder.container():
            is_live = ui.render_header(f"{name} {code}", show_monitor=True)
            full_id, stock, df, src = db.get_stock_data(code)
            
            if src == "fail": 
                st.error("查無資料")
                return False
            elif src == "yahoo":
                df, bid_ask, rt_pack = inject_realtime_data(df, code)
                info = stock.info
                shares = info.get('sharesOutstanding', 0)
                curr = df['Close'].iloc[-1]; prev = df['Close'].iloc[-2]
                chg = curr - prev; pct = (chg/prev)*100
                vt = df['Volume'].iloc[-1]
                turnover = (vt / shares * 100) if shares > 0 else 0
                vy = df['Volume'].iloc[-2]; va = df['Volume'].tail(5).mean() + 1
                high = df['High'].iloc[-1]; low = df['Low'].iloc[-1]; amp = ((high - low) / prev) * 100
                
                # 簡單判斷顯示用
                mf = "主力進貨 🔴" if (chg>0 and vt>vy) else ("主力出貨 🟢" if (chg<0 and vt>vy) else "觀望")
                vol_r = vt/va; vs = "爆量 🔥" if vol_r>1.5 else ("量縮 💤" if vol_r<0.6 else "正常")
                fh = info.get('heldPercentInstitutions', 0)*100
                color_settings = db.get_color_settings(code)
                
                # 1. 頂部儀表板
                ui.render_company_profile(db.translate_text(info.get('longBusinessSummary','')))
                ui.render_metrics_dashboard(curr, chg, pct, high, low, amp, mf, vt, vy, va, vs, fh, turnover, bid_ask, color_settings, rt_pack)
                
                # 2. K線圖
                ui.render_chart(df, f"{name} K線圖", color_settings)
                
                # 3. AI 戰情診斷室 (V91 新功能)
                battle_analysis = analyze_stock_battle_data(df)
                if battle_analysis:
                    ui.render_ai_battle_dashboard(battle_analysis)
                else:
                    st.warning("資料不足，無法進行 AI 診斷")

            ui.render_back_button(go_back)
            return is_live

    is_live_mode = render_content()
    if is_live_mode:
        while True:
            time.sleep(1)
            still_live = render_content()
            if not still_live: break

# --- 其他模式 (Chat, Learn, Scan) 維持基本不變，僅需適配移除自選股後的流程 ---
elif mode == 'learn':
    ui.render_header("📖 股市新手村"); t1, t2, t3 = st.tabs(["策略說明", "名詞解釋", "🕯️ K線型態"])
    with t1: st.markdown(STRATEGY_DESC)
    with t2:
        q = st.text_input("搜尋名詞")
        for cat, items in STOCK_TERMS.items():
            with st.expander(cat, expanded=True):
                for k, v in items.items():
                    if not q or q in k: ui.render_term_card(k, v)
    with t3:
        st.subheader("🔥 多方訊號"); 
        for name, data in KLINE_PATTERNS.get("bull", {}).items(): ui.render_kline_pattern_card(name, data)
        st.subheader("❄️ 空方訊號"); 
        for name, data in KLINE_PATTERNS.get("bear", {}).items(): ui.render_kline_pattern_card(name, data)
    ui.render_back_button(go_back)

elif mode == 'chat':
    ui.render_header("💬 戰友留言板")
    # 簡化留言板，無需登入即可看，但發言可要求暱稱
    with st.form("msg"):
        nick = st.text_input("您的暱稱", value="路人股神")
        m = st.text_input("留言內容")
        if st.form_submit_button("送出") and m: db.save_comment(nick, m); st.rerun() # db 需對應修改或忽略 user_id
    st.markdown("<hr class='compact'>", unsafe_allow_html=True); df_chat = db.get_comments()
    for i, r in df_chat.iloc[::-1].head(20).iterrows(): st.info(f"**{r['Nickname']}** ({r['Time']}):\n{r['Message']}")
    ui.render_back_button(go_back)

elif mode == 'scan': 
    # 掃描邏輯維持 V90 核心，但移除 Watchlist 相關操作
    stype = st.session_state['current_stock']; target_group = st.session_state.get('scan_target_group', '全部')
    title_map = {'day': '⚡ 強力當沖', 'short': '📈 穩健短線', 'long': '🐢 長線安穩', 'top': '🏆 熱門強勢'}
    ui.render_header(f"🤖 {target_group} ⨉ {title_map.get(stype, stype)}")
    
    saved_codes = db.load_scan_results(stype) 
    c1, c2 = st.columns([1, 4]); do_scan = c1.button("🔄 開始智能篩選", type="primary")
    if saved_codes and not do_scan: c2.info(f"上次記錄: 共 {len(saved_codes)} 檔")

    if do_scan:
        st.session_state['scan_results'] = []; raw_results = []
        full_pool = st.session_state['scan_pool']
        target_pool = [c for c in full_pool if c in twstock.codes and twstock.codes[c].group == target_group] if target_group != "🔍 全部上市櫃" else full_pool
        bar = st.progress(0); limit = 200 # 稍微減少數量加快速度
        
        for i, c in enumerate(target_pool):
            if i >= limit: break
            bar.progress((i+1)/min(len(target_pool), limit))
            try:
                fid, _, d, src = db.get_stock_data(c)
                if d is not None and len(d) > 20:
                    d_real, _, _ = inject_realtime_data(d, c)
                    p = d_real['Close'].iloc[-1]; prev = d_real['Close'].iloc[-2]
                    vol = d_real['Volume'].iloc[-1]; m5 = d_real['Close'].rolling(5).mean().iloc[-1]
                    m20 = d_real['Close'].rolling(20).mean().iloc[-1]
                    valid = False
                    
                    if stype == 'day' and vol > d_real['Volume'].iloc[-2]*1.5 and p>m5: valid = True
                    elif stype == 'short' and p>m20 and m5>m20: valid = True
                    elif stype == 'long' and p>d_real['Close'].rolling(60).mean().iloc[-1]: valid = True
                    elif stype == 'top' and vol > 2000: valid = True
                    
                    if valid:
                        n = twstock.codes[c].name if c in twstock.codes else c
                        raw_results.append({'c': c, 'n': n, 'p': p, 'd': d_real, 'src': src, 'info': "符合策略"})
            except: pass
        bar.empty()
        st.session_state['scan_results'] = raw_results; st.rerun()

    display_list = st.session_state['scan_results'] or ([{'c':c, 'n':twstock.codes[c].name, 'p':0, 'd':None, 'src':'', 'info':''} for c in saved_codes[:20]] if saved_codes else [])
    
    if display_list:
        for item in display_list:
            if ui.render_detailed_card(item['c'], item['n'], item.get('p',0), item.get('d'), item.get('src'), key_prefix=f"scan_{stype}", strategy_info=item.get('info')):
                nav_to('analysis', item['c'], item['n']); st.rerun()
    ui.render_back_button(go_back)
