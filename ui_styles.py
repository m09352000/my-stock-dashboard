# ui_styles.py
# 介面樣式表 (CSS)

import streamlit as st

def inject_custom_css():
    st.markdown("""
        <style>
        .stApp { font-family: "Microsoft JhengHei", sans-serif; }
        
        /* 戰情室卡片 */
        .battle-card { 
            background-color: #1e1e1e; 
            padding: 20px; 
            border-radius: 12px; 
            border: 1px solid #333; 
            margin-bottom: 15px; 
            box-shadow: 0 4px 6px rgba(0,0,0,0.3); 
        }
        .battle-title { 
            font-size: 1.2rem; 
            font-weight: 900; 
            color: #fff; 
            margin-bottom: 10px; 
            border-bottom: 2px solid #444; 
            padding-bottom: 5px; 
        }
        
        /* 排名徽章 */
        .rank-badge { 
            display: flex; align-items: center; justify-content: center; 
            width: 45px; height: 45px; border-radius: 50%; 
            font-weight: 900; font-size: 1.4rem; color: #000; 
            margin: auto; box-shadow: 0 2px 5px rgba(0,0,0,0.5); 
        }
        .rank-1 { background: linear-gradient(135deg, #FFD700, #FDB931); border: 2px solid #FFF; box-shadow: 0 0 15px #FFD700; }
        .rank-2 { background: linear-gradient(135deg, #E0E0E0, #B0B0B0); border: 2px solid #FFF; }
        .rank-3 { background: linear-gradient(135deg, #CD7F32, #A0522D); border: 2px solid #FFF; }
        .rank-norm { background-color: #333; color: #EEE; font-size: 1rem; width: 35px; height: 35px; }
        
        /* 狀態標籤 */
        .status-tag { 
            padding: 4px 8px; border-radius: 4px; 
            font-weight: bold; font-size: 0.85rem; 
            text-align: center; display: inline-block; 
        }
        
        /* 報告文字 */
        .report-text { 
            font-size: 1.05rem; line-height: 1.8; 
            color: #E0E0E0; white-space: pre-wrap; 
        }
        
        /* 直播紅點 */
        .live-tag { 
            color: #00FF00; font-weight: bold; 
            font-size: 0.9rem; animation: blink 1s infinite; 
            text-shadow: 0 0 5px #00FF00; 
        }
        @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.4; } 100% { opacity: 1; } }
        
        /* 調整 Streamlit 原生元件 */
        div[data-testid="stMetricValue"] { font-size: 1.35rem !important; font-weight: 800 !important; }
        hr.compact { margin: 8px 0px !important; border: 0; border-top: 1px solid #444; }
        </style>
    """, unsafe_allow_html=True)
