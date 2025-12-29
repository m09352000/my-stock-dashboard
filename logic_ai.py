# logic_ai.py
# AI 核心層：負責技術指標運算、勝率評估、報告生成

import pandas as pd

def generate_detailed_report(df, score, weekly_prob, monthly_prob):
    """生成千字文深度報告"""
    latest = df.iloc[-1]
    p = latest['Close']
    m5 = df['Close'].rolling(5).mean().iloc[-1]
    m20 = df['Close'].rolling(20).mean().iloc[-1]
    m60 = df['Close'].rolling(60).mean().iloc[-1]
    vol = latest['Volume']
    vol_ma5 = df['Volume'].rolling(5).mean().iloc[-1]
    
    trend_txt = "【趨勢型態】\n"
    if p > m5 and m5 > m20 and m20 > m60:
        trend_txt += "呈現「多頭排列」的完美進攻型態。股價站穩五日線之上，均線全面向上發散，是強勢主升段特徵，上方無明顯壓力。"
    elif p < m5 and m5 < m20 and m20 < m60:
        trend_txt += "呈現「空頭排列」的下跌型態。股價遭均線蓋頭反壓，上方套牢賣壓沈重，不宜貿然搶進。"
    elif p > m20:
        trend_txt += "股價位於月線(生命線)之上，屬於中多格局，波段趨勢看好。"
    else:
        trend_txt += "股價跌破月線，短線轉弱，需儘快站回否則整理期將拉長。"

    vol_txt = "\n\n【量能籌碼】\n"
    if vol > vol_ma5 * 1.5:
        vol_txt += f"今日爆出大量 (五日均量的 {vol/vol_ma5:.1f} 倍)！主力強勢表態，有利行情延續。"
    elif vol < vol_ma5 * 0.6:
        vol_txt += "今日呈現「量縮整理」，市場觀望氣氛濃厚。"
    else:
        vol_txt += "量能溫和，屬於健康的換手量。"

    prob_txt = "\n\n【獲利機率預測】\n"
    prob_txt += f"● **本週 (短線)**：**{weekly_prob}%**。{( '🔥 極高！' if weekly_prob > 80 else '⚠️ 需謹慎。' )}\n"
    prob_txt += f"● **本月 (波段)**：**{monthly_prob}%**。{( '💎 趨勢穩健。' if monthly_prob > 70 else '⏳ 建議觀望。' )}"

    return trend_txt + vol_txt + prob_txt

def generate_scan_reason(df):
    """生成掃描列表的短評理由"""
    reasons = []
    latest = df.iloc[-1]
    p = latest['Close']
    m5 = df['Close'].rolling(5).mean().iloc[-1]
    m20 = df['Close'].rolling(20).mean().iloc[-1]
    m60 = df['Close'].rolling(60).mean().iloc[-1]
    vol = latest['Volume']
    vol_ma5 = df['Volume'].rolling(5).mean().iloc[-1]
    
    exp12 = df['Close'].ewm(span=12, adjust=False).mean()
    exp26 = df['Close'].ewm(span=26, adjust=False).mean()
    macd = exp12 - exp26
    signal = macd.ewm(span=9, adjust=False).mean()
    
    delta = df['Close'].diff()
    u = delta.copy(); d = delta.copy(); u[u<0]=0; d[d>0]=0
    rs = u.rolling(14).mean() / d.abs().rolling(14).mean()
    rsi = (100 - 100/(1+rs)).iloc[-1]

    if p > m5 and m5 > m20 and m20 > m60: reasons.append("均線多頭排列")
    elif p > m20 and m20 > m60: reasons.append("站穩月季線")
    elif p > m5 and p > m20: reasons.append("短線轉強")
    
    if vol > vol_ma5 * 2.0: reasons.append(f"爆量{vol/vol_ma5:.1f}倍")
    elif vol > vol_ma5 * 1.3: reasons.append("量能增溫")
    
    if macd.iloc[-1] > signal.iloc[-1] and macd.iloc[-2] <= signal.iloc[-2]: reasons.append("MACD黃金交叉")
    elif macd.iloc[-1] > signal.iloc[-1]: reasons.append("MACD多頭")
    
    if 50 < rsi < 75: reasons.append(f"RSI強勢({int(rsi)})")
    elif rsi < 20: reasons.append("RSI超賣反彈")
    
    if p > df['High'].iloc[-1] * 0.99: reasons.append("收最高")
    
    if not reasons: return "技術面整理中"
    return " + ".join(reasons[:3])

def analyze_stock_battle_data(df):
    """計算勝率與建議"""
    if df is None or len(df) < 30: return None
    latest = df.iloc[-1]
    close = latest['Close']
    
    ma5 = df['Close'].rolling(5).mean().iloc[-1]
    ma20 = df['Close'].rolling(20).mean().iloc[-1]
    ma60 = df['Close'].rolling(60).mean().iloc[-1]
    std20 = df['Close'].rolling(20).std().iloc[-1]
    
    exp12 = df['Close'].ewm(span=12, adjust=False).mean()
    exp26 = df['Close'].ewm(span=26, adjust=False).mean()
    macd = exp12 - exp26
    signal = macd.ewm(span=9, adjust=False).mean()
    
    delta = df['Close'].diff()
    u = delta.copy(); d = delta.copy()
    u[u < 0] = 0; d[d > 0] = 0
    rs = u.rolling(14).mean() / d.abs().rolling(14).mean()
    rsi = (100 - 100/(1+rs)).iloc[-1]
    
    vol_ma5 = df['Volume'].rolling(5).mean().iloc[-1]
    vol_ratio = latest['Volume'] / vol_ma5 if vol_ma5 > 0 else 1
    
    # 週勝率
    w_score = 50 
    if close > ma5: w_score += 15
    if ma5 > ma20: w_score += 10
    if vol_ratio > 1.2: w_score += 10
    if 50 < rsi < 80: w_score += 10
    elif rsi > 80: w_score -= 10
    weekly_prob = min(max(w_score, 10), 98)

    # 月勝率
    m_score = 50
    if close > ma20: m_score += 20
    if ma20 > ma60: m_score += 20
    if macd.iloc[-1] > signal.iloc[-1]: m_score += 10
    monthly_prob = min(max(m_score, 10), 95)

    total_score = (weekly_prob + monthly_prob) / 2
    detailed_report = generate_detailed_report(df, total_score, weekly_prob, monthly_prob)

    short_action = "積極買進" if weekly_prob >= 70 else "拉回佈局" if weekly_prob >= 50 else "觀望"
    mid_trend = "多頭" if ma20 > ma60 else "整理"
    long_bias = ((close - ma60) / ma60) * 100
    long_action = "乖離過大" if long_bias > 20 else "超跌" if long_bias < -15 else "合理"
    
    return {
        "score": total_score, "weekly_prob": weekly_prob, "monthly_prob": monthly_prob,
        "report": detailed_report,
        "heat": "🔥🔥🔥 極熱" if vol_ratio > 2.0 else "🔥 溫熱" if vol_ratio > 1.2 else "☁️ 普通",
        "heat_color": "#FF0000" if vol_ratio > 2.0 else "#FF4500",
        "short_action": short_action, "short_target": f"{close*1.05:.2f}",
        "mid_trend": mid_trend, "mid_action": "續抱" if close > ma20 else "減碼", "mid_support": f"{ma20:.2f}",
        "long_action": long_action, "long_ma60": f"{ma60:.2f}",
        "pressure": ma20 + 2*std20, "support": ma20 - 2*std20, 
        "suggest_price": close if total_score > 70 else ma20, "close": close
    }
