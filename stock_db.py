import streamlit as st
import time
import twstock
import pandas as pd
import re
import shutil
import os
from PIL import Image, ImageOps, ImageEnhance
import pytesseract
import importlib
from datetime import datetime, time as dt_time, timedelta, timezone
import difflib 

try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False

import stock_db as db
import stock_ui as ui

try:
    import knowledge
    importlib.reload(knowledge)
    from knowledge import STOCK_TERMS, STRATEGY_DESC, KLINE_PATTERNS
except:
    STOCK_TERMS = {}; STRATEGY_DESC = "System Loading..."; KLINE_PATTERNS = {}

st.set_page_config(page_title="AI 股市戰情室 V105", layout="wide")

def find_best_match_stock_v90(text):
    garbage = ["試撮", "注意", "處置", "全額", "資券", "當沖", "商品", "群組", "成交", "漲跌", "幅度", "代號", "買進", "賣出", "總量", "強勢", "弱勢", "自選", "庫存", "延遲", "放一", "一些", "一", "二", "三", "R", "G", "B"]
    clean_text = text.upper()
    for w in garbage: clean_text = clean_text.replace(w, "")
    clean_text = re.sub(r'\d+\.\d+', '', clean_text)
    if not (clean_text.isdigit() and len(clean_text) == 4): clean_text = re.sub(r'\d+', '', clean_text)
    clean_text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\-]', '', clean_text).strip()
    if len(clean_text) < 2: return None, None
    all_codes = {}
    for code, data in twstock.codes.items():
        if data.type in ["股票", "ETF"]: all_codes[code] = data.name
    name_to_code = {v: k for k, v in all_codes.items()}
    all_names = list(name_to_code.keys())
    if clean_text in name_to_code: return name_to_code[clean_text], clean_text
    for name in all_names:
        name_no_digit = re.sub(r'\d+', '', name)
        if len(clean_text) >= 2 and (clean_text in name_no_digit or name_no_digit in clean_text):
            if abs(len(name_no_digit) - len(clean_text)) <= 1: return name_to_code[name], name
    matches = difflib.get_close_matches(clean_text, all_names, n=1, cutoff=0.6)
    if matches:
        best = matches[0]
        if abs(len(best) - len(clean_text)) <= 2: return name_to_code[best], best
    return None, None

def process_image_upload(image_file):
    debug_info = {"raw_text": "", "processed_img": None, "error": None}
    found_stocks = set(); full_ocr_log = ""
    try:
        image_file.seek(0)
        if OPENCV_AVAILABLE:
            file_bytes = np.asarray(bytearray(image_file.read()), dtype=np.uint8)
            img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            scale_percent = 300
            width = int(img.shape[1] * scale_percent / 100); height = int(img.shape[0] * scale_percent / 100)
            img = cv2.resize(img, (width, height), interpolation=cv2.INTER_CUBIC)
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(hsv, np.array([0, 0, 80]), np.array([180, 255, 255]))
            kernel = np.ones((2,2), np.uint8); mask = cv2.dilate(mask, kernel, iterations=1)
            result = cv2.bitwise_not(mask); img_pil = Image.fromarray(result)
            w, h = img_pil.size
            crops = [img_pil.crop((int(w*0.13), 0, int(w*0.45), h)), img_pil.crop((int(w*0.13), 0, int(w*0.55), h))]
            debug_mode = "OpenCV 鷹眼模式"
        else:
            img_pil = Image.open(image_file)
            if img_pil.mode != 'RGB': img_pil = img_pil.convert('RGB')
            w, h = img_pil.size; img_pil = img_pil.resize((w*3, h*3), Image.Resampling.LANCZOS)
            crop_std = img_pil.crop((int(w*3*0.13), 0, int(w*3*0.55), h*3))
            gray = crop_std.convert('L'); inverted = ImageOps.invert(gray)
            enhancer = ImageEnhance.Contrast(inverted); img_pil = enhancer.enhance(2.5)
            crops = [img_pil]; debug_mode = "PIL 安全模式"
        
        debug_info['processed_img'] = crops[0]; full_ocr_log += f"[{debug_mode}]\n"
        psm_modes = [6, 4] 
        for crop in crops:
            for psm in psm_modes:
                text = pytesseract.image_to_string(crop, lang='chi_tra+eng', config=f'--psm {psm}')
                full_ocr_log += f"\n--- PSM {psm} ---\n{text}"
                lines = text.split('\n')
                for line in lines:
                    line = line.strip()
                    if len(line) < 2: continue
                    sid, sname = find_best_match_stock_v90(line)
                    if sid: found_stocks.add((sid, sname))
        debug_info['raw_text'] = full_ocr_log
        return list(found_stocks), debug_info
    except Exception as e:
        debug_info['error'] = str(e); return [], debug_info

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
            df.at[last_idx, 'Close'] = latest; df.at[last_idx, 'High'] = max(high, df.at[last_idx, 'High'])
            df.at[last_idx, 'Low'] = min(low, df.at[last_idx, 'Low']); df.at[last_idx, 'Volume'] = int(vol) * 1000
            bid_ask = {'bid_price': rt.get('best_bid_price', []), 'bid_volume': rt.get('best_bid_volume', []), 'ask_price': rt.get('best_ask_price', []), 'ask_volume': rt.get('best_ask_volume', [])}
            return df, bid_ask, rt_pack
    except: return df, None, None
    return df, None, None

def check_market_hours():
    tz = timezone(timedelta(hours=8)); now = datetime.now(tz)
    if now.weekday() > 4: return False, "今日為週末休市"
    if dt_time(8, 30) <= now.time() <= dt_time(13, 30): return True, "市場開盤中"
    else: return False, f"非交易時間 ({now.strftime('%H:%M')})"

def check_session():
    if "user" in st.query_params and not st.session_state.get('user_id'):
        st.session_state['user_id'] = st.query_params["user"]

defaults = {'view_mode': 'welcome', 'user_id': None, 'page_stack': ['welcome'], 'current_stock': "", 'current_name': "", 'scan_pool': [], 'scan_target_group': "全部", 'watch_active': False, 'monitor_active': False}
for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

check_session()

status_container = st.empty()
if not st.session_state['scan_pool']:
    status_container.info("🚀 系統初始化中，正在載入股票代碼，請稍候...")
    try:
        all_codes = [c for c in twstock.codes.values() if c.type in ["股票", "ETF"]]
        st.session_state['scan_pool'] = sorted([c.code for c in all_codes])
        groups = sorted(list(set(c.group for c in all_codes if c.group)))
        st.session_state['all_groups'] = ["🔍 全部上市櫃"] + groups
    except: 
        st.session_state['scan_pool'] = ['2330', '0050']; st.session_state['all_groups'] = ["全部"]
    status_container.empty()

def solve_stock_id(val):
    val = str(val).strip(); clean_val = re.sub(r'[^\w\u4e00-\u9fff\-\.]', '', val)
    if not clean_val: return None, None
    if clean_val in twstock.codes: return clean_val, twstock.codes[clean_val].name
    for c, d in twstock.codes.items():
        if d.type in ["股票", "ETF"] and d.name == clean_val: return c, d.name
    if len(clean_val) >= 2:
        for c, d in twstock.codes.items():
            if d.type in ["股票", "ETF"] and clean_val in d.name: return c, d.name
    return None, None

def is_ocr_ready(): return shutil.which('tesseract') is not None
def nav_to(mode, code=None, name=None):
    if code:
        st.session_state['current_stock'] = code; st.session_state['current_name'] = name
        if st.session_state['user_id']: db.add_history(st.session_state['user_id'], f"{code} {name}")
    st.session_state['view_mode'] = mode
    if st.session_state['page_stack'][-1] != mode: st.session_state['page_stack'].append(mode)

def go_back():
    if len(st.session_state['page_stack']) > 1: st.session_state['page_stack'].pop(); st.session_state['view_mode'] = st.session_state['page_stack'][-1]
    else: st.session_state['view_mode'] = 'welcome'

def handle_search():
    raw = st.session_state.search_input_val
    if raw:
        code, name = solve_stock_id(raw)
        if code: nav_to('analysis', code, name); st.session_state.search_input_val = ""
        else: st.toast(f"找不到代號 '{raw}'", icon="⚠️")

with st.sidebar:
    st.title("🎮 戰情控制台")
    uid = st.session_state['user_id']
    if uid: st.success(f"👤 {uid} (已登入)")
    else: st.info("👤 訪客模式")
    st.divider()
    st.text_input("🔍 搜尋 (支援股票/ETF)", key="search_input_val", on_change=handle_search)
    with st.container(border=True):
        st.markdown("### 🤖 AI 策略")
        sel_group = st.selectbox("1️⃣ 範圍", st.session_state.get('all_groups', ["全部"]), index=0)
        strat_map = {"⚡ 強力當沖": "day", "📈 穩健短線": "short", "🐢 長線安穩": "long", "🏆 熱門強勢": "top"}
        sel_strat_name = st.selectbox("2️⃣ 策略", list(strat_map.keys()))
        if st.button("🚀 啟動掃描 (最少20檔)", use_container_width=True):
            is_open, msg = check_market_hours(); current_mode = strat_map[sel_strat_name]
            if current_mode in ["top", "day"] and not is_open: st.error(f"⛔ {msg}：此策略需盤中使用。")
            else:
                st.session_state['scan_target_group'] = sel_group
                st.session_state['current_stock'] = current_mode
                st.session_state['scan_results'] = []; nav_to('scan', current_mode); st.rerun()
    st.divider()
    if st.button("📖 股市新手村"): nav_to('learn'); st.rerun()
    if st.button("🔒 個人自選股"): nav_to('watch'); st.rerun()
    if st.button("💬 戰友留言板"): nav_to('chat'); st.rerun()
    st.divider()
    if not uid:
        if st.button("🔐 登入/註冊"): nav_to('login'); st.rerun()
    else:
        if st.button("🚪 登出"): st.session_state['user_id']=None; st.session_state['watch_active']=False; st.query_params.clear(); nav_to('welcome'); st.rerun()
    if st.button("🏠 回首頁"): nav_to('welcome'); st.rerun()
    st.markdown("---"); st.caption("Ver: 105.0 (Violence Fix)")

mode = st.session_state['view_mode']

if mode == 'welcome':
    ui.render_header("👋 歡迎來到 AI 股市戰情室 V98")
    st.markdown("### 🚀 V98 穩定版更新：\n* **🏎️ 極速啟動**：優化載入流程，徹底解決黑畫面問題。\n* **🏢 簡介完美版**：無限長文翻譯，若無資料自動隱藏。\n* **🛡️ 雙防護盾**：防止 API 流量超標，保障 24 小時穩定運作。")

elif mode == 'login':
    ui.render_header("🔐 會員中心"); t1, t2 = st.tabs(["登入", "註冊"])
    with t1:
        u = st.text_input("帳號", key="l_u"); p = st.text_input("密碼", type="password", key="l_p")
        if st.button("登入"):
            ok, res = db.login_user(u, p)
            if ok: st.session_state['user_id']=u; st.query_params["user"] = u; st.success("登入成功"); time.sleep(0.5); nav_to('watch'); st.rerun()
            else: st.error(res)
    with t2:
        nu = st.text_input("新帳號", key="r_u"); np = st.text_input("新密碼", type="password", key="r_p"); nn = st.text_input("您的暱稱", key="r_n")
        if st.button("註冊"):
            ok, res = db.register_user(nu, np, nn)
            if ok: st.session_state['user_id']=nu; st.query_params["user"] = nu; st.success(f"歡迎 {nn}"); time.sleep(0.5); nav_to('watch'); st.rerun()
            else: st.error(res)
    ui.render_back_button(go_back)

elif mode == 'watch':
    ui.render_header("🔒 個人自選股"); uid = st.session_state['user_id']
    if not uid: st.warning("請先登入"); ui.render_back_button(go_back)
    else:
        wl = db.get_watchlist(uid); c1, c2 = st.columns([3,1])
        add_c = c1.text_input("✍️ 新增自選股", placeholder="代號/名稱")
        if c2.button("加入", use_container_width=True) and add_c: 
            code, name = solve_stock_id(add_c)
            if code: db.update_watchlist(uid, code, "add"); st.toast(f"已加入: {name}", icon="✅"); time.sleep(0.5); st.rerun()
            else: st.error(f"找不到: {add_c}")
        with st.expander("📸 截圖匯入 (V90 防爆版)", expanded=True):
            if is_ocr_ready():
                uploaded_file = st.file_uploader("上傳自選股截圖", type=['png', 'jpg', 'jpeg'])
                if uploaded_file:
                    with st.spinner("AI 正在分析截圖..."): found_list, debug_info = process_image_upload(uploaded_file)
                    if found_list:
                        new_stocks = [item for item in found_list if item[0] not in wl]
                        st.success(f"✅ 成功辨識 {len(found_list)} 檔商品")
                        if new_stocks:
                            if st.button(f"📥 將 {len(new_stocks)} 檔新商品加入清單"):
                                for wc, wn in new_stocks: db.update_watchlist(uid, wc, "add")
                                st.rerun()
                    else: st.error("未能辨識有效商品")
            else: st.error("❌ OCR 引擎未安裝")
        if wl:
            stock_data = [{"代號": code, "名稱": twstock.codes[code].name if code in twstock.codes else code} for code in wl]
            c_view, c_manage = st.columns([2, 1])
            with c_view: st.subheader(f"📊 持股列表 ({len(wl)})"); st.dataframe(pd.DataFrame(stock_data), use_container_width=True, height=300, hide_index=True)
            with c_manage:
                st.subheader("⚙️ 管理清單"); options = [f"{row['代號']} {row['名稱']}" for row in stock_data]
                remove_list = st.multiselect("選擇移除項目", options, label_visibility="collapsed")
                if st.button("🗑️ 確認移除", type="primary", use_container_width=True):
                    if remove_list:
                        for item in remove_list: db.update_watchlist(uid, item.split(" ")[0], "remove")
                        st.success("已移除"); st.rerun()
            if st.button("🚀 啟動 AI 詳細診斷 (V96)", use_container_width=True): st.session_state['watch_active'] = True; st.rerun()
            if st.session_state['watch_active']:
                st.success("診斷完成！")
                for i, code in enumerate(wl):
                    full_id, _, d, src = db.get_stock_data(code)
                    n = twstock.codes[code].name if code in twstock.codes else code
                    if d is not None:
                        d_real, _, _ = inject_realtime_data(d, code)
                        curr = d_real['Close'].iloc[-1] if isinstance(d_real, pd.DataFrame) else d_real['Close']
                        if ui.render_detailed_card(code, n, curr, d_real, src, key_prefix="watch", strategy_info="自選觀察"): nav_to('analysis', code, n); st.rerun()
        else: st.info("目前無自選股")
        ui.render_back_button(go_back)

elif mode == 'analysis':
    code = st.session_state['current_stock']; name = st.session_state['current_name']
    main_placeholder = st.empty()
    def render_content():
        with main_placeholder.container():
            is_live = ui.render_header(f"{name} {code}", show_monitor=True)
            full_id, stock, df, src = db.get_stock_data(code)
            if src == "fail": st.error("查無資料"); return False
            elif src == "yahoo":
                df, bid_ask, rt_pack = inject_realtime_data(df, code)
                symbol_id = stock.ticker if hasattr(stock, 'ticker') else code
                info = db.get_info_data(symbol_id) 
                
                # --- V105: 確保每個指標都傳入且不為 None ---
                curr = df['Close'].iloc[-1]
                div_data = db.get_dividend_data(symbol_id, curr)
                
                metrics = {
                    "cash_div": div_data['cash_div'], 
                    "yield": div_data['yield'],
                    "pe": info.get('trailingPE'),
                    "pb": info.get('priceToBook'),
                    "rev_growth": info.get('revenueGrowth'),
                    "mkt_cap": info.get('marketCap') or 0
                }
                
                shares = info.get('sharesOutstanding', 0)
                curr = df['Close'].iloc[-1]; prev = df['Close'].iloc[-2]; chg = curr - prev; pct = (chg/prev)*100
                vt = df['Volume'].iloc[-1]
                turnover = (vt / shares * 100) if shares > 0 else 0
                vy = df['Volume'].iloc[-2]; va = df['Volume'].tail(5).mean() + 1
                high = df['High'].iloc[-1]; low = df['Low'].iloc[-1]; amp = ((high - low) / prev) * 100
                fh = info.get('heldPercentInstitutions', 0)*100
                color_settings = db.get_color_settings(code)
                
                # V105: 確保 Chip Data 存在
                chip_data = db.get_chip_data(code)
                if not chip_data: chip_data = {"foreign": 0, "trust": 0, "dealer": 0, "date": ""}
                
                mf_str = "籌碼計算中..."
                if chip_data:
                    f = chip_data.get('foreign', 0); t = chip_data.get('trust', 0)
                    if f > 500 and t > 0: mf_str = "🔴 土洋合流"
                    elif f > 0: mf_str = "🔴 外資買進"
                    elif f < -1000: mf_str = "🟢 外資提款"
                    elif t > 0: mf_str = "🔴 投信佈局"
                    else: mf_str = "⚪ 觀望"
                
                vol_r = vt/va; vs = "爆量 🔥" if vol_r>1.5 else ("量縮 💤" if vol_r<0.6 else "正常")
                
                # V105 修正: 確保簡介區塊不被 try-except 吃掉
                summary = db.translate_text(info.get('longBusinessSummary',''))
                if summary: ui.render_company_profile(summary)
                
                ui.render_metrics_dashboard(curr, chg, pct, high, low, amp, mf_str, vt, vy, va, vs, fh, turnover, bid_ask, color_settings, rt_pack, stock_info=info, df=df, chip_data=chip_data, metrics=metrics)
                ui.render_chart(df, f"{name} K線圖", color_settings)
                
                m5 = df['Close'].rolling(5).mean().iloc[-1]; m20 = df['Close'].rolling(20).mean().iloc[-1]; m60 = df['Close'].rolling(60).mean().iloc[-1]
                delta = df['Close'].diff(); u = delta.copy(); d = delta.copy(); u[u<0]=0; d[d>0]=0
                rs = u.rolling(14).mean() / d.abs().rolling(14).mean(); rsi = (100 - 100/(1+rs)).iloc[-1]
                bias = ((curr-m60)/m60)*100
                ui.render_ai_report(curr, m5, m20, m60, rsi, bias, high, low, df, chip_data=chip_data)
                
                # V105: 籌碼分佈 (混合式強制渲染)
                if code.isdigit():
                    chip_dist = db.get_chip_distribution_v2(code, info)
                    ui.render_chip_structure(chip_dist)

            ui.render_back_button(go_back)
            return is_live

    is_live_mode = render_content()
    if is_live_mode:
        while True: 
            time.sleep(1)
            still_live = render_content() 
            if not still_live: 
                break

elif mode == 'learn':
    ui.render_header("📖 股市新手村"); t1, t2, t3 = st.tabs(["策略說明", "名詞解釋", "🕯️ K線型態"])
    with t1: st.markdown(STRATEGY_DESC)
    with t2:
        q = st.text_input("搜尋名詞"); 
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
    if not st.session_state['user_id']: st.warning("請先登入")
    else:
        with st.form("msg"):
            m = st.text_input("留言內容"); 
            if st.form_submit_button("送出") and m: db.save_comment(st.session_state['user_id'], m); st.rerun()
    st.markdown("<hr class='compact'>", unsafe_allow_html=True); df = db.get_comments()
    for i, r in df.iloc[::-1].head(20).iterrows(): st.info(f"**{r['Nickname']}** ({r['Time']}):\n{r['Message']}")
    ui.render_back_button(go_back)

elif mode == 'scan': 
    stype = st.session_state['current_stock']; target_group = st.session_state.get('scan_target_group', '全部')
    title_map = {'day': '⚡ 強力當沖', 'short': '📈 穩健短線', 'long': '🐢 長線安穩', 'top': '🏆 熱門強勢'}
    ui.render_header(f"🤖 {target_group} ⨉ {title_map.get(stype, stype)}")
    saved_codes = db.load_scan_results(stype) 
    c1, c2 = st.columns([1, 4]); do_scan = c1.button("🔄 開始智能篩選", type="primary")
    if saved_codes and not do_scan: c2.info(f"上次記錄: 共 {len(saved_codes)} 檔")
    else: c2.info(f"目標範圍: {target_group}")
    if do_scan:
        st.session_state['scan_results'] = []; raw_results = []
        full_pool = st.session_state['scan_pool']
        if target_group != "🔍 全部上市櫃": target_pool = [c for c in full_pool if c in twstock.codes and twstock.codes[c].group == target_group]
        else: target_pool = full_pool
        bar = st.progress(0); limit = 300 
        for i, c in enumerate(target_pool):
            if i >= limit: break
            bar.progress((i+1)/min(len(target_pool), limit))
            try:
                fid, _, d, src = db.get_stock_data(c)
                if d is not None and len(d) > 20:
                    d_real, _, _ = inject_realtime_data(d, c)
                    p = d_real['Close'].iloc[-1]; vol = d_real['Volume'].iloc[-1]
                    m5 = d_real['Close'].rolling(5).mean().iloc[-1]
                    valid = False; info_txt = ""
                    if stype == 'top' and vol > 2000000: valid = True; info_txt = f"量 {int(vol/1000)}張"
                    elif stype == 'short' and p > m5: valid = True
                    if valid: raw_results.append({'c': c, 'n': twstock.codes[c].name if c in twstock.codes else c, 'p': p, 'd': d_real, 'src': src, 'info': info_txt})
            except: pass
        bar.empty(); st.session_state['scan_results'] = raw_results[:50]; st.rerun() 
    
    display_list = st.session_state['scan_results']
    if not display_list and not do_scan and saved_codes:
         temp_list = []
         for i, c in enumerate(saved_codes[:30]):
             fid, _, d, src = db.get_stock_data(c)
             if d is not None:
                 n = twstock.codes[c].name if c in twstock.codes else c
                 temp_list.append({'c':c, 'n':n, 'p':d['Close'].iloc[-1], 'd':d, 'src':src, 'info': f"AI 推薦"})
         display_list = temp_list
    if display_list:
        for i, item in enumerate(display_list):
            if ui.render_detailed_card(item['c'], item['n'], item['p'], item['d'], item['src'], key_prefix=f"scan_{stype}", rank=i+1, strategy_info=item['info']):
                nav_to('analysis', item['c'], item['n']); st.rerun()
    ui.render_back_button(go_back)
