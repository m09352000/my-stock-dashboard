import streamlit as st
import time
import twstock
import pandas as pd
import re

# 影像處理套件
from PIL import Image
import pytesseract

# 引入模組
import stock_db as db
import stock_ui as ui
try:
    from knowledge import STOCK_TERMS, STRATEGY_DESC
except:
    STOCK_TERMS = {}; STRATEGY_DESC = "系統模組載入中..."

# --- 設定 (必須第一行) ---
st.set_page_config(page_title="AI 股市戰情室 V48", layout="wide")

# --- 初始化 State ---
defaults = {
    'view_mode': 'welcome',
    'user_id': None,
    'page_stack': ['welcome'],
    'current_stock': "",
    'current_name': "",
    'scan_pool': [],          
    'filtered_pool': [],      
    'scan_target_group': "全部", 
    'watch_active': False,
    'scan_results': []
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# 初始化掃描池
if not st.session_state['scan_pool']:
    try:
        all_codes = [c for c in twstock.codes.values() if c.type == "股票"]
        st.session_state['scan_pool'] = sorted([c.code for c in all_codes])
        groups = sorted(list(set(c.group for c in all_codes if c.group)))
        st.session_state['all_groups'] = ["🔍 全部上市櫃"] + groups
    except:
        st.session_state['scan_pool'] = ['2330', '2317', '2454', '2603', '2881']
        st.session_state['all_groups'] = ["🔍 全部上市櫃", "半導體業"]

# --- 核心邏輯：智慧代號解析 ---
def solve_stock_id(val):
    val = str(val).strip() # 確保轉字串
    if not val: return None, None
    
    # 移除常見雜訊 (如括號、K線等字眼)
    clean_val = re.sub(r'[()\[\]]', '', val)
    
    # 1. 精確代號
    if clean_val in twstock.codes: return clean_val, twstock.codes[clean_val].name
    
    # 2. 精確中文
    for c, d in twstock.codes.items():
        if d.type == "股票" and d.name == clean_val: return c, d.name
            
    # 3. 模糊中文 (長度需>1避免誤判)
    if len(clean_val) > 1:
        for c, d in twstock.codes.items():
            if d.type == "股票" and clean_val in d.name: return c, d.name
            
    if clean_val.replace('.','').isalnum() and not clean_val.isdigit(): return clean_val.upper(), "美股/其他"
    return None, None

# --- OCR 影像辨識邏輯 ---
def process_image_upload(image_file):
    try:
        img = Image.open(image_file)
        # 嘗試使用繁體中文 + 英文模式
        # 注意: 需要 devcontainer 安裝 tesseract-ocr-chi-tra
        text = pytesseract.image_to_string(img, lang='chi_tra+eng')
        
        found_stocks = set()
        
        # 1. 使用正規表達式找 4 位數字 (代號)
        codes = re.findall(r'\b\d{4}\b', text)
        for c in codes:
            sid, sname = solve_stock_id(c)
            if sid and sname != "美股/其他":
                found_stocks.add((sid, sname))
        
        # 2. 逐行掃描找中文名稱
        lines = text.split('\n')
        for line in lines:
            # 去除雜訊
            clean_line = line.strip().replace(" ", "")
            if len(clean_line) > 1:
                # 嘗試每一行拿去解析
                sid, sname = solve_stock_id(clean_line)
                if sid and sname != "美股/其他":
                    found_stocks.add((sid, sname))
                    
        return list(found_stocks)
    except Exception as e:
        st.error(f"辨識失敗: {e} (請確認是否已安裝 Tesseract 引擎)")
        return []

# --- 導航函式 ---
def nav_to(mode, code=None, name=None):
    if code:
        st.session_state['current_stock'] = code
        st.session_state['current_name'] = name
        if st.session_state['user_id']: db.add_history(st.session_state['user_id'], f"{code} {name}")
    st.session_state['view_mode'] = mode
    if st.session_state['page_stack'][-1] != mode: st.session_state['page_stack'].append(mode)

def go_back():
    if len(st.session_state['page_stack']) > 1:
        st.session_state['page_stack'].pop()
        prev = st.session_state['page_stack'][-1]
        st.session_state['view_mode'] = prev
    else: st.session_state['view_mode'] = 'welcome'

def handle_search():
    raw = st.session_state.search_input_val
    if raw:
        code, name = solve_stock_id(raw)
        if code:
            nav_to('analysis', code, name)
            st.session_state.search_input_val = ""
        else: st.toast(f"找不到 '{raw}'", icon="⚠️")

# --- Sidebar ---
with st.sidebar:
    st.title("🎮 戰情控制台")
    uid = st.session_state['user_id']
    if uid: st.success(f"👤 {uid} (已登入)")
    else: st.info("👤 訪客模式")
    
    st.divider()
    
    # 1. 搜尋
    st.text_input("🔍 搜尋 (代號/名稱)", key="search_input_val", on_change=handle_search)

    # 2. 策略掃描
    st.markdown("### 🤖 類股 AI 掃描")
    with st.container(border=True):
        sel_group = st.selectbox("1️⃣ 掃描範圍", st.session_state.get('all_groups', ["全部"]), index=0)
        strat_map = {"⚡ 當沖快篩": "day", "📈 短線波段": "short", "🐢 長線存股": "long", "🏆 強勢前100": "top"}
        sel_strat_name = st.selectbox("2️⃣ AI 策略", list(strat_map.keys()))
        
        if st.button("🚀 啟動排序掃描", use_container_width=True):
            st.session_state['scan_target_group'] = sel_group
            st.session_state['current_stock'] = strat_map[sel_strat_name]
            st.session_state['scan_results'] = [] 
            nav_to('scan', strat_map[sel_strat_name])
            st.rerun()

    if st.button("🔄 更新今日精選池"): db.update_top_100(); st.toast("更新完成", icon="✅")
    
    st.divider()
    
    if st.button("📖 股市新手村"): nav_to('learn'); st.rerun()
    if st.button("🔒 個人自選股"): nav_to('watch'); st.rerun()
    if st.button("💬 戰友留言板"): nav_to('chat'); st.rerun()
    
    st.divider()
    
    if not uid:
        if st.button("🔐 登入 / 註冊"): nav_to('login'); st.rerun()
    else:
        if st.button("🚪 登出系統"): 
            st.session_state['user_id'] = None; st.session_state['watch_active'] = False
            nav_to('welcome'); st.rerun()
            
    if st.button("🏠 回首頁"): nav_to('welcome'); st.rerun()

    st.markdown("---")
    st.caption("Ver: 48.0 (截圖辨識版)")

# --- 主畫面路由 ---
mode = st.session_state['view_mode']

if mode == 'welcome':
    ui.render_header("👋 歡迎來到 AI 股市戰情室")
    st.markdown("""
    ### 🚀 V48 重磅更新：AI 截圖匯入
    * **📸 自選股搬家神器**：
        嫌一檔一檔輸入太麻煩？直接截圖其他券商 APP 的自選股列表，上傳圖片，AI 自動幫您辨識並匯入！
    * **🧠 智慧辨識引擎**：支援辨識股票代號 (如 2330) 與中文名稱 (如 台積電)。
    * **⚡ 快速整合**：自動去重複，一鍵同步到您的雲端清單。
    """)

elif mode == 'login':
    ui.render_header("🔐 會員中心")
    t1, t2 = st.tabs(["登入", "註冊"])
    with t1:
        u = st.text_input("帳號", key="l_u"); p = st.text_input("密碼", type="password", key="l_p")
        if st.button("登入"):
            ok, res = db.login_user(u, p)
            if ok: st.session_state['user_id']=u; st.success("登入成功！"); time.sleep(0.5); nav_to('watch'); st.rerun()
            else: st.error(res)
    with t2:
        nu = st.text_input("新帳號", key="r_u"); np = st.text_input("新密碼", type="password", key="r_p")
        nn = st.text_input("您的暱稱", key="r_n")
        if st.button("註冊"):
            ok, res = db.register_user(nu, np, nn)
            if ok: st.session_state['user_id']=nu; st.success(f"歡迎 {nn}！"); time.sleep(0.5); nav_to('watch'); st.rerun()
            else: st.error(res)
    ui.render_back_button(go_back)

elif mode == 'watch':
    ui.render_header("🔒 個人自選股")
    uid = st.session_state['user_id']
    if not uid: st.warning("請先登入"); ui.render_back_button(go_back)
    else:
        wl = db.get_watchlist(uid)
        
        # --- 1. 手動輸入區 ---
        c1, c2 = st.columns([3,1])
        add_c = c1.text_input("✍️ 手動輸入 (代號/名稱)", placeholder="如: 2330 或 台積電")
        if c2.button("加入", use_container_width=True) and add_c: 
            code, name = solve_stock_id(add_c)
            if code: db.update_watchlist(uid, code, "add"); st.toast(f"已加入: {name}", icon="✅"); time.sleep(0.5); st.rerun()
            else: st.error(f"找不到: {add_c}")

        # --- 2. 截圖匯入區 (V48 新增) ---
        with st.expander("📸 從截圖匯入自選股 (Beta)", expanded=False):
            st.info("請上傳手機截圖，系統將自動分析圖片中的股票代號或名稱。")
            uploaded_file = st.file_uploader("選擇圖片", type=['png', 'jpg', 'jpeg'])
            
            if uploaded_file is not None:
                with st.spinner("AI 正在分析圖片中的文字..."):
                    found_list = process_image_upload(uploaded_file)
                
                if found_list:
                    # 過濾掉已經存在的
                    new_stocks = [item for item in found_list if item[0] not in wl]
                    
                    if new_stocks:
                        st.success(f"🔍 發現 {len(new_stocks)} 檔新股票：")
                        # 顯示預覽
                        cols = st.columns(4)
                        for i, (wc, wn) in enumerate(new_stocks):
                            cols[i%4].caption(f"✅ {wc} {wn}")
                        
                        if st.button(f"📥 全部加入 ({len(new_stocks)})"):
                            count = 0
                            for wc, wn in new_stocks:
                                db.update_watchlist(uid, wc, "add")
                                count += 1
                            st.toast(f"成功匯入 {count} 檔股票！", icon="🎉")
                            time.sleep(1)
                            st.rerun()
                    else:
                        st.warning("圖片中的股票都已經在您的清單中了！")
                else:
                    st.error("未能辨識出有效股票，請嘗試更清晰的截圖。")

        st.divider()

        # --- 3. 清單顯示區 ---
        if wl:
            st.write(f"📊 目前持股清單 ({len(wl)})：")
            cols = st.columns(8)
            for i, code in enumerate(wl):
                if cols[i%8].button(f"❌ {code}", key=f"rm_{code}"): db.update_watchlist(uid, code, "remove"); st.rerun()
            
            st.divider()
            if st.button("🚀 啟動/刷新 AI 診斷", use_container_width=True): st.session_state['watch_active'] = True; st.rerun()
            
            if st.session_state['watch_active']:
                st.success("診斷完成！")
                for i, code in enumerate(wl):
                    full_id, _, d, src = db.get_stock_data(code)
                    n = twstock.codes[code].name if code in twstock.codes else code
                    if d is not None:
                        curr = d['Close'].iloc[-1] if isinstance(d, pd.DataFrame) else d['Close']
                        if ui.render_detailed_card(code, n, curr, d, src, key_prefix="watch"): nav_to('analysis', code, n); st.rerun()
        else: st.info("目前無自選股")
        ui.render_back_button(go_back)

elif mode == 'analysis':
    code = st.session_state['current_stock']
    name = st.session_state['current_name']
    is_live = ui.render_header(f"{name} {code}", show_monitor=True)
    if is_live: time.sleep(5); st.rerun()
    full_id, stock, df, src = db.get_stock_data(code)
    
    if src == "fail": st.error("查無資料")
    elif src == "yahoo":
        info = stock.info
        curr = df['Close'].iloc[-1]; prev = df['Close'].iloc[-2]
        chg = curr - prev; pct = (chg/prev)*100
        vt = df['Volume'].iloc[-1]; vy = df['Volume'].iloc[-2]; va = df['Volume'].tail(5).mean() + 1
        high = df['High'].iloc[-1]; low = df['Low'].iloc[-1]
        amp = ((high - low) / prev) * 100
        mf = "主力進貨 🔴" if (chg>0 and vt>vy) else ("主力出貨 🟢" if (chg<0 and vt>vy) else "觀望")
        vol_r = vt/va; vs = "🔥 爆量" if vol_r>1.5 else ("💤 量縮" if vol_r<0.6 else "正常")
        fh = info.get('heldPercentInstitutions', 0)*100
        color_settings = db.get_color_settings(code)

        ui.render_company_profile(db.translate_text(info.get('longBusinessSummary','')))
        ui.render_metrics_dashboard(curr, chg, pct, high, low, amp, mf, vt, vy, va, vs, fh, color_settings)
        ui.render_chart(df, f"{name} K線圖", color_settings)
        
        m5 = df['Close'].rolling(5).mean().iloc[-1]
        m20 = df['Close'].rolling(20).mean().iloc[-1]
        m60 = df['Close'].rolling(60).mean().iloc[-1]
        delta = df['Close'].diff(); u = delta.copy(); d = delta.copy(); u[u<0]=0; d[d>0]=0
        rs = u.rolling(14).mean() / d.abs().rolling(14).mean(); rsi = (100 - 100/(1+rs)).iloc[-1]
        bias = ((curr-m60)/m60)*100
        ui.render_ai_report(curr, m5, m20, m60, rsi, bias, high, low)
    elif src == "twse":
        st.warning("⚠️ TWSE 即時數據 (無K線)"); st.metric("現價", f"{df['Close']}")
    ui.render_back_button(go_back)

elif mode == 'learn':
    ui.render_header("📖 股市新手村")
    t1, t2 = st.tabs(["策略詳解", "名詞大全"])
    with t1: st.markdown(STRATEGY_DESC)
    with t2:
        q = st.text_input("搜尋名詞")
        for cat, items in STOCK_TERMS.items():
            with st.expander(cat, expanded=True):
                for k, v in items.items():
                    if not q or q in k: ui.render_term_card(k, v)
    ui.render_back_button(go_back)

elif mode == 'chat':
    ui.render_header("💬 戰友留言板")
    if not st.session_state['user_id']: st.warning("請先登入")
    else:
        with st.form("msg_form"):
            m = st.text_input("留言")
            if st.form_submit_button("送出") and m: db.save_comment(st.session_state['user_id'], m); st.rerun()
    st.divider()
    df = db.get_comments()
    for i, r in df.iloc[::-1].head(20).iterrows(): st.info(f"**{r['Nickname']}** ({r['Time']}):\n{r['Message']}")
    ui.render_back_button(go_back)

elif mode == 'scan': 
    stype = st.session_state['current_stock'] 
    target_group = st.session_state.get('scan_target_group', '全部上市櫃')
    title_map = {'day': '當沖快篩', 'short': '短線波段', 'long': '長線存股', 'top': '強勢前 100'}
    
    ui.render_header(f"🤖 {target_group} ⨉ {title_map.get(stype, stype)}")
    
    saved_codes = db.load_scan_results(stype) 
    
    c1, c2 = st.columns([1, 4])
    do_scan = c1.button("🔄 開始分析與排名", type="primary")
    
    if saved_codes and not do_scan: c2.info(f"顯示上次記錄 (共 {len(saved_codes)} 檔)")
    else: c2.info(f"鎖定範圍：{target_group}")

    if do_scan:
        st.session_state['scan_results'] = []
        raw_results = []
        
        full_pool = st.session_state['scan_pool']
        if target_group != "🔍 全部上市櫃":
            target_pool = [c for c in full_pool if c in twstock.codes and twstock.codes[c].group == target_group]
        else: target_pool = full_pool

        if not target_pool: st.error("無符合資料"); st.stop()

        bar = st.progress(0)
        limit = 300 
        
        for i, c in enumerate(target_pool):
            if i >= limit: break
            bar.progress((i+1)/min(len(target_pool), limit))
            try:
                fid, _, d, src = db.get_stock_data(c)
                if d is not None:
                    n = twstock.codes[c].name if c in twstock.codes else c
                    p = d['Close'].iloc[-1] if isinstance(d, pd.DataFrame) else d['Close']
                    sort_val = -999999; info_txt = ""
                    
                    if isinstance(d, pd.DataFrame) and len(d) > 20:
                        vol = d['Volume'].iloc[-1]
                        m5 = d['Close'].rolling(5).mean().iloc[-1]
                        m60 = d['Close'].rolling(60).mean().iloc[-1]
                        prev = d['Close'].iloc[-2]
                        pct = ((p - prev) / prev) * 100
                        
                        valid = True
                        if stype == 'day': 
                            sort_val = vol; info_txt = f"🔥 成交量: {int(vol/1000)}張"
                        elif stype == 'short': 
                            sort_val = (p - m5)/m5; info_txt = f"⚡ 5日動能: {sort_val*100:.1f}%"
                        elif stype == 'long': 
                            sort_val = (p - m60)/m60; info_txt = f"📈 趨勢強度: {sort_val*100:.1f}%"
                            if p < m60: valid = False 
                        elif stype == 'top': 
                            sort_val = pct; info_txt = f"🏆 漲幅: {pct:.2f}%"
                        
                        if valid: raw_results.append({'c': c, 'n': n, 'p': p, 'd': d, 'src': src, 'val': sort_val, 'info': info_txt})
            except: pass
        bar.empty()
        
        raw_results.sort(key=lambda x: x['val'], reverse=True)
        top_100 = [x['c'] for x in raw_results[:100]]
        
        if target_group == "🔍 全部上市櫃": db.save_scan_results(stype, top_100)
        st.session_state['scan_results'] = raw_results[:100]
        st.rerun() 

    display_list = st.session_state['scan_results']
    
    if not display_list and not do_scan and saved_codes and target_group == "🔍 全部上市櫃":
         temp_list = []
         ph = st.empty(); ph.text("讀取排名記錄...")
         for i, c in enumerate(saved_codes[:100]):
             fid, _, d, src = db.get_stock_data(c)
             if d is not None:
                 p = d['Close'].iloc[-1] if isinstance(d, pd.DataFrame) else d['Close']
                 n = twstock.codes[c].name if c in twstock.codes else c
                 temp_list.append({'c':c, 'n':n, 'p':p, 'd':d, 'src':src, 'info': f"推薦序 #{i+1}"})
         display_list = temp_list
         ph.empty()

    if display_list:
        for i, item in enumerate(display_list):
            if ui.render_detailed_card(
                item['c'], item['n'], item['p'], item['d'], item['src'], 
                key_prefix=f"scan_{stype}", 
                rank=i+1, 
                strategy_info=item['info']
            ): nav_to('analysis', item['c'], item['n']); st.rerun()
    elif not do_scan: st.warning("請點擊「開始分析與排名」按鈕。")
    ui.render_back_button(go_back)
