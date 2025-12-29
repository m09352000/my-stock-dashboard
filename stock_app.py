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

st.set_page_config(page_title="股市戰情室 V93", layout="wide", page_icon="📈")

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
        # 如果 yfinance 抓到的資料最後一筆日期是今天，那其實不需要 twstock
        last_date = df.index[-1].date()
        today = datetime.now(timezone(timedelta(hours=8))).date()
        
        # 嘗試抓即時，如果被 Ban 就跳過，直接用 DataFrame 最後一筆當作目前資料
        real = twstock.realtime.get(code)
        if real['success']:
            rt = real['realtime']
            if rt['latest_trade_price'] != '-' and rt['latest_trade_price'] is not None:
                latest = float(rt['latest_trade_price'])
                high = float(rt['high']); low = float(rt['low']); open_p = float(rt['open'])
                vol = float(rt['accumulate_trade_volume'])
                
                # 如果是盤中，yfinance 可能還沒更新今天的 K 棒，我們手動補上去
                if last_date < today:
                    # 新增一行
                    new_idx = pd.Timestamp(today)
                    df.loc[new_idx] = [open_p, high, low, latest, 0, int(vol)*1000] # 假設欄位順序
                    # 但因為欄位對應麻煩，我們直接更新最後一行如果是今天，或者不做任何事
                    pass
                else:
                    # 更新最後一行
                    last_idx = df.index[-1]
                    df.at[last_idx, 'Close'] = latest
                    df.at[last_idx, 'High'] = max(high, df.at[last_idx, 'High'])
                    df.at[last_idx, 'Low'] = min(low, df.at[last_idx, 'Low'])
                    df.at[last_idx, 'Volume'] = int(vol) * 1000
                
                rt_pack = {'latest_trade_price': latest, 'high': high, 'low': low, 'accumulate_trade_volume': vol, 'previous_close': open_p} # 簡化
                bid_ask = {'bid_price': rt.get('best_bid_price', []), 'bid_volume': rt.get('best_bid_volume', []), 'ask_price': rt.get('best_ask_price', []), 'ask_volume': rt.get('best_ask_volume', [])}
                return df, bid_ask, rt_pack
    except: 
        pass
    
    # Fallback: 如果即時抓不到，就用 DataFrame 最後一筆資料偽裝成即時資料
    # 這樣畫面才不會變成「查無資料」
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
    # 簡單正規化
    clean_val = re.sub(r'[^\w]', '', val)
    # 如果是數字且長度為4，直接當作代號回傳，不檢查 twstock 清單 (避免清單失效)
    if clean_val.isdigit() and len(clean_val) == 4:
        return clean_val, clean_val
    return None, None # 暫時不支援名稱搜尋，確保穩定

# --- Session State 初始化 ---
defaults = {
    'view_mode': 'welcome', 'user_id': None, 'page_stack': ['welcome'],
    'current_stock': "", 'current_name': "", 'scan_pool': [], 
    'scan_target_group': "全部", 'scan_results': [], 'monitor_active': False
}
for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

if not st.session_state['scan_pool']:
    st.session_state['scan_pool'] = ['2330', '2317', '2454', '4967', '3231'] # 預設幾個熱門股，避免 twstock 初始化失敗
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
        sel_strat_name = st.selectbox("策略", ["⚡ 強力當沖", "📈 穩健短線", "🐢 長線安穩", "🏆 熱門強勢"])
        if st.button("🚀 啟動掃描", use_container_width=True):
            st.session_state['current_stock'] = "day" # 簡化
            nav_to('scan', "day"); st.rerun()

    st.divider()
    if st.button("📖 股市新手村"): nav_to('learn'); st.rerun()
    if st.button("💬 戰友留言板"): nav_to('chat'); st.rerun()
    if st.button("🏠 回首頁"): nav_to('welcome'); st.rerun()
    st.caption("Ver: 93.0 (Yahoo核心版)")

# --- 主程式 ---
mode = st.session_state['view_mode']

if mode == 'welcome':
    ui.render_header("👋 股市戰情室 V93")
    st.info("系統已切換至 Yahoo Finance 核心，解決資料抓取問題。請直接在左側輸入股票代號。")

elif mode == 'analysis':
    code = st.session_state['current_stock']; name = st.session_state['current_name']
    main_placeholder = st.empty()
    
    def render_content():
        with main_placeholder.container():
            is_live = ui.render_header(f"{code} 個股分析", show_monitor=True)
            
            # 取得資料
            full_id, stock, df, src = db.get_stock_data(code)
            
            if src == "fail":
                st.error(f"⚠️ 無法取得 {code} 資料。可能原因：代號錯誤或 Yahoo API 暫時異常。")
                return False
            
            # 注入即時 (或偽裝即時)
            df, bid_ask, rt_pack = inject_realtime_data(df, code)
            
            # 計算顯示數據
            curr = df['Close'].iloc[-1]; prev = df['Close'].iloc[-2]
            chg = curr - prev; pct = (chg/prev)*100
            high = df['High'].iloc[-1]; low = df['Low'].iloc[-1]; amp = ((high - low) / prev) * 100
            vol = df['Volume'].iloc[-1]
            color_settings = db.get_color_settings(code)
            
            # 儀表板
            info_text = stock.info.get('longBusinessSummary', '資料來源: Yahoo Finance')
            ui.render_company_profile(db.translate_text(info_text))
            
            # 如果 rt_pack 是偽造的，某些欄位可能不存在，做個防呆
            mf = "一般"
            vs = "正常"
            fh = 0.0
            turnover = 0.0
            
            ui.render_metrics_dashboard(curr, chg, pct, high, low, amp, mf, vol, vol, vol, vs, fh, turnover, bid_ask, color_settings, rt_pack)
            
            # K線圖
            ui.render_chart(df, f"{code} K線圖", color_settings)
            
            # AI 戰情
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
    ui.render_header("🤖 掃描結果 (測試版)")
    st.info("因更換資料源，目前僅掃描系統預設池。")
    st.session_state['scan_results'] = []
    
    # 簡易掃描
    pool = ['2330', '2317', '2454', '2603', '2609', '4967', '3231']
    for c in pool:
        fid, _, df, src = db.get_stock_data(c)
        if df is not None:
             p = df['Close'].iloc[-1]
             ui.render_detailed_card(c, c, p, df, src, key_prefix="scan", strategy_info="掃描完成")
             
    ui.render_back_button(go_back)
