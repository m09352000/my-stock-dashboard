import streamlit as st
import time
import twstock
import pandas as pd
import re
import importlib
from datetime import datetime, timedelta, timezone

import stock_db as db
import stock_ui as ui

try:
    import knowledge
    importlib.reload(knowledge)
    from knowledge import STOCK_TERMS, STRATEGY_DESC, KLINE_PATTERNS
except ImportError:
    STOCK_TERMS = {}; STRATEGY_DESC = "知識庫載入失敗"; KLINE_PATTERNS = {}

st.set_page_config(page_title="股市戰情室 V100", layout="wide", page_icon="📈")

# --- V100 核心：深度診斷生成器 ---
def generate_detailed_report(df, score, weekly_prob, monthly_prob):
    """
    生成「超級無敵詳細」的 AI 診斷報告文字
    """
    latest = df.iloc[-1]
    p = latest['Close']
    m5 = df['Close'].rolling(5).mean().iloc[-1]
    m20 = df['Close'].rolling(20).mean().iloc[-1]
    m60 = df['Close'].rolling(60).mean().iloc[-1]
    vol = latest['Volume']
    vol_ma5 = df['Volume'].rolling(5).mean().iloc[-1]
    
    # 1. 均線形態分析
    trend_txt = "【趨勢型態】\n"
    if p > m5 and m5 > m20 and m20 > m60:
        trend_txt += "目前呈現「多頭排列」的完美進攻型態。股價站穩五日線之上，短中長期均線全面向上發散，這是最強勢的主升段特徵，上方無明顯壓力，天空才是極限。"
    elif p < m5 and m5 < m20 and m20 < m60:
        trend_txt += "目前呈現「空頭排列」的下跌型態。股價遭五日線反壓，且月季線下彎形成蓋頭反壓，這代表上方套牢賣壓沈重，任何反彈都容易遇到解套賣壓，不宜貿然搶進。"
    elif p > m20:
        trend_txt += "股價位於月線(生命線)之上，屬於中多格局。雖然短線可能稍有震盪，但只要月線支撐不破，波段趨勢依然看好。"
    else:
        trend_txt += "股價跌破月線(生命線)，短線轉弱。目前進入整理修正階段，需觀察能否盡快站回月線，否則整理時間將拉長。"

    # 2. 量能籌碼分析
    vol_txt = "\n\n【量能籌碼】\n"
    if vol > vol_ma5 * 1.5:
        vol_txt += f"今日爆出 {int(vol/1000):,} 張的大量，是五日均量的 {vol/vol_ma5:.1f} 倍！這代表「主力大戶強勢表態」，有新資金進場換手，這是行情的催化劑。"
    elif vol < vol_ma5 * 0.6:
        vol_txt += "今日呈現「量縮整理」格局，成交量明顯萎縮。這代表市場觀望氣氛濃厚，買賣雙方都在縮手，等待進一步的方向確認。"
    else:
        vol_txt += "今日量能溫和，維持在五日均量附近，屬於健康的換手量，有利於股價穩步推升。"

    # 3. 獲利機率解讀
    prob_txt = "\n\n【獲利機率預測】\n"
    prob_txt += f"根據 AI 演算法綜合運算：\n"
    prob_txt += f"● **本週 (短線)** 獲利機率：**{weekly_prob}%**。{( '🔥 極高！適合積極操作。' if weekly_prob > 80 else '⚠️ 需謹慎，短線波動大。' )}\n"
    prob_txt += f"● **本月 (波段)** 獲利機率：**{monthly_prob}%**。{( '💎 趨勢穩健，適合波段持有。' if monthly_prob > 70 else '⏳ 趨勢不明，建議觀望。' )}"

    return trend_txt + vol_txt + prob_txt

def analyze_stock_battle_data(df):
    if df is None or len(df) < 30: return None
    latest = df.iloc[-1]
    close = latest['Close']
    
    # 技術指標
    ma5 = df['Close'].rolling(5).mean().iloc[-1]
    ma20 = df['Close'].rolling(20).mean().iloc[-1]
    ma60 = df['Close'].rolling(60).mean().iloc[-1]
    std20 = df['Close'].rolling(20).std().iloc[-1]
    
    # MACD
    exp12 = df['Close'].ewm(span=12, adjust=False).mean()
    exp26 = df['Close'].ewm(span=26, adjust=False).mean()
    macd = exp12 - exp26
    signal = macd.ewm(span=9, adjust=False).mean()
    
    # RSI
    delta = df['Close'].diff()
    u = delta.copy(); d = delta.copy()
    u[u < 0] = 0; d[d > 0] = 0
    rs = u.rolling(14).mean() / d.abs().rolling(14).mean()
    rsi = (100 - 100/(1+rs)).iloc[-1]
    
    vol_ma5 = df['Volume'].rolling(5).mean().iloc[-1]
    vol_ratio = latest['Volume'] / vol_ma5 if vol_ma5 > 0 else 1
    
    # --- V100: 雙週期勝率演算法 ---
    
    # 1. 本週獲利機率 (看 5日線, RSI, 量能)
    w_score = 50 # 基礎分
    if close > ma5: w_score += 15
    if ma5 > ma20: w_score += 10
    if vol_ratio > 1.2: w_score += 10
    if 50 < rsi < 80: w_score += 10
    elif rsi > 80: w_score -= 10 # 過熱風險
    weekly_prob = min(max(w_score, 10), 98) # 限制 10-98

    # 2. 本月獲利機率 (看 月線, 季線, MACD)
    m_score = 50 # 基礎分
    if close > ma20: m_score += 20
    if ma20 > ma60: m_score += 20 # 多頭排列權重高
    if macd.iloc[-1] > signal.iloc[-1]: m_score += 10
    monthly_prob = min(max(m_score, 10), 95)

    # 綜合評分
    total_score = (weekly_prob + monthly_prob) / 2
    
    # 生成詳細報告
    detailed_report = generate_detailed_report(df, total_score, weekly_prob, monthly_prob)

    # 操作建議
    short_action = "積極買進" if weekly_prob >= 70 else "拉回佈局" if weekly_prob >= 50 else "觀望"
    mid_trend = "多頭" if ma20 > ma60 else "整理"
    long_bias = ((close - ma60) / ma60) * 100
    long_action = "乖離過大" if long_bias > 20 else "超跌" if long_bias < -15 else "合理"
    
    return {
        "score": total_score,
        "weekly_prob": weekly_prob,
        "monthly_prob": monthly_prob,
        "report": detailed_report,
        "heat": "🔥🔥🔥 極熱" if vol_ratio > 2.0 else "🔥 溫熱" if vol_ratio > 1.2 else "☁️ 普通",
        "heat_color": "#FF0000" if vol_ratio > 2.0 else "#FF4500",
        "short_action": short_action, 
        "short_target": f"{close*1.05:.2f}",
        "mid_trend": mid_trend, "mid_action": "續抱" if close > ma20 else "減碼", "mid_support": f"{ma20:.2f}",
        "long_action": long_action, "long_ma60": f"{ma60:.2f}",
        "pressure": ma20 + 2*std20, "support": ma20 - 2*std20, 
        "suggest_price": close if total_score > 70 else ma20, "close": close
    }

def inject_realtime_data(df, code):
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
    val = str(val).strip()
    if not val: return None, None
    clean_code = re.sub(r'[^\d]', '', val)
    if len(clean_code) == 4:
        name = clean_code
        if clean_code in twstock.codes: name = twstock.codes[clean_code].name
        return clean_code, name
    for code, data in twstock.codes.items():
        if data.type in ["股票", "ETF"]:
            if val == data.name: return code, data.name
    for code, data in twstock.codes.items():
        if data.type in ["股票", "ETF"]:
            if val in data.name: return code, data.name
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
        st.session_state.search_input_val = ""
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
    if st.button("📖 股市新手村 (終極版)"): nav_to('learn'); st.rerun()
    if st.button("🏠 回首頁"): nav_to('welcome'); st.rerun()
    st.caption("Ver: 100.0 (深度診斷版)")

# --- 主程式 ---
mode = st.session_state['view_mode']

if mode == 'welcome':
    ui.render_header("👋 股市戰情室 V100")
    st.success("🎉 V100 里程碑更新：\n1. **雙週期勝率**：新增「本週」與「本月」賺錢機率分析。\n2. **深度診斷報告**：AI 自動生成千字文技術分析。\n3. **新手村重製**：包含 K線戰法 SOP 與詳細停損停利建議。")

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
            df, _, rt_pack = inject_realtime_data(df, code)
            curr = df['Close'].iloc[-1]; prev = df['Close'].iloc[-2]
            chg = curr - prev; pct = (chg/prev)*100
            high = df['High'].iloc[-1]; low = df['Low'].iloc[-1]
            amp = ((high - low) / prev) * 100
            vol = df['Volume'].iloc[-1]
            vy = df['Volume'].iloc[-2]
            va = df['Volume'].rolling(5).mean().iloc[-1]
            vs = "爆量" if vol > vy*1.5 else "量縮" if vol < vy*0.6 else "正常"
            
            info = stock.info.get('longBusinessSummary', '')
            ui.render_company_profile(db.translate_text(info))
            ui.render_metrics_dashboard(curr, chg, pct, high, low, amp, "一般", vol, vy, va, vs, 0, 0, None, None, rt_pack)
            ui.render_chart(df, f"{name} K線圖", db.get_color_settings(code))
            
            battle = analyze_stock_battle_data(df)
            if battle: ui.render_ai_battle_dashboard(battle)

    ui.render_back_button(lambda: nav_to('welcome'))

elif mode == 'learn':
    ui.render_header("📖 股市新手村 (終極詳細版)")
    t1, t2, t3 = st.tabs(["策略解密", "名詞百科", "K線戰法 SOP"])
    with t1: st.markdown(STRATEGY_DESC)
    with t2:
        for cat, items in STOCK_TERMS.items():
            with st.expander(cat, expanded=True):
                for k, v in items.items(): ui.render_term_card(k, v)
    with t3:
        st.info("💡 這裡收錄了最經典的 K 線反轉訊號，並附上完整的操作 SOP。請熟讀！")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🔥 多方訊號 (準備做多)")
            for k, v in KLINE_PATTERNS.get('bull', {}).items(): ui.render_kline_pattern_card(k, v)
        with c2:
            st.subheader("❄️ 空方訊號 (準備做空)")
            for k, v in KLINE_PATTERNS.get('bear', {}).items(): ui.render_kline_pattern_card(k, v)
    ui.render_back_button(lambda: nav_to('welcome'))

elif mode == 'scan':
    stype = st.session_state['current_stock']
    target = st.session_state.get('scan_target_group', '全部')
    title_map = {'tomorrow_star': '🌅 明日之星', 'super_win': '💎 超強力必賺', 'day': '⚡ 強力當沖', 'short': '📈 穩健短線'}
    ui.render_header(f"🤖 {target} ⨉ {title_map.get(stype, stype)}")
    
    display_list = st.session_state.get('scan_results', [])
    
    if not display_list:
        pool = st.session_state['scan_pool']
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
                _, _, df, src = db.get_stock_data(c)
                if df is not None and len(df) > 30:
                    battle = analyze_stock_battle_data(df)
                    score = battle['score']
                    w_prob = battle['weekly_prob']
                    
                    close = df['Close'].iloc[-1]; open_p = df['Open'].iloc[-1]
                    high = df['High'].iloc[-1]; vol = df['Volume'].iloc[-1]
                    vol_ma5 = df['Volume'].rolling(5).mean().iloc[-1]
                    ma5 = df['Close'].rolling(5).mean().iloc[-1]
                    
                    valid = False
                    info_txt = ""
                    
                    if stype == 'tomorrow_star':
                        if close > open_p and close > high * 0.985 and vol > vol_ma5 and close > ma5:
                            valid = True; score += 10; info_txt = "尾盤強勢 | 蓄勢待發"
                    elif stype == 'super_win':
                        if score >= 60: valid = True; info_txt = f"趨勢強 | 評分 {score}"
                    elif stype == 'day':
                        if vol > df['Volume'].iloc[-2]*1.5: valid = True; info_txt = "爆量攻擊"
                    elif stype == 'short':
                        if score >= 40: valid = True; info_txt = "多頭排列"
                    elif stype == 'top':
                         if vol > 2000: valid = True; info_txt = "熱門股"
                         
                    if valid:
                        n = twstock.codes[c].name if c in twstock.codes else c
                        # 把週勝率也存進去
                        raw_results.append({'c': c, 'n': n, 'p': close, 'info': info_txt, 'score': score, 'w_prob': w_prob, 'd': df, 'src': src})
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
            if ui.render_detailed_card(item['c'], item['n'], item['p'], item['d'], item['src'], 
                                     key_prefix=f"scan_{stype}", rank=i+1, 
                                     strategy_info=item['info'], score=item['score'], 
                                     w_prob=item.get('w_prob', 50)): # 傳入週勝率
                nav_to('analysis', item['c'], item['n'])
                st.rerun()
    else:
        st.warning("無符合條件標的")

    ui.render_back_button(lambda: nav_to('welcome'))
