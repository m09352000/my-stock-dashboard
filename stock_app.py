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

st.set_page_config(page_title="AI 股市戰情室 V110", layout="wide")

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
            df.at[last_idx, 'Low'] = min(low, df.at[last_idx, 'Low']); df.at[last_idx, 'Volume'] = int(vol)
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
        if st.session_state['user_id']: db.add_history(st.session_state['user_id'],
