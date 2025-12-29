# ... (前面的程式碼不用變) ...

elif mode == 'scan': 
    # ... (標題與變數設定不用變) ...
    
    if do_scan:
        st.session_state['scan_results'] = []; raw_results = []
        full_pool = st.session_state['scan_pool']
        # ... (篩選 target_pool 邏輯不用變) ...
        
        bar = st.progress(0); limit = 200 
        
        for i, c in enumerate(target_pool):
            if i >= limit: break
            bar.progress((i+1)/min(len(target_pool), limit))
            
            # --- V92 安全修改: 加入冷卻時間 ---
            # 雖然 Yahoo 比較耐操，但為了保險起見，每查詢一檔休息 0.1~0.5 秒
            # 如果是使用 twstock 抓即時資料，建議設為 2 秒 (遵守 3req/5sec)
            time.sleep(0.5) 
            
            try:
                fid, _, d, src = db.get_stock_data(c)
                if d is not None and len(d) > 20:
                    d_real, _, _ = inject_realtime_data(d, c) # 這裡會呼叫 twstock 即時
                    
                    # 如果 inject_realtime_data 裡使用了 twstock，建議這裡多休息一下
                    # 以避免觸發 TWSE 限制
                    
                    # ... (原本的篩選邏輯) ...
                    p = d_real['Close'].iloc[-1]; prev = d_real['Close'].iloc[-2]
                    vol = d_real['Volume'].iloc[-1]; m5 = d_real['Close'].rolling(5).mean().iloc[-1]
                    m20 = d_real['Close'].rolling(20).mean().iloc[-1]
                    valid = False
                    
                    if stype == 'day' and vol > d_real['Volume'].iloc[-2]*1.5 and p>m5: valid = True
                    elif stype == 'short' and p>m20 and m5>m20: valid = True
                    elif stype == 'long' and p>d_real['Close'].rolling(60).mean().iloc[-1]: valid = True
                    elif stype == 'top' and vol > 2000: valid = True
                    
                    if valid:
                        n = twstock.codes[c].name if c in twstock.codes else c
                        raw_results.append({'c': c, 'n': n, 'p': p, 'd': d_real, 'src': src, 'info': "符合策略"})
            except: pass
        
        # ... (後面的顯示邏輯不用變) ...
