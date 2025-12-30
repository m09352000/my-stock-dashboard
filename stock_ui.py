# ... (保留前面的 import 與 css)

# --- 5. Pro 級儀表板 (仿投資先生/XQ 風格) ---
def render_metrics_dashboard(curr, chg, pct, high, low, amp, main_force, 
                             vol, vol_yest, vol_avg, vol_status, foreign_held, 
                             turnover_rate, bid_ask_data, color_settings, 
                             realtime_data=None):
    
    # 資料處理邏輯 (保留原樣)
    is_realtime = False
    if realtime_data:
        is_realtime = True
        curr = realtime_data['latest_trade_price']
        high = realtime_data['high']
        low = realtime_data['low']
        vol = int(float(realtime_data['accumulate_trade_volume']))
        prev_close = realtime_data['previous_close']
        if prev_close > 0:
            chg = curr - prev_close
            pct = (chg / prev_close) * 100
            amp = ((high - low) / prev_close) * 100
        
    # 顏色判斷
    if chg > 0: 
        main_color = "#FF2B2B"; bg_color = "rgba(255, 43, 43, 0.1)"; arrow = "▲"
    elif chg < 0: 
        main_color = "#00E050"; bg_color = "rgba(0, 224, 80, 0.1)"; arrow = "▼"
    else: 
        main_color = "#FFFFFF"; bg_color = "rgba(255, 255, 255, 0.1)"; arrow = ""

    # CSS 優化: 建立專業看盤質感
    st.markdown(f"""
    <style>
    .metric-container {{
        background-color: #1E1E1E;
        border-radius: 10px;
        padding: 15px;
        border: 1px solid #333;
        margin-bottom: 10px;
    }}
    .big-price {{
        font-size: 2.8rem;
        font-weight: 900;
        color: {main_color};
        line-height: 1;
        text-shadow: 0px 0px 10px {bg_color};
    }}
    .price-change {{
        font-size: 1.2rem;
        font-weight: bold;
        color: {main_color};
    }}
    .sub-metric-label {{ font-size: 0.8rem; color: #888; margin-bottom: 0px; }}
    .sub-metric-value {{ font-size: 1.1rem; color: #DDD; font-weight: 600; }}
    .tag {{
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: bold;
        margin-right: 5px;
    }}
    .tag-red {{ background-color: #3d1a1a; color: #ff6b6b; border: 1px solid #ff6b6b; }}
    .tag-green {{ background-color: #1a3d26; color: #6bff92; border: 1px solid #6bff92; }}
    .tag-gray {{ background-color: #2d2d2d; color: #aaa; border: 1px solid #555; }}
    </style>
    """, unsafe_allow_html=True)

    # 版面佈局
    with st.container():
        # 上半部：核心報價區
        c1, c2, c3 = st.columns([1.5, 1, 1])
        
        with c1:
            live_tag = "<span class='live-tag'>● LIVE</span>" if is_realtime else ""
            st.markdown(f"<div style='color:#aaa; font-size:0.9rem;'>成交價 {live_tag}</div>", unsafe_allow_html=True)
            st.markdown(f"""
            <div style='display:flex; align-items:baseline; gap:10px;'>
                <div class='big-price'>{curr:.2f}</div>
                <div class='price-change'>{arrow} {abs(chg):.2f} ({pct:+.2f}%)</div>
            </div>
            """, unsafe_allow_html=True)
        
        with c2:
            st.markdown(f"""
            <div style='margin-top:5px;'>
                <div class='sub-metric-label'>最高 / 最低</div>
                <div class='sub-metric-value'>{high:.2f} / {low:.2f}</div>
                <div style='margin-top:5px;'><span class='sub-metric-label'>振幅:</span> <span style='color:#e0e0e0'>{amp:.2f}%</span></div>
            </div>
            """, unsafe_allow_html=True)

        with c3:
            # 判斷量能狀態的標籤顏色
            vol_color_cls = "tag-red" if vol_status == "爆量" else ("tag-gray" if vol_status == "正常" else "tag-green")
            st.markdown(f"""
            <div style='margin-top:5px;'>
                <div class='sub-metric-label'>總量 / 昨量</div>
                <div class='sub-metric-value'>{int(vol):,} / {int(vol_yest):,}</div>
                <div style='margin-top:8px;'><span class='tag {vol_color_cls}'>{vol_status}</span></div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

        # 下半部：詳細數據矩陣 (仿看盤軟體欄位)
        k1, k2, k3, k4, k5 = st.columns(5)
        
        # 週轉率顏色
        t_color = "#ff4b4b" if turnover_rate > 10 else ("#ccc" if turnover_rate > 1 else "#00d084")
        
        with k1: st.metric("五日均量", f"{int(vol_avg/1000)} K")
        with k2: st.markdown(f"<div class='sub-metric-label'>週轉率</div><div class='sub-metric-value' style='color:{t_color}'>{turnover_rate:.2f}%</div>", unsafe_allow_html=True)
        with k3: st.metric("外資持股", f"{foreign_held:.1f}%")
        with k4: st.metric("主力動向", main_force)
        
        # 簡易技術指標狀態
        ma_status = "多頭排列" # 這裡可以根據傳入參數做更細緻判斷
        with k5: st.markdown(f"<div class='sub-metric-label'>技術面</div><div class='tag tag-gray'>{ma_status}</div>", unsafe_allow_html=True)

    # 五檔報價 (若有)
    if bid_ask_data:
        with st.expander("📊 即時五檔明細 (Best 5)", expanded=False):
            b_price = bid_ask_data.get('bid_price', ['-'])[0]
            b_vol = bid_ask_data.get('bid_volume', ['-'])[0]
            a_price = bid_ask_data.get('ask_price', ['-'])[0]
            a_vol = bid_ask_data.get('ask_volume', ['-'])[0]
            
            col_b, col_a = st.columns(2)
            col_b.error(f"買進: {b_price} ({b_vol})")
            col_a.success(f"賣出: {a_price} ({a_vol})")
