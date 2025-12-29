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
from pytesseract import Output # V86 新增: 用於獲取座標資訊
import importlib
from datetime import datetime, time as dt_time, timedelta, timezone
import difflib 
import numpy as np # V86 新增: 用於計算座標中位數

import stock_db as db
import stock_ui as ui

try:
    import knowledge
    importlib.reload(knowledge)
    from knowledge import STOCK_TERMS, STRATEGY_DESC, KLINE_PATTERNS
except:
    STOCK_TERMS = {}; STRATEGY_DESC = "System Loading..."; KLINE_PATTERNS = {}

st.set_page_config(page_title="AI 股市戰情室 V86", layout="wide")

# --- V86: 終極字串比對與清洗 ---
def clean_text_v86(text):
    """V86 專用強力清洗：移除所有非股名元素"""
    # 1. 移除常見雜訊詞
    garbage = ["試撮", "注意", "處置", "全額", "資券", "當沖", "商品", "群組", "成交", "漲跌", "幅度", "代號", "買進", "賣出", "總量", "庫存", "損益", "現價", "成本"]
    text_upper = text.upper()
    for g in garbage:
        text_upper = text_upper.replace(g, "")
        
    # 2. 移除所有數字和小數點 (V86: 這是關鍵，因為我們依賴座標過濾，殘留的數字一定是雜訊)
    # 但要小心保留 ETF 名稱中的數字 (如 0050 的 50)，這在比對階段處理
    # 這裡先移除像是價格的數字結構
    text_cleaned = re.sub(r'\d+\.\d+', '', text_upper) # 移除小數點價格
    
    # 3. 移除特殊符號，只保留中英數和連字號
    text_cleaned = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\-]', '', text_cleaned)
    
    return text_cleaned.strip()

def find_best_match_stock_v86(text):
    """V86: 基於幾何過濾後的精準比對 (含ETF)"""
    clean_input = clean_text_v86(text)
    if len(clean_input) < 2: return None, None
    # 如果清洗後只剩數字，且不是4碼，極大機率是殘留的價格或代號片段
    if clean_input.isdigit() and len(clean_input) != 4: return None, None

    # 建立搜尋清單 (股票 + ETF)
    all_codes = {}
    for code, data in twstock.codes.items():
        if data.type in ["股票", "ETF"]:
            all_codes[code] = data.name
    
    name_to_code = {v: k for k, v in all_codes.items()}
    all_names = list(name_to_code.keys())

    # 1. 精準匹配 (優先)
    if clean_input in name_to_code: return name_to_code[clean_input], clean_input
    if clean_input in all_codes: return clean_input, all_codes[clean_input]

    # 2. 包含搜尋 (處理 OCR 黏字或漏字)
    # 針對台新介面，有時 "華城" 會被讀成 "撮華城"，清洗後變 "華城"，已在上面擋掉
    # 這裡處理像 "元大台灣50" 被讀成 "元大台灣" 的情況
    for name in all_names:
        # 確保 input 夠長才做包含搜尋，避免 "金" 匹配所有金控
        if len(clean_input) >= 2 and (clean_input in name):
             # 字數差異懲罰：長度差太多視為誤判
            if abs(len(name) - len(clean_input)) <= 2:
                return name_to_code[name], name
    
    # 3. 高門檻模糊比對 (最後防線)
    # 門檻設為 0.7，寧缺勿濫，避免幻覺
    matches = difflib.get_close_matches(clean_input, all_names, n=1, cutoff=0.7)
    if matches:
        best_match = matches[0]
        if abs(len(best_match) - len(clean_input)) <= 2:
            return name_to_code[best_match], best_match

    return None, None

# --- V86 重寫: 幾何結構分析引擎 (The Geometric Engine) ---
def process_image_upload(image_file):
    debug_info = {"raw_text": "V86 Geometric Analysis", "processed_img": None, "error": None}
    found_stocks = set()
    
    try:
        # 1. 影像前處理 (維持高解析與對比)
        img = Image.open(image_file)
        if img.mode != 'RGB': img = img.convert('RGB')
        
        # 3x 超解析放大
        target_width = img.width * 3
        target_height = img.height * 3
        img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
        
        # 黑底轉白底 + 高對比增強
        gray = img.convert('L')
        inverted = ImageOps.invert(gray) 
        enhancer = ImageEnhance.Contrast(inverted)
        # V86: 使用稍微柔和一點的對比度，保留更多細節給幾何分析
        high_contrast = enhancer.enhance(2.0)
        
        # 二值化
        thresh = 150
        final_img = high_contrast.point(lambda x: 255 if x > thresh else 0, mode='1')
        debug_info['processed_img'] = final_img

        # 2. V86 核心: 獲取詳細座標資料 (image_to_data)
        # Output.DICT 會回傳一個字典，包含每個辨識出的字詞的 text, left, top, width, height 等資訊
        data = pytesseract.image_to_data(final_img, lang='chi_tra+eng', output_type=Output.DICT)
        
        # 3. 幾何結構分析：尋找「股名縱貫線」
        potential_stock_lefts = []
        n_boxes = len(data['text'])
        
        # 初步篩選可能的股名候選字詞
        for i in range(n_boxes):
            text = data['text'][i].strip()
            # 排除空白、純數字、純符號、過短的詞
            if not text or text.isdigit() or len(text) < 2: continue
            # 排除常見介面雜訊詞
            if any(x in text for x in ["試撮", "注意", "商品", "成交", "漲跌"]): continue
            
            # 如果包含中文字或英文字母，視為潛在股名片段，記錄其左側座標 (X軸)
            if re.search(r'[\u4e00-\u9fa5a-zA-Z]', text):
                potential_stock_lefts.append(data['left'][i])
                
        if not potential_stock_lefts:
            debug_info['error'] = "無法偵測到垂直排列的股票名稱結構"
            return [], debug_info

        # 計算中位數，找出最可能的「股名起始 X 座標」
        # 大部分的股名應該會對齊在某個 X 軸位置附近
        median_left = np.median(potential_stock_lefts)
        
        # 定義「股名廊道 (Corridor)」：中位數左右各延伸一定範圍
        # 這個範圍內的文字被視為股名，範圍外的視為雜訊
        corridor_margin = target_width * 0.05 # 容許誤差範圍 (例如總寬度的 5%)
        x_min = median_left - corridor_margin
        x_max = median_left + corridor_margin + (target_width * 0.1) # 右側稍微寬一點容納長股名
        
        # 4. 基於幾何位置的文字重建
        # 根據 Y 軸 (top) 將文字分行
        line_map = {} # 格式: {top_coord: [word1, word2, ...]}
        
        for i in range(n_boxes):
            text = data['text'][i].strip()
            left = data['left'][i]
            top = data['top'][i]
            height = data['height'][i]
            
            if not text: continue
            
            # V86 關鍵判斷：只有落在「股名廊道」內的文字才保留
            if x_min <= left <= x_max:
                # 簡單的行對齊邏輯：將 Y 座標相近的視為同一行
                found_line = False
                for existing_top in line_map.keys():
                    # 如果這兩個字的 Y 座標差異小於字高的一半，視為同一行
                    if abs(top - existing_top) < (height * 0.5):
                        line_map[existing_top].append(text)
                        found_line = True
                        break
                if not found_line:
                    line_map[top] = [text]
                    
        # 5. 將重建的行進行比對
        reconstructed_lines = []
        for top in sorted(line_map.keys()):
            # 將同一行的字詞合併
            line_text = "".join(line_map[top])
            reconstructed_lines.append(line_text)
            
            # 呼叫 V86 比對函式
            sid, sname = find_best_match_stock_v86(line_text)
            if sid:
                found_stocks.add((sid, sname))

        debug_info['raw_text'] = "\n".join(reconstructed_lines) # 顯示幾何重建後的文字

        return list(found_stocks), debug_info

    except Exception as e:
        debug_info['error'] = str(e)
        return [], debug_info

# --- 以下維持核心功能 (不簡化) ---

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
        all_codes = [c for c in twstock.codes.values() if c.type in ["股票", "ETF"]] # V86: 確保池子包含 ETF
        st.session_state['scan_pool'] = sorted([c.code for c in all_codes])
        groups = sorted(list(set(c.group for c in all_codes if c.group)))
        st.session_state['all_groups'] = ["🔍 全部上市櫃"] + groups
    except:
        st.session_state['scan_pool'] = ['2330', '0050']; st.session_state['all_groups'] = ["全部"]

def solve_stock_id(val):
    val = str(val).strip()
    if not val: return None, None
    clean_val = re.sub(r'[^\w\u4e00-\u9fff\-\.]', '', val) # V86: 允許 . (針對某些ETF代號)
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
    st.markdown("---"); st.caption("Ver: 86.0 (幾何結構分析終極版)")

# --- Main Logic ---
mode = st.session_state['view_mode']

if mode == 'welcome':
    ui.render_header("👋 歡迎來到 AI 股市戰情室 V86")
    st.markdown("### 🚀 V86 終極更新：幾何結構分析引擎\n* **📐 幾何定位技術**：不再依賴固定裁切，AI 自動分析畫面結構，找出股名所在的「縱貫線」，適應不同券商介面。\n* **🎯 動態雜訊排除**：基於座標位置，自動忽略標籤與股價數字。\n* **🛡️ 嚴格雙重驗證**：結合幾何過濾與高門檻比對，徹底解決偵測錯誤與幻覺問題。")

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

        with st.expander("📸 截圖匯入 (V86 幾何分析版)", expanded=True):
            if is_ocr_ready():
                uploaded_file = st.file_uploader("上傳自選股截圖 (支援各家券商黑底介面)", type=['png', 'jpg', 'jpeg'])
                if uploaded_file:
                    with st.spinner("AI 正在進行幾何結構分析與定位..."): 
                        found_list, debug_info = process_image_upload(uploaded_file)
                    
                    if found_list:
                        new_stocks = [item for item in found_list if item[0] not in wl]
                        st.success(f"✅ 成功定位並辨識 {len(found_list)} 檔商品")
                        
                        cols = st.columns(4)
                        for i, (wc, wn) in enumerate(found_list):
                            cols[i % 4].caption(f"{wc} {wn}")
                            
                        if new_stocks:
                            if st.button(f"📥 將 {len(new_stocks)} 檔新商品加入清單"):
                                for wc, wn in new_stocks: db.update_watchlist(uid, wc, "add")
                                st.rerun()
                        else: st.info("所有商品都已在清單中。")
                        
                        with st.expander("👀 查看幾何重建結果"):
                            if debug_info['processed_img']:
                                st.image(debug_info['processed_img'], caption="AI 分析用影像")
                            st.text("--- 幾何重建後的文字序列 ---")
                            st.text(debug_info['raw_text'])
                    else: 
                        if debug_info['error']:
                            st.error(f"分析失敗: {debug_info['error']}")
                        else:
                            st.error("未能辨識有效商品，請確認截圖清晰度。")
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
