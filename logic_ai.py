# logic_ai.py
# V112: AI 核心 (全中文深度分析)

import pandas as pd

def generate_detailed_report(df, score, weekly_prob, monthly_prob):
    latest = df.iloc[-1]
    p = latest['Close']
    m5 = df['Close'].rolling(5).mean().iloc[-1]
    m20 = df['Close'].rolling(20).mean().iloc[-1]
    m60 = df['Close'].rolling(60).mean().iloc[-1]
    vol = latest['Volume']
    vol_ma5 = df['Volume'].rolling(5).mean().iloc[-1]
    
    trend_txt = "【📊 趨勢技術面】\n"
    if p > m5 and m5 > m20 and m20 > m60:
        trend_txt += "🚀 **多頭強勢排列**：股價站穩所有均線之上，且 5日 > 20日 > 60日，這是最標準的主升段架構。上方萬里無雲，適合順勢加碼。"
    elif p < m5 and m5 < m20 and m20 < m60:
        trend_txt += "📉 **空頭修正格局**：股價位於所有均線之下，且均線下彎形成蓋頭反壓。目前趨勢向下，切勿猜底，建議觀望。"
    elif p > m20:
        trend_txt += "🌤️ **多方掌控節奏**：股價穩守月線(20MA 生命線)之上，中多格局未變。短線震盪視為清洗浮額，只要月線不破，波段趨勢依然向上。"
    else:
        trend_txt += "🌧️ **轉弱整理**：股價跌破月線，短線動能轉弱。需觀察能否在季線(60MA)附近獲得支撐，否則整理時間將拉長。"

    vol_txt = "\n\n【💸 籌碼與量能】\n"
    if vol > vol_ma5 * 1.8:
        vol_txt += f"🔥 **爆量攻擊**：今日成交量放大至五日均量的 {vol/vol_ma5:.1f} 倍！代表主力大戶態度積極，有新資金進場換手，是強烈的攻擊訊號。"
    elif vol < vol_ma5 * 0.6:
        vol_txt += "❄️ **量縮觀望**：成交量明顯萎縮，市場觀望氣氛濃厚。在多頭回檔時量縮是好事(惜售)，但在跌勢中則代表沒人敢接。"
    else:
        vol_txt += "⚖️ **量價平穩**：成交量維持在均量附近，屬於健康的換手量，有利於股價穩步推升。"

    prob_txt = "\n\n【🎯 AI 獲利機率預測】\n"
    prob_txt += f"● **短線 (本週)**：勝率 **{weekly_prob}%**。{( '🔥 極高！建議積極尋找買點。' if weekly_prob > 80 else '⚠️ 波動風險大，嚴設停損。' )}\n"
    prob_txt += f"● **波段 (本月)**：勝率 **{monthly_prob}%**。{( '💎 趨勢穩健，適合波段持有。' if monthly_prob > 70 else '⏳ 趨勢不明，建議觀望。' )}"

    return trend_txt + vol_txt + prob_txt

def generate_scan_reason(df):
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
    elif p > m20 and m20 > m60: reasons.append("站穩季線翻多")
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
    
    w_score = 50 
    if close > ma5: w_score += 15
    if ma5 > ma20: w_score += 10
    if vol_ratio > 1.2: w_score += 10
    if 50 < rsi < 80: w_score += 10
    elif rsi > 80: w_score -= 10
    weekly_prob = min(max(w_score, 10), 98)

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
