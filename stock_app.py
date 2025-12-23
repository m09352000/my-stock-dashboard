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
    STOCK_TERMS = {}; STRATEGY_DESC = "請建立 knowledge.py"

# --- 設定 ---
st.set_page_config(page_title="AI 股市戰情室 V42", layout="wide")

# --- 初始化 State ---
if 'view_mode' not in st.session_state: st.session_state['view_mode'] = 'welcome'
if 'user_id' not in st.session_state: st.session_state['user_id'] = None
if 'page_stack' not in st.session_state: st.session_state['page_stack'] = ['welcome']
if 'current_stock' not in st.session_state: st.session_state['current_stock'] = ""
if 'current_name' not in st.session_state: st.session_state['current_name'] = ""
if 'scan_pool' not in st.session_state:
    try: st.session_state['scan_pool'] = sorted([c for c in twstock.codes.keys() if twstock.codes[c].type == "股票"])[:500]
    except: st.session_state['scan_pool'] = ['2330', '2317', '2454', '2603', '2881', '2891', '2002', '1301', '2412']

# 狀態控制
if 'watch_active' not in st.session_state: st.session_state['watch_active'] = False
if 'scan_results' not in st.session_state: st.session_state['scan_results'] = []

# --- 導航函式 ---
def nav_to(mode, code=None, name=None):
    if code:
        st.session_state['current_stock'] = code
        st.session_state['current_name'] = name
        if st.session_state['user_id']: db.add_history(st.session_state['user_id'], f"{code} {name}")
    st.session_state['view_mode'] = mode
    st.session_state['page_stack'].append(mode)

def go_back():
    if len(st.session_state['page_stack']) > 1:
        st.session_state['page_stack'].pop()
        st.session_state['view_mode'] = st.session_state['page_stack'][-1]
        st.rerun()

def handle_search_form():
    raw = st.session_state.sidebar_search_input
    if raw:
        n = "美股"
        if raw in twstock.codes: n = twstock.codes[raw].name
        elif raw.isdigit(): n = "台股"
        nav_to('analysis', raw, n)

# --- 側邊欄 ---
with st.sidebar:
    st.title("🎮 戰情控制台")
    uid = st.session_state['user_id']
    if uid: st.success(f"👤 {uid} (已登入)")
    else: st.info("👤 訪客")
    st.divider()
    
    with st.form("search"):
        q = st.text_input("🔍 輸入代號 (Enter)", key="sidebar_search_input")
        if st.form_submit_button("搜尋"): handle_search_form()

    st.subheader("🤖 AI 策略")
    c1,c2,c3 = st.columns(3)
    if c1.button("⚡ 當沖快篩"): 
        st.session_state['scan_results'] = [] 
        nav_to('scan', 'day'); st.rerun()
    if c2.button("📈 短線波段"): 
        st.session_state['scan_results'] = []
        nav_to('scan', 'short'); st.rerun()
    if c3.button("🐢 長線存股"): 
        st.session_state['scan_results'] = []
        nav_to('scan', 'long'); st.rerun()
    
    if st.button("🏆 漲幅前 100"): 
        st.session_state['scan_results'] = []
        nav_to('scan', 'top'); st.rerun()
        
    if st.button("🔄 更新精選池"): 
        db.update_top_100()
        st.toast("精選池已更新", icon="✅")
    
    st.divider()
    if st.button("📖 股市新手村"): nav_to('learn'); st.rerun()
    if st.button("🔒 個人自選股"): nav_to('watch'); st.rerun()
    if st.button("💬 戰友留言板"): nav_to('chat'); st.rerun()
    
    st.divider()
    if not uid:
        if st.button("🔐 登入 / 註冊"): nav_to('login'); st.rerun()
    else:
        if st.button("🚪 登出系統"): 
            st.session_state['user_id']=None
            st.session_state['watch_active'] = False
            nav_to('welcome'); st.rerun()
    
    if st.button("🏠 回首頁"): nav_to('welcome'); st.rerun()

# --- 主畫面路由 ---
mode = st.session_state['view_mode']

if mode == 'welcome':
    ui.render_header("👋 歡迎來到 AI 股市戰情室 V42")
    st.markdown("### 🚀 V42 策略優化版\n* **🎯 精準排序**：各個策略按鈕會依照不同邏輯（成交量、漲幅、乖離率）進行排名。\n* **📊 關鍵資訊**：掃描結果卡片直接顯示該策略的重點數據。")

elif mode == 'login':
    ui.render_header("🔐 會員登入中心")
    t1, t2 = st.tabs(["登入", "註冊"])
    with t1:
        u = st.text_input("帳號"); p = st.text_input("密碼", type="password")
        if st.button("登入"):
            ok, res = db.login_user(u, p)
            if ok: st.session_state['user_id']=u; st.success("成功"); time.sleep(0.5); nav_to('watch'); st.rerun()
            else: st.error(res)
    with t2:
        nu = st.text_input("新帳號"); np = st.text_input("新密碼", type="password"); nn = st.text_input("暱稱")
        if st.button("註冊"):
            ok, res = db.register_user(nu, np, nn)
            if ok: st.session_state['user_id']=nu; st.success("成功"); time.sleep(0.5); nav_to('watch'); st.rerun()
            else: st.error(res)
    ui.render_back_button(go_back)

elif mode == 'watch':
    ui.render_header("🔒 個人自選股")
    uid = st.session_state['user_id']
    if not uid: st.warning("請先登入"); ui.render_back_button(go_back)
    else:
        wl = db.get_watchlist(uid)
        c1, c2 = st.columns([3,1]); add_c = c1.text_input("加股")
        if c2.button("加入") and add_c: db.update_watchlist(uid, add_c, "add"); st.rerun()
        
        if wl:
            st.write("管理清單：")
            cols = st.columns(8)
            for i, code in enumerate(wl):
                if cols[i%8].button(f"❌ {code}"): db.update_watchlist(uid, code, "remove"); st.rerun()
            
            st.divider()
            st.subheader(f"📊 持股詳細診斷 ({len(wl)} 檔)")
            
            if st.button("🚀 啟動/刷新 AI 診斷"):
                st.session_state['watch_active'] = True
                st.rerun()
            
            if st.session_state['watch_active']:
                bar = st.progress(0)
                for i, code in enumerate(wl):
                    bar.progress((i+1)/len(wl))
                    full_id, _, d, src = db.get_stock_data(code)
                    n = twstock.codes[code].name if code in twstock.codes else code
                    
                    if d is not None:
                        curr = d['Close'].iloc[-1] if isinstance(d, pd.DataFrame) else d['Close']
                        if ui.render_detailed_card(code, n, curr, d, src, key_prefix="watch"):
                            nav_to('analysis', code, n); st.rerun()
                    else:
                        st.error(f"{code} 讀取失敗")
                bar.empty()
        else: st.info("目前無自選股")
        ui.render_back_button(go_back)

elif mode == 'analysis':
    code = st.session_state['current_stock']
    name = st.session_state['current_name']
    
    is_live = ui.render_header(f"{name} {code}", show_monitor=True)
    if is_live: time.sleep(3); st.rerun()
    
    full_id, stock, df, src = db.get_stock_data(code)
    
    if src == "fail":
        st.error("查無資料 (可能 Yahoo 連線忙碌)")
    elif src == "yahoo":
        info = stock.info
        curr = df['Close'].iloc[-1]; prev = df['Close'].iloc[-2]
        chg = curr - prev; pct = (chg/prev)*100
        vt = df['Volume'].iloc[-1]; vy = df['Volume'].iloc[-2]; va = df['Volume'].tail(5).mean()
        high = df['High'].iloc[-1]; low = df['Low'].iloc[-1]
        amp = ((high - low) / prev) * 100
        mf = "主力進貨 🔴" if (chg>0 and vt>vy) else ("主力出貨 🟢" if (chg<0 and vt>vy) else "觀望")
        vol_r = vt/va if va>0 else 1
        vs = "🔥 爆量" if vol_r>1.5 else ("💤 量縮" if vol_r<0.6 else "正常")
        fh = info.get('heldPercentInstitutions', 0)*100
        color_settings = db.get_color_settings(code)

        ui.render_company_profile(db.translate_text(info.get('longBusinessSummary','')))
        ui.render_metrics_dashboard(curr, chg, pct, high, low, amp, mf, vt, vy, va, vs, fh, color_settings)
        ui.render_chart(df, f"{name} K線圖")
        
        m20 = df['Close'].rolling(20).mean().iloc[-1]
        m60 = df['Close'].rolling(60).mean().iloc[-1]
        delta = df['Close'].diff(); u=delta.copy(); d=delta.copy(); u[u<0]=0; d[d>0]=0
        rs = u.rolling(14).mean()/d.abs().rolling(14).mean(); rsi = (100-100/(1+rs)).iloc[-1]
        bias = ((curr-m60)/m60)*100
        ui.render_ai_report(curr, m20, m60, rsi, bias)
        
    elif src == "twse":
        st.warning("⚠️ 使用即時備援數據 (無 K 線)")
        st.metric("現價", f"{df['Close']}")
        st.metric("成交量", f"{df['Volume']}")

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
                    ui.render_term_card(k, v)
    ui.render_back_button(go_back)

elif mode == 'chat':
    ui.render_header("💬 留言板")
    if not st.session_state['user_id']: st.warning("請先登入")
    else:
        m = st.text_input("留言")
        if st.button("送出") and m: db.save_comment(st.session_state['user_id'], m); st.rerun()
    df = db.get_comments()
    for i, r in df.iloc[::-1].iterrows(): st.info(f"{r['Nickname']} ({r['Time']}): {r['Message']}")
    ui.render_back_button(go_back)

# --- 掃描頁面 (🔥 V42: 排序權重邏輯實作) ---
elif mode == 'scan': 
    stype = st.session_state['current_stock']
    title_map = {'day': '當沖快篩', 'short': '短線波段', 'long': '長線存股', 'top': '漲幅前 100'}
    
    ui.render_header(f"🤖 掃描結果: {title_map.get(stype, stype)}")
    
    # 嘗試讀取已存結果 (如果要用檔案存取，可結合 V41 的 db.load_scan_results)
    # 這裡為了展示邏輯，先用 session_state
    has_results = len(st.session_state['scan_results']) > 0
    
    if st.button("開始/重新掃描 (前200檔)"):
        st.session_state['scan_results'] = []
        raw_results = [] # 暫存未排序資料
        bar = st.progress(0)
        pool = st.session_state['scan_pool']
        limit = 200 # 限制數量
        
        for i, c in enumerate(pool):
            if i >= limit: break
            bar.progress((i+1)/limit)
            try:
                fid, _, d, src = db.get_stock_data(c)
                
                if d is not None:
                    n = twstock.codes[c].name if c in twstock.codes else c
                    p = d['Close'].iloc[-1] if isinstance(d, pd.DataFrame) else d['Close']
                    
                    # 計算排序權重 (Sort Key) 和 顯示文字 (Info)
                    sort_val = 0
                    info_txt = ""
                    
                    # 處理 Yahoo 資料
                    if isinstance(d, pd.DataFrame) and len(d) > 20:
                        vol = d['Volume'].iloc[-1]
                        m5 = d['Close'].rolling(5).mean().iloc[-1]
                        m60 = d['Close'].rolling(60).mean().iloc[-1]
                        prev = d['Close'].iloc[-2]
                        pct_change = ((p - prev) / prev) * 100
                        
                        if stype == 'day':
                            # 當沖：看成交量
                            sort_val = vol 
                            info_txt = f"成交量: {int(vol/1000)} 張"
                        elif stype == 'short':
                            # 短線：看乖離率 (離5日線多遠)
                            sort_val = (p - m5) / m5 
                            info_txt = f"5日乖離: {sort_val*100:.1f}%"
                        elif stype == 'long':
                            # 長線：看季線乖離
                            sort_val = (p - m60) / m60
                            info_txt = f"季線乖離: {sort_val*100:.1f}%"
                        elif stype == 'top':
                            # 漲幅：看 %
                            sort_val = pct_change
                            info_txt = f"漲跌幅: {pct_change:.2f}%"
                            
                    # 處理 TWSE 資料 (只支援漲幅和價格)
                    elif isinstance(d, dict):
                        # TWSE 無 K 線，只能簡單處理
                        sort_val = p 
                        info_txt = f"股價: {p}"

                    # 加入清單 (code, name, price, df, src, sort_val, info_txt)
                    raw_results.append({
                        'c': c, 'n': n, 'p': p, 'd': d, 'src': src, 
                        'val': sort_val, 'info': info_txt
                    })
            except: pass
        bar.empty()
        
        # 🔥 關鍵：根據策略進行排序 (由大到小)
        raw_results.sort(key=lambda x: x['val'], reverse=True)
        
        # 取前 50 名存入 session
        st.session_state['scan_results'] = raw_results[:50]
        st.rerun() 

    # 顯示結果
    if st.session_state['scan_results']:
        for i, item in enumerate(st.session_state['scan_results']):
            # 呼叫卡片，傳入 strategy_info 顯示關鍵數據
            if ui.render_detailed_card(
                item['c'], item['n'], item['p'], item['d'], item['src'], 
                key_prefix=f"scan_{stype}", 
                rank=i+1, 
                strategy_info=item['info']
            ):
                nav_to('analysis', item['c'], item['n']); st.rerun()
    elif has_results == False:
        st.info("請點擊按鈕開始掃描")
    else:
        st.warning("無符合標的")
                
    ui.render_back_button(go_back)
