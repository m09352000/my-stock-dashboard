import streamlit as st
import time
import twstock
import pandas as pd

# 引入模組
import stock_db as db
import stock_ui as ui
try:
    from knowledge import STOCK_TERMS, STRATEGY_DESC
except:
    STOCK_TERMS = {}; STRATEGY_DESC = "系統模組載入中..."

# --- 設定 (必須第一行) ---
st.set_page_config(page_title="AI 股市戰情室 V45", layout="wide")

# --- 初始化 State ---
defaults = {
    'view_mode': 'welcome',
    'user_id': None,
    'page_stack': ['welcome'],
    'current_stock': "",
    'current_name': "",
    'scan_pool': [],
    'watch_active': False,
    'scan_results': []
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# 初始化掃描池
if not st.session_state['scan_pool']:
    try:
        st.session_state['scan_pool'] = sorted([c for c in twstock.codes.keys() if twstock.codes[c].type == "股票"])[:800]
    except:
        st.session_state['scan_pool'] = ['2330', '2317', '2454', '2603', '2881']

# --- 核心邏輯：智慧代號解析 (V45 新增) ---
def solve_stock_id(val):
    """
    輸入可以是代號 (2330) 或名稱 (台積電)，回傳 (代號, 名稱)
    """
    val = val.strip()
    if not val: return None, None
    
    # 1. 直接是代號 (精確匹配)
    if val in twstock.codes:
        return val, twstock.codes[val].name
        
    # 2. 搜尋中文名稱 (優先找精確符合，例如輸入'鴻海')
    for c, d in twstock.codes.items():
        if d.type == "股票" and d.name == val:
            return c, d.name
            
    # 3. 搜尋中文名稱 (模糊搜尋，例如輸入'台積' -> 找到'台積電')
    # 為了避免雜訊，我們取第一個找到的
    for c, d in twstock.codes.items():
        if d.type == "股票" and val in d.name:
            return c, d.name
    
    # 4. 判斷是否為美股 (全英文或數字但不在台股清單)
    # 假設輸入 NVDA 或 TSLA
    if val.replace('.','').isalnum():
        return val.upper(), "美股/其他"
        
    return None, None

# --- 導航函式 ---
def nav_to(mode, code=None, name=None):
    if code:
        st.session_state['current_stock'] = code
        st.session_state['current_name'] = name
        if st.session_state['user_id']: 
            db.add_history(st.session_state['user_id'], f"{code} {name}")
    
    st.session_state['view_mode'] = mode
    if st.session_state['page_stack'][-1] != mode:
        st.session_state['page_stack'].append(mode)

def go_back():
    if len(st.session_state['page_stack']) > 1:
        st.session_state['page_stack'].pop()
        prev = st.session_state['page_stack'][-1]
        st.session_state['view_mode'] = prev
    else:
        st.session_state['view_mode'] = 'welcome'

def handle_search():
    # 這是給 on_change 用的 callback
    raw = st.session_state.search_input_val
    if raw:
        # 使用新的解析邏輯
        code, name = solve_stock_id(raw)
        if code:
            nav_to('analysis', code, name)
            st.session_state.search_input_val = "" # 清空
        else:
            st.toast(f"找不到 '{raw}' 相關股票", icon="⚠️")

# --- Sidebar ---
with st.sidebar:
    st.title("🎮 戰情控制台")
    uid = st.session_state['user_id']
    if uid: st.success(f"👤 {uid} (已登入)")
    else: st.info("👤 訪客模式")
    
    st.divider()
    
    # 1. 搜尋 (支援中文)
    st.text_input("🔍 搜尋 (代號/名稱)", key="search_input_val", on_change=handle_search, placeholder="例如: 2330 或 台積電")

    # 2. 策略按鈕
    st.subheader("🤖 AI 策略掃描")
    c1,c2 = st.columns(2)
    if c1.button("⚡ 當沖快篩"): 
        st.session_state['scan_results'] = [] 
        nav_to('scan', 'day'); st.rerun()
    if c2.button("📈 短線波段"): 
        st.session_state['scan_results'] = []
        nav_to('scan', 'short'); st.rerun()
        
    c3,c4 = st.columns(2)
    if c3.button("🐢 長線存股"): 
        st.session_state['scan_results'] = []
        nav_to('scan', 'long'); st.rerun()
    if c4.button("🏆 強勢前100"): 
        st.session_state['scan_results'] = []
        nav_to('scan', 'top'); st.rerun()
        
    if st.button("🔄 更新今日精選池"): 
        db.update_top_100()
        st.toast("精選池已更新", icon="✅")
    
    st.divider()
    
    # 3. 功能按鈕
    if st.button("📖 股市新手村"): nav_to('learn'); st.rerun()
    if st.button("🔒 個人自選股"): nav_to('watch'); st.rerun()
    if st.button("💬 戰友留言板"): nav_to('chat'); st.rerun()
    
    st.divider()
    
    # 4. 登入/登出
    if not uid:
        if st.button("🔐 登入 / 註冊"): nav_to('login'); st.rerun()
    else:
        if st.button("🚪 登出系統"): 
            st.session_state['user_id'] = None
            st.session_state['watch_active'] = False
            nav_to('welcome'); st.rerun()
            
    # 5. 回首頁
    if st.button("🏠 回首頁"): nav_to('welcome'); st.rerun()

    st.markdown("---")
    st.caption("Ver: 45.0 (中文搜尋版)")

# --- 主畫面路由 ---
mode = st.session_state['view_mode']

if mode == 'welcome':
    ui.render_header("👋 歡迎來到 AI 股市戰情室")
    st.markdown("""
    ### 🚀 V45 更新：支援中文搜尋！
    * **🔍 智慧搜尋**：現在您可以直接輸入 **「台積電」**、**「鴻海」** 或 **「長榮」** 進行分析。
    * **📝 自選股優化**：新增自選股時，也支援輸入中文名稱。
    * **✅ 穩定性提升**：核心代碼與 V44 保持一致，僅升級搜尋引擎。
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
        nn = st.text_input("您的暱稱", key="r_n", placeholder="例如：股海小神童")
        if st.button("註冊"):
            ok, res = db.register_user(nu, np, nn)
            if ok: st.session_state['user_id']=nu; st.success(f"歡迎 {nn}！註冊成功"); time.sleep(0.5); nav_to('watch'); st.rerun()
            else: st.error(res)
    ui.render_back_button(go_back)

elif mode == 'watch':
    ui.render_header("🔒 個人自選股")
    uid = st.session_state['user_id']
    if not uid: 
        st.warning("請先登入以使用自選股功能"); ui.render_back_button(go_back)
    else:
        wl = db.get_watchlist(uid)
        c1, c2 = st.columns([3,1])
        # 這裡也使用中文解析
        add_c = c1.text_input("新增自選股", placeholder="輸入代號或名稱 (如: 緯創)")
        
        if c2.button("加入") and add_c: 
            code, name = solve_stock_id(add_c)
            if code:
                db.update_watchlist(uid, code, "add")
                st.toast(f"已加入: {name} ({code})", icon="✅")
                time.sleep(0.5)
                st.rerun()
            else:
                st.error(f"找不到股票: {add_c}")
        
        if wl:
            st.write("🗑️ 點擊移除：")
            cols = st.columns(8)
            for i, code in enumerate(wl):
                if cols[i%8].button(f"❌ {code}", key=f"rm_{code}"): db.update_watchlist(uid, code, "remove"); st.rerun()
            
            st.divider()
            
            if st.button("🚀 啟動/刷新 AI 診斷 (可能需時幾秒)", use_container_width=True):
                st.session_state['watch_active'] = True
                st.rerun()
            
            if st.session_state['watch_active']:
                st.success("診斷完成！")
                for i, code in enumerate(wl):
                    full_id, _, d, src = db.get_stock_data(code)
                    n = twstock.codes[code].name if code in twstock.codes else code
                    
                    if d is not None:
                        curr = d['Close'].iloc[-1] if isinstance(d, pd.DataFrame) else d['Close']
                        if ui.render_detailed_card(code, n, curr, d, src, key_prefix="watch"):
                            nav_to('analysis', code, n); st.rerun()
                    else:
                        st.error(f"{code} 讀取失敗")
        else: st.info("目前無自選股，請從上方新增。")
        ui.render_back_button(go_back)

elif mode == 'analysis':
    code = st.session_state['current_stock']
    name = st.session_state['current_name']
    is_live = ui.render_header(f"{name} {code}", show_monitor=True)
    if is_live: time.sleep(5); st.rerun()
    
    full_id, stock, df, src = db.get_stock_data(code)
    
    if src == "fail": 
        st.error("查無資料，請確認代號是否正確。")
    elif src == "yahoo":
        info = stock.info
        curr = df['Close'].iloc[-1]; prev = df['Close'].iloc[-2]
        chg = curr - prev; pct = (chg/prev)*100
        vt = df['Volume'].iloc[-1]; vy = df['Volume'].iloc[-2]
        va = df['Volume'].tail(5).mean() + 1 
        high = df['High'].iloc[-1]; low = df['Low'].iloc[-1]
        amp = ((high - low) / prev) * 100
        mf = "主力進貨 🔴" if (chg>0 and vt>vy) else ("主力出貨 🟢" if (chg<0 and vt>vy) else "觀望")
        vol_r = vt/va
        vs = "🔥 爆量" if vol_r>1.5 else ("💤 量縮" if vol_r<0.6 else "正常")
        fh = info.get('heldPercentInstitutions', 0)*100
        color_settings = db.get_color_settings(code)

        ui.render_company_profile(db.translate_text(info.get('longBusinessSummary','')))
        ui.render_metrics_dashboard(curr, chg, pct, high, low, amp, mf, vt, vy, va, vs, fh, color_settings)
        ui.render_chart(df, f"{name} K線圖", color_settings)
        
        m5 = df['Close'].rolling(5).mean().iloc[-1]
        m20 = df['Close'].rolling(20).mean().iloc[-1]
        m60 = df['Close'].rolling(60).mean().iloc[-1]
        delta = df['Close'].diff()
        u = delta.copy(); d = delta.copy()
        u[u<0]=0; d[d>0]=0
        rs = u.rolling(14).mean() / d.abs().rolling(14).mean()
        rsi = (100 - 100/(1+rs)).iloc[-1]
        bias = ((curr-m60)/m60)*100
        
        ui.render_ai_report(curr, m5, m20, m60, rsi, bias, high, low)
        
    elif src == "twse":
        st.warning("⚠️ 目前僅顯示 TWSE 即時報價 (無歷史K線)")
        st.metric("現價", f"{df['Close']}")
        
    ui.render_back_button(go_back)

# ... learn, chat, scan 區塊保持原樣 ...
# 為了節省篇幅，這裡省略未變更的 learn, chat, scan 程式碼
# 實際執行時，請保留原有的 scan/learn/chat 區塊
# (若您是直接覆蓋，我把剩餘部分補完給您以防萬一)

elif mode == 'learn':
    ui.render_header("📖 股市新手村")
    t1, t2 = st.tabs(["策略詳解", "名詞大全"])
    with t1: st.markdown(STRATEGY_DESC)
    with t2:
        q = st.text_input("搜尋名詞")
        for cat, items in STOCK_TERMS.items():
            with st.expander(cat, expanded=True):
                for k, v in items.items():
                    if not q or q in k:
                        ui.render_term_card(k, v)
    ui.render_back_button(go_back)

elif mode == 'chat':
    ui.render_header("💬 戰友留言板")
    if not st.session_state['user_id']: 
        st.warning("請先登入才能留言")
    else:
        with st.form("msg_form"):
            m = st.text_input("留言內容")
            if st.form_submit_button("送出留言") and m: 
                db.save_comment(st.session_state['user_id'], m)
                st.rerun()
    st.divider()
    df = db.get_comments()
    for i, r in df.iloc[::-1].head(20).iterrows(): 
        st.info(f"**{r['Nickname']}** ({r['Time']}):\n{r['Message']}")
    ui.render_back_button(go_back)

elif mode == 'scan': 
    stype = st.session_state['current_stock']
    title_map = {'day': '當沖快篩', 'short': '短線波段', 'long': '長線存股', 'top': '強勢前 100'}
    
    ui.render_header(f"🤖 掃描結果: {title_map.get(stype, stype)}")
    
    saved_codes = db.load_scan_results(stype)
    
    c1, c2 = st.columns([1, 4])
    do_scan = c1.button("🔄 執行新掃描 (約 30 秒)")
    if saved_codes: c2.info(f"上次掃描記錄：共 {len(saved_codes)} 檔")
    
    if do_scan:
        st.session_state['scan_results'] = []
        raw_results = []
        bar = st.progress(0)
        pool = st.session_state['scan_pool']
        limit = 400 
        
        for i, c in enumerate(pool):
            if i >= limit: break
            bar.progress((i+1)/limit)
            try:
                fid, _, d, src = db.get_stock_data(c)
                if d is not None:
                    n = twstock.codes[c].name if c in twstock.codes else c
                    p = d['Close'].iloc[-1] if isinstance(d, pd.DataFrame) else d['Close']
                    sort_val = 0; info_txt = ""
                    
                    if isinstance(d, pd.DataFrame) and len(d) > 20:
                        vol = d['Volume'].iloc[-1]
                        m5 = d['Close'].rolling(5).mean().iloc[-1]
                        m60 = d['Close'].rolling(60).mean().iloc[-1]
                        prev = d['Close'].iloc[-2]
                        pct = ((p - prev) / prev) * 100
                        
                        if stype == 'day': sort_val = vol; info_txt = f"量: {int(vol/1000)}張"
                        elif stype == 'short': sort_val = (p - m5)/m5; info_txt = f"5日乖離: {sort_val*100:.1f}%"
                        elif stype == 'long': sort_val = (p - m60)/m60; info_txt = f"季線乖離: {sort_val*100:.1f}%"
                        elif stype == 'top': sort_val = pct; info_txt = f"漲幅: {pct:.2f}%"
                        
                        raw_results.append({'c': c, 'n': n, 'p': p, 'd': d, 'src': src, 'val': sort_val, 'info': info_txt})
            except: pass
        bar.empty()
        
        raw_results.sort(key=lambda x: x['val'], reverse=True)
        top_100 = [x['c'] for x in raw_results[:100]]
        db.save_scan_results(stype, top_100)
        st.session_state['scan_results'] = raw_results[:100]
        st.rerun() 

    display_list = st.session_state['scan_results']
    
    if not display_list and saved_codes:
        temp_list = []
        placeholder = st.empty()
        placeholder.text("正在載入存檔數據...")
        for i, c in enumerate(saved_codes[:100]):
             fid, _, d, src = db.get_stock_data(c)
             if d is not None:
                 p = d['Close'].iloc[-1] if isinstance(d, pd.DataFrame) else d['Close']
                 n = twstock.codes[c].name if c in twstock.codes else c
                 temp_list.append({'c':c, 'n':n, 'p':p, 'd':d, 'src':src, 'info':"存檔記錄"})
        display_list = temp_list
        placeholder.empty()
        
    if display_list:
        for i, item in enumerate(display_list):
            if ui.render_detailed_card(
                item['c'], item['n'], item['p'], item['d'], item['src'], 
                key_prefix=f"scan_{stype}", 
                rank=i+1, 
                strategy_info=item['info']
            ):
                nav_to('analysis', item['c'], item['n']); st.rerun()
    elif not saved_codes:
        st.warning("尚無掃描記錄，請點擊上方按鈕開始掃描。")
                
    ui.render_back_button(go_back)
