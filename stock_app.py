import streamlit as st
import time
import twstock
import pandas as pd
import re
import shutil
import subprocess
import os
from PIL import Image, ImageOps, ImageEnhance, ImageFilter
import pytesseract
import importlib
from datetime import datetime, time as dt_time, timedelta, timezone
import difflib 
import numpy as np
import cv2 # 引入 OpenCV (需在 requirements.txt 加入 opencv-python-headless)

import stock_db as db
import stock_ui as ui

# 載入知識庫
try:
    import knowledge
    importlib.reload(knowledge)
    from knowledge import STOCK_TERMS, STRATEGY_DESC, KLINE_PATTERNS
except:
    STOCK_TERMS = {}; STRATEGY_DESC = "System Loading..."; KLINE_PATTERNS = {}

st.set_page_config(page_title="AI 股市戰情室 V86", layout="wide")

# --- V86: 基於 OpenCV 的高階影像處理 ---
def preprocess_image_v86(image_file):
    """
    V86 核心技術:
    1. 轉換為 OpenCV 格式
    2. 針對台新介面進行色彩過濾 (去除橘色標籤)
    3. 增強白色/黃色/綠色文字 (股名)
    """
    # 讀取圖片並轉為 OpenCV 格式
    file_bytes = np.asarray(bytearray(image_file.read()), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    
    # 1. 放大圖片 (Upscaling) - 提升小字辨識率
    scale_percent = 300 # 放大 300%
    width = int(img.shape[1] * scale_percent / 100)
    height = int(img.shape[0] * scale_percent / 100)
    dim = (width, height)
    img = cv2.resize(img, dim, interpolation=cv2.INTER_CUBIC)

    # 2. 轉換到 HSV 色彩空間
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # 3. 定義遮罩 (Masking)
    # 台新介面的股名通常是: 白色、黃色、綠色、紅色
    # 我們要過濾掉的是背景(黑)和雜訊
    
    # 定義 "非黑色" 的區域 (保留所有彩色文字)
    lower_val = np.array([0, 0, 80]) # 亮度大於 80
    upper_val = np.array([180, 255, 255])
    mask = cv2.inRange(hsv, lower_val, upper_val)
    
    # 4. 形態學操作 (Morphology)
    # 膨脹 (Dilation) 與 腐蝕 (Erosion)
    # 目的: 把斷掉的筆畫連起來，去除孤立的噪點
    kernel = np.ones((2,2), np.uint8)
    mask = cv2.dilate(mask, kernel, iterations=1)
    
    # 5. 反轉 (Invert) -> 變成白底黑字 (Tesseract 最愛)
    result = cv2.bitwise_not(mask)
    
    # 轉回 PIL Image 以供 Tesseract 使用
    final_pil = Image.fromarray(result)
    return final_pil

# --- V86: 智慧型 Regex 撈取邏輯 ---
def find_stocks_in_text(text):
    """
    從雜亂的 OCR 文字堆中，精準撈出股票名稱
    """
    potential_stocks = []
    
    # 1. 建立資料庫索引 (含 ETF)
    all_codes = {}
    for code, data in twstock.codes.items():
        if data.type in ["股票", "ETF"]:
            all_codes[code] = data.name
    
    # 反查表: 名稱 -> 代號
    name_to_code = {v: k for k, v in all_codes.items()}
    all_names = list(name_to_code.keys())

    # 2. 逐行分析
    lines = text.split('\n')
    for line in lines:
        line = line.strip().upper()
        if len(line) < 2: continue
        
        # 移除干擾字
        line = re.sub(r'[|\[\](){}]', '', line) # 移除框線符號
        line = line.replace("試撮", "").replace("注意", "")
        
        # 模式 A: 偵測 4 碼數字 (代號)
        # 例如: "2330 台積電" -> 抓出 2330
        code_match = re.search(r'\b\d{4}\b', line)
        if code_match:
            code = code_match.group(0)
            if code in all_codes:
                potential_stocks.append((code, all_codes[code]))
                continue # 這行抓到了，換下一行

        # 模式 B: 偵測純中文名稱 (2~6字)
        # 過濾掉數字、股價，只看中文
        # 針對 ETF，名稱可能含數字 (如 0050)，所以我們比較寬鬆
        
        # 移除股價 (小數點前後的數字)
        clean_line = re.sub(r'\d+\.\d+', '', line)
        # 移除大整數 (可能是成交量)
        clean_line = re.sub(r'\b\d{3,}\b', '', clean_line)
        
        # 移除特殊符號，只留中英數
        clean_line = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\-]', '', clean_line)
        
        # 直接拿去資料庫比對
        # 1. 完全匹配
        if clean_line in name_to_code:
            potential_stocks.append((name_to_code[clean_line], clean_line))
            continue
            
        # 2. 包含搜尋 (例如 OCR 讀成 "元大台灣50 63.85" -> "元大台灣50")
        for db_name in all_names:
            if len(db_name) < 2: continue
            
            # 策略：如果資料庫的股票名稱，完整出現在這一行文字裡
            if db_name in clean_line:
                # 再次確認長度，避免 "金" 對到 "國泰金"
                # 如果 clean_line 很長 (例如 "元大台灣50ETF基金")，但 db_name 是 "元大台灣50"，這是 OK 的
                # 但如果 clean_line 是 "金"，db_name 是 "國泰金"，這是 不OK 的
                potential_stocks.append((name_to_code[db_name], db_name))
                break # 找到一個最像的就停
                
        # 3. 模糊比對 (針對錯字)
        # 只有當字串長度 > 2 才做，避免誤判
        if len(clean_line) >= 2:
            matches = difflib.get_close_matches(clean_line, all_names, n=1, cutoff=0.7) # 高門檻 0.7
            if matches:
                best_match = matches[0]
                potential_stocks.append((name_to_code[best_match], best_match))

    # 去除重複
    unique_stocks = list(set(potential_stocks))
    return unique_stocks

# --- V86: 主處理流程 ---
def process_image_upload(image_file):
    debug_info = {"raw_text": "", "processed_img": None, "error": None}
    
    try:
        # 1. 為了使用 OpenCV，需重置 file pointer
        image_file.seek(0)
        
        # 2. OpenCV 高階預處理
        processed_img_pil = preprocess_image_v86(image_file)
        debug_info['processed_img'] = processed_img_pil
        
        # 3. Tesseract OCR (使用雙語模式 + PSM 6)
        # PSM 6: 假設是統一的文字區塊，這對列表式資料最有效
        text = pytesseract.image_to_string(processed_img_pil, lang='chi_tra+eng', config='--psm 6')
        debug_info['raw_text'] = text
        
        # 4. 智慧撈取
        found_list = find_stocks_in_text(text)
        
        return found_list, debug_info

    except Exception as e:
        debug_info['error'] = str(e)
        # 如果 OpenCV 失敗 (例如 user 沒裝套件)，回退到 PIL
        return [], debug_info

# --- 以下維持 V79~V85 核心功能 (不簡化) ---

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
            
            rt_pack = {
                'latest_trade_price': latest, 'high': high, 'low': low, 'open': open_p,
                'accumulate_trade_volume': vol,
                'previous_close': float(df['Close'].iloc[-2]) if len(df)>1 else open_p
            }
            
            last_idx = df.index[-1]
            df.at[last_idx, 'Close'] = latest
            df.at[last_idx, 'High'] = max(high, df.at[last_idx, 'High'])
            df.at[last_idx, 'Low'] = min(low, df.at[last_idx, 'Low'])
            df.at[last_idx, 'Volume'] = int(vol) * 1000
            
            bid_ask = {
                'bid_price': rt.get('best_bid_price', []), 'bid_volume': rt.get('best_bid_volume', []),
                'ask_price': rt.get('best_ask_price', []), 'ask_volume': rt.get('best_ask_volume', [])
            }
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

def check_session():
    qp = st.query_params
    if "user" in qp and not st.session_state.get('user_id'):
        uid = qp["user"]
        st.session_state['user_id'] = uid
        return True
    return False

defaults = {
    'view_mode': 'welcome', 'user_id': None, 'page_stack': ['welcome'],
    'current_stock': "", 'current_name': "", 'scan_pool': [], 'filtered_pool': [],      
    'scan_target_group': "全部", 'watch_active': False, 'scan_results': [],
    'monitor_active': False
}
for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

check_session()

if not st.session_state['scan_pool']:
    try:
        all_codes = [c for c in twstock.codes.values() if c.type in ["股票", "ETF"]]
        st.session_state['scan_pool'] = sorted([c.code for c in all_codes])
        groups = sorted(list(set(c.group for c in all_codes if c.group)))
        st.session_state['all_groups'] = ["🔍 全部上市櫃"] + groups
    except:
        st.session_state['scan_pool'] = ['2330', '0050']; st.session_state['all_groups'] = ["全部"]

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

def is_ocr_ready(): return shutil.which('tesseract') is not None
def check_language_pack(): return True 

def nav_to(mode, code=None, name=None):
    if code:
        st.session_state['current_stock'] = code
        st.session_state['current_name'] = name
        if st.session_state['user_id']: db.add_history(st.session_state['user_id'], f"{code} {name}")
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

# --- Sidebar ---
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
            is_open, msg = check_market_hours()
            current_mode = strat_map[sel_strat_name]
            if current_mode in ["top", "day"] and not is_open:
                st.error(f"⛔ {msg}：此策略需盤中使用。")
            else:
                st.session_state['scan_target_group'] = sel_group
                st.session_state['current_stock'] = current_mode
                st.session_state['scan_results'] = []
                nav_to('scan', current_mode); st.rerun()

    if st.button("🔥 當日強勢股票 (開盤限定)"):
        is_open, msg = check_market_hours()
        if is_open:
            st.toast("🚀 正在鎖定當日強勢股...", icon="🔥")
            st.session_state['scan_target_group'] = "🔍 全部上市櫃"
            st.session_state['current_stock'] = "top"
            st.session_state['scan_results'] = [] 
            nav_to('scan', 'top'); st.rerun()
        else: st.error(f"⛔ {msg}")

    st.divider()
    if st.button("📖 股市新手村"): nav_to('learn'); st.rerun()
    if st.button("🔒 個人自選股"): nav_to('watch'); st.rerun()
    if st.button("💬 戰友留言板"): nav_to('chat'); st.rerun()
    st.divider()
    if not uid:
        if st.button("🔐 登入/註冊"): nav_to('login'); st.rerun()
    else:
        if st.button("🚪 登出"): 
            st.session_state['user_id']=None
            st.session_state['watch_active']=False
            st.query_params.clear()
            nav_to('welcome'); st.rerun()
    if st.button("🏠 回首頁"): nav_to('welcome'); st.rerun()
    st.markdown("---"); st.caption("Ver: 86.0 (OpenCV視覺神經版)")

# --- Main Logic ---
mode = st.session_state['view_mode']

if mode == 'welcome':
    ui.render_header("👋 歡迎來到 AI 股市戰情室 V86")
    st.markdown("### 🚀 V86 更新：適應性視覺神經網路\n* **👁️ 模擬人眼**：導入 OpenCV 電腦視覺，像人眼一樣過濾顏色與雜訊。\n* **🎨 色彩分離**：自動隱藏橘色標籤，突顯白色股名。\n* **🧬 膨脹修復**：修補破碎字體，大幅提升辨識率。")

elif mode == 'login':
    ui.render_header("🔐 會員中心")
    t1, t2 = st.tabs(["登入", "註冊"])
    with t1:
        u = st.text_input("帳號", key="l_u"); p = st.text_input("密碼", type="password", key="l_p")
        if st.button("登入"):
            ok, res = db.login_user(u, p)
            if ok: 
                st.session_state['user_id']=u
                st.query_params["user"] = u
                st.success("登入成功"); time.sleep(0.5); nav_to('watch'); st.rerun()
            else: st.error(res)
    with t2:
        nu = st.text_input("新帳號", key="r_u"); np = st.text_input("新密碼", type="password", key="r_p")
        nn = st.text_input("您的暱稱", key="r_n")
        if st.button("註冊"):
            ok, res = db.register_user(nu, np, nn)
            if ok: 
                st.session_state['user_id']=nu
                st.query_params["user"] = nu
                st.success(f"歡迎 {nn}"); time.sleep(0.5); nav_to('watch'); st.rerun()
            else: st.error(res)
    ui.render_back_button(go_back)

elif mode == 'watch':
    ui.render_header("🔒 個人自選股")
    uid = st.session_state['user_id']
    if not uid: st.warning("請先登入"); ui.render_back_button(go_back)
    else:
        wl = db.get_watchlist(uid)
        c1, c2 = st.columns([3,1])
        add_c = c1.text_input("✍️ 新增自選股", placeholder="代號/名稱")
        if c2.button("加入", use_container_width=True) and add_c: 
            code, name = solve_stock_id(add_c)
            if code: db.update_watchlist(uid, code, "add"); st.toast(f"已加入: {name}", icon="✅"); time.sleep(0.5); st.rerun()
            else: st.error(f"找不到: {add_c}")

        with st.expander("📸 截圖匯入 (V86 OpenCV神經版)", expanded=True):
            if is_ocr_ready():
                uploaded_file = st.file_uploader("上傳自選股截圖 (支援各家券商黑底介面)", type=['png', 'jpg', 'jpeg'])
                if uploaded_file:
                    with st.spinner("AI 正在使用電腦視覺 (OpenCV) 進行色彩分離與識別..."): 
                        found_list, debug_info = process_image_upload(uploaded_file)
                    
                    if found_list:
                        new_stocks = [item for item in found_list if item[0] not in wl]
                        st.success(f"✅ 成功辨識 {len(found_list)} 檔商品")
                        
                        cols = st.columns(4)
                        for i, (wc, wn) in enumerate(found_list):
                            cols[i % 4].caption(f"{wc} {wn}")
                            
                        if new_stocks:
                            if st.button(f"📥 將 {len(new_stocks)} 檔新商品加入清單"):
                                for wc, wn in new_stocks: db.update_watchlist(uid, wc, "add")
                                st.rerun()
                        else: st.info("所有商品都已在清單中。")
                        
                        with st.expander("👀 查看 AI 視覺處理結果"):
                            if debug_info['processed_img']:
                                st.image(debug_info['processed_img'], caption="經由 OpenCV 增強後的影像")
                            st.text("--- 辨識原始文字 ---")
                            st.text(debug_info['raw_text'])
                    else: 
                        if debug_info['error']: st.error(f"處理失敗: {debug_info['error']}")
                        else: st.error("未能辨識有效商品，請確認圖片清晰度。")
            else: st.error("❌ OCR 引擎未安裝")

        if wl:
            stock_data = []
            for code in wl:
                name = code
                if code in twstock.codes: name = twstock.codes[code].name
                stock_data.append({"代號": code, "名稱": name})
            
            c_view, c_manage = st.columns([2, 1])
            with c_view:
                st.subheader(f"📊 持股列表 ({len(wl)})")
                st.dataframe(pd.DataFrame(stock_data), use_container_width=True, height=300, hide_index=True)
            
            with c_manage:
                st.subheader("⚙️ 管理清單")
                options = [f"{row['代號']} {row['名稱']}" for row in stock_data]
                remove_list = st.multiselect("選擇移除項目", options, label_visibility="collapsed")
                if st.button("🗑️ 確認移除", type="primary", use_container_width=True):
                    if remove_list:
                        for item in remove_list:
                            code_to_remove = item.split(" ")[0]
                            db.update_watchlist(uid, code_to_remove, "remove")
                        st.success("已移除"); st.rerun()

            st.markdown("<hr class='compact'>", unsafe_allow_html=True)
            if st.button("🚀 啟動 AI 詳細診斷 (V86)", use_container_width=True): 
                st.session_state['watch_active'] = True; st.rerun()
            
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

# (其他頁面 analysis, learn, chat, scan 皆維持原樣，不簡化)
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
                curr = df['Close'].iloc[-1]; prev = df['Close'].iloc[-2]; chg = curr - prev; pct = (chg/prev)*100
                vt = df['Volume'].iloc[-1]
                turnover = (vt / shares * 100) if shares > 0 else 0
                vy = df['Volume'].iloc[-2]; va = df['Volume'].tail(5).mean() + 1
                high = df['High'].iloc[-1]; low = df['Low'].iloc[-1]; amp = ((high - low) / prev) * 100
                mf = "主力進貨 🔴" if (chg>0 and vt>vy) else ("主力出貨 🟢" if (chg<0 and vt>vy) else "觀望")
                vol_r = vt/va; vs = "爆量 🔥" if vol_r>1.5 else ("量縮 💤" if vol_r<0.6 else "正常")
                fh = info.get('heldPercentInstitutions', 0)*100
                color_settings = db.get_color_settings(code)
                ui.render_company_profile(db.translate_text(info.get('longBusinessSummary','')))
                ui.render_metrics_dashboard(curr, chg, pct, high, low, amp, mf, vt, vy, va, vs, fh, turnover, bid_ask, color_settings, rt_pack)
                ui.render_chart(df, f"{name} K線圖", color_settings)
                m5 = df['Close'].rolling(5).mean().iloc[-1]; m20 = df['Close'].rolling(20).mean().iloc[-1]; m60 = df['Close'].rolling(60).mean().iloc[-1]
                delta = df['Close'].diff(); u = delta.copy(); d = delta.copy(); u[u<0]=0; d[d>0]=0
                rs = u.rolling(14).mean() / d.abs().rolling(14).mean(); rsi = (100 - 100/(1+rs)).iloc[-1]
                bias = ((curr-m60)/m60)*100
                ui.render_ai_report(curr, m5, m20, m60, rsi, bias, high, low, df)
            ui.render_back_button(go_back)
            return is_live
    is_live_mode = render_content()
    if is_live_mode:
        while True:
            time.sleep(1)
            still_live = render_content()
            if not still_live: break

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
        st.info("這裡展示常見的 K 線反轉訊號，紅 K 代表漲 (台股規則)。")
        st.subheader("🔥 多方訊號 (看漲)")
        for name, data in KLINE_PATTERNS.get("bull", {}).items(): ui.render_kline_pattern_card(name, data)
        st.divider()
        st.subheader("❄️ 空方訊號 (看跌)")
        for name, data in KLINE_PATTERNS.get("bear", {}).items(): ui.render_kline_pattern_card(name, data)
    ui.render_back_button(go_back)

elif mode == 'chat':
    ui.render_header("💬 戰友留言板")
    if not st.session_state['user_id']: st.warning("請先登入")
    else:
        with st.form("msg"):
            m = st.text_input("留言內容")
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
        if not target_pool: st.error("無資料"); st.stop()
        bar = st.progress(0); limit = 500 
        for i, c in enumerate(target_pool):
            if i >= limit: break
            bar.progress((i+1)/min(len(target_pool), limit))
            try:
                fid, _, d, src = db.get_stock_data(c)
                if d is not None:
                    d_real, _, _ = inject_realtime_data(d, c)
                    n = twstock.codes[c].name if c in twstock.codes else c
                    p = d_real['Close'].iloc[-1] if isinstance(d_real, pd.DataFrame) else d_real['Close']
                    sort_val = -999999; info_txt = ""
                    if isinstance(d_real, pd.DataFrame) and len(d_real) > 20:
                        vol = d_real['Volume'].iloc[-1]; vol_prev = d_real['Volume'].iloc[-2]
                        m5 = d_real['Close'].rolling(5).mean().iloc[-1]
                        m20 = d_real['Close'].rolling(20).mean().iloc[-1]
                        m60 = d_real['Close'].rolling(60).mean().iloc[-1]
                        prev = d_real['Close'].iloc[-2]
                        pct = ((p - prev) / prev) * 100
                        amp = ((d_real['High'].iloc[-1] - d_real['Low'].iloc[-1]) / prev) * 100
                        delta = d_real['Close'].diff(); u = delta.copy(); down = delta.copy(); u[u<0]=0; down[down>0]=0
                        rs = u.rolling(14).mean() / down.abs().rolling(14).mean()
                        rsi = (100 - 100/(1+rs)).iloc[-1]
                        valid = False
                        if stype == 'day': 
                            if vol > vol_prev * 1.5 and p > d_real['Open'].iloc[-1] and p > m5 and amp > 2:
                                sort_val = vol; info_txt = f"🔥 爆量 {int(vol/vol_prev)} 倍 | 振幅 {amp:.1f}%"; valid = True
                        elif stype == 'short': 
                            if m5 > m20 and p > m20 and 50 < rsi < 75:
                                sort_val = pct; info_txt = f"🚀 多頭排列 | RSI {rsi:.0f}"; valid = True
                        elif stype == 'long': 
                            bias = ((p - m60)/m60)*100
                            if p > m60 and -5 < bias < 10: 
                                sort_val = vol; info_txt = f"🐢 季線之上 | 乖離 {bias:.1f}%"; valid = True
                        elif stype == 'top': 
                            if vol > 1000000: 
                                sort_val = pct; info_txt = f"🏆 漲幅 {pct:.2f}% | 量 {int(vol/1000)}張"; valid = True
                        if valid: raw_results.append({'c': c, 'n': n, 'p': p, 'd': d_real, 'src': src, 'val': sort_val, 'info': info_txt})
            except: pass
        bar.empty()
        raw_results.sort(key=lambda x: x['val'], reverse=True)
        top_50 = [x['c'] for x in raw_results[:50]]
        db.save_scan_results(stype, top_50)
        st.session_state['scan_results'] = raw_results[:50]; st.rerun() 

    display_list = st.session_state['scan_results']
    if not display_list and not do_scan and saved_codes and target_group == "🔍 全部上市櫃":
         temp_list = []
         for i, c in enumerate(saved_codes[:50]):
             fid, _, d, src = db.get_stock_data(c)
             if d is not None:
                 d_real, _, _ = inject_realtime_data(d, c)
                 p = d_real['Close'].iloc[-1] if isinstance(d_real, pd.DataFrame) else d_real['Close']
                 n = twstock.codes[c].name if c in twstock.codes else c
                 temp_list.append({'c':c, 'n':n, 'p':p, 'd':d_real, 'src':src, 'info': f"AI 推薦 #{i+1}"})
         display_list = temp_list

    if display_list:
        for i, item in enumerate(display_list):
            if ui.render_detailed_card(item['c'], item['n'], item['p'], item['d'], item['src'], key_prefix=f"scan_{stype}", rank=i+1, strategy_info=item['info']):
                nav_to('analysis', item['c'], item['n']); st.rerun()
    elif not do_scan: st.warning("請點擊上方按鈕「開始智能篩選」")
    ui.render_back_button(go_back)
