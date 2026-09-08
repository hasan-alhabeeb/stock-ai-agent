import google.genai as genai
import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime
import os

# إعداد الصفحة في Streamlit
st.set_page_config(page_title="Financial AI Agent", layout="wide")

# إعداد API ومكافحة السجلات
API_KEY = "AQ.Ab8RN6LaoE1_xRfhAJYEVEbWb2pE-T6zrHoxwEdV2GP1gWjm-A"
client = genai.Client(api_key=API_KEY)
LOG_FILE = "agent_recommendations_log.csv"

if not os.path.exists(LOG_FILE):
    df_empty = pd.DataFrame(columns=["Timestamp", "Ticker", "Current_Price", "Decision", "Status"])
    df_empty.to_csv(LOG_FILE, index=False)

def calculate_rsi(data, window=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def analyze_stock_full(ticker_symbol):
    if not ticker_symbol:
        return "الرجاء إدخال رمز السهم أولاً.", None, None
    
    ticker_symbol = ticker_symbol.upper().strip()
    stock = yf.Ticker(ticker_symbol)
    hist = stock.history(period="6mo")
    info = stock.info
    
    if hist.empty:
        return f"عذراً، لم يتم العثور على بيانات للسهم {ticker_symbol}.", None, None
        
    current_price = hist['Close'].iloc[-1]
    hist['SMA_50'] = hist['Close'].rolling(window=50).mean()
    hist['RSI'] = calculate_rsi(hist['Close'])
    
    sma_50 = hist['SMA_50'].iloc[-1]
    rsi = hist['RSI'].iloc[-1]
    
    pe_ratio = info.get('trailingPE', 'غير متوفر')
    eps = info.get('trailingEps', 'غير متوفر')
    market_cap = info.get('marketCap', 'غير متوفر')
    if isinstance(market_cap, (int, float)):
        market_cap = f"${market_cap / 1e9:.2f} مليار"

    news_list = stock.news
    headlines = []
    if news_list:
        for item in news_list[:5]:
            title = item.get('title') or item.get('content', {}).get('title', '')
            if title:
                headlines.append(f"- {title}")
    news_text = "\n".join(headlines) if headlines else "لا توجد أخبار حديثة متاحة حالياً."

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=hist.index, open=hist['Open'], high=hist['High'],
        low=hist['Low'], close=hist['Close'], name='سعر السهم'
    ))
    fig.add_trace(go.Scatter(x=hist.index, y=hist['SMA_50'], mode='lines', name='SMA 50'))
    fig.update_layout(
        title=f"الرسم البياني التفاعلي لسهم {ticker_symbol}",
        xaxis_title="التاريخ", yaxis_title="السعر ($)",
        template="plotly_white", margin=dict(l=20, r=20, t=40, b=20)
    )

    stop_loss = current_price * 0.95
    take_profit = current_price * 1.10
    
    prompt = f"""
    أنت وكيل ذكاء اصطناعي خبير في التحليل المالي والأساسي والفني (FMVA).
    بيانات سهم {ticker_symbol}:
    - السعر الحالي: ${current_price:.2f}
    - مكرر الربحية (P/E Ratio): {pe_ratio}
    - ربحية السهم (EPS): {eps}
    - القيمة السوقية: {market_cap}
    - المتوسط المتحرك 50 يوم: ${sma_50:.2f}
    - مؤشر القوة النسبية RSI: {rsi:.2f}
    - وقف الخسارة المقترح: ${stop_loss:.2f}
    - هدف الربح المقترح: ${take_profit:.2f}
    
    أحدث الأخبار:
    {news_text}
    
    المطلوب:
    1. تقييم التحليل الأساسي والمالي للشركة.
    2. تقييم التحليل الفني ومشاعر الأخبار.
    3. تحديد مستويات المخاطر وتوصية نهائية صريحة (شراء / بيع / احتفاظ).
    """
    
        response = client.models.generate_content(
        model='gemini-2.0-flash',
        contents=prompt
    )

        contents=prompt,
    )
    return response.text, current_price, fig

def confirm_decision(user_choice, ticker_symbol, current_price):
    if not ticker_symbol or not current_price:
        return "الرجاء أدخل رمز السهم والتحليل أولاً."
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = "Approved" if user_choice == "نعم" else "Rejected"
    
    new_log = pd.DataFrame([{
        "Timestamp": now,
        "Ticker": ticker_symbol.upper(),
        "Current_Price": f"${current_price:.2f}",
        "Decision": user_choice,
        "Status": status
    }])
    new_log.to_csv(LOG_FILE, mode='a', header=False, index=False)
    
    msg = f"✓ تم اعتماد التوصية وحفظها لسهم {ticker_symbol}!" if user_choice == "نعم" else f"✗ تم رفض التوصية لسهم {ticker_symbol}."
    return msg

# --- واجهة المستخدم بلغة Streamlit ---
st.title("🤖 المنظومة المالية الفائقة (Financial AI Professional Agent)")
st.write("تحليل أساسي + تحليل فني + رسم بياني تفاعلي + أخبار + إدارة مخاطر + تصدير السجلات.")

# إدخال رمز السهم
col1, col2 = st.columns([3, 1])
with col1:
    ticker_input = st.text_input("رمز السهم (Ticker)", placeholder="مثال: AAPL, NVDA, TSLA")
with col2:
    st.write(" ")
    st.write(" ")
    analyze_btn = st.button("بدء التحليل الفائق 🚀", type="primary")

# إجراء التحليل عند الضغط على الزر
if analyze_btn and ticker_input:
    with st.spinner("جاري جلب البيانات والتحليل بواسطة الذكاء الاصطناعي..."):
        analysis_text, current_price, fig = analyze_stock_full(ticker_input)
        st.session_state['analysis_text'] = analysis_text
        st.session_state['current_price'] = current_price
        st.session_state['fig'] = fig
        st.session_state['ticker'] = ticker_input

# عرض النتائج إذا كانت متوفرة
if 'analysis_text' in st.session_state:
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.subheader("تقرير الذكاء الاصطناعي الشامل")
        st.write(st.session_state['analysis_text'])
        
    with col_right:
        st.subheader("الرسم البياني التفاعلي")
        if st.session_state['fig']:
            st.plotly_chart(st.session_state['fig'], use_container_width=True)

    st.markdown("---")
    st.subheader("🛡️ نظام الحماية البشري واتخاذ القرار")
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("أوافق على التوصية (نعم)"):
            res = confirm_decision("نعم", st.session_state['ticker'], st.session_state['current_price'])
            st.success(res)
    with col_btn2:
        if st.button("أرفض التوصية (لا)"):
            res = confirm_decision("لا", st.session_state['ticker'], st.session_state['current_price'])
            st.error(res)

st.markdown("---")
st.subheader("📜 سجل التوصيات المحفوظة")

if os.path.exists(LOG_FILE):
    df_logs = pd.read_csv(LOG_FILE)
    st.dataframe(df_logs, use_container_width=True)
    
    with open(LOG_FILE, "rb") as file:
        st.download_button(
            label="تنزيل ملف السجلات CSV إلى جهازك 📥",
            data=file,
            file_name="agent_recommendations_log.csv",
            mime="text/csv"
        )
