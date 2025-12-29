import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

# ... (CSS 與 Header 函式完全保留 V100 的版本) ...

# 僅需修改 render_metrics_dashboard 函式
def render_metrics_dashboard(curr, chg, pct, high, low, amp, mf, vol, vy, va, vs, fh, tr, ba, cs, rt, unit="張", code=""):
    with st.container():
        c1, c2, c3, c4 = st.columns(4)
        
        # 漲跌顏色：為了不混淆，目前統一維持 紅漲綠跌 (若您想改美股綠漲，可在此修改)
        val_color = "#FF2B2B" if chg > 0 else "#00E050" if chg < 0 else "white"
        
        c1.markdown(f"<div style='font-size:0.9rem; color:#aaa'>成交價</div><div style='font-size:2rem; font-weight:bold; color:{val_color}'>{curr:.2f} <span style='font-size:1rem'>({pct:+.2f}%)</span></div>", unsafe_allow_html=True)
        c2.metric("最高", f"{high:.2f}")
        c3.metric("最低", f"{low:.2f}")
        
        # 智能成交量顯示
        vol_str = f"{int(vol):,}"
        if unit == "股" and vol > 1000000: # 美股顯示 M
            vol_str = f"{vol/1000000:.2f}M"
            
        c4.metric("成交量", f"{vol_str} {unit}")
        
        st.markdown("<hr style='margin: 8px 0px; border:0; border-top:1px solid #444;'>", unsafe_allow_html=True)
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("振幅", f"{amp:.2f}%")
        d2.metric("量能狀態", vs)
        
        # 均量也做單位處理
        va_val = va
        if unit == "張": va_val = va / 1000
        
        va_str = f"{int(va_val):,}"
        if unit == "股" and va_val > 1000000:
            va_str = f"{va_val/1000000:.2f}M"
            
        d3.metric("五日均量", f"{va_str} {unit}")
        
        # 前日量 (美股前日 volume 也是股，台股是張)
        vy_val = vy
        if unit == "張": vy_val = vy / 1000
        
        vy_str = f"{int(vy_val):,}"
        if unit == "股" and vy_val > 1000000:
            vy_str = f"{vy_val/1000000:.2f}M"
            
        d4.metric("昨日量", f"{vy_str} {unit}")

# ... (其他 render_detailed_card, render_chart 等函式完全保留 V100 的版本) ...
# 注意：請確保將 V100 的 stock_ui.py 內容複製過來，只替換 render_metrics_dashboard
# 為了完整性，這裡提供一個省略版指示，實際上您應該保留原本的完整代碼，只換這一個函式
# 但為了方便您全選複製，您可以直接使用 V100 的 stock_ui.py，然後只改這一小段
