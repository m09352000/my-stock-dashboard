import streamlit as st
import time
import twstock
import pandas as pd
import re
import shutil
import subprocess
import os
from PIL import Image, ImageOps, ImageEnhance
import pytesseract

import stock_db as db
import stock_ui as ui
try:
    from knowledge import STOCK_TERMS, STRATEGY_DESC
except:
    STOCK_TERMS = {}; STRATEGY_DESC = "系統模組載入中..."

st.set_page_config(page_title="AI 股市戰情室 V60", layout="wide")

defaults = {
    'view_mode': 'welcome', 'user_id': None, 'page_stack': ['welcome'],
    'current_stock': "", 'current_name': "", 'scan_pool': [], 'filtered_pool': [],      
    'scan_target_group': "全部", 'watch_active': False, 'scan_results': []
}
for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

if not st.session_state['scan_pool']:
    try:
        all_codes = [c for c in twstock.codes.values() if c.type == "股票"]
        st.session_state['scan_pool'] = sorted([c.code for c in all_codes])
        groups = sorted(list(set(c.group for c in all_codes if c.group)))
        st.session_state['all_groups'] = ["🔍 全部上市櫃"] + groups
    except:
        st.session_state['scan_pool'] = ['2330', '2317']; st.session_state['all_groups'] = ["全部"]

def solve_stock_id(val):
    val = str(val).strip()
    if not val: return None, None
    clean_val = re.sub(r'[^\w\u4e00-\u9fff]', '', val)
    if clean_val in twstock.codes: return clean_val, twstock.codes[clean_val].name
    for c, d in twstock.codes.items():
        if d.type == "股票" and d.name == clean_val: return c, d.name
    if len(clean_val) >= 2:
        for c, d in twstock.codes.items():
            if d.type == "股票" and clean_val in d.name: return c, d.name
    return None, None

def is_ocr_ready(): return shutil.which('tesseract') is not None
def check_language_pack():
    try:
        result = subprocess.run(['tesseract', '--list-langs'], capture_output=True, text=True)
        return 'chi_tra' in result.stdout
    except: return False

def process_image_upload(image_file):
    debug_info = {"raw_text": "", "processed_img": None, "error": None}
    try:
        img = Image.open(image_file)
        if img.mode != 'RGB': img = img.convert('RGB')
        gray = img.convert('L'); inverted = ImageOps.invert(gray)
        enhancer = ImageEnhance.Contrast(inverted); final_img = enhancer.enhance(2.0)
        debug_info['processed_img'] = final_img
        try:
            text = pytesseract.image_to_string(final_img, lang='chi_tra+eng', config=r'--psm 6')
            debug_info['raw_text'] = text
        except:
            text = pytesseract.image_to_string(final_img, lang='eng', config=r'--psm 6')
            debug_info['raw_text'] = f"(En Only)\n{text}"
        found_stocks = set()
        lines = text.split('\n')
        for line in lines:
            clean_line = line.replace(" ", "").strip()
            if len(clean_line) > 1:
                sid, sname = solve_stock_id(clean_line)
                if sid: found_stocks.add((sid, sname))
                else:
                    sid2, sname2 = solve_stock_id(clean_line[:2])
                    if sid2: found_stocks.add((sid2, sname2))
                    else:
                        sid3, sname3 = solve_stock_id(clean_line[:3])
                        if sid3: found_stocks.add((sid3, sname3))
        return list(found_stocks), debug_info
    except Exception as e:
        debug_info['error'] = str(e); return [], debug_info

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
        else: st.toast(f"找不到 '{raw}'", icon="⚠️")

with st.sidebar:
    st.title("🎮 戰情控制台")
    uid = st.session_state['user_id']
    if uid: st.success(f"👤 {uid} (已登入)")
    else: st.info("👤 訪客模式")
    st.divider()
    st.text_input("🔍 搜尋", key="search_input_val", on_change=handle_search)
    st.markdown("### 🤖 類股 AI 掃描")
    with st.container(border=True):
        sel_group = st.selectbox("1️⃣ 範圍", st.session_state.get('all_groups', ["全部"]), index=0)
        strat_map = {"⚡ 強力當沖": "day", "📈 穩健短線": "short", "🐢 長線安穩": "long", "🏆 熱門強勢": "top"}
        sel_strat_name = st.selectbox("2️⃣ 策略", list(strat_map.keys()))
        if st.button("🚀 啟動掃描", use_container_width=True):
            st.session_state['scan_target_group'] = sel_group; st.session_state['current_stock'] = strat_map[sel_strat_name]
            st.session_state['scan_results'] = []; nav_to('scan', strat_map[sel_strat_name]); st.rerun()

    if st.button("🔄 更新精選池"): db.update_top_100(); st.toast("更新完成", icon="✅")
    st.divider()
    if st.button("📖 新手村"): nav_to('learn'); st.rerun()
    if st.button("🔒 自選股"): nav_to('watch'); st.rerun()
    if st.button("💬 留言板"): nav_to('chat'); st.rerun()
    st.divider()
    if not uid:
        if st.button("🔐 登入/註冊"): nav_to('login'); st.rerun()
    else:
        if st.button("🚪 登出"): st.session_state['user_id']=None; st.session_state['watch_active']=False; nav_to('welcome'); st.rerun()
    if st.button("🏠 回首頁"): nav_to('welcome'); st.rerun()
    st.markdown("---"); st.caption("Ver: 60.0 (語法修復版)")

mode = st.session_state['view_mode']

if mode == 'welcome':
    ui.render_header("👋 歡迎來到 AI 股市戰情室")
    st.markdown("### 🚀 V60 更新：語法與功能完全修復\n* **✅ 零錯誤**：修復了 V59 的 SyntaxError，確保系統穩定運行。\n* **📊 完整資訊**：儀表板雙排數據回歸，成交量、振幅、外資一目瞭然。\n* **🎯 戰術面板**：自選股與掃描結果均顯示「目標/停損」價位。")
    c1, c2 = st.columns(2)
    with c1:
        if is_ocr_ready(): st.success("✅ Tesseract 引擎就緒")
        else: st.error("❌ Tesseract 引擎未安裝")
    with c2:
        if check_language_pack(): st.success("✅ 中文語言包就緒")
        else: st.warning("⚠️ 中文包未安裝")

elif mode == 'login':
    ui.render_header("🔐 會員中心")
    t1, t2 = st.tabs(["登入", "註冊"])
    with t1:
        u = st.text_input("帳號", key="l_u"); p = st.text_input("密碼", type="password", key="l_p")
        if st.button("登入"):
            ok, res = db.login_user(u, p)
            if ok: st.session_state['user_id']=u; st.success("登入成功"); time.sleep(0.5); nav_to('watch'); st.rerun()
            else: st.error(res)
    with t2:
        nu = st.text_input("新帳號", key="r_u"); np = st.text_input("新密碼", type="password", key="r_p")
        nn = st.text_input("暱稱", key="r_n")
        if st.button("註冊"):
            ok, res = db.register_user(nu, np, nn)
            if ok: st.session_state['user_id']=nu; st.success(f"歡迎 {nn}"); time.sleep(0.5); nav_to('watch'); st.rerun()
            else: st.error(res)
    ui.render_back_button(go_back)

elif mode == 'watch':
    ui.render_header("🔒 個人自選股")
    uid = st.session_state['user_id']
    if not uid: st.warning("請先登入"); ui.render_back_button(go_back)
    else:
        wl = db.get_watchlist(uid)
        c1, c2 = st.columns([3,1])
        add_c = c1.text_input("✍️ 手動輸入", placeholder="代號或名稱")
        if c2.button("加入", use_container_width=True) and add_c: 
            code, name = solve_stock_id(add_c)
            if code: db.update_watchlist(uid, code, "add"); st.toast(f"已加入: {name}", icon="✅"); time.sleep(0.5); st.rerun()
            else: st.error(f"找不到: {add_c}")

        with st.expander("📸 截圖匯入", expanded=False):
            if is_ocr_ready():
                uploaded_file = st.file_uploader("上傳圖片", type=['png', 'jpg', 'jpeg'])
                if uploaded_file:
                    with st.spinner("解析中..."): found_list, debug_info = process_image_upload(uploaded_file)
                    if found_list:
                        new_stocks = [item for item in found_list if item[0] not in wl]
                        if new_stocks:
                            st.success(f"發現 {len(new_stocks)} 檔新股票")
                            if st.button("📥 全部加入"):
                                for wc, wn in new_stocks: db.update_watchlist(uid, wc, "add")
                                st.rerun()
                        else: st.warning("都在清單中了")
                    else: st.error("未能辨識有效股票"); st.text_area("除錯資訊", debug_info['raw_text'])
            else: st.error("❌ OCR 引擎未安裝")

        st.divider()

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
                st.subheader("⚙️ 清單管理")
                options = [f"{row['代號']} {row['名稱']}" for row in stock_data]
                remove_list = st.multiselect("選擇移除項目", options, label_visibility="collapsed")
                if st.button("🗑️ 確認移除", type="primary", use_container_width=True):
                    if remove_list:
                        for item in remove_list:
                            code_to_remove = item.split(" ")[0]
                            db.update_watchlist(uid, code_to_remove, "remove")
                        st.success("已移除"); st.rerun()

            st.divider()
            if st.button("🚀 啟動 AI 戰略診斷 (V60)", use_container_width=True): 
                st.session_state['watch_active'] = True; st.rerun()
            
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
    code = st.session_state['current_stock']; name = st.session_state['current_name']
    is_live = ui.render_header(f"{name} {code}", show_monitor=True)
    if is_live: time.sleep(5); st.rerun()
    full_id, stock, df, src = db.get_stock_data(code)
    
    if src == "fail": st.error("查無資料")
    elif src == "yahoo":
        info = stock.info; curr = df['Close'].iloc[-1]; prev = df['Close'].iloc[-2]; chg = curr - prev; pct = (chg/prev)*100
        vt = df['Volume'].iloc[-1]; vy = df['Volume'].iloc[-2]; va = df['Volume'].tail(5).mean() + 1
        high = df['High'].iloc[-1]; low = df['Low'].iloc[-1]; amp = ((high - low) / prev) * 100
        mf = "主力進貨 🔴" if (chg>0 and vt>vy) else ("主力出貨 🟢" if (chg<0 and vt>vy) else "觀望")
        vol_r = vt/va; vs = "🔥 爆量" if vol_r>1.5 else ("💤 量縮" if vol_r<0.6 else "正常")
        fh = info.get('heldPercentInstitutions', 0)*100
        color_settings = db.get_color_settings(code)

        ui.render_company_profile(db.translate_text(info.get('longBusinessSummary','')))
        ui.render_metrics_dashboard(curr, chg, pct, high, low, amp, mf, vt, vy, va, vs, fh, color_settings)
        ui.render_chart(df, f"{name} K線圖", color_settings)
        
        m5 = df['Close'].rolling(5).mean().iloc[-1]; m20 = df['Close'].rolling(20).mean().iloc[-1]; m60 = df['Close'].rolling(60).mean().iloc[-1]
        delta = df['Close'].diff(); u = delta.copy(); d = delta.copy(); u[u<0]=0; d[d>0]=0
        rs = u.rolling(14).mean() / d.abs().rolling(14).mean(); rsi = (100 - 100/(1+rs)).iloc[-1]
        bias = ((curr-m60)/m60)*100
        ui.render_ai_report(curr, m5, m20, m60, rsi, bias, high, low)
    elif src == "twse": st.metric("現價", f"{df['Close']}")
    ui.render_back_button(go_back)

elif mode == 'learn':
    ui.render_header("📖 新手村"); t1, t2 = st.tabs(["策略", "名詞"])
    with t1: st.markdown(STRATEGY_DESC)
    with t2:
        q = st.text_input("搜尋")
        for cat, items in STOCK_TERMS.items():
            with st.expander(cat, expanded=True):
                for k, v in items.items():
                    if not q or q in k: ui.render_term_card(k, v)
    ui.render_back_button(go_back)

elif mode == 'chat':
    ui.render_header("💬 留言板")
    if not st.session_state['user_id']: st.warning("請先登入")
    else:
        with st.form("msg"):
            m = st.text_input("內容")
            if st.form_submit_button("送出") and m: db.save_comment(st.session_state['user_id'], m); st.rerun()
    st.divider(); df = db.get_comments()
    for i, r in df.iloc[::-1].head(20).iterrows(): st.info(f"**{r['Nickname']}** ({r['Time']}):\n{r['Message']}")
    ui.render_back_button(go_back)

elif mode == 'scan': 
    stype = st.session_state['current_stock']; target_group = st.session_state.get('scan_target_group', '全部')
    title_map = {'day': '⚡ 強力當沖', 'short': '📈 穩健短線', 'long': '🐢 長線安穩', 'top': '🏆 熱門強勢'}
    ui.render_header(f"🤖 {target_group} ⨉ {title_map.get(stype, stype)}")
    
    saved_codes = db.load_scan_results(stype) 
    c1, c2 = st.columns([1, 4]); do_scan = c1.button("🔄 開始智能篩選", type="primary")
    if saved_codes and not do_scan: c2.info(f"上次記錄: {len(saved_codes)} 檔")
    else: c2.info(f"範圍: {target_group} (將自動過濾低勝率標的)")

    if do_scan:
        st.session_state['scan_results'] = []; raw_results = []
        full_pool = st.session_state['scan_pool']
        if target_group != "🔍 全部上市櫃": target_pool = [c for c in full_pool if c in twstock.codes and twstock.codes[c].group == target_group]
        else: target_pool = full_pool

        if not target_pool: st.error("無資料"); st.stop()
        bar = st.progress(0); limit = 300 
        
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
                        vol = d['Volume'].iloc[-1]; vol_prev = d['Volume'].iloc[-2]
                        m5 = d['Close'].rolling(5).mean().iloc[-1]
                        m20 = d['Close'].rolling(20).mean().iloc[-1]
                        m60 = d['Close'].rolling(60).mean().iloc[-1]
                        prev = d['Close'].iloc[-2]
                        pct = ((p - prev) / prev) * 100
                        amp = ((d['High'].iloc[-1] - d['Low'].iloc[-1]) / prev) * 100
                        
                        delta = d['Close'].diff(); u = delta.copy(); down = delta.copy(); u[u<0]=0; down[down>0]=0
                        rs = u.rolling(14).mean() / down.abs().rolling(14).mean()
                        rsi = (100 - 100/(1+rs)).iloc[-1]

                        valid = False
                        
                        if stype == 'day': 
                            if vol > vol_prev * 1.5 and p > d['Open'].iloc[-1] and p > m5 and amp > 2:
                                sort_val = vol 
                                info_txt = f"🔥 爆量{int(vol/vol_prev)}倍 | 振幅{amp:.1f}%"
                                valid = True
                        elif stype == 'short': 
                            if m5 > m20 and p > m20 and 50 < rsi < 75:
                                sort_val = pct 
                                info_txt = f"🚀 多頭排列 | RSI {rsi:.0f}"
                                valid = True
                        elif stype == 'long': 
                            bias = ((p - m60)/m60)*100
                            if p > m60 and -5 < bias < 10: 
                                sort_val = vol 
                                info_txt = f"🐢 季線之上 | 乖離{bias:.1f}%"
                                valid = True
                        elif stype == 'top': 
                            if vol > 2000000 and p > m20: 
                                sort_val = pct 
                                info_txt = f"🏆 漲幅{pct:.2f}% | 量{int(vol/1000)}張"
                                valid = True
                        
                        if valid: raw_results.append({'c': c, 'n': n, 'p': p, 'd': d, 'src': src, 'val': sort_val, 'info': info_txt})
            except: pass
        bar.empty()
        
        raw_results.sort(key=lambda x: x['val'], reverse=True)
        top_100 = [x['c'] for x in raw_results[:100]]
        if target_group == "🔍 全部上市櫃": db.save_scan_results(stype, top_100)
        st.session_state['scan_results'] = raw_results[:100]; st.rerun() 

    display_list = st.session_state['scan_results']
    if not display_list and not do_scan and saved_codes and target_group == "🔍 全部上市櫃":
         temp_list = []
         for i, c in enumerate(saved_codes[:100]):
             fid, _, d, src = db.get_stock_data(c)
             if d is not None:
                 p = d['Close'].iloc[-1] if isinstance(d, pd.DataFrame) else d['Close']
                 n = twstock.codes[c].name if c in twstock.codes else c
                 temp_list.append({'c':c, 'n':n, 'p':p, 'd':d, 'src':src, 'info': f"AI 推薦 #{i+1}"})
         display_list = temp_list

    if display_list:
        for i, item in enumerate(display_list):
            if ui.render_detailed_card(item['c'], item['n'], item['p'], item['d'], item['src'], key_prefix=f"scan_{stype}", rank=i+1, strategy_info=item['info']):
                nav_to('analysis', item['c'], item['n']); st.rerun()
    elif not do_scan: st.warning("請點擊「開始智能篩選」")
    ui.render_back_button(go_back)
